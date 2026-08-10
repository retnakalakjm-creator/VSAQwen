from __future__ import annotations

from pathlib import Path

import pandas as pd
import yfinance as yf

from config import CACHE_DIR, DEFAULT_PERIOD, MIN_DAILY_BARS, WEEK_RULE

# ---------------------------------------------------------------------
# Initialize Cache
# ---------------------------------------------------------------------

CACHE_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------
# Download Data
# ---------------------------------------------------------------------

def download_data(symbol: str, refresh: bool = False) -> pd.DataFrame:
    """
    Download daily OHLCV data from Yahoo Finance.

    Parameters
    ----------
    symbol : str
        Yahoo Finance ticker (e.g. IRCTC.NS)

    refresh : bool
        Force download even if cache exists.

    Returns
    -------
    pd.DataFrame
        Daily OHLCV dataframe.
    """

    cache_file = CACHE_DIR / f"{symbol}.csv"

    # -------------------------------------------------------------
    # Load cached copy
    # -------------------------------------------------------------

    if cache_file.exists() and not refresh:
        df = pd.read_csv(
            cache_file,
            index_col=0,
            parse_dates=True,
        )
        return df

    # -------------------------------------------------------------
    # Download
    # -------------------------------------------------------------

    df = yf.download(
        tickers=symbol,
        period=DEFAULT_PERIOD,
        interval="1d",
        auto_adjust=False,
        progress=False,
    )

    if df.empty:
        raise ValueError(f"No data returned for {symbol}")

    # -------------------------------------------------------------
    # Flatten MultiIndex columns (new yfinance versions)
    # -------------------------------------------------------------

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    required = ["Open", "High", "Low", "Close", "Volume"]

    missing = [c for c in required if c not in df.columns]

    if missing:
        raise ValueError(
            f"Missing columns: {missing}\n"
            f"Available columns: {list(df.columns)}"
        )

    # -------------------------------------------------------------
    # Keep only OHLCV
    # -------------------------------------------------------------

    df = df[required].copy()

    # -------------------------------------------------------------
    # Standardize column names
    # -------------------------------------------------------------

    df.columns = [
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]

    # -------------------------------------------------------------
    # Clean index
    # -------------------------------------------------------------

    df.index = pd.to_datetime(df.index)

    df.sort_index(inplace=True)

    df.index.name = "date"

    # -------------------------------------------------------------
    # Remove an incomplete latest bar only
    # -------------------------------------------------------------

    if df.iloc[-1].isna().any():
        latest_date = df.index[-1]
        print(
            f"{symbol}: dropping incomplete latest bar "
            f"{latest_date.date()}"
        )
        df = df.iloc[:-1].copy()

    # -------------------------------------------------------------
    # Validate before saving cache
    # -------------------------------------------------------------

    validate_data(df)

    # -------------------------------------------------------------
    # Save cache
    # -------------------------------------------------------------

    df.to_csv(cache_file)

    return df


# ---------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------

def validate_data(df: pd.DataFrame) -> None:
    """
    Validate downloaded data.
    """

    if len(df) < MIN_DAILY_BARS:
        raise ValueError(
            f"Only {len(df)} daily bars found."
        )

    if df.isna().any().any():
        raise ValueError("Dataset contains missing values.")

    if not df.index.is_monotonic_increasing:
        raise ValueError("Dates are not sorted.")

    required = [
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]

    missing = [c for c in required if c not in df.columns]

    if missing:
        raise ValueError(
            f"Missing required columns: {missing}"
        )


# ---------------------------------------------------------------------
# Daily -> Weekly
# ---------------------------------------------------------------------

def daily_to_weekly(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert daily OHLCV into weekly OHLCV.

    Returns
    -------
    DataFrame

    Columns
    -------
    week_beginning
    open
    high
    low
    close
    volume
    """

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

    # Calculate the first trading day in each week
    week_start = (
        df.groupby(pd.Grouper(freq=WEEK_RULE))
          .apply(lambda x: x.index.min())
    )

    weekly["week_beginning"] = week_start

    weekly = weekly[
        [
            "week_beginning",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]
    ]

    return weekly.reset_index(drop=True)
