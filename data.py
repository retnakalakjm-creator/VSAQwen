from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, time as datetime_time, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

import config
from config import CACHE_DIR, DEFAULT_PERIOD, MIN_DAILY_BARS, WEEK_RULE
from market_data import MarketDataProvider
from scanner_state import ScannerState

CACHE_DIR.mkdir(exist_ok=True)

# Historical data is downloaded once. Live scans only refresh a small recent window.
CACHE_MAX_AGE_SECONDS = 15 * 60
INCREMENTAL_PERIOD = "10d"
METRIC_REPLAY_SEED_BARS = config.LOOKBACK_PERIOD * 2
MARKET_TIMEZONE = "Asia/Kolkata"
WEEKLY_BAR_CLOSE_TIME = "15:30"
CACHE_FORMAT_VERSION = 1
CACHE_INTERVAL = "1d"
CACHE_FORMAT_PARQUET = "parquet"
CACHE_FORMAT_CSV = "csv"


class _DataModuleYFinanceProvider:
    """Default provider that preserves the historical `data.yf` test seam."""

    name = "yfinance"

    def download_daily(
        self,
        symbol: str,
        *,
        period: str,
        interval: str,
        auto_adjust: bool,
    ) -> pd.DataFrame:
        return yf.download(
            tickers=symbol,
            period=period,
            interval=interval,
            auto_adjust=auto_adjust,
            progress=False,
        )


DEFAULT_DATA_PROVIDER = _DataModuleYFinanceProvider()


def _resolve_market_data_provider(
    provider: MarketDataProvider | None = None,
) -> MarketDataProvider:
    return DEFAULT_DATA_PROVIDER if provider is None else provider


@dataclass(frozen=True, slots=True)
class CacheMetadata:
    """Sidecar metadata for one cached daily OHLCV dataset."""

    schema_version: int
    symbol: str
    format: str
    source: str
    period: str
    interval: str
    rows: int
    first_date: str | None
    last_date: str | None
    updated_at_utc: str
    stale_reason: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "CacheMetadata":
        return cls(
            schema_version=int(data["schema_version"]),
            symbol=str(data["symbol"]),
            format=str(data["format"]),
            source=str(data["source"]),
            period=str(data["period"]),
            interval=str(data["interval"]),
            rows=int(data["rows"]),
            first_date=(None if data.get("first_date") is None else str(data["first_date"])),
            last_date=(None if data.get("last_date") is None else str(data["last_date"])),
            updated_at_utc=str(data["updated_at_utc"]),
            stale_reason=(None if data.get("stale_reason") is None else str(data["stale_reason"])),
        )


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


def _parquet_engine_available() -> bool:
    """Return whether pandas can actually use a local Parquet engine.

    Some environments can find pyarrow/fastparquet but still fail to load their
    native DLLs because of Windows Application Control or Python-version wheel
    compatibility. Treat any engine-load failure as unavailable and use CSV.
    """
    try:
        from pandas.io.parquet import get_engine

        get_engine("auto")
    except Exception:
        return False
    return True


def _cache_data_path(symbol: str) -> Path:
    return CACHE_DIR / f"{symbol}.parquet"


def _legacy_cache_path(symbol: str) -> Path:
    return CACHE_DIR / f"{symbol}.csv"


def _cache_metadata_path(symbol: str) -> Path:
    return CACHE_DIR / f"{symbol}.metadata.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cache_metadata(
    symbol: str,
    df: pd.DataFrame,
    *,
    source: str,
    cache_format: str,
    stale_reason: str | None = None,
) -> CacheMetadata:
    return CacheMetadata(
        schema_version=CACHE_FORMAT_VERSION,
        symbol=symbol,
        format=cache_format,
        source=source,
        period=DEFAULT_PERIOD,
        interval=CACHE_INTERVAL,
        rows=len(df),
        first_date=None if df.empty else pd.Timestamp(df.index[0]).isoformat(),
        last_date=None if df.empty else pd.Timestamp(df.index[-1]).isoformat(),
        updated_at_utc=_utc_now(),
        stale_reason=stale_reason,
    )


