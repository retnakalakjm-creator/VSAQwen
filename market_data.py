from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Protocol

import pandas as pd
import yfinance as yf

PROVIDER_YFINANCE = "yfinance"
PROVIDER_UPSTOX = "upstox"


class MarketDataProvider(Protocol):
    """Read-only market-data provider contract for daily OHLCV downloads.

    Providers must return the raw provider payload. The canonical ProVSA
    normalization, validation, caching, weekly resampling, and completed-bar
    policy remain owned by `data.py`.
    """

    name: str

    def download_daily(
        self,
        symbol: str,
        *,
        period: str,
        interval: str,
        auto_adjust: bool,
    ) -> pd.DataFrame:
        """Return raw daily OHLCV bars for one symbol."""


class MarketDataProviderError(RuntimeError):
    """Raised when a configured market-data provider cannot serve data safely."""


class UnsupportedMarketDataProviderError(ValueError):
    """Raised when a provider name is not registered."""


@dataclass(frozen=True, slots=True)
class YFinanceMarketDataProvider:
    """Default read-only provider backed by yfinance."""

    progress: bool = False
    name: str = PROVIDER_YFINANCE

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
            progress=self.progress,
        )


@dataclass(frozen=True, slots=True)
class UpstoxProviderConfig:
    """Configuration placeholder for a future read-only Upstox data adapter.

    Tokens are referenced by environment-variable name only. The config never
    stores token values and this scaffold intentionally does not implement any
    broker/order capability.
    """

    enabled: bool = False
    access_token_env: str = "UPSTOX_ACCESS_TOKEN"
    api_base_url: str | None = None

    def access_token(self) -> str | None:
        """Return a token from the environment, if configured externally."""
        token = os.environ.get(self.access_token_env, "").strip()
        return token or None


@dataclass(frozen=True, slots=True)
class UpstoxMarketDataProvider:
    """Disabled scaffold for a future read-only Upstox daily OHLCV adapter."""

    config: UpstoxProviderConfig = field(default_factory=UpstoxProviderConfig)
    name: str = PROVIDER_UPSTOX

    def download_daily(
        self,
        symbol: str,
        *,
        period: str,
        interval: str,
        auto_adjust: bool,
    ) -> pd.DataFrame:
        if not self.config.enabled:
            raise MarketDataProviderError(
                "Upstox provider scaffold is disabled. Keep MARKET_DATA_PROVIDER "
                "as 'yfinance' until a read-only OHLCV adapter is implemented."
            )
        raise NotImplementedError(
            "Upstox daily OHLCV downloads are not implemented yet. This scaffold "
            "is read-only and must not place, modify, cancel, or size orders."
        )


DEFAULT_MARKET_DATA_PROVIDER = YFinanceMarketDataProvider()


def create_market_data_provider(
    provider_name: str | None = None,
    *,
    upstox_config: UpstoxProviderConfig | None = None,
) -> MarketDataProvider:
    """Create a registered market-data provider by name.

    The default remains yfinance. Upstox is available only as an explicit,
    disabled scaffold so it cannot be selected accidentally.
    """
    normalized = (provider_name or PROVIDER_YFINANCE).strip().lower()
    if normalized in ("", PROVIDER_YFINANCE):
        return DEFAULT_MARKET_DATA_PROVIDER
    if normalized == PROVIDER_UPSTOX:
        return UpstoxMarketDataProvider(config=upstox_config or UpstoxProviderConfig())
    raise UnsupportedMarketDataProviderError(f"Unsupported market data provider: {provider_name!r}")


def resolve_market_data_provider(
    provider: MarketDataProvider | None = None,
) -> MarketDataProvider:
    """Return the supplied provider or the default yfinance adapter."""
    return DEFAULT_MARKET_DATA_PROVIDER if provider is None else provider


__all__ = [
    "DEFAULT_MARKET_DATA_PROVIDER",
    "MarketDataProvider",
    "MarketDataProviderError",
    "PROVIDER_UPSTOX",
    "PROVIDER_YFINANCE",
    "UnsupportedMarketDataProviderError",
    "UpstoxMarketDataProvider",
    "UpstoxProviderConfig",
    "YFinanceMarketDataProvider",
    "create_market_data_provider",
    "resolve_market_data_provider",
]
