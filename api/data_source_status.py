from __future__ import annotations

from dataclasses import asdict

import data
from market_data import (
    MarketDataProvider,
    PROVIDER_UPSTOX,
    PROVIDER_YFINANCE,
    UpstoxMarketDataProvider,
)


def _normalize_symbol(symbol: str) -> str:
    normalized = symbol.strip().upper()
    if not normalized:
        raise ValueError("symbol is required")
    return normalized


def build_data_source_status(
    symbol: str,
    provider: MarketDataProvider | None,
) -> dict[str, object]:
    """Return read-only provider/cache diagnostics for one symbol.

    This helper intentionally does not download data, refresh cache files, call
    scanner logic, or expose token values. It only reflects the configured
    runtime provider object and the existing cache metadata sidecar, if present.
    """
    normalized_symbol = _normalize_symbol(symbol)
    active_provider = provider or data.DEFAULT_DATA_PROVIDER
    provider_name = getattr(active_provider, "name", PROVIDER_YFINANCE)
    cache_metadata = data.read_cache_metadata(normalized_symbol)
    cache_payload = None if cache_metadata is None else asdict(cache_metadata)

    upstox_enabled: bool | None = None
    upstox_token_env: str | None = None
    upstox_token_present: bool | None = None
    upstox_symbol_mapped: bool | None = None

    if isinstance(active_provider, UpstoxMarketDataProvider):
        upstox_enabled = active_provider.config.enabled
        upstox_token_env = active_provider.config.access_token_env
        upstox_token_present = active_provider.config.access_token() is not None
        try:
            active_provider.config.instrument_key_for(normalized_symbol)
        except Exception:
            upstox_symbol_mapped = False
        else:
            upstox_symbol_mapped = True

    return {
        "symbol": normalized_symbol,
        "configured_provider": provider_name,
        "active_provider": provider_name,
        "cache_available": cache_metadata is not None,
        "cache_source": None if cache_metadata is None else cache_metadata.source,
        "cache_format": None if cache_metadata is None else cache_metadata.format,
        "cache_rows": None if cache_metadata is None else cache_metadata.rows,
        "cache_first_date": None if cache_metadata is None else cache_metadata.first_date,
        "cache_last_date": None if cache_metadata is None else cache_metadata.last_date,
        "cache_updated_at_utc": None if cache_metadata is None else cache_metadata.updated_at_utc,
        "stale_cache": bool(cache_metadata and cache_metadata.stale_reason),
        "stale_reason": None if cache_metadata is None else cache_metadata.stale_reason,
        "upstox_enabled": upstox_enabled,
        "upstox_token_env": upstox_token_env,
        "upstox_token_present": upstox_token_present,
        "upstox_symbol_mapped": upstox_symbol_mapped,
        "diagnostic_only": True,
        "cache_metadata": cache_payload,
    }
