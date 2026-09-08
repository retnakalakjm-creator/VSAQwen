from __future__ import annotations

import pandas as pd

from api import main as api_main
import api.service as service_module
from api.service import ProVSAService
from market_data import PROVIDER_UPSTOX, UpstoxMarketDataProvider, UpstoxProviderConfig


class FakeMarketDataProvider:
    name = "fake-runtime-provider"

    def download_daily(
        self,
        symbol: str,
        *,
        period: str,
        interval: str,
        auto_adjust: bool,
    ) -> pd.DataFrame:
        raise AssertionError("service test should not call provider directly")


def _daily_frame() -> pd.DataFrame:
    index = pd.bdate_range(start="2026-08-24", periods=10)
    return pd.DataFrame(
        {
            "open": range(100, 110),
            "high": range(101, 111),
            "low": range(99, 109),
            "close": range(100, 110),
            "volume": range(1000, 1010),
        },
        index=index,
    )


def test_api_service_uses_legacy_default_download_path_without_provider(monkeypatch) -> None:
    calls: list[str] = []

    def fake_download_data(symbol: str) -> pd.DataFrame:
        calls.append(symbol)
        return _daily_frame()

    monkeypatch.setattr(service_module, "download_data", fake_download_data)

    weekly = ProVSAService(persist_decision_context=False)._completed_weekly_for_symbol(
        "TEST.NS"
    )

    assert calls == ["TEST.NS"]
    assert not weekly.empty


def test_api_service_forwards_configured_provider_to_download_data(monkeypatch) -> None:
    provider = FakeMarketDataProvider()
    calls: list[dict[str, object]] = []

    def fake_download_data(symbol: str, *, provider=None) -> pd.DataFrame:
        calls.append({"symbol": symbol, "provider": provider})
        return _daily_frame()

    monkeypatch.setattr(service_module, "download_data", fake_download_data)

    weekly = ProVSAService(
        persist_decision_context=False,
        market_data_provider=provider,
    )._completed_weekly_for_symbol("TEST.NS")

    assert calls == [{"symbol": "TEST.NS", "provider": provider}]
    assert not weekly.empty


def test_api_create_service_uses_env_provider_factory(monkeypatch) -> None:
    provider = UpstoxMarketDataProvider(
        UpstoxProviderConfig(enabled=False),
    )

    monkeypatch.setattr(
        api_main,
        "create_market_data_provider_from_env",
        lambda: provider,
    )

    service = api_main.create_service()

    assert service._market_data_provider is provider
    assert service._market_data_provider.name == PROVIDER_UPSTOX
