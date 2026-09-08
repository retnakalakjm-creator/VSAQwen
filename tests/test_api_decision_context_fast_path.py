from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient
import pandas as pd

from decision_context import DecisionContextStore, build_decision_context
from api import main as api_main
import api.service as service_module
from api.service import ProVSAService


LATEST_WEEK = "2026-08-31 00:00:00"
OLD_WEEK = "2026-08-24 00:00:00"


def _weekly_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "week_beginning": pd.to_datetime(["2026-08-24", "2026-08-31"]),
            "open": [100.0, 110.0],
            "high": [112.0, 118.0],
            "low": [96.0, 108.0],
            "close": [109.0, 116.0],
            "volume": [1_000_000.0, 1_250_000.0],
        }
    )


def _fake_candidate(*, bar_index: int = 1, week: str = LATEST_WEEK) -> SimpleNamespace:
    trend = SimpleNamespace(
        direction=SimpleNamespace(value="SIDEWAYS"),
        state=SimpleNamespace(value="UNKNOWN"),
        strength=0.0,
        confidence=0.0,
        swing_count=0,
        hh_count=0,
        hl_count=0,
        lh_count=0,
        ll_count=0,
        swings=(),
        structural_swings=(),
    )
    return SimpleNamespace(
        evidence=SimpleNamespace(
            context=SimpleNamespace(trend=trend),
            evidence=(),
        ),
        qualification=SimpleNamespace(value="UNQUALIFIED"),
        qualification_result=SimpleNamespace(
            evidence_codes=(),
            evidence_bar_indices=(),
        ),
        actionable=False,
        reason="No actionable candidate.",
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


def _patch_weekly_pipeline(monkeypatch) -> None:
    monkeypatch.setattr(service_module, "download_data", lambda symbol: pd.DataFrame())
    monkeypatch.setattr(service_module, "daily_to_weekly", lambda daily: _weekly_frame())
    monkeypatch.setattr(service_module, "completed_weekly_only", lambda weekly: weekly)


def _current_decision_context_payload() -> dict[str, object]:
    context = build_decision_context(
        _fake_candidate(),
        symbol="TEST.NS",
        evaluated_at_utc="2026-09-08T10:00:00+00:00",
    )
    return context.to_dict()


class _FakeMetricsEngine:
    def calculate(self, weekly: pd.DataFrame) -> pd.DataFrame:
        return weekly.copy()


def test_decision_context_fast_path_returns_current_cached_context_without_scanning(
    monkeypatch,
    tmp_path,
) -> None:
    store = DecisionContextStore(tmp_path / "decision_context")
    cached = build_decision_context(
        _fake_candidate(),
        symbol="TEST.NS",
        evaluated_at_utc="2026-09-08T10:00:00+00:00",
    )
    store.save(cached)
    _patch_weekly_pipeline(monkeypatch)

    def fail_if_scanned(*args, **kwargs):
        raise AssertionError("fresh cached decision context should avoid scanning")

    monkeypatch.setattr(
        service_module,
        "scan_latest_candidate_production",
        fail_if_scanned,
    )

    result = ProVSAService(decision_context_store=store).decision_context_for_symbol(
        " test.ns "
    )

    assert result.symbol == "TEST.NS"
    assert result.latest_week == LATEST_WEEK
    assert result.evaluated_at_utc == "2026-09-08T10:00:00+00:00"


def test_decision_context_fast_path_refreshes_stale_cached_context(
    monkeypatch,
    tmp_path,
) -> None:
    store = DecisionContextStore(tmp_path / "decision_context")
    stale = build_decision_context(
        _fake_candidate(bar_index=0, week=OLD_WEEK),
        symbol="TEST.NS",
        evaluated_at_utc="2026-09-01T10:00:00+00:00",
    )
    store.save(stale)
    _patch_weekly_pipeline(monkeypatch)
    monkeypatch.setattr(service_module, "MetricsEngine", lambda: _FakeMetricsEngine())

    production_calls: list[dict[str, object]] = []

    def fake_scan_latest_candidate_production(
        metrics: pd.DataFrame,
        *,
        symbol: str,
        timeframe: str,
        state_store,
        state_root,
        allow_full_replay_fallback: bool,
    ):
        production_calls.append(
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "rows": len(metrics),
                "allow_full_replay_fallback": allow_full_replay_fallback,
            }
        )
        return _fake_candidate()

    monkeypatch.setattr(
        service_module,
        "scan_latest_candidate_production",
        fake_scan_latest_candidate_production,
    )

    result = ProVSAService(decision_context_store=store).decision_context_for_symbol(
        "TEST.NS"
    )

    assert production_calls == [
        {
            "symbol": "TEST.NS",
            "timeframe": "1W",
            "rows": 2,
            "allow_full_replay_fallback": True,
        }
    ]
    assert result.latest_week == LATEST_WEEK
    assert result.evaluated_at_utc != "2026-09-01T10:00:00+00:00"
    assert store.load("TEST.NS", "1W").latest_week == LATEST_WEEK


def test_decision_context_endpoint_returns_compact_service_payload(monkeypatch) -> None:
    captured: list[str] = []
    payload = _current_decision_context_payload()

    class FakeService:
        def decision_context_for_symbol(self, symbol: str):
            captured.append(symbol)
            return payload

    monkeypatch.setattr(api_main, "_service", FakeService())

    response = TestClient(api_main.app).get("/api/symbols/test.ns/decision-context")

    assert response.status_code == 200
    assert captured == ["test.ns"]
    body = response.json()
    assert body["symbol"] == "TEST.NS"
    assert body["latest_week"] == LATEST_WEEK
    assert "bars" not in body
    assert "evidence" not in body
