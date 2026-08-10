from __future__ import annotations

import pandas as pd

# =============================================================================
# Rolling Statistics Helpers
# =============================================================================

def rolling_mean(
    series: pd.Series,
    window: int,
) -> pd.Series:
    """
    Rolling mean using only historical bars.

    The current bar is excluded to prevent look-ahead bias.
    """

    return (
        series.shift(1)
        .rolling(
            window=window,
            min_periods=window,
        )
        .mean()
    )
    

def rolling_std(
    series: pd.Series,
    window: int,
) -> pd.Series:
    """
    Rolling population standard deviation using only
    historical bars.
    """

    return (
        series.shift(1)
        .rolling(
            window=window,
            min_periods=window,
        )
        .std(ddof=0)
    )
    

def historical_percentile_rank(
    series: pd.Series,
    window: int,
) -> pd.Series:
    """
    Rolling percentile rank using only historical data.

    Returns values between 0 and 100.
    """

    def percentile(values: pd.Series) -> float:

        current = values.iloc[-1]

        history = values.iloc[:-1]

        if history.empty:
            return 50.0

        return (
            (history <= current).mean()
            * 100.0
        )

    return (
        series
        .rolling(
            window=window + 1,
            min_periods=window + 1,
        )
        .apply(
            percentile,
            raw=False,
        )
        .fillna(50.0)
    ) 