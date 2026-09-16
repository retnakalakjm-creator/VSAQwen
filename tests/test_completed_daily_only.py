from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from daily_completion import completed_daily_only
from trading_calendar import NSETradingCalendar


def _daily(*dates: str) -> pd.DataFrame:
    index = pd.DatetimeIndex(pd.to_datetime(list(dates)), name="date")
    return pd.DataFrame(
        {
            "open": [100.0 + i for i in range(len(index))],
            "high": [101.0 + i for i in range(len(index))],
            "low": [99.0 + i for i in range(len(index))],
            "close": [100.5 + i for i in range(len(index))],
            "volume": [1_000.0 + i for i in range(len(index))],
        },
        index=index,
    )


def test_current_session_is_excluded_before_close() -> None:
    daily = _daily("2026-09-14", "2026-09-15", "2026-09-16")

    result = completed_daily_only(daily, now="2026-09-16 14:00:00+05:30")

    assert tuple(result.index.date) == (
        date(2026, 9, 14),
        date(2026, 9, 15),
    )


def test_current_session_is_still_excluded_exactly_at_close() -> None:
    daily = _daily("2026-09-15", "2026-09-16")

    result = completed_daily_only(daily, now="2026-09-16 15:30:00+05:30")

    assert tuple(result.index.date) == (date(2026, 9, 15),)


def test_current_session_is_included_after_close() -> None:
    daily = _daily("2026-09-15", "2026-09-16")

    result = completed_daily_only(daily, now="2026-09-16 15:30:01+05:30")

    assert tuple(result.index.date) == (
        date(2026, 9, 15),
        date(2026, 9, 16),
    )


def test_non_session_rows_are_excluded_when_calendar_marks_closure() -> None:
    holiday = date(2026, 9, 16)
    calendar = NSETradingCalendar(closed_dates=frozenset({holiday}))
    daily = _daily("2026-09-15", "2026-09-16", "2026-09-17")

    result = completed_daily_only(
        daily,
        now="2026-09-17 16:00:00+05:30",
        calendar=calendar,
    )

    assert tuple(result.index.date) == (
        date(2026, 9, 15),
        date(2026, 9, 17),
    )


def test_special_weekend_session_can_be_completed() -> None:
    saturday = date(2026, 9, 19)
    calendar = NSETradingCalendar(extra_sessions=frozenset({saturday}))
    daily = _daily("2026-09-18", "2026-09-19")

    result = completed_daily_only(
        daily,
        now="2026-09-19 16:00:00+05:30",
        calendar=calendar,
    )

    assert tuple(result.index.date) == (
        date(2026, 9, 18),
        date(2026, 9, 19),
    )


def test_future_sessions_are_not_included() -> None:
    daily = _daily("2026-09-16", "2026-09-17")

    result = completed_daily_only(daily, now="2026-09-16 16:00:00+05:30")

    assert tuple(result.index.date) == (date(2026, 9, 16),)


def test_empty_frame_preserves_shape_without_calendar_lookup() -> None:
    daily = _daily()

    result = completed_daily_only(daily, now="2026-09-16 16:00:00+05:30")

    assert result.empty
    assert list(result.columns) == ["open", "high", "low", "close", "volume"]
    assert result.index.name == "date"


def test_daily_filter_requires_datetime_index() -> None:
    daily = pd.DataFrame({"close": [100.0]}, index=["2026-09-16"])

    with pytest.raises(TypeError, match="DatetimeIndex"):
        completed_daily_only(daily, now="2026-09-16 16:00:00+05:30")