def _write_cache_metadata(
    symbol: str,
    df: pd.DataFrame,
    *,
    source: str,
    cache_format: str,
    stale_reason: str | None = None,
) -> None:
    metadata_path = _cache_metadata_path(symbol)
    temp_path = metadata_path.with_name(f".{metadata_path.name}.tmp")
    metadata = _cache_metadata(
        symbol,
        df,
        source=source,
        cache_format=cache_format,
        stale_reason=stale_reason,
    )
    temp_path.write_text(
        json.dumps(asdict(metadata), ensure_ascii=False, sort_keys=True, indent=2),
        encoding="utf-8",
    )
    temp_path.replace(metadata_path)


def _write_parquet_cache(symbol: str, df: pd.DataFrame, *, source: str) -> Path:
    data_path = _cache_data_path(symbol)
    temp_path = data_path.with_name(f".{data_path.name}.tmp")
    try:
        df.to_parquet(temp_path)
        temp_path.replace(data_path)
        _write_cache_metadata(
            symbol,
            df,
            source=source,
            cache_format=CACHE_FORMAT_PARQUET,
        )
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
    return data_path


def _write_csv_cache(symbol: str, df: pd.DataFrame, *, source: str) -> Path:
    data_path = _legacy_cache_path(symbol)
    temp_path = data_path.with_name(f".{data_path.name}.tmp")
    try:
        df.to_csv(temp_path)
        temp_path.replace(data_path)
        _write_cache_metadata(
            symbol,
            df,
            source=source,
            cache_format=CACHE_FORMAT_CSV,
        )
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
    return data_path


def _write_cached_data(symbol: str, df: pd.DataFrame, *, source: str) -> Path:
    """Write cache in the best available local format.

    Parquet is preferred for speed and compactness. Python environments without
    pyarrow/fastparquet, blocked native DLLs, or unsupported wheels continue to
    work with CSV plus the same metadata sidecar.
    """
    if _parquet_engine_available():
        try:
            return _write_parquet_cache(symbol, df, source=source)
        except Exception:
            # If a Parquet engine is present but blocked at write time, keep the
            # scanner usable by falling back to CSV instead of crashing.
            return _write_csv_cache(symbol, df, source=source)
    return _write_csv_cache(symbol, df, source=source)


def read_cache_metadata(symbol: str) -> CacheMetadata | None:
    """Read cache metadata for diagnostics, if the sidecar exists."""
    metadata_path = _cache_metadata_path(symbol)
    if not metadata_path.exists():
        return None
    return CacheMetadata.from_dict(json.loads(metadata_path.read_text(encoding="utf-8")))


def _read_parquet_cache(symbol: str) -> pd.DataFrame:
    if not _parquet_engine_available():
        raise RuntimeError(
            "Parquet cache exists, but no usable Parquet engine is installed or "
            "the engine DLL is blocked by policy. Delete the .parquet cache so "
            "CSV fallback can be rebuilt, or unblock/install pyarrow/fastparquet."
        )
    df = pd.read_parquet(_cache_data_path(symbol))
    df.index = pd.to_datetime(df.index)
    df.index.name = "date"
    return df


def _read_legacy_csv_cache(symbol: str) -> pd.DataFrame:
    df = pd.read_csv(_legacy_cache_path(symbol), index_col=0, parse_dates=True)
    df.index.name = "date"
    return df


def _read_cached_data(symbol: str) -> tuple[pd.DataFrame, Path, str] | None:
    parquet_path = _cache_data_path(symbol)
    legacy_path = _legacy_cache_path(symbol)

    if parquet_path.exists() and _parquet_engine_available():
        return _read_parquet_cache(symbol), parquet_path, CACHE_FORMAT_PARQUET

    if legacy_path.exists():
        return _read_legacy_csv_cache(symbol), legacy_path, CACHE_FORMAT_CSV

    if parquet_path.exists():
        return _read_parquet_cache(symbol), parquet_path, CACHE_FORMAT_PARQUET

    return None


