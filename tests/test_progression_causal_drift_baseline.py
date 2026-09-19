from __future__ import annotations

import pandas as pd

from audit.progression_causal_drift_baseline import (
    PROGRESSION_CAUSAL_DRIFT_AUDIT_ID,
    ProgressionCausalDriftRow,
    build_progression_causal_drift_audit,
    build_symbol_progression_causal_drift,
    summarize_progression_causal_drift,
)
from audit.progression_drift_baseline import (
    FrozenProgressionOutcomeArtifact,
    FrozenProgressionOutcomeObservation,
)
from daily_completion import completed_daily_only
from data import completed_weekly_only, daily_to_weekly


def _daily() -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=700, freq="D")
    close = [100.0 + item * 0.05 for item in range(len(index))]
    return pd.DataFrame(
        {
            "open": close,
            "high": [item + 1.0 for item in close],
            "low": [item - 1.0 for item in close],
            "close": close,
            "volume": [1000.0] * len(index),
        },
        index=index,
    )


def _observation(
    *,
    week: str,
    source_index: int,
    direction: str,
    horizon: int,
    trend_alignment: str = "aligned",
) -> FrozenProgressionOutcomeObservation:
    return FrozenProgressionOutcomeObservation(
        symbol="AAA.NS",
        event_bar_index=source_index,
        event_week=week,
        event_direction=direction,
        progression_difference=0.1,
        trend_direction="up",
        trend_alignment=trend_alignment,
        structural_pattern="stable",
        structural_pattern_alignment="ambiguous",
        horizon_weeks=horizon,
        outcome_available=True,
        complete=True,
        execution_bar_index=source_index + 1,
        exit_bar_index=source_index + 1 + horizon,
        raw_return=0.01,
        favorable_return=0.01,
        mfe=0.02,
        mae=-0.01,
    )


def _weekly(daily: pd.DataFrame, now: str) -> pd.DataFrame:
    return completed_weekly_only(
        daily_to_weekly(
            completed_daily_only(
                daily,
                now=now,
            )
        ),
        now=now,
    )


def test_controls_end_before_event_and_exclude_event_windows() -> None:
    daily = _daily()
    now = "2025-11-28T16:00:00+05:30"
    weekly = _weekly(daily, now)
    first_week = str(pd.Timestamp(weekly.iloc[20]["week_beginning"]))
    event_week = str(pd.Timestamp(weekly.iloc[60]["week_beginning"]))

    observations = (
        _observation(
            week=first_week,
            source_index=999,
            direction="bullish",
            horizon=3,
        ),
        _observation(
            week=event_week,
            source_index=1000,
            direction="bullish",
            horizon=3,
        ),
    )
    rows = build_symbol_progression_causal_drift(
        symbol="AAA.NS",
        daily=daily,
        observations=observations,
        now=now,
        control_windows=(26,),
    )

    target = next(
        item
        for item in rows
        if pd.Timestamp(item.event_week).normalize()
        == pd.Timestamp(event_week).normalize()
    )
    assert target.resolved_event_bar_index == 60
    assert target.source_event_bar_index == 1000
    assert target.control_count == 26
    assert target.newest_control_exit_bar is not None
    assert target.newest_control_exit_bar < target.resolved_event_bar_index


def test_multiple_control_windows_use_most_recent_eligible_controls() -> None:
    daily = _daily()
    now = "2025-11-28T16:00:00+05:30"
    weekly = _weekly(daily, now)
    event_week = str(pd.Timestamp(weekly.iloc[70]["week_beginning"]))
    observations = (
        _observation(
            week=event_week,
            source_index=70,
            direction="bullish",
            horizon=1,
        ),
    )

    rows = build_symbol_progression_causal_drift(
        symbol="AAA.NS",
        daily=daily,
        observations=observations,
        now=now,
        control_windows=(5, 10, 20),
    )

    assert [item.control_window_size for item in rows] == [5, 10, 20]
    assert [item.control_count for item in rows] == [5, 10, 20]
    assert all(
        item.newest_control_exit_bar < item.resolved_event_bar_index
        for item in rows
        if item.newest_control_exit_bar is not None
    )


