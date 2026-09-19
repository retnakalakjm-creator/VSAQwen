from __future__ import annotations

import json

import pandas as pd

from daily_completion import completed_daily_only
from data import completed_weekly_only, daily_to_weekly
from audit.progression_drift_baseline import (
    EXPECTED_K15_AUDIT_ID,
    PROGRESSION_DRIFT_BASELINE_AUDIT_ID,
    FrozenProgressionOutcomeArtifact,
    FrozenProgressionOutcomeObservation,
    build_progression_drift_baseline_audit,
    build_symbol_progression_drift_baseline,
    load_frozen_progression_outcomes,
    summarize_progression_drift_lift,
)


def _daily() -> pd.DataFrame:
    index = pd.date_range("2026-01-05", periods=70, freq="D")
    close = [100.0 + item * 0.5 for item in range(len(index))]
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
    event_bar: int,
    week: str,
    direction: str,
    horizon: int,
    favorable: float | None,
    complete: bool = True,
    trend_alignment: str = "aligned",
) -> FrozenProgressionOutcomeObservation:
    return FrozenProgressionOutcomeObservation(
        symbol="AAA.NS",
        event_bar_index=event_bar,
        event_week=week,
        event_direction=direction,
        progression_difference=0.1,
        trend_direction="up",
        trend_alignment=trend_alignment,
        structural_pattern="stable",
        structural_pattern_alignment="ambiguous",
        horizon_weeks=horizon,
        outcome_available=True,
        complete=complete,
        execution_bar_index=event_bar + 1,
        exit_bar_index=event_bar + 1 + horizon,
        raw_return=favorable,
        favorable_return=favorable,
        mfe=0.1,
        mae=-0.05,
    )


def test_frozen_k15_loader_validates_counts_and_horizons(tmp_path) -> None:
    summary = {
        "audit_id": EXPECTED_K15_AUDIT_ID,
        "basket_name": "fixture",
        "requested_symbol_count": 1,
        "successful_symbol_count": 1,
        "failed_symbol_count": 0,
        "event_count": 1,
        "observation_count": 2,
        "horizons_weeks": [1, 3],
    }
    (tmp_path / "progression_directional_outcomes_summary.json").write_text(
        json.dumps(summary),
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            {
                "symbol": "AAA.NS",
                "event_bar_index": 2,
                "event_week": "2026-01-19",
                "event_direction": "bullish",
                "progression_difference": 0.1,
                "trend_direction": "up",
                "trend_alignment": "aligned",
                "structural_pattern": "stable",
                "structural_pattern_alignment": "ambiguous",
                "horizon_weeks": horizon,
                "outcome_available": True,
                "complete": True,
                "execution_bar_index": 3,
                "exit_bar_index": 3 + horizon,
                "raw_return": 0.02,
                "favorable_return": 0.02,
                "mfe": 0.03,
                "mae": -0.01,
            }
            for horizon in (1, 3)
        ]
    ).to_csv(
        tmp_path / "progression_directional_outcome_observations.csv",
        index=False,
    )

    artifact = load_frozen_progression_outcomes(
        input_dir=tmp_path,
        expected_basket_name="fixture",
    )

    assert artifact.event_count == 1
    assert artifact.observation_count == 2
    assert artifact.horizons_weeks == (1, 3)
    assert len(artifact.observations_by_symbol["AAA.NS"]) == 2


def test_symbol_baseline_excludes_progression_event_bars() -> None:
    daily = _daily()
    now = "2026-03-20T16:00:00+05:30"
    weekly = completed_weekly_only(
        daily_to_weekly(
            completed_daily_only(
                daily,
                now=now,
            )
        ),
        now=now,
    )
    event_week = str(pd.Timestamp(weekly.iloc[2]["week_beginning"]))
    observations = (
        _observation(
            event_bar=2,
            week=event_week,
            direction="bullish",
            horizon=1,
            favorable=0.03,
        ),
        _observation(
            event_bar=5,
            week=str(pd.Timestamp(weekly.iloc[5]["week_beginning"])),
            direction="bullish",
            horizon=1,
            favorable=0.04,
        ),
    )

    baseline_rows, lift_rows = build_symbol_progression_drift_baseline(
        symbol="AAA.NS",
        daily=daily,
        observations=observations,
        now=now,
    )

    assert len(baseline_rows) == 1
    assert baseline_rows[0].control_window_start_bar == 2
    assert baseline_rows[0].control_window_end_bar == len(weekly) - 1

    event_bars = {2, 5}
    expected_controls = sum(
        1
        for signal_bar in range(2, len(weekly))
        if signal_bar not in event_bars
        and signal_bar + 2 < len(weekly)
    )
    assert baseline_rows[0].control_count == expected_controls
    assert expected_controls > 0

    assert len(lift_rows) == 2
    assert all(
        item.baseline_control_count == expected_controls
        for item in lift_rows
    )