def _download_history(
    symbol: str,
    provider: MarketDataProvider,
) -> pd.DataFrame:
    return _normalize_daily_data(
        provider.download_daily(
            symbol,
            period=DEFAULT_PERIOD,
            interval=CACHE_INTERVAL,
            auto_adjust=False,
        )
    )


def _refresh_recent(
    symbol: str,
    cached: pd.DataFrame,
    provider: MarketDataProvider,
) -> pd.DataFrame:
    """Refresh only the recent window and merge it into cached history."""
    recent = provider.download_daily(
        symbol,
        period=INCREMENTAL_PERIOD,
        interval=CACHE_INTERVAL,
        auto_adjust=False,
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
    provider: MarketDataProvider | None = None,
) -> pd.DataFrame:
    """Load historical data once and incrementally refresh recent bars."""
    market_data_provider = _resolve_market_data_provider(provider)
    cached_result = _read_cached_data(symbol)

    if cached_result is not None:
        cached, cache_path, cache_format = cached_result
        validate_data(cached)

        # One-time migration path for existing CSV caches when Parquet is usable.
        if cache_format == CACHE_FORMAT_CSV and _parquet_engine_available():
            cache_path = _write_cached_data(symbol, cached, source="csv_migration")
            cache_format = CACHE_FORMAT_PARQUET if cache_path.suffix == ".parquet" else CACHE_FORMAT_CSV

        age = time.time() - cache_path.stat().st_mtime
        if not refresh and age <= cache_max_age:
            return cached

        # Do not re-download years of history during a live scan.
        try:
            merged = _refresh_recent(symbol, cached, market_data_provider)
            validate_data(merged)
            _write_cached_data(symbol, merged, source="incremental_refresh")
            return merged
        except Exception as exc:
            # Preserve a usable cache if the live refresh fails, but record why.
            _write_cache_metadata(
                symbol,
                cached,
                source="stale_cache",
                cache_format=cache_format,
                stale_reason=str(exc),
            )
            return cached

    # First use only: build the historical baseline.
    df = _download_history(symbol, market_data_provider)
    validate_data(df)
    _write_cached_data(symbol, df, source="historical_download")
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


def _local_timestamp(value: pd.Timestamp | str | None) -> pd.Timestamp:
    if value is None:
        return pd.Timestamp.now(tz=MARKET_TIMEZONE)

    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        return timestamp.tz_localize(MARKET_TIMEZONE)
    return timestamp.tz_convert(MARKET_TIMEZONE)


def _parse_market_close_time(value: str) -> datetime_time:
    parts = value.split(":")
    if len(parts) not in (2, 3):
        raise ValueError("market_close_time must use HH:MM or HH:MM:SS format")

    try:
        hour, minute = int(parts[0]), int(parts[1])
        second = int(parts[2]) if len(parts) == 3 else 0
        return datetime_time(hour=hour, minute=minute, second=second)
    except ValueError as exc:
        raise ValueError("market_close_time must use HH:MM or HH:MM:SS format") from exc


def completed_weekly_only(
    weekly: pd.DataFrame,
    *,
    now: pd.Timestamp | str | None = None,
    market_close_time: str = WEEKLY_BAR_CLOSE_TIME,
) -> pd.DataFrame:
    """Return weekly bars that are known to be complete.

    `daily_to_weekly` can produce a partial current-week bar during live scans.
    Weekly VSA signals should only evaluate a bar after the exchange close of
    that bar's weekly period.
    """
    if weekly.empty:
        return weekly
    if "week_beginning" not in weekly.columns:
        raise ValueError("weekly data must contain week_beginning")

    current = _local_timestamp(now)
    last_week_beginning = pd.Timestamp(weekly["week_beginning"].iloc[-1])
    week_end_date = last_week_beginning.to_period(WEEK_RULE).end_time.normalize()
    close_time = _parse_market_close_time(market_close_time)
    week_close = pd.Timestamp.combine(week_end_date.date(), close_time).tz_localize(
        MARKET_TIMEZONE
    )

    if current <= week_close:
        return weekly.iloc[:-1].copy()

    return weekly


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
