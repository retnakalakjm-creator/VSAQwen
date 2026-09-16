from __future__ import annotations

from datetime import date

import pandas as pd

from background.qualification import PatternQualification
from daily_behavior import DailyBehaviorDimension, evaluate_daily_behavior
from daily_trigger_replay import (
    DailyTriggerReplayStatus,
    build_daily_trigger_replay_output,
)
from models import Evidence, EvidenceCategory, EvidenceCode, EvidenceDirection
from trading_calendar import NSETradingCalendar
from weekly_daily_coordinator import WeeklyDailyContext
from weekly_setup import (
    WeeklySetup,
    WeeklySetupDirection,
    WeeklySetupStatus,
    build_weekly_setup_id,
)


def _setup(
    *,
    direction: WeeklySetupDirection = WeeklySetupDirection.BULLISH,
    status: WeeklySetupStatus = WeeklySetupStatus.ARMED,
) -> WeeklySetup:
    qualification = (
        PatternQualification.PERSISTENT_BULLISH
        if direction is WeeklySetupDirection.BULLISH
        else PatternQualification.PERSISTENT_BEARISH
    )
    signal_week = "2026-09-07"
    return WeeklySetup(
        setup_id=build_weekly_setup_id("LT.NS", signal_week, direction),
        symbol="LT.NS",
        direction=direction,
        signal_week=signal_week,
        qualification=qualification,
        weekly_confidence=0.8,
        weekly_net_strength=1.2,
        weekly_net_pressure=0.4,
        status=status,
    )


def _context(
    setup: WeeklySetup | None,
    *,
    daily_session: date = date(2026, 9, 18),
) -> WeeklyDailyContext:
    return WeeklyDailyContext(
        symbol="LT.NS",
        daily_session=daily_session,
        setup=setup,
        weekly_completion_session=date(2026, 9, 11) if setup else None,
        setup_available_session=date(2026, 9, 14) if setup else None,
    )


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
        week_beginning="2026-09-14",
    )


def test_replay_output_requires_armed_weekly_setup() -> None:
    behavior = evaluate_daily_behavior(
        weekly_direction=WeeklySetupDirection.BULLISH,
        daily_bar_index=0,
        evidence=(),
    )

    result = build_daily_trigger_replay_output(
        context=_context(None),
        behavior=behavior,
        sessions=pd.Index(pd.to_datetime(["2026-09-18"])),
        calendar=NSETradingCalendar(),
    )

    assert result.status is DailyTriggerReplayStatus.NO_ARMED_WEEKLY_SETUP
    assert result.signal_observed is False
    assert result.is_actionable is False


def test_old_lookback_evidence_does_not_repeat_as_fresh_signal() -> None:
    setup = _setup()
    old = _evidence(
        code=EvidenceCode.NO_SUPPLY,
        direction=EvidenceDirection.BULLISH,
        bar_index=0,
    )
    behavior = evaluate_daily_behavior(
        weekly_direction=WeeklySetupDirection.BULLISH,
        daily_bar_index=1,
        evidence=(old,),
        lookback_bars=5,
    )

    result = build_daily_trigger_replay_output(
        context=_context(setup),
        behavior=behavior,
        sessions=pd.Index(pd.to_datetime(["2026-09-17", "2026-09-18"])),
        calendar=NSETradingCalendar(),
    )

    assert DailyBehaviorDimension.OPPOSING_PRESSURE_RECEDING in result.behavior_dimensions
    assert result.signal_dimensions == ()
    assert result.status is DailyTriggerReplayStatus.NO_NEW_BEHAVIOR
    assert result.execution_session is None


