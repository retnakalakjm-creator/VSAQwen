"""Causal pre-event drift baseline for progression outcomes.

This analysis-only audit compares each frozen progression event with same-symbol,
same-side, same-horizon non-event controls whose complete forward outcomes were
already known before the event. Controls whose holding windows contain any
progression event are excluded.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean, median

import pandas as pd

from audit.outcomes import ForwardOutcome, compute_forward_outcome
from audit.progression_drift_baseline import (
    FrozenProgressionOutcomeArtifact,
    FrozenProgressionOutcomeObservation,
    load_frozen_progression_outcomes,
    resolve_frozen_progression_event_bar_index,
)
from daily_completion import completed_daily_only
from data import completed_weekly_only, daily_to_weekly
from trading_calendar import NSETradingCalendar, TradingCalendar


PROGRESSION_CAUSAL_DRIFT_AUDIT_ID = (
    "progression-causal-pre-event-drift-baseline-v1"
)
DEFAULT_CONTROL_WINDOWS = (26, 52, 104)


@dataclass(frozen=True, slots=True)
class ProgressionCausalDriftRow:
    symbol: str
    event_week: str
    event_direction: str
    trend_alignment: str
    source_event_bar_index: int
    resolved_event_bar_index: int
    horizon_weeks: int
    control_window_size: int
    control_count: int
    oldest_control_signal_bar: int | None
    newest_control_signal_bar: int | None
    newest_control_exit_bar: int | None
    event_complete: bool
    event_favorable_return: float | None
    baseline_mean_favorable_return: float | None
    baseline_median_favorable_return: float | None
    favorable_return_lift: float | None


@dataclass(frozen=True, slots=True)
class ProgressionCausalDriftSummary:
    cohort_dimension: str
    cohort_value: str
    horizon_weeks: int
    control_window_size: int
    usable_event_count: int
    symbol_count: int
    mean_control_count: float | None
    min_control_count: int | None
    mean_event_favorable_return: float | None
    mean_baseline_favorable_return: float | None
    mean_favorable_return_lift: float | None
    median_favorable_return_lift: float | None
    positive_lift_count: int
    positive_lift_rate: float | None
    equal_weighted_symbol_mean_lift: float | None
    positive_symbol_count: int
    positive_symbol_rate: float | None


@dataclass(frozen=True, slots=True)
class ProgressionCausalDriftFailure:
    symbol: str
    exception_type: str
    reason: str


@dataclass(frozen=True, slots=True)
class ProgressionCausalDriftAudit:
    audit_id: str
    basket_name: str
    requested_symbol_count: int
    successful_symbol_count: int
    failed_symbol_count: int
    source_event_count: int
    source_observation_count: int
    comparison_row_count: int
    control_windows: tuple[int, ...]
    rows: tuple[ProgressionCausalDriftRow, ...]
    summaries: tuple[ProgressionCausalDriftSummary, ...]
    failures: tuple[ProgressionCausalDriftFailure, ...]

    @property
    def is_actionable(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class ProgressionCausalDriftAuditPaths:
    summary_json: Path
    rows_csv: Path
    cohorts_csv: Path
    failures_csv: Path

    def as_dict(self) -> dict[str, str]:
        return {
            "summary_json": str(self.summary_json),
            "rows_csv": str(self.rows_csv),
            "cohorts_csv": str(self.cohorts_csv),
            "failures_csv": str(self.failures_csv),
        }


def _normalized_windows(values: tuple[int, ...]) -> tuple[int, ...]:
    normalized = tuple(sorted(set(int(item) for item in values)))
    if not normalized or any(item <= 0 for item in normalized):
        raise ValueError("control windows must contain positive counts")
    return normalized


def _event_identity_rows(
    observations: tuple[FrozenProgressionOutcomeObservation, ...],
) -> dict[tuple[str, str], FrozenProgressionOutcomeObservation]:
    result: dict[
        tuple[str, str],
        FrozenProgressionOutcomeObservation,
    ] = {}
    for item in observations:
        key = (item.event_week, item.event_direction)
        existing = result.get(key)
        if (
            existing is not None
            and existing.event_bar_index != item.event_bar_index
        ):
            raise ValueError(f"frozen event identity conflict: {key}")
        result.setdefault(key, item)
    return result


def _candidate_controls(
    *,
    weekly: pd.DataFrame,
    event_bars: set[int],
    side: str,
    horizon_weeks: int,
) -> tuple[ForwardOutcome, ...]:
    candidates: list[ForwardOutcome] = []
    for signal_bar_index in range(len(weekly)):
        if signal_bar_index in event_bars:
            continue
        outcome = compute_forward_outcome(
            weekly,
            signal_bar_index=signal_bar_index,
            horizon_bars=horizon_weeks,
            side=side,
        )
        if outcome is None or not outcome.complete:
            continue
        if any(
            signal_bar_index <= event_bar <= outcome.exit_bar_index
            for event_bar in event_bars
        ):
            continue
        candidates.append(outcome)
    return tuple(candidates)


def _select_prior_controls(
    *,
    candidates: tuple[ForwardOutcome, ...],
    event_bar_index: int,
    max_count: int,
) -> tuple[ForwardOutcome, ...]:
    eligible = [
        item
        for item in candidates
        if item.exit_bar_index < event_bar_index
    ]
    if len(eligible) > max_count:
        eligible = eligible[-max_count:]
    return tuple(eligible)


def build_symbol_progression_causal_drift(
    *,
    symbol: str,
    daily: pd.DataFrame,
    observations: tuple[FrozenProgressionOutcomeObservation, ...],
    now: str | pd.Timestamp | None,
    control_windows: tuple[int, ...] = DEFAULT_CONTROL_WINDOWS,
    calendar: TradingCalendar | None = None,
) -> tuple[ProgressionCausalDriftRow, ...]:
    clean_symbol = symbol.strip().upper()
    if any(item.symbol != clean_symbol for item in observations):
        raise ValueError(
            f"{clean_symbol} received observations from another symbol"
        )
    if not observations:
        return ()

    windows = _normalized_windows(control_windows)
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

    event_rows = _event_identity_rows(observations)
    resolved = {
        key: resolve_frozen_progression_event_bar_index(
            weekly=weekly,
            observation=item,
        )
        for key, item in event_rows.items()
    }
    event_bars = set(resolved.values())

    candidate_cache: dict[
        tuple[str, int],
        tuple[ForwardOutcome, ...],
    ] = {}
    for side in sorted(
        {item.event_direction for item in event_rows.values()}
    ):
        for horizon in sorted(
            {item.horizon_weeks for item in observations}
        ):
            candidate_cache[(side, horizon)] = _candidate_controls(
                weekly=weekly,
                event_bars=event_bars,
                side=side,
                horizon_weeks=horizon,
            )

    rows: list[ProgressionCausalDriftRow] = []
    for item in observations:
        event_index = resolved[
            (item.event_week, item.event_direction)
        ]
        event_outcome = compute_forward_outcome(
            weekly,
            signal_bar_index=event_index,
            horizon_bars=item.horizon_weeks,
            side=item.event_direction,
        )
        event_complete = (
            event_outcome is not None and event_outcome.complete
        )
        event_return = (
            event_outcome.favorable_return
            if event_complete and event_outcome is not None
            else None
        )

        candidates = candidate_cache[
            (item.event_direction, item.horizon_weeks)
        ]
        for window in windows:
            controls = _select_prior_controls(
                candidates=candidates,
                event_bar_index=event_index,
                max_count=window,
            )
            control_returns = [
                control.favorable_return for control in controls
            ]
            baseline_mean = (
                None if not control_returns else mean(control_returns)
            )
            baseline_median = (
                None if not control_returns else median(control_returns)
            )
            lift = (
                None
                if event_return is None or baseline_mean is None
                else event_return - baseline_mean
            )
            rows.append(
                ProgressionCausalDriftRow(
                    symbol=clean_symbol,
                    event_week=item.event_week,
                    event_direction=item.event_direction,
                    trend_alignment=item.trend_alignment,
                    source_event_bar_index=item.event_bar_index,
                    resolved_event_bar_index=event_index,
                    horizon_weeks=item.horizon_weeks,
                    control_window_size=window,
                    control_count=len(controls),
                    oldest_control_signal_bar=(
                        None
                        if not controls
                        else controls[0].signal_bar_index
                    ),
                    newest_control_signal_bar=(
                        None
                        if not controls
                        else controls[-1].signal_bar_index
                    ),
                    newest_control_exit_bar=(
                        None
                        if not controls
                        else controls[-1].exit_bar_index
                    ),
                    event_complete=event_complete,
                    event_favorable_return=event_return,
                    baseline_mean_favorable_return=baseline_mean,
                    baseline_median_favorable_return=baseline_median,
                    favorable_return_lift=lift,
                )
            )

    return tuple(rows)


def _cohort_keys(
    item: ProgressionCausalDriftRow,
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


def summarize_progression_causal_drift(
    rows: tuple[ProgressionCausalDriftRow, ...],
) -> tuple[ProgressionCausalDriftSummary, ...]:
    groups: dict[
        tuple[str, str, int, int],
        list[ProgressionCausalDriftRow],
    ] = defaultdict(list)
    for item in rows:
        for dimension, value in _cohort_keys(item):
            groups[
                (
                    dimension,
                    value,
                    item.horizon_weeks,
                    item.control_window_size,
                )
            ].append(item)

    summaries: list[ProgressionCausalDriftSummary] = []
    for (dimension, value, horizon, window), group in groups.items():
        usable = [
            item
            for item in group
            if item.favorable_return_lift is not None
            and item.event_favorable_return is not None
            and item.baseline_mean_favorable_return is not None
        ]
        lifts = [
            float(item.favorable_return_lift)
            for item in usable
        ]
        event_returns = [
            float(item.event_favorable_return)
            for item in usable
        ]
        baselines = [
            float(item.baseline_mean_favorable_return)
            for item in usable
        ]
        control_counts = [item.control_count for item in usable]

        by_symbol: dict[str, list[float]] = defaultdict(list)
        for item in usable:
            by_symbol[item.symbol].append(
                float(item.favorable_return_lift)
            )
        symbol_lifts = [
            mean(values) for values in by_symbol.values()
        ]
        positive_lifts = sum(item > 0.0 for item in lifts)
        positive_symbols = sum(
            item > 0.0 for item in symbol_lifts
        )

        summaries.append(
            ProgressionCausalDriftSummary(
                cohort_dimension=dimension,
                cohort_value=value,
                horizon_weeks=horizon,
                control_window_size=window,
                usable_event_count=len(usable),
                symbol_count=len(symbol_lifts),
                mean_control_count=(
                    None
                    if not control_counts
                    else mean(control_counts)
                ),
                min_control_count=(
                    None if not control_counts else min(control_counts)
                ),
                mean_event_favorable_return=(
                    None if not event_returns else mean(event_returns)
                ),
                mean_baseline_favorable_return=(
                    None if not baselines else mean(baselines)
                ),
                mean_favorable_return_lift=(
                    None if not lifts else mean(lifts)
                ),
                median_favorable_return_lift=(
                    None if not lifts else median(lifts)
                ),
                positive_lift_count=positive_lifts,
                positive_lift_rate=(
                    None
                    if not lifts
                    else positive_lifts / len(lifts)
                ),
                equal_weighted_symbol_mean_lift=(
                    None
                    if not symbol_lifts
                    else mean(symbol_lifts)
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
            summaries,
            key=lambda item: (
                item.cohort_dimension,
                item.cohort_value,
                item.horizon_weeks,
                item.control_window_size,
            ),
        )
    )


def build_progression_causal_drift_audit(
    *,
    artifact: FrozenProgressionOutcomeArtifact,
    requested_symbols: tuple[str, ...],
    symbol_rows: tuple[
        tuple[ProgressionCausalDriftRow, ...],
        ...,
    ],
    control_windows: tuple[int, ...] = DEFAULT_CONTROL_WINDOWS,
    failures: tuple[ProgressionCausalDriftFailure, ...] = (),
) -> ProgressionCausalDriftAudit:
    windows = _normalized_windows(control_windows)
    if len(symbol_rows) + len(failures) != len(requested_symbols):
        raise ValueError(
            "successful plus failed symbols must equal requested symbols"
        )

    failure_symbols = [item.symbol for item in failures]
    if len(set(failure_symbols)) != len(failure_symbols):
        raise ValueError("failure symbols must be unique")
    unknown_failures = sorted(
        set(failure_symbols) - set(requested_symbols)
    )
    if unknown_failures:
        raise ValueError(
            f"failure symbols are outside requested symbols: "
            f"{unknown_failures}"
        )

    failed_symbols = set(failure_symbols)
    expected_observations = sum(
        len(artifact.observations_by_symbol.get(symbol, ()))
        for symbol in requested_symbols
        if symbol not in failed_symbols
    )
    rows = tuple(item for group in symbol_rows for item in group)
    expected_rows = expected_observations * len(windows)
    if len(rows) != expected_rows:
        raise ValueError(
            f"causal drift row count mismatch: "
            f"{len(rows)} != {expected_rows}"
        )

    seen: set[tuple[str, str, str, int, int]] = set()
    for item in rows:
        key = (
            item.symbol,
            item.event_week,
            item.event_direction,
            item.horizon_weeks,
            item.control_window_size,
        )
        if key in seen:
            raise ValueError(f"duplicate causal drift row: {key}")
        seen.add(key)

    return ProgressionCausalDriftAudit(
        audit_id=PROGRESSION_CAUSAL_DRIFT_AUDIT_ID,
        basket_name=artifact.basket_name,
        requested_symbol_count=len(requested_symbols),
        successful_symbol_count=len(symbol_rows),
        failed_symbol_count=len(failures),
        source_event_count=artifact.event_count,
        source_observation_count=artifact.observation_count,
        comparison_row_count=len(rows),
        control_windows=windows,
        rows=rows,
        summaries=summarize_progression_causal_drift(rows),
        failures=tuple(sorted(failures, key=lambda item: item.symbol)),
    )


def write_progression_causal_drift_audit(
    audit: ProgressionCausalDriftAudit,
    output_dir: str | Path,
) -> ProgressionCausalDriftAuditPaths:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    paths = ProgressionCausalDriftAuditPaths(
        summary_json=root / "progression_causal_drift_summary.json",
        rows_csv=root / "progression_causal_drift_rows.csv",
        cohorts_csv=root / "progression_causal_drift_cohorts.csv",
        failures_csv=root / "progression_causal_drift_failures.csv",
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
        "comparison_row_count": audit.comparison_row_count,
        "control_windows": list(audit.control_windows),
        "direction_lift_by_horizon_and_window": [
            asdict(item) for item in direction_summaries
        ],
        "control_definition": (
            "same symbol + same side + same horizon + most recent N "
            "non-event controls whose complete outcome ended before the "
            "event and whose holding window contained no progression event"
        ),
        "execution_semantics": (
            "event and control signal week N; execution at N+1 close"
        ),
        "is_actionable": False,
    }
    paths.summary_json.write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    pd.DataFrame(
        [asdict(item) for item in audit.rows],
    ).to_csv(paths.rows_csv, index=False)
    pd.DataFrame(
        [asdict(item) for item in audit.summaries],
    ).to_csv(paths.cohorts_csv, index=False)
    pd.DataFrame(
        [asdict(item) for item in audit.failures],
        columns=("symbol", "exception_type", "reason"),
    ).to_csv(paths.failures_csv, index=False)
    return paths


__all__ = [
    "DEFAULT_CONTROL_WINDOWS",
    "PROGRESSION_CAUSAL_DRIFT_AUDIT_ID",
    "ProgressionCausalDriftAudit",
    "ProgressionCausalDriftAuditPaths",
    "ProgressionCausalDriftFailure",
    "ProgressionCausalDriftRow",
    "ProgressionCausalDriftSummary",
    "build_progression_causal_drift_audit",
    "build_symbol_progression_causal_drift",
    "summarize_progression_causal_drift",
    "write_progression_causal_drift_audit",
]
