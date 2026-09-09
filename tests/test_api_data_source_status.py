from __future__ import annotations

import pandas as pd
from fastapi.testclient import TestClient

import data
from api import main as api_main
from api.data_source_status import build_data_source_status
from market_data import UpstoxMarketDataProvider, UpstoxProviderConfig


def test_data_source_status_defaults_to_yfinance_without_cache(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(data, "CACHE_DIR", tmp_path)

    status = build_data_source_status(" test.ns ", None)

    assert status["symbol"] == "TEST.NS"
    assert status["active_provider"] == "yfinance"
    assert status["cache_available"] is False
    assert status["cache_metadata"] is None
    assert status["stale_cache"] is False
    assert status["diagnostic_only"] is True


def test_data_source_status_reports_stale_cache_metadata(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(data, "CACHE_DIR", tmp_path)
    frame = pd.DataFrame(
        {
            "open": [100.0, 101.0],
            "high": [102.0, 103.0],
            "low": [99.0, 100.0],
            "close": [101.0, 102.0],
            "volume": [1_000_000.0, 1_100_000.0],
        },
        index=pd.date_range("2026-01-01", periods=2, freq="D"),
    )
    data._write_cache_metadata(
        "TEST.NS",
        frame,
        source="stale_cache",
        cache_format=data.CACHE_FORMAT_CSV,
        stale_reason="rate limit during incremental refresh",
    )

    status = build_data_source_status("TEST.NS", None)

    assert status["cache_available"] is True
    assert status["cache_source"] == "stale_cache"
    assert status["cache_format"] == data.CACHE_FORMAT_CSV
    assert status["cache_rows"] == 2
    assert status["stale_cache"] is True
    assert status["stale_reason"] == "rate limit during incremental refresh"
    assert status["cache_metadata"] is not None


def test_data_source_status_reports_upstox_readiness_without_token_value(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(data, "CACHE_DIR", tmp_path)
    monkeypatch.delenv("UPSTOX_TEST_TOKEN", raising=False)
    provider = UpstoxMarketDataProvider(
        UpstoxProviderConfig(
            enabled=True,
            access_token_env="UPSTOX_TEST_TOKEN",
            symbol_map={"TEST.NS": "NSE_EQ|INE000000000"},
        )
    )

    status = build_data_source_status("TEST.NS", provider)

    assert status["active_provider"] == "upstox"
    assert status["upstox_enabled"] is True
    assert status["upstox_token_env"] == "UPSTOX_TEST_TOKEN"
    assert status["upstox_token_present"] is False
    assert status["upstox_symbol_mapped"] is True
    assert "INE000000000" not in str(status["upstox_token_env"])


def test_data_source_status_endpoint_is_read_only(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(data, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(api_main._service, "_market_data_provider", None)
    client = TestClient(api_main.app)

    response = client.get("/api/symbols/test.ns/data-source")

    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "TEST.NS"
    assert body["active_provider"] == "yfinance"
    assert body["cache_available"] is False
    assert body["diagnostic_only"] is True
