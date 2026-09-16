from __future__ import annotations

from datetime import date

import pandas as pd

from execution_timing import next_session_execution
from trading_calendar import NSETradingCalendar


def test_execution_moves_from_friday_signal_to_monday_session() -> None:
    calendar = NSETradingCalendar()
    sessions = pd.Index(pd.to_datetime(["2026-09-18", "2026-09-21"]))

    result = next_session_execution(
        sessions,
        signal_session="2026-09-18",
        calendar=calendar,
    )

    assert result.signal_session == date(2026, 9, 18)
    assert result.execution_session == date(2026, 9, 21)
    assert result.execution_bar_index == 1
    assert result.execution_available is True


def test_execution_skips_exchange_holiday() -> None:
    calendar = NSETradingCalendar(closed_dates=frozenset({date(2026, 9, 21)}))
    sessions = pd.Index(pd.to_datetime(["2026-09-18", "2026-09-22"]))

    result = next_session_execution(
        sessions,
        signal_session="2026-09-18",
        calendar=calendar,
    )

    assert result.execution_session == date(2026, 9, 22)
    assert result.execution_bar_index == 1
    assert result.execution_available is True


def test_execution_uses_explicit_special_weekend_session() -> None:
    calendar = NSETradingCalendar(extra_sessions=frozenset({date(2026, 9, 19)}))
    sessions = pd.Index(pd.to_datetime(["2026-09-18", "2026-09-19", "2026-09-21"]))

    result = next_session_execution(
        sessions,
        signal_session="2026-09-18",
        calendar=calendar,
    )

    assert result.execution_session == date(2026, 9, 19)
    assert result.execution_bar_index == 1
    assert result.execution_available is True


def test_missing_expected_execution_session_is_pending_not_skipped() -> None:
    calendar = NSETradingCalendar()
    sessions = pd.Index(pd.to_datetime(["2026-09-18", "2026-09-22"]))

    result = next_session_execution(
        sessions,
        signal_session="2026-09-18",
        calendar=calendar,
    )

    assert result.execution_session == date(2026, 9, 21)
    assert result.execution_bar_index is None
    assert result.execution_available is False


def test_latest_signal_without_future_bar_still_has_expected_execution_session() -> None:
    calendar = NSETradingCalendar()
    sessions = pd.Index(pd.to_datetime(["2026-09-18"]))

    result = next_session_execution(
        sessions,
        signal_session="2026-09-18",
        calendar=calendar,
    )

    assert result.execution_session == date(2026, 9, 21)
    assert result.execution_bar_index is None
    assert result.execution_available is False
