"""Causal forward outcomes for production progression evidence direction.

This module is analysis-only. It tests whether already-emitted bullish/bearish
progression labels have forward weekly directional value. Signal-week evidence
is never scored on the same bar; execution begins on the next weekly bar using
the existing audit outcome contract.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from statistics import mean, median

import pandas as pd

from audit.outcomes import ForwardOutcome, compute_forward_outcome
from audit.progression_directionality_semantics import (
    ProgressionDirectionalityFailure,
    ProgressionDirectionalityRow,
    summarize_progression_directionality,
)
from daily_completion import completed_daily_only
from data import completed_weekly_only, daily_to_weekly
from engine.columns import COL_WEEK
from trading_calendar import NSETradingCalendar, TradingCalendar


PROGRESSION_DIRECTIONAL_OUTCOME_AUDIT_ID = (
    "production-progression-directional-outcomes-v1"
)
DEFAULT_PROGRESSION_OUTCOME_HORIZONS = (1, 3, 5, 10, 15)


@dataclass(frozen=True, slots=True)
class ProgressionDirectionalityArtifactInput:
    basket_name: str
    requested_symbols: tuple[str, ...]
    rows_by_symbol: dict[str, tuple[ProgressionDirectionalityRow, ...]]
    event_counts_by_symbol: dict[str, int]


@dataclass(frozen=True, slots=True)
class ProgressionDirectionalOutcomeObservation:
    symbol: str
    event_bar_index: int
    event_week: str
    event_direction: str
    progression_difference: float | None
    trend_direction: str
    trend_alignment: str
    structural_pattern: str
    structural_pattern_alignment: str
    horizon_weeks: int
    outcome_available: bool
    complete: bool
    execution_bar_index: int | None
    exit_bar_index: int | None
    raw_return: float | None
    favorable_return: float | None
    mfe: float | None
    mae: float | None

    @property
    def is_actionable(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class ProgressionDirectionalOutcomeSummary:
    cohort_dimension: str
    cohort_value: str
    horizon_weeks: int
    observation_count: int
    outcome_available_count: int
    complete_outcome_count: int
    positive_favorable_count: int
    favorable_hit_rate: float | None
    mean_favorable_return: float | None
    median_favorable_return: float | None
    mean_mfe: float | None
    mean_mae: float | None


@dataclass(frozen=True, slots=True)
class ProgressionDirectionalOutcomeAudit:
    audit_id: str
    basket_name: str
    requested_symbol_count: int
    successful_symbol_count: int
    failed_symbol_count: int
    event_count: int
    observation_count: int
    horizons_weeks: tuple[int, ...]
    observations: tuple[ProgressionDirectionalOutcomeObservation, ...]
    summaries: tuple[ProgressionDirectionalOutcomeSummary, ...]
    failures: tuple[ProgressionDirectionalityFailure, ...]

    @property
    def is_actionable(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class ProgressionDirectionalOutcomeAuditPaths:
    summary_json: Path
    observations_csv: Path
    cohort_summaries_csv: Path
    failures_csv: Path

    def as_dict(self) -> dict[str, str]:
        return {
            "summary_json": str(self.summary_json),
            "observations_csv": str(self.observations_csv),
            "cohort_summaries_csv": str(self.cohort_summaries_csv),
            "failures_csv": str(self.failures_csv),
        }


def _optional_float(value: object) -> float | None:
    if pd.isna(value):
        return None
    return float(value)


def load_progression_directionality_artifacts(
    *,
    input_dir: str | Path,
    basket_name: str,
    requested_symbols: tuple[str, ...],
) -> ProgressionDirectionalityArtifactInput:
    """Load and verify the validated K14 event/symbol artifacts."""

    root = Path(input_dir)
    events_path = root / "progression_directionality_events.csv"
    symbols_path = root / "progression_directionality_symbols.csv"
    if not events_path.exists():
        raise FileNotFoundError(
            f"missing K14 event artifact: {events_path}"
        )
    if not symbols_path.exists():
        raise FileNotFoundError(
            f"missing K14 symbol artifact: {symbols_path}"
        )

    events = pd.read_csv(events_path)
    symbols = pd.read_csv(symbols_path)

    required_event_columns = {
        "symbol",
        "event_bar_index",
        "event_week",
        "event_code",
        "event_direction",
        "progression_difference",
        "trend_direction",
        "trend_state",
        "structural_pattern",
        "trend_alignment",
        "structural_pattern_alignment",
        "qualification_after_event",
    }
    missing_event_columns = sorted(
        required_event_columns - set(events.columns)
    )
    if missing_event_columns:
        raise ValueError(
            "K14 event artifact is missing columns: "
            f"{missing_event_columns}"
        )

    required_symbol_columns = {"symbol", "event_count"}
    missing_symbol_columns = sorted(
        required_symbol_columns - set(symbols.columns)
    )
    if missing_symbol_columns:
        raise ValueError(
            "K14 symbol artifact is missing columns: "
            f"{missing_symbol_columns}"
        )

    requested = tuple(str(symbol).strip().upper() for symbol in requested_symbols)
    if len(set(requested)) != len(requested):
        raise ValueError("requested symbols must be unique")

    symbol_rows = symbols.copy()
    symbol_rows["symbol"] = symbol_rows["symbol"].astype(str).str.upper()
    duplicated_symbols = sorted(
        symbol_rows.loc[
            symbol_rows["symbol"].duplicated(keep=False),
            "symbol",
        ].unique()
    )
    if duplicated_symbols:
        raise ValueError(
            f"K14 symbol artifact contains duplicates: {duplicated_symbols}"
        )

    available_symbols = set(symbol_rows["symbol"])
    missing_symbols = sorted(set(requested) - available_symbols)
    if missing_symbols:
        raise ValueError(
            "K14 symbol artifact is missing requested symbols: "
            f"{missing_symbols}"
        )

    events = events.copy()
    if not events.empty:
        events["symbol"] = events["symbol"].astype(str).str.upper()

    rows_by_symbol: dict[
        str,
        tuple[ProgressionDirectionalityRow, ...],
    ] = {}
    event_counts_by_symbol: dict[str, int] = {}

    for symbol in requested:
        expected_count = int(
            symbol_rows.loc[
                symbol_rows["symbol"] == symbol,
                "event_count",
            ].iloc[0]
        )
        symbol_events = events.loc[events["symbol"] == symbol].copy()
        actual_count = len(symbol_events)
        if actual_count != expected_count:
            raise ValueError(
                f"{symbol} K14 event count mismatch: "
                f"{actual_count} != {expected_count}"
            )

        if not symbol_events.empty:
            duplicate_mask = symbol_events.duplicated(
                subset=("event_bar_index", "event_code"),
                keep=False,
            )
            if duplicate_mask.any():
                duplicate_rows = symbol_events.loc[
                    duplicate_mask,
                    ["event_bar_index", "event_code"],
                ].to_dict("records")
                raise ValueError(
                    f"{symbol} K14 event artifact contains duplicates: "
                    f"{duplicate_rows}"
                )

        converted = tuple(
            ProgressionDirectionalityRow(
                symbol=symbol,
                event_bar_index=int(row.event_bar_index),
                event_week=str(row.event_week),
                event_code=str(row.event_code),
                event_direction=str(row.event_direction),
                progression_difference=_optional_float(
                    row.progression_difference
                ),
                trend_direction=str(row.trend_direction),
                trend_state=str(row.trend_state),
                structural_pattern=str(row.structural_pattern),
                trend_alignment=str(row.trend_alignment),
                structural_pattern_alignment=str(
                    row.structural_pattern_alignment
                ),
                qualification_after_event=str(
                    row.qualification_after_event
                ),
            )
            for row in symbol_events.itertuples(index=False)
        )
        rows_by_symbol[symbol] = converted
        event_counts_by_symbol[symbol] = expected_count

    return ProgressionDirectionalityArtifactInput(
        basket_name=basket_name,
        requested_symbols=requested,
        rows_by_symbol=rows_by_symbol,
        event_counts_by_symbol=event_counts_by_symbol,
    )


def _normalized_horizons(
    horizons: tuple[int, ...],
) -> tuple[int, ...]:
    normalized = tuple(sorted(set(int(item) for item in horizons)))
    if not normalized or any(item <= 0 for item in normalized):
        raise ValueError("horizons must contain positive week counts")
    return normalized


def _validate_event_week(
    weekly: pd.DataFrame,
    row: ProgressionDirectionalityRow,
) -> None:
    if row.event_bar_index < 0 or row.event_bar_index >= len(weekly):
        raise IndexError(
            f"{row.symbol} event bar index {row.event_bar_index} "
            "is outside completed weekly history"
        )
    if COL_WEEK not in weekly.columns:
        raise ValueError("completed weekly data must contain week_beginning")
    actual = pd.Timestamp(
        weekly.iloc[row.event_bar_index][COL_WEEK]
    ).normalize()
    expected = pd.Timestamp(row.event_week).normalize()
    if actual != expected:
        raise ValueError(
            f"{row.symbol} event week mismatch at bar {row.event_bar_index}: "
            f"audit={expected.date().isoformat()} "
            f"weekly={actual.date().isoformat()}"
        )


def _observation_from_outcome(
    *,
    row: ProgressionDirectionalityRow,
    horizon_weeks: int,
    outcome: ForwardOutcome | None,
) -> ProgressionDirectionalOutcomeObservation:
    return ProgressionDirectionalOutcomeObservation(
        symbol=row.symbol,
        event_bar_index=row.event_bar_index,
        event_week=row.event_week,
        event_direction=row.event_direction,
        progression_difference=row.progression_difference,
        trend_direction=row.trend_direction,
        trend_alignment=row.trend_alignment,
        structural_pattern=row.structural_pattern,
        structural_pattern_alignment=(
            row.structural_pattern_alignment
        ),
        horizon_weeks=horizon_weeks,
        outcome_available=outcome is not None,
        complete=outcome is not None and outcome.complete,
        execution_bar_index=(
            None if outcome is None else outcome.execution_bar_index
        ),
        exit_bar_index=None if outcome is None else outcome.exit_bar_index,
        raw_return=None if outcome is None else outcome.raw_return,
        favorable_return=(
            None if outcome is None else outcome.favorable_return
        ),
        mfe=None if outcome is None else outcome.mfe,
        mae=None if outcome is None else outcome.mae,
    )


def build_progression_directional_outcomes(
    *,
    weekly: pd.DataFrame,
    rows: tuple[ProgressionDirectionalityRow, ...],
    horizons_weeks: tuple[int, ...] = DEFAULT_PROGRESSION_OUTCOME_HORIZONS,
) -> tuple[ProgressionDirectionalOutcomeObservation, ...]:
    """Attach next-week execution outcomes to existing progression events."""

    horizons = _normalized_horizons(horizons_weeks)
    observations: list[ProgressionDirectionalOutcomeObservation] = []
    seen_events: set[tuple[str, int, str]] = set()
    for row in rows:
        event_key = (
            row.symbol,
            row.event_bar_index,
            row.event_code,
        )
        if event_key in seen_events:
            raise ValueError(
                "duplicate progression event in outcome input: "
                f"{event_key}"
            )
        seen_events.add(event_key)
        _validate_event_week(weekly, row)
        for horizon in horizons:
            outcome = compute_forward_outcome(
                weekly,
                signal_bar_index=row.event_bar_index,
                horizon_bars=horizon,
                side=row.event_direction,
            )
            observations.append(
                _observation_from_outcome(
                    row=row,
                    horizon_weeks=horizon,
                    outcome=outcome,
                )
            )
    return tuple(observations)


def _cohort_keys(
    item: ProgressionDirectionalOutcomeObservation,
) -> tuple[tuple[str, str], ...]:
    return (
        ("all", "all"),
        ("event_direction", item.event_direction),
        ("trend_alignment", item.trend_alignment),
        (
            "structural_pattern_alignment",
            item.structural_pattern_alignment,
        ),
    )


def summarize_progression_directional_outcomes(
    observations: tuple[ProgressionDirectionalOutcomeObservation, ...],
) -> tuple[ProgressionDirectionalOutcomeSummary, ...]:
    groups: dict[
        tuple[str, str, int],
        list[ProgressionDirectionalOutcomeObservation],
    ] = defaultdict(list)

    for item in observations:
        for dimension, value in _cohort_keys(item):
            groups[(dimension, value, item.horizon_weeks)].append(item)

    summaries: list[ProgressionDirectionalOutcomeSummary] = []
    for (dimension, value, horizon), group in groups.items():
        available = [item for item in group if item.outcome_available]
        complete = [item for item in group if item.complete]
        favorable = [
            item.favorable_return
            for item in complete
            if item.favorable_return is not None
        ]
        mfe = [item.mfe for item in complete if item.mfe is not None]
        mae = [item.mae for item in complete if item.mae is not None]
        positive = sum(value_ > 0.0 for value_ in favorable)

        summaries.append(
            ProgressionDirectionalOutcomeSummary(
                cohort_dimension=dimension,
                cohort_value=value,
                horizon_weeks=horizon,
                observation_count=len(group),
                outcome_available_count=len(available),
                complete_outcome_count=len(complete),
                positive_favorable_count=positive,
                favorable_hit_rate=(
                    None if not favorable else positive / len(favorable)
                ),
                mean_favorable_return=(
                    None if not favorable else mean(favorable)
                ),
                median_favorable_return=(
                    None if not favorable else median(favorable)
                ),
                mean_mfe=None if not mfe else mean(mfe),
                mean_mae=None if not mae else mean(mae),
            )
        )

    return tuple(
        sorted(
            summaries,
            key=lambda item: (
                item.cohort_dimension,
                item.cohort_value,
                item.horizon_weeks,
            ),
        )
    )


def build_symbol_progression_directional_outcomes(
    *,
    symbol: str,
    daily: pd.DataFrame,
    rows: tuple[ProgressionDirectionalityRow, ...],
    now: datetime | pd.Timestamp | str | None = None,
    calendar: TradingCalendar | None = None,
    horizons_weeks: tuple[int, ...] = DEFAULT_PROGRESSION_OUTCOME_HORIZONS,
) -> tuple[
    tuple[ProgressionDirectionalOutcomeObservation, ...],
    int,
]:
    """Score frozen K14 events against completed weekly outcome bars."""

    clean_symbol = str(symbol).strip().upper()
    if any(row.symbol != clean_symbol for row in rows):
        raise ValueError(
            f"{clean_symbol} received K14 rows from another symbol"
        )

    exchange_calendar = calendar or NSETradingCalendar()
    completed_daily = completed_daily_only(
        daily,
        now=now,
        calendar=exchange_calendar,
    )
    weekly = completed_weekly_only(
        daily_to_weekly(completed_daily),
        now=now,
    )
    if weekly.empty:
        raise ValueError("no completed weekly bars are available")

    observations = build_progression_directional_outcomes(
        weekly=weekly,
        rows=rows,
        horizons_weeks=horizons_weeks,
    )
    return observations, len(rows)


def build_progression_directional_outcome_audit(
    *,
    basket_name: str,
    requested_symbols: tuple[str, ...],
    symbol_observations: tuple[
        tuple[ProgressionDirectionalOutcomeObservation, ...],
        ...,
    ],
    event_counts: tuple[int, ...],
    failures: tuple[ProgressionDirectionalityFailure, ...] = (),
    horizons_weeks: tuple[int, ...] = DEFAULT_PROGRESSION_OUTCOME_HORIZONS,
) -> ProgressionDirectionalOutcomeAudit:
    horizons = _normalized_horizons(horizons_weeks)
    if len(symbol_observations) != len(event_counts):
        raise ValueError(
            "symbol observation groups and event counts must have equal length"
        )
    if any(count < 0 for count in event_counts):
        raise ValueError("event counts cannot be negative")
    if len(symbol_observations) + len(failures) != len(requested_symbols):
        raise ValueError(
            "successful plus failed symbol counts must equal requested symbols"
        )

    failure_symbols = [item.symbol for item in failures]
    if len(set(failure_symbols)) != len(failure_symbols):
        raise ValueError("failure symbols must be unique")
    unknown_failures = sorted(set(failure_symbols) - set(requested_symbols))
    if unknown_failures:
        raise ValueError(
            f"failure symbols are outside requested symbols: {unknown_failures}"
        )

    for group, event_count in zip(symbol_observations, event_counts):
        expected = event_count * len(horizons)
        if len(group) != expected:
            raise ValueError(
                "symbol outcome observation count does not match "
                f"event_count × horizon_count: {len(group)} != {expected}"
            )

    observations = tuple(
        item
        for group in symbol_observations
        for item in group
    )
    seen_observations: set[tuple[str, int, str, int]] = set()
    for item in observations:
        if item.horizon_weeks not in horizons:
            raise ValueError(
                f"unexpected outcome horizon: {item.horizon_weeks}"
            )
        key = (
            item.symbol,
            item.event_bar_index,
            item.event_direction,
            item.horizon_weeks,
        )
        if key in seen_observations:
            raise ValueError(
                f"duplicate progression outcome observation: {key}"
            )
        seen_observations.add(key)

    return ProgressionDirectionalOutcomeAudit(
        audit_id=PROGRESSION_DIRECTIONAL_OUTCOME_AUDIT_ID,
        basket_name=basket_name,
        requested_symbol_count=len(requested_symbols),
        successful_symbol_count=len(symbol_observations),
        failed_symbol_count=len(failures),
        event_count=sum(event_counts),
        observation_count=len(observations),
        horizons_weeks=horizons,
        observations=observations,
        summaries=summarize_progression_directional_outcomes(observations),
        failures=tuple(sorted(failures, key=lambda item: item.symbol)),
    )


def write_progression_directional_outcome_audit(
    audit: ProgressionDirectionalOutcomeAudit,
    output_dir: str | Path,
) -> ProgressionDirectionalOutcomeAuditPaths:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    paths = ProgressionDirectionalOutcomeAuditPaths(
        summary_json=root / "progression_directional_outcomes_summary.json",
        observations_csv=(
            root / "progression_directional_outcome_observations.csv"
        ),
        cohort_summaries_csv=(
            root / "progression_directional_outcome_cohorts.csv"
        ),
        failures_csv=root / "progression_directional_outcome_failures.csv",
    )

    all_summaries = [
        item
        for item in audit.summaries
        if item.cohort_dimension == "all"
        and item.cohort_value == "all"
    ]
    summary = {
        "audit_id": audit.audit_id,
        "basket_name": audit.basket_name,
        "requested_symbol_count": audit.requested_symbol_count,
        "successful_symbol_count": audit.successful_symbol_count,
        "failed_symbol_count": audit.failed_symbol_count,
        "event_count": audit.event_count,
        "observation_count": audit.observation_count,
        "horizons_weeks": list(audit.horizons_weeks),
        "all_event_outcomes_by_horizon": [
            asdict(item) for item in all_summaries
        ],
        "execution_semantics": (
            "signal week N; execution at completed weekly bar N+1 close; "
            "no same-bar outcome"
        ),
        "is_actionable": False,
    }
    paths.summary_json.write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    pd.DataFrame(
        [asdict(item) for item in audit.observations],
    ).to_csv(paths.observations_csv, index=False)
    pd.DataFrame(
        [asdict(item) for item in audit.summaries],
    ).to_csv(paths.cohort_summaries_csv, index=False)
    pd.DataFrame(
        [asdict(item) for item in audit.failures],
        columns=("symbol", "exception_type", "reason"),
    ).to_csv(paths.failures_csv, index=False)
    return paths


__all__ = [
    "DEFAULT_PROGRESSION_OUTCOME_HORIZONS",
    "PROGRESSION_DIRECTIONAL_OUTCOME_AUDIT_ID",
    "ProgressionDirectionalityArtifactInput",
    "ProgressionDirectionalOutcomeAudit",
    "ProgressionDirectionalOutcomeAuditPaths",
    "ProgressionDirectionalOutcomeObservation",
    "ProgressionDirectionalOutcomeSummary",
    "build_progression_directional_outcome_audit",
    "load_progression_directionality_artifacts",
    "build_progression_directional_outcomes",
    "build_symbol_progression_directional_outcomes",
    "summarize_progression_directional_outcomes",
    "write_progression_directional_outcome_audit",
]
