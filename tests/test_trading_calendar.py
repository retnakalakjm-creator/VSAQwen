from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from trading_calendar import NSETradingCalendar, TradingCalendar


def test_regular_weekdays_are_sessions_and_weekends_are_not() -> None:
    calendar = NSETradingCalendar()

    assert calendar.is_session("2026-09-16")
    assert not calendar.is_session("2026-09-19")
    assert not calendar.is_session("2026-09-20")


def test_authoritative_closures_and_special_sessions_override_weekday_rule() -> None:
    holiday = date(2026, 9, 17)
    special_saturday = date(2026, 9, 19)
    calendar = NSETradingCalendar(
        closed_dates=frozenset({holiday}),
        extra_sessions=frozenset({special_saturday}),
    )

    assert not calendar.is_session(holiday)
    assert calendar.is_session(special_saturday)


def test_conflicting_calendar_configuration_is_rejected() -> None:
    value = date(2026, 9, 17)

    with pytest.raises(ValueError, match="must not overlap"):
        NSETradingCalendar(
            closed_dates=frozenset({value}),
            extra_sessions=frozenset({value}),
        )


def test_session_close_is_timezone_aware_and_rejects_non_sessions() -> None:
    calendar = NSETradingCalendar()

    close = calendar.session_close("2026-09-16")

    assert close == pd.Timestamp("2026-09-16 15:30:00", tz="Asia/Kolkata")
    with pytest.raises(ValueError, match="not an NSE trading session"):
        calendar.session_close("2026-09-20")


def test_session_completion_is_strictly_after_market_close() -> None:
    calendar = NSETradingCalendar()

    assert not calendar.is_session_complete(
        "2026-09-16",
        now="2026-09-16 15:29:59+05:30",
    )
    assert not calendar.is_session_complete(
        "2026-09-16",
        now="2026-09-16 15:30:00+05:30",
    )
    assert calendar.is_session_complete(
        "2026-09-16",
        now="2026-09-16 15:30:01+05:30",
    )


def test_session_completion_converts_other_timezones_to_nse_time() -> None:
    calendar = NSETradingCalendar()

    assert calendar.is_session_complete(
        "2026-09-16",
        now="2026-09-16 10:00:01+00:00",
    )
    assert not calendar.is_session_complete(
        "2026-09-16",
        now="2026-09-16 10:00:00+00:00",
    )


def test_next_and_previous_session_skip_weekends_and_closures() -> None:
    calendar = NSETradingCalendar(
        closed_dates=frozenset({date(2026, 9, 21)}),
    )

    assert calendar.next_session("2026-09-18") == date(2026, 9, 22)
    assert calendar.previous_session("2026-09-22") == date(2026, 9, 18)


def test_next_session_can_use_explicit_weekend_session() -> None:
    calendar = NSETradingCalendar(
        extra_sessions=frozenset({date(2026, 9, 19)}),
    )

    assert calendar.next_session("2026-09-18") == date(2026, 9, 19)


def test_calendar_satisfies_runtime_protocol() -> None:
    calendar = NSETradingCalendar()

    assert isinstance(calendar, TradingCalendar)
