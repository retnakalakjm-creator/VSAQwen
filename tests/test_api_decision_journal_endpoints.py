from __future__ import annotations

import pandas as pd
from fastapi.testclient import TestClient

from decision_journal import (
    DECISION_JOURNAL_SCHEMA_VERSION,
    DecisionJournalEntry,
    DecisionJournalStore,
    ValidationOutcome,
)
from api import main as api_main
import api.service as service_module
from api.service import ProVSAService


OLD_WEEK = "2026-08-24 00:00:00"
LATEST_WEEK = "2026-08-31 00:00:00"


def _weekly_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "week_beginning": pd.to_datetime(["2026-08-24", "2026-08-31"]),
            "open": [100.0, 105.0],
            "high": [108.0, 116.0],
            "low": [95.0, 104.0],
            "close": [104.0, 115.0],
            "volume": [1_000_000.0, 1_250_000.0],
        }
    )


def _patch_weekly_pipeline(monkeypatch) -> None:
    monkeypatch.setattr(service_module, "download_data", lambda symbol: pd.DataFrame())
    monkeypatch.setattr(service_module, "daily_to_weekly", lambda daily: _weekly_frame())
    monkeypatch.setattr(service_module, "completed_weekly_only", lambda weekly: weekly)


def _journal_entry(
    *,
    status: ValidationOutcome = ValidationOutcome.PENDING,
) -> DecisionJournalEntry:
    return DecisionJournalEntry(
        schema_version=DECISION_JOURNAL_SCHEMA_VERSION,
        entry_id="TEST.NS__1W__2026-08-24__0",
        symbol="TEST.NS",
        timeframe="1W",
        source_context_week=OLD_WEEK,
        source_context_bar_index=0,
        source_context_evaluated_at_utc="2026-09-01T10:00:00+00:00",
        created_at_utc="2026-09-01T10:01:00+00:00",
        phase="late_accumulation",
        bias="bullish",
        tradability="wait_for_confirmation",
        decision="wait_for_confirmation",
        confidence=0.72,
        net_pressure=0.35,
        headline="Bullish VSA context in late accumulation",
        summary="Demand is improving after absorption.",
        confirmation_condition="Close above resistance confirms demand.",
        invalidation_condition="Close below support invalidates the read.",
        expected_next_behavior=("Constructive pullbacks should hold support.",),
        support_price=95.0,
        resistance_price=110.0,
        reference_price=100.0,
        status=status,
    )


def test_decision_journal_list_returns_saved_entries(tmp_path) -> None:
    store = DecisionJournalStore(tmp_path / "journal")
    store.save_all("TEST.NS", "1W", [_journal_entry()])

    result = ProVSAService(decision_journal_store=store).decision_journal_for_symbol(
        " test.ns "
    )

    assert result.symbol == "TEST.NS"
    assert result.timeframe == "1W"
    assert len(result.entries) == 1
    entry = result.entries[0]
    assert entry.entry_id == "TEST.NS__1W__2026-08-24__0"
    assert entry.bias == "bullish"
    assert entry.status == "pending"
    assert entry.expected_next_behavior == ["Constructive pullbacks should hold support."]


def test_decision_journal_evaluation_is_read_only_by_default(
    monkeypatch,
    tmp_path,
) -> None:
    store = DecisionJournalStore(tmp_path / "journal")
    store.save_all("TEST.NS", "1W", [_journal_entry()])
    _patch_weekly_pipeline(monkeypatch)

    result = ProVSAService(decision_journal_store=store).evaluate_decision_journal_for_symbol(
        "test.ns",
        horizon_bars=4,
    )

    assert result.symbol == "TEST.NS"
    assert result.timeframe == "1W"
    assert result.horizon_bars == 4
    assert result.latest_week == LATEST_WEEK
    assert result.persist_status is False
    assert len(result.evaluations) == 1

    evaluation = result.evaluations[0]
    assert evaluation.entry_id == "TEST.NS__1W__2026-08-24__0"
    assert evaluation.source_context_week == OLD_WEEK
    assert evaluation.source_context_bar_index == 0
    assert evaluation.outcome == "confirmed"
    assert evaluation.checked_bars == 1
    assert evaluation.first_checked_week == LATEST_WEEK
    assert evaluation.last_checked_week == LATEST_WEEK
    assert evaluation.confirmation_hit is True
    assert evaluation.invalidation_hit is False
    assert evaluation.favorable_move_pct == 16.0
    assert evaluation.adverse_move_pct == 0.0

    saved = store.load_all("TEST.NS", "1W")
    assert saved[0].status is ValidationOutcome.PENDING


def test_decision_journal_evaluation_can_persist_status(
    monkeypatch,
    tmp_path,
) -> None:
    store = DecisionJournalStore(tmp_path / "journal")
    store.save_all("TEST.NS", "1W", [_journal_entry()])
    _patch_weekly_pipeline(monkeypatch)

    result = ProVSAService(decision_journal_store=store).evaluate_decision_journal_for_symbol(
        "TEST.NS",
        horizon_bars=4,
        persist_status=True,
    )

    assert result.persist_status is True
    assert result.evaluations[0].outcome == "confirmed"
    saved = store.load_all("TEST.NS", "1W")
    assert saved[0].status is ValidationOutcome.CONFIRMED


def test_decision_journal_evaluation_rejects_invalid_horizon(tmp_path) -> None:
    store = DecisionJournalStore(tmp_path / "journal")
    service = ProVSAService(decision_journal_store=store)

    try:
        service.evaluate_decision_journal_for_symbol("TEST.NS", horizon_bars=0)
    except ValueError as exc:
        assert str(exc) == "horizon_bars must be greater than zero"
    else:
        raise AssertionError("invalid horizon should raise ValueError")


def test_decision_journal_routes_delegate_to_service(monkeypatch) -> None:
    captured: list[object] = []

    class FakeService:
        def decision_journal_for_symbol(self, symbol: str):
            captured.append(("list", symbol))
            return {"symbol": "TEST.NS", "timeframe": "1W", "entries": []}

        def evaluate_decision_journal_for_symbol(
            self,
            symbol: str,
            *,
            horizon_bars: int,
            persist_status: bool,
        ):
            captured.append(("evaluate", symbol, horizon_bars, persist_status))
            return {
                "symbol": "TEST.NS",
                "timeframe": "1W",
                "horizon_bars": horizon_bars,
                "latest_week": LATEST_WEEK,
                "persist_status": persist_status,
                "evaluations": [],
            }

    monkeypatch.setattr(api_main, "_service", FakeService())
    client = TestClient(api_main.app)

    list_response = client.get("/api/symbols/test.ns/decision-journal")
    assert list_response.status_code == 200
    assert list_response.json() == {"symbol": "TEST.NS", "timeframe": "1W", "entries": []}

    eval_response = client.get(
        "/api/symbols/test.ns/decision-journal/evaluations",
        params={"horizon_bars": 4, "persist_status": True},
    )
    assert eval_response.status_code == 200
    assert eval_response.json() == {
        "symbol": "TEST.NS",
        "timeframe": "1W",
        "horizon_bars": 4,
        "latest_week": LATEST_WEEK,
        "persist_status": True,
        "evaluations": [],
    }
    assert captured == [
        ("list", "test.ns"),
        ("evaluate", "test.ns", 4, True),
    ]