def test_symbol_baseline_resolves_event_by_week_not_source_index() -> None:
    daily = _daily()
    now = "2026-03-20T16:00:00+05:30"
    weekly = completed_weekly_only(
        daily_to_weekly(
            completed_daily_only(
                daily,
                now=now,
            )
        ),
        now=now,
    )
    event_week = str(pd.Timestamp(weekly.iloc[2]["week_beginning"]))
    observation = _observation(
        event_bar=999,
        week=event_week,
        direction="bullish",
        horizon=1,
        favorable=0.99,
    )

    _, lift_rows = build_symbol_progression_drift_baseline(
        symbol="AAA.NS",
        daily=daily,
        observations=(observation,),
        now=now,
    )

    assert len(lift_rows) == 1
    row = lift_rows[0]
    assert row.event_bar_index == 999
    assert row.resolved_event_bar_index == 2
    assert row.event_complete is True
    assert row.event_favorable_return != 0.99
    assert row.frozen_event_favorable_return == 0.99
    assert row.event_return_revision_delta is not None


def test_drift_summary_reports_event_and_symbol_normalized_lift() -> None:
    rows = (
        # Same symbol contributes two events.
        dict(
            symbol="AAA.NS",
            event_bar_index=1,
            event_week="W1",
            event_direction="bullish",
            trend_alignment="aligned",
            horizon_weeks=5,
            event_complete=True,
            event_favorable_return=0.10,
            baseline_control_count=10,
            baseline_mean_favorable_return=0.04,
            favorable_return_lift=0.06,
        ),
        dict(
            symbol="AAA.NS",
            event_bar_index=2,
            event_week="W2",
            event_direction="bullish",
            trend_alignment="aligned",
            horizon_weeks=5,
            event_complete=True,
            event_favorable_return=0.08,
            baseline_control_count=10,
            baseline_mean_favorable_return=0.04,
            favorable_return_lift=0.04,
        ),
        dict(
            symbol="BBB.NS",
            event_bar_index=1,
            event_week="W1",
            event_direction="bullish",
            trend_alignment="aligned",
            horizon_weeks=5,
            event_complete=True,
            event_favorable_return=0.01,
            baseline_control_count=10,
            baseline_mean_favorable_return=0.03,
            favorable_return_lift=-0.02,
        ),
    )
    from audit.progression_drift_baseline import ProgressionDriftLiftRow

    summaries = summarize_progression_drift_lift(
        tuple(ProgressionDriftLiftRow(**item) for item in rows)
    )
    direction = next(
        item
        for item in summaries
        if item.cohort_dimension == "event_direction"
        and item.cohort_value == "bullish"
    )

    assert direction.complete_event_count == 3
    assert direction.symbol_count == 2
    assert direction.mean_favorable_return_lift > 0
    # AAA mean lift = 0.05, BBB = -0.02, equally weighted = +0.015.
    assert abs(direction.equal_weighted_symbol_mean_lift - 0.015) < 1e-12
    assert direction.positive_symbol_count == 1
    assert direction.positive_symbol_rate == 0.5


def test_audit_preserves_all_k15_observations() -> None:
    artifact = FrozenProgressionOutcomeArtifact(
        basket_name="fixture",
        requested_symbol_count=1,
        event_count=0,
        observation_count=0,
        horizons_weeks=(1, 3),
        observations_by_symbol={},
    )

    audit = build_progression_drift_baseline_audit(
        artifact=artifact,
        requested_symbols=("AAA.NS",),
        symbol_baselines=((),),
        symbol_lifts=((),),
    )

    assert audit.audit_id == PROGRESSION_DRIFT_BASELINE_AUDIT_ID
    assert audit.observation_count == 0
    assert audit.is_actionable is False