def test_summary_equal_weights_symbols() -> None:
    rows = (
        ProgressionCausalDriftRow(
            symbol="AAA.NS",
            event_week="W1",
            event_direction="bullish",
            trend_alignment="aligned",
            source_event_bar_index=1,
            resolved_event_bar_index=1,
            horizon_weeks=5,
            control_window_size=26,
            control_count=26,
            oldest_control_signal_bar=1,
            newest_control_signal_bar=26,
            newest_control_exit_bar=25,
            event_complete=True,
            event_favorable_return=0.10,
            baseline_mean_favorable_return=0.04,
            baseline_median_favorable_return=0.03,
            favorable_return_lift=0.06,
        ),
        ProgressionCausalDriftRow(
            symbol="AAA.NS",
            event_week="W2",
            event_direction="bullish",
            trend_alignment="aligned",
            source_event_bar_index=2,
            resolved_event_bar_index=2,
            horizon_weeks=5,
            control_window_size=26,
            control_count=26,
            oldest_control_signal_bar=1,
            newest_control_signal_bar=26,
            newest_control_exit_bar=25,
            event_complete=True,
            event_favorable_return=0.08,
            baseline_mean_favorable_return=0.04,
            baseline_median_favorable_return=0.03,
            favorable_return_lift=0.04,
        ),
        ProgressionCausalDriftRow(
            symbol="BBB.NS",
            event_week="W1",
            event_direction="bullish",
            trend_alignment="aligned",
            source_event_bar_index=1,
            resolved_event_bar_index=1,
            horizon_weeks=5,
            control_window_size=26,
            control_count=26,
            oldest_control_signal_bar=1,
            newest_control_signal_bar=26,
            newest_control_exit_bar=25,
            event_complete=True,
            event_favorable_return=0.01,
            baseline_mean_favorable_return=0.03,
            baseline_median_favorable_return=0.02,
            favorable_return_lift=-0.02,
        ),
    )

    summary = next(
        item
        for item in summarize_progression_causal_drift(rows)
        if item.cohort_dimension == "event_direction"
    )
    assert summary.usable_event_count == 3
    assert summary.symbol_count == 2
    assert abs(summary.equal_weighted_symbol_mean_lift - 0.015) < 1e-12


def test_audit_row_count_expands_by_control_windows() -> None:
    artifact = FrozenProgressionOutcomeArtifact(
        basket_name="fixture",
        requested_symbol_count=1,
        event_count=1,
        observation_count=2,
        horizons_weeks=(1, 3),
        observations_by_symbol={"AAA.NS": ()},
    )
    row = ProgressionCausalDriftRow(
        symbol="AAA.NS",
        event_week="W1",
        event_direction="bullish",
        trend_alignment="aligned",
        source_event_bar_index=1,
        resolved_event_bar_index=1,
        horizon_weeks=1,
        control_window_size=26,
        control_count=1,
        oldest_control_signal_bar=0,
        newest_control_signal_bar=0,
        newest_control_exit_bar=0,
        event_complete=True,
        event_favorable_return=0.01,
        baseline_mean_favorable_return=0.0,
        baseline_median_favorable_return=0.0,
        favorable_return_lift=0.01,
    )
    second = ProgressionCausalDriftRow(
        symbol=row.symbol,
        event_week=row.event_week,
        event_direction=row.event_direction,
        trend_alignment=row.trend_alignment,
        source_event_bar_index=row.source_event_bar_index,
        resolved_event_bar_index=row.resolved_event_bar_index,
        horizon_weeks=3,
        control_window_size=26,
        control_count=1,
        oldest_control_signal_bar=0,
        newest_control_signal_bar=0,
        newest_control_exit_bar=0,
        event_complete=True,
        event_favorable_return=0.01,
        baseline_mean_favorable_return=0.0,
        baseline_median_favorable_return=0.0,
        favorable_return_lift=0.01,
    )
    artifact = FrozenProgressionOutcomeArtifact(
        basket_name="fixture",
        requested_symbol_count=1,
        event_count=1,
        observation_count=2,
        horizons_weeks=(1, 3),
        observations_by_symbol={
            "AAA.NS": (
                _observation(
                    week="W1",
                    source_index=1,
                    direction="bullish",
                    horizon=1,
                ),
                _observation(
                    week="W1",
                    source_index=1,
                    direction="bullish",
                    horizon=3,
                ),
            )
        },
    )

    audit = build_progression_causal_drift_audit(
        artifact=artifact,
        requested_symbols=("AAA.NS",),
        symbol_rows=((row, second),),
        control_windows=(26,),
    )

    assert audit.audit_id == PROGRESSION_CAUSAL_DRIFT_AUDIT_ID
    assert audit.comparison_row_count == 2
    assert audit.is_actionable is False
