from __future__ import annotations

import pandas as pd
import pytest

from data import completed_weekly_only, daily_to_weekly


def _daily_frame(start: str, periods: int) -> pd.DataFrame:
    index = pd.bdate_range(start=start, periods=periods)
    return pd.DataFrame(
        {
            "open": range(100, 100 + periods),
            "high": range(101, 101 + periods),
            "low": range(99, 99 + periods),
            "close": range(100, 100 + periods),
            "volume": range(1000, 1000 + periods),
        },
        index=index,
    )


def test_completed_weekly_only_drops_current_week_before_close() -> None:
    daily = _daily_frame("2026-08-31", 6)
    weekly = daily_to_weekly(daily)

    completed = completed_weekly_only(weekly, now="2026-09-07 10:00")

    assert len(weekly) == 2
    assert len(completed) == 1
    assert completed.iloc[-1]["week_beginning"] == pd.Timestamp("2026-08-31")


def test_completed_weekly_only_keeps_week_after_friday_close() -> None:
    daily = _daily_frame("2026-08-31", 5)
    weekly = daily_to_weekly(daily)

    completed = completed_weekly_only(weekly, now="2026-09-04 16:00")

    assert len(weekly) == 1
    assert len(completed) == 1
    assert completed.iloc[-1]["week_beginning"] == pd.Timestamp("2026-08-31")


def test_completed_weekly_only_drops_week_before_friday_close() -> None:
    daily = _daily_frame("2026-08-31", 5)
    weekly = daily_to_weekly(daily)

    completed = completed_weekly_only(weekly, now="2026-09-04 10:00")

    assert len(weekly) == 1
    assert completed.empty


def test_completed_weekly_only_returns_empty_input_safely() -> None:
    columns = ["week_beginning", "open", "high", "low", "close", "volume"]
    weekly = pd.DataFrame(columns=columns)

    completed = completed_weekly_only(weekly, now="2026-09-07 10:00")

    assert completed.empty
    assert list(completed.columns) == columns


def test_completed_weekly_only_rejects_missing_week_identity() -> None:
    weekly = pd.DataFrame({"open": [1.0]})

    with pytest.raises(ValueError, match="week_beginning"):
        completed_weekly_only(weekly, now="2026-09-07 10:00")
