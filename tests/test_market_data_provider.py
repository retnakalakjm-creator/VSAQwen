from __future__ import annotations

import pandas as pd

import data
from config import DEFAULT_PERIOD


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
