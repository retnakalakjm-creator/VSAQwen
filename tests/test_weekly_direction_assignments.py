from __future__ import annotations

from datetime import date

import pandas as pd

from audit.weekly_direction_assignments import (
    WEEKLY_DIRECTION_ASSIGNMENT_PRODUCER_ID,
    fingerprint_weekly_direction_source,
    produce_causal_weekly_direction_assignments,
)
from background.qualification import PatternQualification
from trading_calendar import NSETradingCalendar
from weekly_setup import (
    WeeklySetup,
    WeeklySetupDirection,
    WeeklySetupStatus,
    build_weekly_setup_id,
)


def _daily() -> pd.DataFrame:
    index = pd.to_datetime(
        [
            "2026-09-11",
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
            "open": [100, 101, 102, 103, 104, 105, 106, 107],
            "high": [102, 103, 104, 105, 106, 107, 108, 109],
            "low": [99, 100, 101, 102, 103, 104, 105, 106],
            "close": [101, 102, 103, 104, 105, 106, 107, 108],
            "volume": [1000, 1100, 1050, 1200, 1300, 1250, 1400, 1500],
        },
        index=index,
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


def test_same_week_sessions_cannot_receive_friday_weekly_direction() -> None:
    archive = produce_causal_weekly_direction_assignments(
        symbol="lt.ns",
        daily=_daily(),
        setups=(_setup(),),
        now="2026-09-22T16:00:00+05:30",
    )

    assert archive.symbol == "LT.NS"
    assert archive.producer_id == WEEKLY_DIRECTION_ASSIGNMENT_PRODUCER_ID
    assert tuple(item.bar_index for item in archive.observations) == (6, 7)
    assert tuple(item.session for item in archive.observations) == (
        "2026-09-21",
        "2026-09-22",
    )
    assert all(
        item.direction is WeeklySetupDirection.BULLISH
        for item in archive.observations
    )
    assert archive.is_actionable is False


def test_latest_causally_visible_weekly_setup_controls_direction() -> None:
    older = _setup(signal_week="2026-08-31")
    newer = _setup(
        signal_week="2026-09-07",
        direction=WeeklySetupDirection.BEARISH,
    )

    archive = produce_causal_weekly_direction_assignments(
        symbol="LT.NS",
        daily=_daily(),
        setups=(newer, older),
        now="2026-09-22T16:00:00+05:30",
    )

    by_bar = {item.bar_index: item for item in archive.observations}
    assert by_bar[0].direction is WeeklySetupDirection.BULLISH
    assert by_bar[1].direction is WeeklySetupDirection.BEARISH
    assert all(
        by_bar[index].direction is WeeklySetupDirection.BEARISH
        for index in range(1, 8)
    )


def test_terminal_latest_setup_suppresses_active_direction_assignment() -> None:
    older = _setup(signal_week="2026-08-31")
    terminal = _setup(
        signal_week="2026-09-07",
        direction=WeeklySetupDirection.BEARISH,
        status=WeeklySetupStatus.INVALIDATED,
    )

    archive = produce_causal_weekly_direction_assignments(
        symbol="LT.NS",
        daily=_daily(),
        setups=(older, terminal),
        now="2026-09-22T16:00:00+05:30",
    )

    assert tuple(item.bar_index for item in archive.observations) == (0,)
    assert archive.observations[0].direction is WeeklySetupDirection.BULLISH


def test_forming_daily_session_is_excluded_before_assignment() -> None:
    daily = _daily()
    last_session = daily.index[-1]
    now = pd.Timestamp(last_session).tz_localize("Asia/Kolkata") + pd.Timedelta(
        hours=12
    )

    archive = produce_causal_weekly_direction_assignments(
        symbol="LT.NS",
        daily=daily,
        setups=(_setup(signal_week="2026-09-07"),),
        now=now,
    )

    assert len(archive.completed_daily) == 7
    assert archive.completed_daily.index[-1] == daily.index[-2]
    assert max(item.bar_index for item in archive.observations) == 6


def test_friday_exchange_closure_preserves_next_session_visibility() -> None:
    calendar = NSETradingCalendar(
        closed_dates=frozenset({date(2026, 9, 18)})
    )
    daily = _daily().drop(pd.Timestamp("2026-09-18"))

    archive = produce_causal_weekly_direction_assignments(
        symbol="LT.NS",
        daily=daily,
        setups=(_setup(),),
        now="2026-09-22T16:00:00+05:30",
        calendar=calendar,
    )

    assert tuple(item.session for item in archive.observations) == (
        "2026-09-21",
        "2026-09-22",
    )


def test_future_setup_does_not_change_existing_direction_assignments() -> None:
    daily = _daily()
    older = _setup(signal_week="2026-09-07")
    future = _setup(
        signal_week="2026-09-14",
        direction=WeeklySetupDirection.BEARISH,
    )

    base = produce_causal_weekly_direction_assignments(
        symbol="LT.NS",
        daily=daily.iloc[:6],
        setups=(older,),
        now="2026-09-18T16:00:00+05:30",
    )
    extended = produce_causal_weekly_direction_assignments(
        symbol="LT.NS",
        daily=daily,
        setups=(older, future),
        now="2026-09-22T16:00:00+05:30",
    )

    assert extended.observations[: len(base.observations)] == base.observations


def test_assignments_are_directly_compatible_with_k3_input_contract() -> None:
    archive = produce_causal_weekly_direction_assignments(
        symbol="LT.NS",
        daily=_daily(),
        setups=(_setup(signal_week="2026-09-07"),),
        now="2026-09-22T16:00:00+05:30",
    )

    assert tuple(item.bar_index for item in archive.assignments) == tuple(
        item.bar_index for item in archive.observations
    )
    assert tuple(item.direction for item in archive.assignments) == tuple(
        item.direction for item in archive.observations
    )
    assert archive.assignment_count == len(archive.assignments)


def test_source_fingerprint_is_deterministic_and_setup_sensitive() -> None:
    daily = _daily()
    calendar = NSETradingCalendar()
    bullish = _setup(signal_week="2026-09-07")
    bearish = _setup(
        signal_week="2026-09-07",
        direction=WeeklySetupDirection.BEARISH,
    )

    first = fingerprint_weekly_direction_source(
        symbol="lt.ns",
        completed_daily=daily,
        setups=(bullish,),
        calendar=calendar,
    )
    second = fingerprint_weekly_direction_source(
        symbol="LT.NS",
        completed_daily=daily.copy(),
        setups=(bullish,),
        calendar=calendar,
    )
    changed = fingerprint_weekly_direction_source(
        symbol="LT.NS",
        completed_daily=daily,
        setups=(bearish,),
        calendar=calendar,
    )

    assert first == second
    assert first.sha256.startswith("sha256:")
    assert first.completed_daily_bar_count == len(daily)
    assert changed.sha256 != first.sha256


def test_other_symbol_setups_do_not_enter_symbol_archive() -> None:
    archive = produce_causal_weekly_direction_assignments(
        symbol="LT.NS",
        daily=_daily(),
        setups=(
            _setup(symbol="RELIANCE.NS", signal_week="2026-09-07"),
        ),
        now="2026-09-22T16:00:00+05:30",
    )

    assert archive.observations == ()
    assert archive.source_fingerprint.setup_count == 0
