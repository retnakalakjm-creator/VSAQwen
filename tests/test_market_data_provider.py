from __future__ import annotations

import json

import pandas as pd
import pytest

import data
from config import DEFAULT_PERIOD
from market_data import (
    DEFAULT_UPSTOX_ACCESS_TOKEN_ENV,
    DEFAULT_UPSTOX_API_BASE_URL,
    MARKET_DATA_PROVIDER_ENV,
    PROVIDER_UPSTOX,
    PROVIDER_YFINANCE,
    UPSTOX_ACCESS_TOKEN_ENV_VAR_ENV,
    UPSTOX_API_BASE_URL_ENV,
    UPSTOX_ENABLED_ENV,
    UPSTOX_SYMBOL_MAP_ENV,
    MarketDataProviderError,
    UpstoxMarketDataProvider,
    UpstoxProviderConfig,
    YFinanceMarketDataProvider,
    create_market_data_provider,
    create_market_data_provider_from_env,
    resolve_market_data_provider,
)


class FakeMarketDataProvider:
    name = "fake"

    def __init__(self, frames: list[pd.DataFrame]) -> None:
        self._frames = list(frames)
        self.calls: list[dict[str, object]] = []

    def download_daily(
        self,
        symbol: str,
        *,
        period: str,
        interval: str,
        auto_adjust: bool,
    ) -> pd.DataFrame:
        self.calls.append(
            {
                "symbol": symbol,
                "period": period,
                "interval": interval,
                "auto_adjust": auto_adjust,
            }
        )
        if not self._frames:
            raise AssertionError("Fake provider was called more times than expected")
        return self._frames.pop(0)


class FakeHttpGet:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.calls: list[dict[str, object]] = []

    def __call__(self, url: str, headers: dict[str, str]) -> bytes:
        self.calls.append({"url": url, "headers": headers})
        return json.dumps(self.payload).encode("utf-8")


def _raw_daily_frame(
    start: str,
    periods: int,
    *,
    base: float = 100.0,
) -> pd.DataFrame:
    index = pd.date_range(start, periods=periods, freq="D")
    values = [base + index for index in range(periods)]
    return pd.DataFrame(
        {
            "Open": values,
            "High": [value + 2.0 for value in values],
            "Low": [value - 2.0 for value in values],
            "Close": [value + 1.0 for value in values],
            "Volume": [1_000_000 + index for index in range(periods)],
        },
        index=index,
    )


