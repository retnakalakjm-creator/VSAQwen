from datetime import date

from background.qualification import PatternQualification
from daily_behavior import DailyBehaviorDimension
from daily_entry import DailyEntryEngine
from models import Evidence, EvidenceCategory, EvidenceCode, EvidenceDirection
from weekly_daily_coordinator import WeeklyDailyContext
from weekly_setup import WeeklySetup, WeeklySetupDirection, build_weekly_setup_id


def _setup(direction: WeeklySetupDirection = WeeklySetupDirection.BULLISH) -> WeeklySetup:
    qualification = (
        PatternQualification.PERSISTENT_BULLISH
        if direction is WeeklySetupDirection.BULLISH
        else PatternQualification.PERSISTENT_BEARISH
    )
    signal_week = "2026-03-02"
    return WeeklySetup(
        setup_id=build_weekly_setup_id("LT.NS", signal_week, direction),
        symbol="LT.NS",
        direction=direction,
        signal_week=signal_week,
        qualification=qualification,
        weekly_confidence=0.8,
        weekly_net_strength=1.2,
        weekly_net_pressure=0.4,
    )


def _context(setup: WeeklySetup | None) -> WeeklyDailyContext:
    return WeeklyDailyContext(
        symbol="LT.NS",
        daily_session=date(2026, 3, 9),
        setup=setup,
        weekly_completion_session=date(2026, 3, 6) if setup else None,
        setup_available_session=date(2026, 3, 9) if setup else None,
    )


def _evidence(
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
        week_beginning="2026-03-09",
    )


def test_behavior_does_not_require_no_supply_or_test() -> None:
    demand = _evidence(
        EvidenceCode.DEMAND_COMING_IN,
        EvidenceDirection.BULLISH,
        10,
    )

    result = DailyEntryEngine().evaluate_behavior_shadow(
        context=_context(_setup()),
        daily_bar_index=10,
        evidence=(demand,),
    )

    assert result is not None
    assert DailyBehaviorDimension.ALIGNED_PRESSURE_EMERGING in result.dimensions
    assert DailyBehaviorDimension.OPPOSING_PRESSURE_RECEDING not in result.dimensions
    assert result.is_actionable is False


def test_named_textbook_events_are_supporting_evidence_not_gatekeepers() -> None:
    no_supply = _evidence(EvidenceCode.NO_SUPPLY, EvidenceDirection.BULLISH, 9)
    test = _evidence(EvidenceCode.TEST, EvidenceDirection.BULLISH, 10)

    result = DailyEntryEngine().evaluate_behavior_shadow(
        context=_context(_setup()),
        daily_bar_index=10,
        evidence=(no_supply, test),
    )

    assert result is not None
    assert result.evidence_for(
        DailyBehaviorDimension.OPPOSING_PRESSURE_RECEDING
    ) == (no_supply, test)


def test_behavior_uses_bounded_recent_window_without_future_leakage() -> None:
    stale = _evidence(EvidenceCode.DEMAND_COMING_IN, EvidenceDirection.BULLISH, 4)
    recent = _evidence(EvidenceCode.INCREASING_DEMAND, EvidenceDirection.BULLISH, 8)
    current = _evidence(EvidenceCode.HIDDEN_DEMAND, EvidenceDirection.BULLISH, 10)
    future = _evidence(EvidenceCode.STOPPING_VOLUME, EvidenceDirection.BULLISH, 11)

    result = DailyEntryEngine().evaluate_behavior_shadow(
        context=_context(_setup()),
        daily_bar_index=10,
        evidence=(future, current, stale, recent),
        lookback_bars=3,
    )

    assert result is not None
    assert result.observed_evidence == (recent, current)
    assert future not in result.observed_evidence
    assert stale not in result.observed_evidence


def test_opposing_daily_event_does_not_become_positive_behavior() -> None:
    opposing = _evidence(EvidenceCode.NO_DEMAND, EvidenceDirection.BEARISH, 10)

    result = DailyEntryEngine().evaluate_behavior_shadow(
        context=_context(_setup()),
        daily_bar_index=10,
        evidence=(opposing,),
    )

    assert result is not None
    assert result.dimensions == ()
    assert result.observed_evidence == (opposing,)


def test_bearish_weekly_setup_uses_symmetric_behavior_mapping() -> None:
    supply = _evidence(
        EvidenceCode.SUPPLY_COMING_IN,
        EvidenceDirection.BEARISH,
        10,
    )
    no_demand = _evidence(
        EvidenceCode.NO_DEMAND,
        EvidenceDirection.BEARISH,
        9,
    )

    result = DailyEntryEngine().evaluate_behavior_shadow(
        context=_context(_setup(WeeklySetupDirection.BEARISH)),
        daily_bar_index=10,
        evidence=(supply, no_demand),
    )

    assert result is not None
    assert DailyBehaviorDimension.ALIGNED_PRESSURE_EMERGING in result.dimensions
    assert DailyBehaviorDimension.OPPOSING_PRESSURE_RECEDING in result.dimensions


def test_no_behavior_snapshot_without_armed_weekly_setup() -> None:
    result = DailyEntryEngine().evaluate_behavior_shadow(
        context=_context(None),
        daily_bar_index=10,
    )

    assert result is None


def test_invalid_behavior_lookback_is_rejected() -> None:
    try:
        DailyEntryEngine().evaluate_behavior_shadow(
            context=_context(_setup()),
            daily_bar_index=10,
            lookback_bars=0,
        )
    except ValueError as exc:
        assert "lookback_bars" in str(exc)
    else:
        raise AssertionError("zero lookback_bars should fail")
