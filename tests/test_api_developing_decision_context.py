from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient
import pandas as pd
import pytest

from api import main as api_main
import api.service as service_module
from api.service import ProVSAService
from decision_context import DecisionContextStore, DecisionMode, build_decision_context
from decision_journal import DecisionJournalStore


DEVELOPING_WEEK = "2026-09-07 00:00:00"


def _weekly_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "week_beginning": pd.to_datetime(["2026-08-31", "2026-09-07"]),
            "open": [100.0, 110.0],
            "high": [112.0, 118.0],
            "low": [96.0, 108.0],
            "close": [109.0, 116.0],
            "volume": [1_000_000.0, 1_250_000.0],
        }
    )


def _fake_candidate(*, bar_index: int = 1, week: str = DEVELOPING_WEEK) -> SimpleNamespace:
    trend = SimpleNamespace(
        direction=SimpleNamespace(value="SIDEWAYS"),
        state=SimpleNamespace(value="DEVELOPING"),
        strength=0.0,
        confidence=0.0,
        swing_count=0,
        hh_count=0,
        hl_count=0,
        lh_count=0,
        ll_count=0,
        swings=(),
        structural_swings=(),
        structure=SimpleNamespace(structural_swings=()),
    )
    return SimpleNamespace(
        evidence=SimpleNamespace(
            context=SimpleNamespace(trend=trend),
            evidence=(),
        ),
        campaign_evidence=(),
        qualifying_evidence=(),
        scoring_evidence=(),
        target_bar_evidence=(),
        qualification=SimpleNamespace(value="UNQUALIFIED"),
        qualification_result=SimpleNamespace(
            evidence_codes=(),
            evidence_bar_indices=(),
        ),
        actionable=False,
        reason="Developing preview only.",
        signal_bar_anomaly=False,
        signal_bar_anomaly_reason=None,
        bar_index=bar_index,
        week=week,
        execution_pending=False,
        professional=SimpleNamespace(
            trend=0.0,
            supply=0.0,
            demand=0.0,
            effort=0.0,
            strength=0.0,
            weakness=0.0,
            confidence=0.0,
        ),
        net_strength=0.0,
        net_pressure=0.0,
        confidence=0.0,
    )


class _FakeMetricsEngine:
    def calculate(self, weekly: pd.DataFrame) -> pd.DataFrame:
        return weekly.copy()


class _FakeDevelopingScanner:
    def __init__(self, calls: list[dict[str, int]]) -> None:
        self._calls = calls

    def scan_to_index(self, metrics: pd.DataFrame, target_index: int):
        self._calls.append({"rows": len(metrics), "target_index": target_index})
        return _fake_candidate(
            bar_index=target_index,
            week=str(metrics.iloc[target_index]["week_beginning"]),
        )


def _developing_context_payload() -> dict[str, object]:
    return build_decision_context(
        _fake_candidate(),
        symbol="TEST.NS",
        mode=DecisionMode.DEVELOPING,
        evaluated_at_utc="2026-09-09T04:30:00+00:00",
    ).to_dict()


def test_developing_context_is_preview_only_and_uses_latest_available_week(
    monkeypatch,
    tmp_path,
) -> None:
    store = DecisionContextStore(tmp_path / "decision_context")
    journal_store = DecisionJournalStore(tmp_path / "decision_journal")
    scanner_calls: list[dict[str, int]] = []

    monkeypatch.setattr(service_module, "download_data", lambda symbol: pd.DataFrame())
    monkeypatch.setattr(service_module, "daily_to_weekly", lambda daily: _weekly_frame())

    def fail_completed_weekly_only(*args, **kwargs):
        raise AssertionError("developing preview must not drop the current partial week")

    def fail_production_scan(*args, **kwargs):
        raise AssertionError("developing preview must not use production scanner state")

    monkeypatch.setattr(service_module, "completed_weekly_only", fail_completed_weekly_only)
    monkeypatch.setattr(service_module, "scan_latest_candidate_production", fail_production_scan)
    monkeypatch.setattr(service_module, "MetricsEngine", lambda: _FakeMetricsEngine())
    monkeypatch.setattr(
        service_module,
        "ScannerEngine",
        lambda: _FakeDevelopingScanner(scanner_calls),
    )

    result = ProVSAService(
        decision_context_store=store,
        decision_journal_store=journal_store,
        persist_decision_context=True,
        persist_decision_journal=True,
    ).developing_decision_context_for_symbol(" test.ns ")

    assert result.symbol == "TEST.NS"
    assert result.mode == "developing"
    assert result.latest_week == DEVELOPING_WEEK
    assert scanner_calls == [{"rows": 2, "target_index": 1}]

    with pytest.raises(FileNotFoundError):
        store.load("TEST.NS", "1W")
    assert list(journal_store.load_all("TEST.NS", "1W")) == []


def test_developing_context_endpoint_returns_labeled_preview(monkeypatch) -> None:
    captured: list[str] = []
    payload = _developing_context_payload()

    class FakeService:
        def developing_decision_context_for_symbol(self, symbol: str):
            captured.append(symbol)
            return payload

    monkeypatch.setattr(api_main, "_service", FakeService())

    response = TestClient(api_main.app).get(
        "/api/symbols/test.ns/decision-context/developing"
    )

    assert response.status_code == 200
    assert captured == ["test.ns"]
    body = response.json()
    assert body["symbol"] == "TEST.NS"
    assert body["mode"] == "developing"
    assert body["latest_week"] == DEVELOPING_WEEK