def test_current_behavior_signal_waits_for_exact_next_session() -> None:
    setup = _setup()
    current = _evidence(
        code=EvidenceCode.DEMAND_COMING_IN,
        direction=EvidenceDirection.BULLISH,
        bar_index=0,
    )
    behavior = evaluate_daily_behavior(
        weekly_direction=WeeklySetupDirection.BULLISH,
        daily_bar_index=0,
        evidence=(current,),
    )

    result = build_daily_trigger_replay_output(
        context=_context(setup),
        behavior=behavior,
        sessions=pd.Index(pd.to_datetime(["2026-09-18"])),
        calendar=NSETradingCalendar(),
    )

    assert result.status is DailyTriggerReplayStatus.PENDING_NEXT_SESSION
    assert result.signal_dimensions == (
        DailyBehaviorDimension.ALIGNED_PRESSURE_EMERGING,
    )
    assert result.signal_evidence == (current,)
    assert result.execution_session == date(2026, 9, 21)
    assert result.execution_bar_index is None
    assert result.execution_available is False
    assert result.is_actionable is False


def test_current_behavior_signal_exposes_next_session_when_bar_exists() -> None:
    setup = _setup()
    current = _evidence(
        code=EvidenceCode.NO_SUPPLY,
        direction=EvidenceDirection.BULLISH,
        bar_index=0,
    )
    behavior = evaluate_daily_behavior(
        weekly_direction=WeeklySetupDirection.BULLISH,
        daily_bar_index=0,
        evidence=(current,),
    )

    result = build_daily_trigger_replay_output(
        context=_context(setup),
        behavior=behavior,
        sessions=pd.Index(pd.to_datetime(["2026-09-18", "2026-09-21"])),
        calendar=NSETradingCalendar(),
    )

    assert result.status is DailyTriggerReplayStatus.NEXT_SESSION_AVAILABLE
    assert result.signal_observed is True
    assert result.execution_session == date(2026, 9, 21)
    assert result.execution_bar_index == 1
    assert result.execution_available is True
    assert result.is_actionable is False


def test_exchange_holiday_moves_replay_execution_to_next_valid_session() -> None:
    setup = _setup()
    current = _evidence(
        code=EvidenceCode.TEST,
        direction=EvidenceDirection.BULLISH,
        bar_index=0,
    )
    behavior = evaluate_daily_behavior(
        weekly_direction=WeeklySetupDirection.BULLISH,
        daily_bar_index=0,
        evidence=(current,),
    )
    calendar = NSETradingCalendar(
        closed_dates=frozenset({date(2026, 9, 21)})
    )

    result = build_daily_trigger_replay_output(
        context=_context(setup),
        behavior=behavior,
        sessions=pd.Index(pd.to_datetime(["2026-09-18", "2026-09-22"])),
        calendar=calendar,
    )

    assert result.execution_session == date(2026, 9, 22)
    assert result.execution_bar_index == 1
    assert result.execution_available is True


def test_behavior_direction_must_match_weekly_setup() -> None:
    setup = _setup(direction=WeeklySetupDirection.BULLISH)
    behavior = evaluate_daily_behavior(
        weekly_direction=WeeklySetupDirection.BEARISH,
        daily_bar_index=0,
        evidence=(),
    )

    try:
        build_daily_trigger_replay_output(
            context=_context(setup),
            behavior=behavior,
            sessions=pd.Index(pd.to_datetime(["2026-09-18"])),
            calendar=NSETradingCalendar(),
        )
    except ValueError as exc:
        assert "weekly direction" in str(exc)
    else:
        raise AssertionError("mismatched weekly direction should fail")


def test_behavior_bar_must_match_context_daily_session() -> None:
    setup = _setup()
    current = _evidence(
        code=EvidenceCode.DEMAND_COMING_IN,
        direction=EvidenceDirection.BULLISH,
        bar_index=0,
    )
    behavior = evaluate_daily_behavior(
        weekly_direction=WeeklySetupDirection.BULLISH,
        daily_bar_index=0,
        evidence=(current,),
    )

    try:
        build_daily_trigger_replay_output(
            context=_context(setup),
            behavior=behavior,
            sessions=pd.Index(pd.to_datetime(["2026-09-17"])),
            calendar=NSETradingCalendar(),
        )
    except ValueError as exc:
        assert "daily bar" in str(exc)
    else:
        raise AssertionError("context/session mismatch should fail")
