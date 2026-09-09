from __future__ import annotations

from fastapi.testclient import TestClient
import pandas as pd

from api import main as api_main


def _weekly_frame(rows: int = 24) -> pd.DataFrame:
    weeks = pd.date_range("2026-03-16", periods=rows, freq="W-MON")
    records = []
    for index, week in enumerate(weeks):
        open_ = 100.0 + index
        close = open_ + (3.0 if index % 2 == 0 else -1.0)
        high = max(open_, close) + 2.0
        low = min(open_, close) - 2.0
        records.append(
            {
                "week_beginning": week,
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": 1_000_000.0 + index * 10_000.0,
            }
        )
    return pd.DataFrame(records)


def test_weekly_bar_readings_endpoint_returns_week_and_professional_reading(monkeypatch) -> None:
    captured: list[str] = []

    class FakeService:
        @staticmethod
        def _normalize_symbol(symbol: str) -> str:
            captured.append(symbol)
            return symbol.strip().upper()

        @staticmethod
        def _completed_weekly_for_symbol(symbol: str) -> pd.DataFrame:
            assert symbol == "TEST.NS"
            return _weekly_frame()

    monkeypatch.setattr(api_main, "_service", FakeService())

    response = TestClient(api_main.app).get(
        "/api/symbols/test.ns/weekly-bar-readings?lookback=3"
    )

    assert response.status_code == 200
    assert captured == ["test.ns"]
    body = response.json()
    assert body["symbol"] == "TEST.NS"
    assert body["timeframe"] == "1W"
    assert body["lookback"] == 3
    assert body["latest_week"] == "2026-08-24 00:00:00"
    assert len(body["readings"]) == 3
    assert set(body["readings"][0]) == {"week", "professional_reading"}
    assert "professional_reading" in body["readings"][0]
    assert "week_ending" not in body["readings"][0]


def test_weekly_bar_readings_endpoint_rejects_invalid_lookback() -> None:
    response = TestClient(api_main.app).get(
        "/api/symbols/test.ns/weekly-bar-readings?lookback=0"
    )

    assert response.status_code == 422