def test_download_data_uses_injected_provider_for_initial_history(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(data, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(data, "_parquet_engine_available", lambda: False)
    provider = FakeMarketDataProvider(
        [_raw_daily_frame("2025-01-01", data.MIN_DAILY_BARS + 5)]
    )

    result = data.download_data("TEST.NS", provider=provider)

    assert provider.calls == [
        {
            "symbol": "TEST.NS",
            "period": DEFAULT_PERIOD,
            "interval": data.CACHE_INTERVAL,
            "auto_adjust": False,
        }
    ]
    assert list(result.columns) == ["open", "high", "low", "close", "volume"]
    assert result.index.name == "date"
    assert result.index.is_monotonic_increasing

    metadata = data.read_cache_metadata("TEST.NS")
    assert metadata is not None
    assert metadata.source == "historical_download"
    assert metadata.format == data.CACHE_FORMAT_CSV


def test_download_data_uses_injected_provider_for_incremental_refresh(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(data, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(data, "_parquet_engine_available", lambda: False)
    initial = _raw_daily_frame("2025-01-01", data.MIN_DAILY_BARS + 5)
    recent = _raw_daily_frame(
        str(initial.index[-2].date()),
        4,
        base=250.0,
    )
    provider = FakeMarketDataProvider([initial, recent])

    data.download_data("TEST.NS", provider=provider)
    refreshed = data.download_data("TEST.NS", refresh=True, provider=provider)

    assert provider.calls[1] == {
        "symbol": "TEST.NS",
        "period": data.INCREMENTAL_PERIOD,
        "interval": data.CACHE_INTERVAL,
        "auto_adjust": False,
    }
    assert refreshed.index.is_unique
    assert refreshed.index[-1] == recent.index[-1]
    assert refreshed.loc[recent.index[-1], "close"] == recent.iloc[-1]["Close"]

    metadata = data.read_cache_metadata("TEST.NS")
    assert metadata is not None
    assert metadata.source == "incremental_refresh"
    assert metadata.format == data.CACHE_FORMAT_CSV


def test_default_provider_remains_yfinance() -> None:
    provider = resolve_market_data_provider()

    assert isinstance(provider, YFinanceMarketDataProvider)
    assert provider.name == PROVIDER_YFINANCE


def test_create_provider_keeps_yfinance_as_default() -> None:
    assert create_market_data_provider().name == PROVIDER_YFINANCE
    assert create_market_data_provider(" yfinance ").name == PROVIDER_YFINANCE


def test_env_provider_resolver_keeps_yfinance_as_default() -> None:
    assert create_market_data_provider_from_env({}).name == PROVIDER_YFINANCE
    assert create_market_data_provider_from_env({MARKET_DATA_PROVIDER_ENV: ""}).name == (
        PROVIDER_YFINANCE
    )
    assert create_market_data_provider_from_env(
        {MARKET_DATA_PROVIDER_ENV: " YFINANCE "}
    ).name == PROVIDER_YFINANCE


def test_upstox_provider_is_explicit_and_disabled_by_default() -> None:
    provider = create_market_data_provider(PROVIDER_UPSTOX)

    assert isinstance(provider, UpstoxMarketDataProvider)
    assert provider.name == PROVIDER_UPSTOX
    assert provider.config.enabled is False

    with pytest.raises(MarketDataProviderError, match="disabled"):
        provider.download_daily(
            "TEST.NS",
            period="5y",
            interval="1d",
            auto_adjust=False,
        )


def test_env_provider_resolver_selects_upstox_only_when_explicit() -> None:
    provider = create_market_data_provider_from_env(
        {
            MARKET_DATA_PROVIDER_ENV: " upstox ",
            UPSTOX_ACCESS_TOKEN_ENV_VAR_ENV: "PROVSA_TEST_UPSTOX_TOKEN",
            UPSTOX_API_BASE_URL_ENV: "https://example.test/upstox",
            UPSTOX_SYMBOL_MAP_ENV: "TEST.NS=NSE_EQ|INE000000000",
        }
    )

    assert isinstance(provider, UpstoxMarketDataProvider)
    assert provider.name == PROVIDER_UPSTOX
    assert provider.config.enabled is False
    assert provider.config.access_token_env == "PROVSA_TEST_UPSTOX_TOKEN"
    assert provider.config.api_base_url == "https://example.test/upstox"
    assert provider.config.symbol_map["TEST.NS"] == "NSE_EQ|INE000000000"

    with pytest.raises(MarketDataProviderError, match="disabled"):
        provider.download_daily(
            "TEST.NS",
            period="5y",
            interval="1d",
            auto_adjust=False,
        )


def test_env_provider_resolver_can_enable_upstox_without_io_when_token_missing() -> None:
    provider = create_market_data_provider_from_env(
        {
            MARKET_DATA_PROVIDER_ENV: PROVIDER_UPSTOX,
            UPSTOX_ENABLED_ENV: "true",
        }
    )

    assert isinstance(provider, UpstoxMarketDataProvider)
    assert provider.config.enabled is True
    assert provider.config.access_token_env == DEFAULT_UPSTOX_ACCESS_TOKEN_ENV

    with pytest.raises(MarketDataProviderError, match="access token is missing"):
        provider.download_daily(
            "NSE_EQ|INE000000000",
            period="5y",
            interval="1d",
            auto_adjust=False,
        )


def test_upstox_provider_downloads_daily_ohlcv_read_only(monkeypatch) -> None:
    monkeypatch.setenv("PROVSA_TEST_UPSTOX_TOKEN", "token-from-env")
    http_get = FakeHttpGet(
        {
            "status": "success",
            "data": {
                "candles": [
                    ["2025-01-03T00:00:00+05:30", 103.0, 108.0, 101.0, 106.0, 3000],
                    ["2025-01-02T00:00:00+05:30", 100.0, 105.0, 99.0, 104.0, 2000],
                ]
            },
        }
    )
    provider = UpstoxMarketDataProvider(
        UpstoxProviderConfig(
            enabled=True,
            access_token_env="PROVSA_TEST_UPSTOX_TOKEN",
            api_base_url="https://example.test",
            http_get=http_get,
        )
    )

    result = provider.download_daily(
        "NSE_EQ|INE000000000",
        period="10d",
        interval="1d",
        auto_adjust=False,
    )

    assert list(result.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert result.index.is_monotonic_increasing
    assert result.iloc[0]["Close"] == 104.0
    assert result.iloc[1]["Volume"] == 3000.0
    assert len(http_get.calls) == 1
    call = http_get.calls[0]
    assert call["url"].startswith(
        "https://example.test/v3/historical-candle/NSE_EQ%7CINE000000000/days/1/"
    )
    assert call["headers"]["Authorization"] == "Bearer token-from-env"


def test_upstox_provider_supports_symbol_map(monkeypatch) -> None:
    monkeypatch.setenv("PROVSA_TEST_UPSTOX_TOKEN", "token-from-env")
    http_get = FakeHttpGet({"status": "success", "data": {"candles": []}})
    provider = UpstoxMarketDataProvider(
        UpstoxProviderConfig(
            enabled=True,
            access_token_env="PROVSA_TEST_UPSTOX_TOKEN",
            symbol_map={"TEST.NS": "NSE_EQ|INE000000000"},
            http_get=http_get,
        )
    )

    result = provider.download_daily(
        "test.ns",
        period="1d",
        interval="1d",
        auto_adjust=False,
    )

    assert result.empty
    assert http_get.calls[0]["url"].startswith(
        f"{DEFAULT_UPSTOX_API_BASE_URL}/v3/historical-candle/NSE_EQ%7CINE000000000/days/1/"
    )


def test_upstox_provider_requires_explicit_instrument_key_or_mapping(monkeypatch) -> None:
    monkeypatch.setenv("PROVSA_TEST_UPSTOX_TOKEN", "token-from-env")
    provider = UpstoxMarketDataProvider(
        UpstoxProviderConfig(enabled=True, access_token_env="PROVSA_TEST_UPSTOX_TOKEN")
    )

    with pytest.raises(MarketDataProviderError, match="requires an explicit instrument key"):
        provider.download_daily(
            "TEST.NS",
            period="5y",
            interval="1d",
            auto_adjust=False,
        )


def test_upstox_provider_rejects_non_daily_or_adjusted_requests(monkeypatch) -> None:
    monkeypatch.setenv("PROVSA_TEST_UPSTOX_TOKEN", "token-from-env")
    provider = UpstoxMarketDataProvider(
        UpstoxProviderConfig(enabled=True, access_token_env="PROVSA_TEST_UPSTOX_TOKEN")
    )

    with pytest.raises(MarketDataProviderError, match="daily candles only"):
        provider.download_daily(
            "NSE_EQ|INE000000000",
            period="5y",
            interval="1h",
            auto_adjust=False,
        )

    with pytest.raises(MarketDataProviderError, match="raw data only"):
        provider.download_daily(
            "NSE_EQ|INE000000000",
            period="5y",
            interval="1d",
            auto_adjust=True,
        )


def test_env_provider_resolver_rejects_invalid_symbol_map() -> None:
    with pytest.raises(ValueError, match=UPSTOX_SYMBOL_MAP_ENV):
        create_market_data_provider_from_env(
            {
                MARKET_DATA_PROVIDER_ENV: PROVIDER_UPSTOX,
                UPSTOX_SYMBOL_MAP_ENV: "BROKEN_ENTRY",
            }
        )


def test_env_provider_resolver_rejects_invalid_bool() -> None:
    with pytest.raises(ValueError, match=UPSTOX_ENABLED_ENV):
        create_market_data_provider_from_env(
            {
                MARKET_DATA_PROVIDER_ENV: PROVIDER_UPSTOX,
                UPSTOX_ENABLED_ENV: "sometimes",
            }
        )


def test_env_provider_resolver_rejects_unknown_provider_name() -> None:
    with pytest.raises(ValueError, match="Unsupported market data provider"):
        create_market_data_provider_from_env({MARKET_DATA_PROVIDER_ENV: "broker"})


def test_upstox_config_references_env_token_without_storing_secret(monkeypatch) -> None:
    monkeypatch.setenv("PROVSA_TEST_UPSTOX_TOKEN", "  token-from-env  ")
    config = UpstoxProviderConfig(access_token_env="PROVSA_TEST_UPSTOX_TOKEN")

    assert config.access_token_env == "PROVSA_TEST_UPSTOX_TOKEN"
    assert config.access_token() == "token-from-env"
    assert "token-from-env" not in repr(config)


def test_unknown_provider_name_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported market data provider"):
        create_market_data_provider("broker")
