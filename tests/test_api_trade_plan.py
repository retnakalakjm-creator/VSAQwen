from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from api import main as api_main


def _bar(close: float) -> SimpleNamespace:
    return SimpleNamespace(close=close)


def _swing(type_: str, label: str, price: float) -> SimpleNamespace:
    return SimpleNamespace(
        type=type_,
        label=label,
        price=price,
        week="2026-08-31 00:00:00",
        is_failed=False,
    )


def _analysis() -> SimpleNamespace:
    return SimpleNamespace(
        symbol="TEST.NS",
        timeframe="1W",
        latest_week="2026-08-31 00:00:00",
        bars=[_bar(100.0)],
        structural_swings=[
            _swing("LOW", "HL", 96.0),
            _swing("HIGH", "HH", 112.0),
        ],
        decision_context=SimpleNamespace(
            bias="bullish",
            tradability="wait_for_pullback",
            decision="wait_for_pullback",
            confidence=0.64,
            story=SimpleNamespace(
                confirmation_condition="Fresh demand confirms the plan.",
                invalidation_condition="A breakdown below support invalidates the plan.",
            ),
        ),
    )


def test_trade_plan_endpoint_returns_analysis_only_contract(monkeypatch) -> None:
    captured: list[str] = []

    class FakeService:
        def analyze_symbol(self, symbol: str):
            captured.append(symbol)
            return _analysis()

    monkeypatch.setattr(api_main, "_service", FakeService())

    response = TestClient(api_main.app).get("/api/symbols/test.ns/trade-plan")

    assert response.status_code == 200
    assert captured == ["test.ns"]
    body = response.json()
    assert body["symbol"] == "TEST.NS"
    assert body["timeframe"] == "1W"
    assert body["latest_week"] == "2026-08-31 00:00:00"
    assert body["plan"]["analysis_only"] is True
    assert body["plan"]["posture"] == "Wait for pullback"
    assert body["plan"]["setup_type"] == "Bullish pullback watch"
    assert body["plan"]["support"]["price"] == 96.0
    assert body["plan"]["resistance"]["price"] == 112.0
    assert "position_size" not in body["plan"]
    assert "order" not in body["plan"]
    assert "account" not in body["plan"]


def test_trade_plan_endpoint_rejects_missing_decision_context(monkeypatch) -> None:
    class FakeService:
        def analyze_symbol(self, symbol: str):
            return SimpleNamespace(
                symbol="TEST.NS",
                timeframe="1W",
                latest_week="2026-08-31 00:00:00",
                bars=[_bar(100.0)],
                structural_swings=[],
                decision_context=None,
            )

    monkeypatch.setattr(api_main, "_service", FakeService())

    response = TestClient(api_main.app).get("/api/symbols/test.ns/trade-plan")

    assert response.status_code == 400
    assert "decision context" in response.json()["detail"]
