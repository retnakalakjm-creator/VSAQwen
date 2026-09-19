"""Symbol-normalized drift baseline for progression directional outcomes.

This module is analysis-only. It compares frozen K15 progression-event outcomes
with non-progression weekly control bars from the same symbol, same observed
event era, same directional side, and same forward horizon.

The purpose is to separate progression-specific directional lift from ordinary
symbol/market drift without rerunning the production scanner.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean, median

import pandas as pd

from audit.outcomes import compute_forward_outcome
from daily_completion import completed_daily_only
from data import completed_weekly_only, daily_to_weekly
from engine.columns import COL_WEEK
from trading_calendar import NSETradingCalendar, TradingCalendar


PROGRESSION_DRIFT_BASELINE_AUDIT_ID = (
    "progression-symbol-normalized-drift-baseline-v1"
)
EXPECTED_K15_AUDIT_ID = "production-progression-directional-outcomes-v1"


@dataclass(frozen=True, slots=True)
class FrozenProgressionOutcomeObservation:
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


@dataclass(frozen=True, slots=True)
class FrozenProgressionOutcomeArtifact:
    basket_name: str
    requested_symbol_count: int
    event_count: int
    observation_count: int
    horizons_weeks: tuple[int, ...]
    observations_by_symbol: dict[
        str,
        tuple[FrozenProgressionOutcomeObservation, ...],
    ]


@dataclass(frozen=True, slots=True)
class ProgressionDriftBaselineRow:
    symbol: str
    event_direction: str
    horizon_weeks: int
    control_window_start_bar: int
    control_window_end_bar: int
    control_count: int
    control_hit_rate: float | None
    control_mean_favorable_return: float | None
    control_median_favorable_return: float | None


@dataclass(frozen=True, slots=True)
class ProgressionDriftLiftRow:
    symbol: str
    event_bar_index: int
    event_week: str
    event_direction: str
    trend_alignment: str
    horizon_weeks: int
    event_complete: bool
    event_favorable_return: float | None
    baseline_control_count: int
    baseline_mean_favorable_return: float | None
    favorable_return_lift: float | None
    resolved_event_bar_index: int | None = None
    frozen_event_favorable_return: float | None = None
    event_return_revision_delta: float | None = None


@dataclass(frozen=True, slots=True)
class ProgressionDriftLiftSummary:
    cohort_dimension: str
    cohort_value: str
    horizon_weeks: int
    complete_event_count: int
    symbol_count: int
    mean_event_favorable_return: float | None
    mean_matched_baseline_favorable_return: float | None
    mean_favorable_return_lift: float | None
    median_favorable_return_lift: float | None
    positive_lift_count: int
    positive_lift_rate: float | None
    equal_weighted_symbol_mean_lift: float | None
    positive_symbol_count: int
    positive_symbol_rate: float | None


@dataclass(frozen=True, slots=True)
class ProgressionDriftBaselineFailure:
    symbol: str
    exception_type: str
    reason: str


@dataclass(frozen=True, slots=True)
class ProgressionDriftBaselineAudit:
    audit_id: str
    basket_name: str
    requested_symbol_count: int
    successful_symbol_count: int
    failed_symbol_count: int
    source_event_count: int
    source_observation_count: int
    event_count: int
    observation_count: int
    horizons_weeks: tuple[int, ...]
    baseline_rows: tuple[ProgressionDriftBaselineRow, ...]
    lift_rows: tuple[ProgressionDriftLiftRow, ...]
    summaries: tuple[ProgressionDriftLiftSummary, ...]
    failures: tuple[ProgressionDriftBaselineFailure, ...]

    @property
    def is_actionable(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class ProgressionDriftBaselineAuditPaths:
    summary_json: Path
    baseline_csv: Path
    lift_csv: Path
    cohort_csv: Path
    failures_csv: Path

    def as_dict(self) -> dict[str, str]:
        return {
            "summary_json": str(self.summary_json),
            "baseline_csv": str(self.baseline_csv),
            "lift_csv": str(self.lift_csv),
            "cohort_csv": str(self.cohort_csv),
            "failures_csv": str(self.failures_csv),
        }


def _optional_float(value: object) -> float | None:
    if pd.isna(value):
        return None
    return float(value)


def _optional_int(value: object) -> int | None:
    if pd.isna(value):
        return None
    return int(value)


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"true", "1"}:
        return True
    if normalized in {"false", "0"}:
        return False
    raise ValueError(f"unsupported boolean value: {value!r}")


def load_frozen_progression_outcomes(
    *,
    input_dir: str | Path,
    expected_basket_name: str,
) -> FrozenProgressionOutcomeArtifact:
    """Load and validate frozen K15 summary + observation artifacts."""

    root = Path(input_dir)
    summary_path = root / "progression_directional_outcomes_summary.json"
    observations_path = (
        root / "progression_directional_outcome_observations.csv"
    )
    if not summary_path.exists():
        raise FileNotFoundError(
            f"missing K15 summary artifact: {summary_path}"
        )
    if not observations_path.exists():
        raise FileNotFoundError(
            f"missing K15 observation artifact: {observations_path}"
        )

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("audit_id") != EXPECTED_K15_AUDIT_ID:
        raise ValueError(
            "K15 summary audit_id does not match expected outcome audit"
        )
    if summary.get("basket_name") != expected_basket_name:
        raise ValueError(
            "K15 basket does not match requested basket: "
            f"{summary.get('basket_name')!r} != {expected_basket_name!r}"
        )
    if int(summary.get("failed_symbol_count", 0)) != 0:
        raise ValueError("K15 artifact contains failed symbols")

    horizons = tuple(
        sorted({int(item) for item in summary["horizons_weeks"]})
    )
    if not horizons or any(item <= 0 for item in horizons):
        raise ValueError("K15 horizons must be positive")

    frame = pd.read_csv(observations_path)
    required = {
        "symbol",
        "event_bar_index",
        "event_week",
        "event_direction",
        "progression_difference",
        "trend_direction",
        "trend_alignment",
        "structural_pattern",
        "structural_pattern_alignment",
        "horizon_weeks",
        "outcome_available",
        "complete",
        "execution_bar_index",
        "exit_bar_index",
        "raw_return",
        "favorable_return",
        "mfe",
        "mae",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(
            f"K15 observation artifact is missing columns: {missing}"
        )

    expected_observations = int(summary["observation_count"])
    if len(frame) != expected_observations:
        raise ValueError(
            "K15 observation count mismatch: "
            f"{len(frame)} != {expected_observations}"
        )

    rows: list[FrozenProgressionOutcomeObservation] = []
    for raw in frame.itertuples(index=False):
        rows.append(
            FrozenProgressionOutcomeObservation(
                symbol=str(raw.symbol).strip().upper(),
                event_bar_index=int(raw.event_bar_index),
                event_week=str(raw.event_week),
                event_direction=str(raw.event_direction),
                progression_difference=_optional_float(
                    raw.progression_difference
                ),
                trend_direction=str(raw.trend_direction),
                trend_alignment=str(raw.trend_alignment),
                structural_pattern=str(raw.structural_pattern),
                structural_pattern_alignment=str(
                    raw.structural_pattern_alignment
                ),
                horizon_weeks=int(raw.horizon_weeks),
                outcome_available=_as_bool(raw.outcome_available),
                complete=_as_bool(raw.complete),
                execution_bar_index=_optional_int(
                    raw.execution_bar_index
                ),
                exit_bar_index=_optional_int(raw.exit_bar_index),
                raw_return=_optional_float(raw.raw_return),
                favorable_return=_optional_float(raw.favorable_return),
                mfe=_optional_float(raw.mfe),
                mae=_optional_float(raw.mae),
            )
        )

    unique_events: set[tuple[str, int, str, str]] = set()
    observed_horizons: dict[
        tuple[str, int, str, str],
        set[int],
    ] = defaultdict(set)
    observations_by_symbol: dict[
        str,
        list[FrozenProgressionOutcomeObservation],
    ] = defaultdict(list)

    for row in rows:
        if row.horizon_weeks not in horizons:
            raise ValueError(
                f"unexpected K15 horizon: {row.horizon_weeks}"
            )
        event_key = (
            row.symbol,
            row.event_bar_index,
            row.event_week,
            row.event_direction,
        )
        if row.horizon_weeks in observed_horizons[event_key]:
            raise ValueError(
                "duplicate K15 event/horizon observation: "
                f"{event_key} horizon={row.horizon_weeks}"
            )
        observed_horizons[event_key].add(row.horizon_weeks)
        unique_events.add(event_key)
        observations_by_symbol[row.symbol].append(row)

    for event_key, seen in observed_horizons.items():
        if seen != set(horizons):
            raise ValueError(
                f"K15 event has incomplete horizon identity set: {event_key}"
            )

    expected_events = int(summary["event_count"])
    if len(unique_events) != expected_events:
        raise ValueError(
            f"K15 unique event count mismatch: "
            f"{len(unique_events)} != {expected_events}"
        )

    return FrozenProgressionOutcomeArtifact(
        basket_name=expected_basket_name,
        requested_symbol_count=int(summary["requested_symbol_count"]),
        event_count=expected_events,
        observation_count=expected_observations,
        horizons_weeks=horizons,
        observations_by_symbol={
            symbol: tuple(items)
            for symbol, items in observations_by_symbol.items()
        },
    )


def resolve_frozen_progression_event_bar_index(
    *,
    weekly: pd.DataFrame,
    observation: FrozenProgressionOutcomeObservation,
) -> int:
    """Resolve a frozen event by stable week identity, not source row index."""

    if COL_WEEK not in weekly.columns:
        raise ValueError("completed weekly data must contain week_beginning")

    expected = pd.Timestamp(observation.event_week).normalize()
    normalized_weeks = pd.to_datetime(
        weekly[COL_WEEK],
    ).dt.normalize()
    matches = normalized_weeks[normalized_weeks == expected].index.tolist()
    if not matches:
        raise ValueError(
            f"{observation.symbol} event week is absent from local history: "
            f"{expected.date()}"
        )
    if len(matches) != 1:
        raise ValueError(
            f"{observation.symbol} event week is not unique locally: "
            f"{expected.date()}"
        )

    return int(weekly.index.get_loc(matches[0]))


def _complete_control_outcomes(
    *,
    weekly: pd.DataFrame,
    start_bar: int,
    end_bar: int,
    excluded_event_bars: set[int],
    horizon_weeks: int,
    side: str,
) -> list[float]:
    values: list[float] = []
    for signal_bar_index in range(start_bar, end_bar + 1):
        if signal_bar_index in excluded_event_bars:
            continue
        outcome = compute_forward_outcome(
            weekly,
            signal_bar_index=signal_bar_index,
            horizon_bars=horizon_weeks,
            side=side,
        )
        if outcome is None or not outcome.complete:
            continue
        values.append(outcome.favorable_return)
    return values


def build_symbol_progression_drift_baseline(
    *,
    symbol: str,
    daily: pd.DataFrame,
    observations: tuple[FrozenProgressionOutcomeObservation, ...],
    now: str | pd.Timestamp | None,
    calendar: TradingCalendar | None = None,
) -> tuple[
    tuple[ProgressionDriftBaselineRow, ...],
    tuple[ProgressionDriftLiftRow, ...],
]:
    """Build same-symbol non-event baselines and event-level lift."""

    clean_symbol = symbol.strip().upper()
    if any(item.symbol != clean_symbol for item in observations):
        raise ValueError(
            f"{clean_symbol} received K15 observations from another symbol"
        )
    if not observations:
        return (), ()

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

    unique_event_rows: dict[
        tuple[str, str],
        FrozenProgressionOutcomeObservation,
    ] = {}
    for item in observations:
        key = (
            item.event_week,
            item.event_direction,
        )
        existing = unique_event_rows.get(key)
        if (
            existing is not None
            and existing.event_bar_index != item.event_bar_index
        ):
            raise ValueError(
                f"{clean_symbol} frozen event identity conflict: {key}"
            )
        unique_event_rows.setdefault(key, item)

    resolved_event_indices = {
        key: resolve_frozen_progression_event_bar_index(
            weekly=weekly,
            observation=item,
        )
        for key, item in unique_event_rows.items()
    }

    event_bars = set(resolved_event_indices.values())
    control_window_end = len(weekly) - 1

    baseline_rows: list[ProgressionDriftBaselineRow] = []
    baseline_map: dict[
        tuple[str, int],
        ProgressionDriftBaselineRow,
    ] = {}

    directions = sorted(
        {item.event_direction for item in unique_event_rows.values()}
    )
    horizons = sorted({item.horizon_weeks for item in observations})
    for direction in directions:
        direction_start = min(
            resolved_event_indices[
                (item.event_week, item.event_direction)
            ]
            for item in unique_event_rows.values()
            if item.event_direction == direction
        )
        for horizon in horizons:
            controls = _complete_control_outcomes(
                weekly=weekly,
                start_bar=direction_start,
                end_bar=control_window_end,
                excluded_event_bars=event_bars,
                horizon_weeks=horizon,
                side=direction,
            )
            positive = sum(item > 0.0 for item in controls)
            row = ProgressionDriftBaselineRow(
                symbol=clean_symbol,
                event_direction=direction,
                horizon_weeks=horizon,
                control_window_start_bar=direction_start,
                control_window_end_bar=control_window_end,
                control_count=len(controls),
                control_hit_rate=(
                    None if not controls else positive / len(controls)
                ),
                control_mean_favorable_return=(
                    None if not controls else mean(controls)
                ),
                control_median_favorable_return=(
                    None if not controls else median(controls)
                ),
            )
            baseline_rows.append(row)
            baseline_map[(direction, horizon)] = row

    lift_rows: list[ProgressionDriftLiftRow] = []
    for item in observations:
        baseline = baseline_map[
            (item.event_direction, item.horizon_weeks)
        ]
        baseline_mean = baseline.control_mean_favorable_return
        resolved_index = resolved_event_indices[
            (item.event_week, item.event_direction)
        ]
        recomputed = compute_forward_outcome(
            weekly,
            signal_bar_index=resolved_index,
            horizon_bars=item.horizon_weeks,
            side=item.event_direction,
        )
        event_complete = recomputed is not None and recomputed.complete
        event_return = (
            recomputed.favorable_return
            if event_complete and recomputed is not None
            else None
        )
        frozen_return = (
            item.favorable_return
            if item.complete and item.favorable_return is not None
            else None
        )
        revision_delta = (
            None
            if event_return is None or frozen_return is None
            else event_return - frozen_return
        )
        lift = (
            None
            if event_return is None or baseline_mean is None
            else event_return - baseline_mean
        )
        lift_rows.append(
            ProgressionDriftLiftRow(
                symbol=clean_symbol,
                event_bar_index=item.event_bar_index,
                event_week=item.event_week,
                event_direction=item.event_direction,
                trend_alignment=item.trend_alignment,
                horizon_weeks=item.horizon_weeks,
                event_complete=event_complete,
                event_favorable_return=event_return,
                baseline_control_count=baseline.control_count,
                baseline_mean_favorable_return=baseline_mean,
                favorable_return_lift=lift,
                resolved_event_bar_index=resolved_index,
                frozen_event_favorable_return=frozen_return,
                event_return_revision_delta=revision_delta,
            )
        )

    return tuple(baseline_rows), tuple(lift_rows)


def _cohort_keys(
    item: ProgressionDriftLiftRow,
) -> tuple[tuple[str, str], ...]:
    return (
        ("all", "all"),
        ("event_direction", item.event_direction),
        ("trend_alignment", item.trend_alignment),
        (
            "direction_trend_alignment",
            f"{item.event_direction}|{item.trend_alignment}",
        ),
    )


def summarize_progression_drift_lift(
    rows: tuple[ProgressionDriftLiftRow, ...],
) -> tuple[ProgressionDriftLiftSummary, ...]:
    groups: dict[
        tuple[str, str, int],
        list[ProgressionDriftLiftRow],
    ] = defaultdict(list)
    for item in rows:
        for dimension, value in _cohort_keys(item):
            groups[(dimension, value, item.horizon_weeks)].append(item)

    output: list[ProgressionDriftLiftSummary] = []
    for (dimension, value, horizon), group in groups.items():
        complete = [
            item
            for item in group
            if item.favorable_return_lift is not None
            and item.event_favorable_return is not None
            and item.baseline_mean_favorable_return is not None
        ]
        event_returns = [
            float(item.event_favorable_return)
            for item in complete
        ]
        baseline_returns = [
            float(item.baseline_mean_favorable_return)
            for item in complete
        ]
        lifts = [
            float(item.favorable_return_lift)
            for item in complete
        ]
        positive = sum(item > 0.0 for item in lifts)

        by_symbol: dict[str, list[float]] = defaultdict(list)
        for item in complete:
            by_symbol[item.symbol].append(
                float(item.favorable_return_lift)
            )
        symbol_lifts = [
            mean(values) for values in by_symbol.values()
        ]
        positive_symbols = sum(item > 0.0 for item in symbol_lifts)

        output.append(
            ProgressionDriftLiftSummary(
                cohort_dimension=dimension,
                cohort_value=value,
                horizon_weeks=horizon,
                complete_event_count=len(complete),
                symbol_count=len(symbol_lifts),
                mean_event_favorable_return=(
                    None if not event_returns else mean(event_returns)
                ),
                mean_matched_baseline_favorable_return=(
                    None if not baseline_returns else mean(baseline_returns)
                ),
                mean_favorable_return_lift=(
                    None if not lifts else mean(lifts)
                ),
                median_favorable_return_lift=(
                    None if not lifts else median(lifts)
                ),
                positive_lift_count=positive,
                positive_lift_rate=(
                    None if not lifts else positive / len(lifts)
                ),
                equal_weighted_symbol_mean_lift=(
                    None if not symbol_lifts else mean(symbol_lifts)
                ),
                positive_symbol_count=positive_symbols,
                positive_symbol_rate=(
                    None
                    if not symbol_lifts
                    else positive_symbols / len(symbol_lifts)
                ),
            )
        )

    return tuple(
        sorted(
            output,
            key=lambda item: (
                item.cohort_dimension,
                item.cohort_value,
                item.horizon_weeks,
            ),
        )
    )


def build_progression_drift_baseline_audit(
    *,
    artifact: FrozenProgressionOutcomeArtifact,
    requested_symbols: tuple[str, ...],
    symbol_baselines: tuple[
        tuple[ProgressionDriftBaselineRow, ...],
        ...,
    ],
    symbol_lifts: tuple[
        tuple[ProgressionDriftLiftRow, ...],
        ...,
    ],
    failures: tuple[ProgressionDriftBaselineFailure, ...] = (),
) -> ProgressionDriftBaselineAudit:
    if len(symbol_baselines) != len(symbol_lifts):
        raise ValueError(
            "baseline and lift symbol groups must have equal length"
        )
    if len(symbol_lifts) + len(failures) != len(requested_symbols):
        raise ValueError(
            "successful plus failed symbols must equal requested symbols"
        )

    failure_symbols = [item.symbol for item in failures]
    if len(set(failure_symbols)) != len(failure_symbols):
        raise ValueError("failure symbols must be unique")

    baselines = tuple(
        row for group in symbol_baselines for row in group
    )
    lifts = tuple(row for group in symbol_lifts for row in group)

    failed_symbols = {item.symbol for item in failures}
    expected_observations = sum(
        len(artifact.observations_by_symbol.get(symbol, ()))
        for symbol in requested_symbols
        if symbol not in failed_symbols
    )
    if len(lifts) != expected_observations:
        raise ValueError(
            "K18 lift rows do not match successful frozen K15 inputs: "
            f"{len(lifts)} != {expected_observations}"
        )

    seen: set[tuple[str, int, str, int]] = set()
    for item in lifts:
        key = (
            item.symbol,
            item.event_bar_index,
            item.event_direction,
            item.horizon_weeks,
        )
        if key in seen:
            raise ValueError(f"duplicate K18 lift row: {key}")
        seen.add(key)

    processed_events = {
        (
            item.symbol,
            item.event_bar_index,
            item.event_week,
            item.event_direction,
        )
        for item in lifts
    }

    return ProgressionDriftBaselineAudit(
        audit_id=PROGRESSION_DRIFT_BASELINE_AUDIT_ID,
        basket_name=artifact.basket_name,
        requested_symbol_count=len(requested_symbols),
        successful_symbol_count=len(symbol_lifts),
        failed_symbol_count=len(failures),
        source_event_count=artifact.event_count,
        source_observation_count=artifact.observation_count,
        event_count=len(processed_events),
        observation_count=len(lifts),
        horizons_weeks=artifact.horizons_weeks,
        baseline_rows=baselines,
        lift_rows=lifts,
        summaries=summarize_progression_drift_lift(lifts),
        failures=tuple(sorted(failures, key=lambda item: item.symbol)),
    )


def write_progression_drift_baseline_audit(
    audit: ProgressionDriftBaselineAudit,
    output_dir: str | Path,
) -> ProgressionDriftBaselineAuditPaths:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    paths = ProgressionDriftBaselineAuditPaths(
        summary_json=root / "progression_drift_baseline_summary.json",
        baseline_csv=root / "progression_drift_baselines.csv",
        lift_csv=root / "progression_drift_event_lift.csv",
        cohort_csv=root / "progression_drift_lift_cohorts.csv",
        failures_csv=root / "progression_drift_baseline_failures.csv",
    )

    direction_summaries = [
        item
        for item in audit.summaries
        if item.cohort_dimension == "event_direction"
    ]
    summary = {
        "audit_id": audit.audit_id,
        "basket_name": audit.basket_name,
        "requested_symbol_count": audit.requested_symbol_count,
        "successful_symbol_count": audit.successful_symbol_count,
        "failed_symbol_count": audit.failed_symbol_count,
        "source_event_count": audit.source_event_count,
        "source_observation_count": audit.source_observation_count,
        "event_count": audit.event_count,
        "observation_count": audit.observation_count,
        "horizons_weeks": list(audit.horizons_weeks),
        "direction_lift_by_horizon": [
            asdict(item) for item in direction_summaries
        ],
        "control_definition": (
            "same symbol + same side + same horizon + non-progression "
            "weekly bars from first same-direction event to fixed cutoff"
        ),
        "execution_semantics": (
            "signal week N; execution at weekly bar N+1 close"
        ),
        "event_locator": (
            "frozen K15 event_week resolved exactly in local completed-weekly "
            "history; source event_bar_index retained as provenance only"
        ),
        "event_outcome_source": (
            "recomputed from the same local weekly history used for controls"
        ),
        "is_actionable": False,
    }
    paths.summary_json.write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    pd.DataFrame(
        [asdict(item) for item in audit.baseline_rows],
    ).to_csv(paths.baseline_csv, index=False)
    pd.DataFrame(
        [asdict(item) for item in audit.lift_rows],
    ).to_csv(paths.lift_csv, index=False)
    pd.DataFrame(
        [asdict(item) for item in audit.summaries],
    ).to_csv(paths.cohort_csv, index=False)
    pd.DataFrame(
        [asdict(item) for item in audit.failures],
        columns=("symbol", "exception_type", "reason"),
    ).to_csv(paths.failures_csv, index=False)
    return paths


__all__ = [
    "EXPECTED_K15_AUDIT_ID",
    "PROGRESSION_DRIFT_BASELINE_AUDIT_ID",
    "FrozenProgressionOutcomeArtifact",
    "FrozenProgressionOutcomeObservation",
    "ProgressionDriftBaselineAudit",
    "ProgressionDriftBaselineAuditPaths",
    "ProgressionDriftBaselineFailure",
    "ProgressionDriftBaselineRow",
    "ProgressionDriftLiftRow",
    "ProgressionDriftLiftSummary",
    "build_progression_drift_baseline_audit",
    "build_symbol_progression_drift_baseline",
    "load_frozen_progression_outcomes",
    "resolve_frozen_progression_event_bar_index",
    "summarize_progression_drift_lift",
    "write_progression_drift_baseline_audit",
]
