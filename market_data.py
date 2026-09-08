from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import pandas as pd
import yfinance as yf


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


@dataclass(frozen=True, slots=True)
class YFinanceMarketDataProvider:
    """Default read-only provider backed by yfinance."""

    progress: bool = False
    name: str = "yfinance"

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


DEFAULT_MARKET_DATA_PROVIDER = YFinanceMarketDataProvider()


def resolve_market_data_provider(
    provider: MarketDataProvider | None = None,
) -> MarketDataProvider:
    """Return the supplied provider or the default yfinance adapter."""
    return DEFAULT_MARKET_DATA_PROVIDER if provider is None else provider


__all__ = [
    "DEFAULT_MARKET_DATA_PROVIDER",
    "MarketDataProvider",
    "YFinanceMarketDataProvider",
    "resolve_market_data_provider",
]
