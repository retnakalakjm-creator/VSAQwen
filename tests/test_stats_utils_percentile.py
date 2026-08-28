from __future__ import annotations

import numpy as np
import pandas as pd

from stats_utils import historical_percentile_rank


def _reference(series: pd.Series, window: int) -> pd.Series:
    def percentile(values: pd.Series) -> float:
        current = values.iloc[-1]
        history = values.iloc[:-1]
        if history.empty:
            return 50.0
        return (history <= current).mean() * 100.0

    return (
        series.rolling(window=window + 1, min_periods=window + 1)
        .apply(percentile, raw=False)
        .fillna(50.0)
    )


def _assert_equivalent(series: pd.Series, window: int) -> None:
    actual = historical_percentile_rank(series, window=window)
    expected = _reference(series, window=window)
    pd.testing.assert_series_equal(actual, expected, check_exact=True)


def test_historical_percentile_rank_matches_reference_with_ties():
    _assert_equivalent(
        pd.Series([1.0, 2.0, 2.0, 4.0, 2.0, 5.0, 5.0, 3.0]),
        window=4,
    )


def test_historical_percentile_rank_matches_reference_for_insufficient_history():
    _assert_equivalent(pd.Series([10.0, 20.0, 30.0]), window=4)


def test_historical_percentile_rank_matches_reference_with_nan_values():
    _assert_equivalent(
        pd.Series([1.0, np.nan, 3.0, 3.0, 2.0, 4.0, np.nan, 5.0, 5.0]),
        window=3,
    )


def test_historical_percentile_rank_matches_reference_randomized():
    rng = np.random.default_rng(20260828)

    for window in (1, 2, 3, 5, 10):
        for _ in range(20):
            values = rng.integers(0, 8, size=40).astype(float)
            values[rng.random(40) < 0.15] = np.nan
            _assert_equivalent(pd.Series(values), window=window)
