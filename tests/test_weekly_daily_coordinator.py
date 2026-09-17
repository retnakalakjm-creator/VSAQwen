from __future__ import annotations

from datetime import date

import pytest

from background.qualification import PatternQualification
from trading_calendar import NSETradingCalendar
from weekly_daily_coordinator import (
    WeeklyDailyCoordinator,
    weekly_setup_available_session,
    weekly_setup_completion_session,
)
from weekly_setup import (
    WeeklySetup,
    WeeklySetupDirection,
    WeeklySetupStatus,
    build_weekly_setup_id,
)


def _setup(
    *,
    symbol: str = "LT.NS",
    signal_week: str = "2026-09-14",
    direction: WeeklySetupDirection = WeeklySetupDirection.BULLISH,
    status: WeeklySetupStatus = WeeklySetupStatus.ARMED,
) -> WeeklySetup:
    qualification = (
        PatternQualification.PERSISTENT_BULLISH
        if direction is WeeklySetupDirection.BULLISH
        else PatternQualification.PERSISTENT_BEARISH
    )
    return WeeklySetup(
        setup_id=build_weekly_setup_id(symbol, signal_week, direction),
        symbol=symbol,
        direction=direction,
        signal_week=signal_week,
        qualification=qualification,
        weekly_confidence=0.8,
        weekly_net_strength=0.6,
        weekly_net_pressure=0.4,
        status=status,
    )


def test_same_week_daily_sessions_cannot_see_friday_weekly_setup() -> None:
    calendar = NSETradingCalendar()
    coordinator = WeeklyDailyCoordinator(calendar)
    setup = _setup()

    for session in ("2026-09-14", "2026-09-15", "2026-09-16", "2026-09-17", "2026-09-18"):
        context = coordinator.context_for(
            symbol="LT.NS",
            daily_session=session,
            setups=[setup],
        )
        assert context.setup is None


def test_setup_becomes_visible_on_next_trading_session() -> None:
    calendar = NSETradingCalendar()
    setup = _setup()

    assert weekly_setup_completion_session(setup, calendar=calendar) == date(2026, 9, 18)
    assert weekly_setup_available_session(setup, calendar=calendar) == date(2026, 9, 21)

    context = WeeklyDailyCoordinator(calendar).context_for(
        symbol="lt.ns",
        daily_session="2026-09-21",
        setups=[setup],
    )

    assert context.setup == setup
    assert context.weekly_completion_session == date(2026, 9, 18)
    assert context.setup_available_session == date(2026, 9, 21)
    assert context.is_armed


def test_friday_exchange_closure_moves_weekly_completion_to_thursday() -> None:
    calendar = NSETradingCalendar(closed_dates=frozenset({date(2026, 9, 18)}))
    setup = _setup()

    assert weekly_setup_completion_session(setup, calendar=calendar) == date(2026, 9, 17)
    assert weekly_setup_available_session(setup, calendar=calendar) == date(2026, 9, 21)


def test_special_weekend_session_can_be_first_consumer_of_weekly_setup() -> None:
    calendar = NSETradingCalendar(extra_sessions=frozenset({date(2026, 9, 19)}))
    setup = _setup()

    assert weekly_setup_available_session(setup, calendar=calendar) == date(2026, 9, 19)
    context = WeeklyDailyCoordinator(calendar).context_for(
        symbol="LT.NS",
        daily_session="2026-09-19",
        setups=[setup],
    )
    assert context.setup == setup


def test_latest_causally_available_weekly_setup_wins() -> None:
    calendar = NSETradingCalendar()
    older = _setup(signal_week="2026-08-31")
    newer = _setup(signal_week="2026-09-07", direction=WeeklySetupDirection.BEARISH)
    future = _setup(signal_week="2026-09-14")

    context = WeeklyDailyCoordinator(calendar).context_for(
        symbol="LT.NS",
        daily_session="2026-09-16",
        setups=[future, older, newer],
    )

    assert context.setup == newer


def test_other_symbols_do_not_leak_into_context() -> None:
    calendar = NSETradingCalendar()
    setup = _setup(symbol="RELIANCE.NS", signal_week="2026-09-07")

    context = WeeklyDailyCoordinator(calendar).context_for(
        symbol="LT.NS",
        daily_session="2026-09-16",
        setups=[setup],
    )

    assert context.setup is None


def test_terminal_setup_remains_visible_but_is_not_armed() -> None:
    calendar = NSETradingCalendar()
    setup = _setup(
        signal_week="2026-09-07",
        status=WeeklySetupStatus.INVALIDATED,
    )

    context = WeeklyDailyCoordinator(calendar).context_for(
        symbol="LT.NS",
        daily_session="2026-09-16",
        setups=[setup],
    )

    assert context.setup == setup
    assert not context.is_armed


def test_non_session_daily_date_is_rejected() -> None:
    calendar = NSETradingCalendar()

    with pytest.raises(ValueError, match="not a trading session"):
        WeeklyDailyCoordinator(calendar).context_for(
            symbol="LT.NS",
            daily_session="2026-09-20",
            setups=[],
        )


def test_duplicate_setup_identity_is_rejected() -> None:
    calendar = NSETradingCalendar()
    setup = _setup(signal_week="2026-09-07")

    with pytest.raises(ValueError, match="duplicate weekly setup id"):
        WeeklyDailyCoordinator(calendar).context_for(
            symbol="LT.NS",
            daily_session="2026-09-16",
            setups=[setup, setup],
        )


def test_conflicting_latest_weekly_setups_are_rejected() -> None:
    calendar = NSETradingCalendar()
    bullish = _setup(signal_week="2026-09-07")
    bearish = _setup(
        signal_week="2026-09-07",
        direction=WeeklySetupDirection.BEARISH,
    )

    with pytest.raises(ValueError, match="multiple weekly setups share"):
        WeeklyDailyCoordinator(calendar).context_for(
            symbol="LT.NS",
            daily_session="2026-09-16",
            setups=[bullish, bearish],
        )
