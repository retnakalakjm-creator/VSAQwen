from datetime import date

from background.qualification import PatternQualification
from daily_entry import DailyEntryEngine, DailyEntryShadowStatus
from models import Evidence, EvidenceCategory, EvidenceCode, EvidenceDirection
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
        status=status,
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
        week_beginning="2026-03-09",
    )


def _context(setup: WeeklySetup | None) -> WeeklyDailyContext:
    return WeeklyDailyContext(
        symbol="LT.NS",
        daily_session=date(2026, 3, 9),
        setup=setup,
        weekly_completion_session=date(2026, 3, 6) if setup else None,
        setup_available_session=date(2026, 3, 9) if setup else None,
    )


def test_shadow_engine_reports_missing_weekly_setup_without_actionability() -> None:
    result = DailyEntryEngine().evaluate_shadow(
        context=_context(None),
        daily_bar_index=10,
    )

    assert result.status is DailyEntryShadowStatus.NO_WEEKLY_SETUP
    assert result.weekly_setup_id is None
    assert result.is_actionable is False


def test_shadow_engine_observes_armed_weekly_setup() -> None:
    setup = _setup()
    result = DailyEntryEngine().evaluate_shadow(
        context=_context(setup),
        daily_bar_index=10,
    )

    assert result.status is DailyEntryShadowStatus.OBSERVING
    assert result.weekly_setup_id == setup.setup_id
    assert result.weekly_direction is WeeklySetupDirection.BULLISH
    assert result.has_armed_weekly_setup is True
    assert result.is_actionable is False


def test_shadow_engine_does_not_treat_terminal_weekly_setup_as_armed() -> None:
    setup = _setup(status=WeeklySetupStatus.INVALIDATED)
    result = DailyEntryEngine().evaluate_shadow(
        context=_context(setup),
        daily_bar_index=10,
    )

    assert result.status is DailyEntryShadowStatus.WEEKLY_SETUP_NOT_ARMED
    assert result.has_armed_weekly_setup is False
    assert result.is_actionable is False


def test_shadow_engine_only_admits_evidence_from_current_daily_bar() -> None:
    setup = _setup()
    stale = _evidence(
        code=EvidenceCode.NO_SUPPLY,
        direction=EvidenceDirection.BULLISH,
        bar_index=9,
    )
    current = _evidence(
        code=EvidenceCode.TEST,
        direction=EvidenceDirection.BULLISH,
        bar_index=10,
    )
    future = _evidence(
        code=EvidenceCode.NO_DEMAND,
        direction=EvidenceDirection.BEARISH,
        bar_index=11,
    )

    result = DailyEntryEngine().evaluate_shadow(
        context=_context(setup),
        daily_bar_index=10,
        evidence=(future, current, stale),
    )

    assert result.observed_evidence == (current,)
    assert result.aligned_evidence == (current,)
    assert result.opposing_evidence == ()


def test_opposing_daily_evidence_is_observed_without_reversing_weekly_thesis() -> None:
    setup = _setup(direction=WeeklySetupDirection.BULLISH)
    opposing = _evidence(
        code=EvidenceCode.NO_DEMAND,
        direction=EvidenceDirection.BEARISH,
        bar_index=10,
    )

    result = DailyEntryEngine().evaluate_shadow(
        context=_context(setup),
        daily_bar_index=10,
        evidence=(opposing,),
    )

    assert result.status is DailyEntryShadowStatus.OBSERVING
    assert result.weekly_direction is WeeklySetupDirection.BULLISH
    assert result.opposing_evidence == (opposing,)
    assert setup.status is WeeklySetupStatus.ARMED
    assert result.is_actionable is False


def test_bearish_weekly_setup_aligns_bearish_daily_evidence() -> None:
    setup = _setup(direction=WeeklySetupDirection.BEARISH)
    bearish = _evidence(
        code=EvidenceCode.NO_DEMAND,
        direction=EvidenceDirection.BEARISH,
        bar_index=10,
    )

    result = DailyEntryEngine().evaluate_shadow(
        context=_context(setup),
        daily_bar_index=10,
        evidence=(bearish,),
    )

    assert result.status is DailyEntryShadowStatus.OBSERVING
    assert result.aligned_evidence == (bearish,)
    assert result.opposing_evidence == ()


def test_negative_daily_bar_index_is_rejected() -> None:
    try:
        DailyEntryEngine().evaluate_shadow(
            context=_context(_setup()),
            daily_bar_index=-1,
        )
    except ValueError as exc:
        assert "daily_bar_index" in str(exc)
    else:
        raise AssertionError("negative daily_bar_index should fail")
