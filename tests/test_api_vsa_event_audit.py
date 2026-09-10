from __future__ import annotations

from fastapi.testclient import TestClient
import pandas as pd

from api import main as api_main
from vsa_event_audit import VSAEventAuditRow, VSAEventAuditSymbolResult


def _weekly_frame(rows: int = 24) -> pd.DataFrame:
    weeks = pd.date_range("2026-03-16", periods=rows, freq="W-MON")
    return pd.DataFrame(
        {
            "week_beginning": weeks,
            "open": [100.0 + index for index in range(rows)],
            "high": [103.0 + index for index in range(rows)],
            "low": [97.0 + index for index in range(rows)],
            "close": [101.0 + index for index in range(rows)],
            "volume": [1_000_000.0 + index * 10_000.0 for index in range(rows)],
        }
    )


def test_vsa_event_audit_endpoint_returns_compact_multi_symbol_response(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeService:
        @staticmethod
        def _normalize_symbol(symbol: str) -> str:
            return symbol.strip().upper()

        @staticmethod
        def _completed_weekly_for_symbol(symbol: str) -> pd.DataFrame:
            captured.setdefault("symbols", []).append(symbol)
            return _weekly_frame()

    def fake_build_vsa_event_audit(**kwargs):
        captured["audit_kwargs"] = kwargs
        row = VSAEventAuditRow(
            symbol=kwargs["symbol"],
            replay_bar_index=22,
            replay_week="2026-08-17 00:00:00",
            target_event_codes=("stopping_volume",),
            scoring_event_codes=("stopping_volume",),
            qualifying_event_codes=(),
            campaign_event_codes=("stopping_volume",),
            structural_event_codes=(),
            vsa_event_codes=("stopping_volume",),
            qualification="unqualified",
            actionable=False,
            used_fallback_evidence=False,
            scoring_evidence_age=0,
            net_pressure=0.25,
            confidence=0.55,
            audit_flags=("manual_review_candidate",),
            detector_diagnostics=("review_potential_effort_gt_result",),
        )
        return VSAEventAuditSymbolResult(
            symbol=kwargs["symbol"],
            timeframe="1W",
            start_week="2026-08-17 00:00:00",
            end_week="2026-08-17 00:00:00",
            replay_weeks=1,
            rows=(row,),
        )

    monkeypatch.setattr(api_main, "_service", FakeService())
    monkeypatch.setattr(api_main, "build_vsa_event_audit", fake_build_vsa_event_audit)

    response = TestClient(api_main.app).get(
        "/api/vsa-audit/events?symbols=lt.ns,srf.ns&start_week=2026-08-17&horizon_weeks=4"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["symbols"] == ["LT.NS", "SRF.NS"]
    assert body["timeframe"] == "1W"
    assert body["horizon_weeks"] == 4
    assert body["audit_only"] is True
    assert body["errors"] == {}
    assert len(body["results"]) == 2
    row = body["results"][0]["rows"][0]
    assert row["target_event_codes"] == ["stopping_volume"]
    assert row["audit_flags"] == ["manual_review_candidate"]
    assert row["detector_diagnostics"] == ["review_potential_effort_gt_result"]
    assert "order" not in row
    assert captured["symbols"] == ["LT.NS", "SRF.NS"]


def test_vsa_event_audit_endpoint_rejects_empty_symbol_list() -> None:
    response = TestClient(api_main.app).get("/api/vsa-audit/events?symbols=,,")
    assert response.status_code == 400
    assert "at least one symbol" in response.json()["detail"]
