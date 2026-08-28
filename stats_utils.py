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

    The percentile is the percentage of the preceding ``window``
    observations that are less than or equal to the current value.
    The current observation is excluded from the comparison.
    """

    rolling_window = series.rolling(
        window=window + 1,
        min_periods=window + 1,
    )

    # For a complete [history + current] window, the current value's
    # maximum rank includes the current observation itself. Removing
    # one therefore leaves exactly the number of historical values
    # less than or equal to the current value.
    current_rank = rolling_window.rank(method="max")

    result = (
        current_rank
        .sub(1.0)
        .div(float(window))
        .mul(100.0)
    )

    # The original rolling().apply() requires all window values to be
    # non-null because min_periods=window + 1. Any incomplete or
    # NaN-containing window therefore becomes 50.0 after fillna.
    return result.fillna(50.0)
