from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
import yfinance as yf

import config
from config import CACHE_DIR, DEFAULT_PERIOD, MIN_DAILY_BARS, WEEK_RULE
from scanner_state import ScannerState

CACHE_DIR.mkdir(exist_ok=True)

# Historical data is downloaded once. Live scans only refresh a small recent window.
CACHE_MAX_AGE_SECONDS = 15 * 60
INCREMENTAL_PERIOD = "10d"
METRIC_REPLAY_SEED_BARS = config.LOOKBACK_PERIOD * 2


def _normalize_daily_data(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        raise ValueError("No data returned")

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    required = ["Open", "High", "Low", "Close", "Volume"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(
            f"Missing columns: {missing}\n"
            f"Available columns: {list(df.columns)}"
        )

    df = df[required].copy()
    df.columns = ["open", "high", "low", "close", "volume"]
    df.index = pd.to_datetime(df.index)
    df.sort_index(inplace=True)
    df.index.name = "date"

    # Ignore the currently forming daily bar.
    if not df.empty and df.iloc[-1].isna().any():
        df = df.iloc[:-1].copy()

    return df


def _download_history(symbol: str) -> pd.DataFrame:
    return _normalize_daily_data(
        yf.download(
            tickers=symbol,
            period=DEFAULT_PERIOD,
            interval="1d",
            auto_adjust=False,
            progress=False,
        )
    )


def _refresh_recent(symbol: str, cached: pd.DataFrame) -> pd.DataFrame:
    """Refresh only the recent window and merge it into cached history."""
    recent = yf.download(
        tickers=symbol,
        period=INCREMENTAL_PERIOD,
        interval="1d",
        auto_adjust=False,
        progress=False,
    )
    if recent.empty:
        return cached

    recent = _normalize_daily_data(recent)
    merged = pd.concat([cached, recent])
    merged = merged[~merged.index.duplicated(keep="last")]
    merged.sort_index(inplace=True)
    return merged


def download_data(
    symbol: str,
    refresh: bool = False,
    cache_max_age: int = CACHE_MAX_AGE_SECONDS,
) -> pd.DataFrame:
    """Load historical data once and incrementally refresh recent bars."""
    cache_file = CACHE_DIR / f"{symbol}.csv"

    if cache_file.exists():
        cached = pd.read_csv(cache_file, index_col=0, parse_dates=True)
        cached.index.name = "date"

        age = time.time() - cache_file.stat().st_mtime
        if not refresh and age <= cache_max_age:
            validate_data(cached)
            return cached

        # Do not re-download years of history during a live scan.
        try:
            merged = _refresh_recent(symbol, cached)
            validate_data(merged)
            merged.to_csv(cache_file)
            return merged
        except Exception:
            # Preserve a usable cache if the live refresh fails.
            validate_data(cached)
            return cached

    # First use only: build the historical baseline.
    df = _download_history(symbol)
    validate_data(df)
    df.to_csv(cache_file)
    return df


def validate_data(df: pd.DataFrame) -> None:
    if len(df) < MIN_DAILY_BARS:
        raise ValueError(f"Only {len(df)} daily bars found.")
    if df.isna().any().any():
        raise ValueError("Dataset contains missing values.")
    if not df.index.is_monotonic_increasing:
        raise ValueError("Dates are not sorted.")
    required = ["open", "high", "low", "close", "volume"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")


def daily_to_weekly(df: pd.DataFrame) -> pd.DataFrame:
    """Convert daily OHLCV into weekly OHLCV."""
    weekly = (
        df.assign(week_beginning=df.index)
        .resample(WEEK_RULE)
        .agg(
            {
                "week_beginning": "first",
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }
        )
        .dropna()
    )

    return weekly[
        ["week_beginning", "open", "high", "low", "close", "volume"]
    ].reset_index(drop=True)


def incremental_replay_window(
    weekly: pd.DataFrame,
    state: ScannerState,
    *,
    metric_seed_bars: int = METRIC_REPLAY_SEED_BARS,
) -> pd.DataFrame:
    """Return the smallest safe weekly replay window for a persisted state.

    Every persisted state identity must remain available, and enough raw bars
    must precede the earliest required identity to reproduce rolling metrics.
    """
    if weekly.empty:
        raise ValueError("weekly data cannot be empty")
    if metric_seed_bars < 0:
        raise ValueError("metric_seed_bars cannot be negative")
    if "week_beginning" not in weekly.columns:
        raise ValueError("weekly data must contain week_beginning")
    if state.candidate is None:
        raise ValueError("ScannerState must contain an active candidate")

    keys = [state.last_closed_bar, state.candidate.bar_key]
    keys.extend(swing.pivot_bar_key for swing in state.confirmed_swings)
    keys.extend(swing.confirmation_bar_key for swing in state.confirmed_swings)

    key_to_index: dict[str, int] = {}
    for index, value in enumerate(weekly["week_beginning"]):
        key = str(value)
        if key in key_to_index:
            raise ValueError(f"Duplicate weekly bar identity: {key!r}")
        key_to_index[key] = index

    missing = [key for key in keys if key not in key_to_index]
    if missing:
        raise ValueError(f"State identities not present in weekly data: {missing}")

    earliest_required = min(key_to_index[key] for key in keys)
    replay_start = max(0, earliest_required - metric_seed_bars)
    return weekly.iloc[replay_start:].reset_index(drop=True)
