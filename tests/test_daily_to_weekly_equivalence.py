from __future__ import annotations

import pandas as pd
from pandas.testing import assert_frame_equal

from config import WEEK_RULE
from data import daily_to_weekly


def _reference_daily_to_weekly(df: pd.DataFrame) -> pd.DataFrame:
    weekly = (
        df.resample(WEEK_RULE)
        .agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }
        )
        .dropna()
    )

    week_start = df.groupby(pd.Grouper(freq=WEEK_RULE)).apply(
        lambda x: x.index.min()
    )
    weekly["week_beginning"] = week_start
    weekly = weekly[
        ["week_beginning", "open", "high", "low", "close", "volume"]
    ]
    return weekly.reset_index(drop=True)


def test_daily_to_weekly_matches_existing_semantics():
    index = pd.date_range("2025-01-02", periods=80, freq="B")
    df = pd.DataFrame(
        {
            "open": range(100, 180),
            "high": range(102, 182),
            "low": range(98, 178),
            "close": range(101, 181),
            "volume": range(1000, 1080),
        },
        index=index,
    )
    df.index.name = "date"

    actual = daily_to_weekly(df)
    expected = _reference_daily_to_weekly(df)

    assert_frame_equal(actual, expected, check_exact=True)
