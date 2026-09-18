from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

from background.qualification import PatternQualification
from daily_behavior import DailyBehaviorDimension
from daily_entry import DailyEntryShadowStatus
from daily_trigger_replay import DailyTriggerReplayStatus
from models import Evidence, EvidenceCategory, EvidenceCode, EvidenceDirection
from weekly_daily_shadow_pipeline import evaluate_weekly_daily_shadow_pipeline
from weekly_setup import WeeklySetupDirection


def _daily() -> pd.DataFrame:
    index = pd.to_datetime(
        [
            "2026-09-14",
            "2026-09-15",
            "2026-09-16",
            "2026-09-17",
            "2026-09-18",
            "2026-09-21",
            "2026-09-22",
        ]
    )
    return pd.DataFrame(
        {
            "open": [100, 101, 102, 103, 104, 105, 106],
            "high": [102, 103, 104, 105, 106, 107, 108],
            "low": [99, 100, 101, 102, 103, 104, 105],
            "close": [101, 102, 103, 104, 105, 106, 107],
            "volume": [1000, 1100, 1050, 1200, 1300, 1250, 1400],
        },
        index=index,
    )


def _candidate(**overrides):
    values = {
        "actionable": True,
        "qualification": PatternQualification.PERSISTENT_BULLISH,
        "week": "2026-09-14",
        "confidence": 0.82,
        "net_strength": 1.25,
        "net_pressure": 0.74,
        "qualifying_evidence": (),
        "scoring_evidence": (),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _evidence(
    *,
    code: EvidenceCode,
    direction: EvidenceDirection,
    bar_index: int,
) -> Evidence:
    return Evidence(
        code=code,
        category=EvidenceCategory.SIGNAL,
        direction=direction,
        strength=0.8,
        weight=1.0,
        observation=str(code),
        description=str(code),
        bar_index=bar_index,
        week_beginning="2026-09-21",
    )


def test_same_week_daily_bar_cannot_consume_friday_weekly_setup() -> None:
    result = evaluate_weekly_daily_shadow_pipeline(
        candidate=_candidate(),
        symbol="LT.NS",
        daily=_daily(),
        daily_bar_index=4,
        now="2026-09-22 16:00:00",
    )

    assert result.daily_session.isoformat() == "2026-09-18"
    assert result.weekly_setup is not None
    assert result.context.setup is None
    assert result.observation.status is DailyEntryShadowStatus.NO_WEEKLY_SETUP
    assert result.behavior is None
    assert result.trigger is None
    assert result.is_actionable is False


def test_next_week_fresh_aligned_behavior_flows_to_next_session_shadow_replay() -> None:
    demand = _evidence(
        code=EvidenceCode.DEMAND_COMING_IN,
        direction=EvidenceDirection.BULLISH,
        bar_index=5,
    )

    result = evaluate_weekly_daily_shadow_pipeline(
        candidate=_candidate(),
        symbol=" lt.ns ",
        daily=_daily(),
        evidence=(demand,),
        daily_bar_index=5,
        now="2026-09-22 16:00:00",
    )

    assert result.symbol == "LT.NS"
    assert result.daily_session.isoformat() == "2026-09-21"
    assert result.context.setup == result.weekly_setup
    assert result.context.is_armed
    assert result.observation.status is DailyEntryShadowStatus.OBSERVING
    assert result.behavior is not None
    assert result.behavior.weekly_direction is WeeklySetupDirection.BULLISH
    assert DailyBehaviorDimension.ALIGNED_PRESSURE_EMERGING in result.behavior.dimensions
    assert result.trigger is not None
    assert result.trigger.status is DailyTriggerReplayStatus.NEXT_SESSION_AVAILABLE
    assert result.trigger.execution_session.isoformat() == "2026-09-22"
    assert result.trigger.execution_bar_index == 6
    assert result.trigger.is_actionable is False
    assert result.is_actionable is False


def test_incomplete_latest_daily_bar_is_excluded_and_expected_session_stays_pending() -> None:
    demand = _evidence(
        code=EvidenceCode.DEMAND_COMING_IN,
        direction=EvidenceDirection.BULLISH,
        bar_index=5,
    )

    result = evaluate_weekly_daily_shadow_pipeline(
        candidate=_candidate(),
        symbol="LT.NS",
        daily=_daily(),
        evidence=(demand,),
        now="2026-09-22 12:00:00",
    )

    assert result.completed_daily_bar_count == 6
    assert result.daily_bar_index == 5
    assert result.daily_session.isoformat() == "2026-09-21"
    assert result.trigger is not None
    assert result.trigger.status is DailyTriggerReplayStatus.PENDING_NEXT_SESSION
    assert result.trigger.execution_session.isoformat() == "2026-09-22"
    assert result.trigger.execution_bar_index is None
    assert result.trigger.execution_available is False


def test_non_actionable_weekly_candidate_never_creates_daily_behavior() -> None:
    result = evaluate_weekly_daily_shadow_pipeline(
        candidate=_candidate(actionable=False),
        symbol="LT.NS",
        daily=_daily(),
        daily_bar_index=5,
        now="2026-09-22 16:00:00",
    )

    assert result.weekly_setup is None
    assert result.context.setup is None
    assert result.observation.status is DailyEntryShadowStatus.NO_WEEKLY_SETUP
    assert result.behavior is None
    assert result.trigger is None


def test_future_daily_evidence_cannot_leak_into_current_behavior() -> None:
    future = _evidence(
        code=EvidenceCode.DEMAND_COMING_IN,
        direction=EvidenceDirection.BULLISH,
        bar_index=6,
    )

    result = evaluate_weekly_daily_shadow_pipeline(
        candidate=_candidate(),
        symbol="LT.NS",
        daily=_daily(),
        evidence=(future,),
        daily_bar_index=5,
        now="2026-09-22 16:00:00",
    )

    assert result.behavior is not None
    assert result.behavior.observed_evidence == ()
    assert result.behavior.dimensions == ()
    assert result.trigger is not None
    assert result.trigger.status is DailyTriggerReplayStatus.NO_NEW_BEHAVIOR


def test_bearish_weekly_candidate_uses_bearish_daily_behavior_symmetrically() -> None:
    supply = _evidence(
        code=EvidenceCode.SUPPLY_COMING_IN,
        direction=EvidenceDirection.BEARISH,
        bar_index=5,
    )

    result = evaluate_weekly_daily_shadow_pipeline(
        candidate=_candidate(
            qualification=PatternQualification.PERSISTENT_BEARISH,
            net_strength=-1.1,
            net_pressure=-0.9,
        ),
        symbol="ABC.NS",
        daily=_daily(),
        evidence=(supply,),
        daily_bar_index=5,
        now="2026-09-22 16:00:00",
    )

    assert result.weekly_setup is not None
    assert result.weekly_setup.direction is WeeklySetupDirection.BEARISH
    assert result.behavior is not None
    assert DailyBehaviorDimension.ALIGNED_PRESSURE_EMERGING in result.behavior.dimensions
    assert result.trigger is not None
    assert result.trigger.status is DailyTriggerReplayStatus.NEXT_SESSION_AVAILABLE


def test_pipeline_rejects_target_outside_completed_daily_bars() -> None:
    with pytest.raises(IndexError, match="outside completed daily bars"):
        evaluate_weekly_daily_shadow_pipeline(
            candidate=_candidate(),
            symbol="LT.NS",
            daily=_daily(),
            daily_bar_index=6,
            now="2026-09-22 12:00:00",
        )
