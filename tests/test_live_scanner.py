from types import SimpleNamespace

import pytest

from live_scanner import (
    _candidate_payload,
    _observation_signature,
    _worker_count,
    run_once,
    scan_symbols_parallel,
)


def test_candidate_payload_exposes_decision_boundary() -> None:
    candidate = SimpleNamespace(
        bar_index=42,
        week="2026-08-21",
        signal_bar_index=42,
        signal_week="2026-08-21",
        signal_bar_anomaly=True,
        signal_bar_anomaly_reason="review adjusted data",
        execution_bar_index=None,
        execution_week=None,
        execution_available=False,
        execution_pending=False,
        execution_note="Execution bar is not available yet; evaluate entry on the next completed bar/session.",
        qualification="PERSISTENT_BULLISH",
        actionable=False,
        reason="review adjusted data",
        net_strength=1.25,
        net_pressure=0.75,
        confidence=0.8,
        target_bar_evidence_codes=("STOPPING_VOLUME",),
        campaign_evidence_codes=("STOPPING_VOLUME", "TEST"),
        qualifying_evidence_codes=("STOPPING_VOLUME",),
        scoring_evidence_codes=("STOPPING_VOLUME",),
        scoring_bar_index=42,
        scoring_evidence_age=0,
        used_fallback_evidence=False,
    )

    payload = _candidate_payload("TEST.NS", candidate)

    assert payload["symbol"] == "TEST.NS"
    assert payload["actionable"] is False
    assert payload["bar_index"] == 42
    assert payload["week"] == "2026-08-21"
    assert payload["signal_bar_index"] == 42
    assert payload["signal_week"] == "2026-08-21"
    assert payload["signal_bar_anomaly"] is True
    assert payload["signal_bar_anomaly_reason"] == "review adjusted data"
    assert payload["execution_bar_index"] is None
    assert payload["execution_week"] is None
    assert payload["execution_available"] is False
    assert payload["execution_pending"] is False
    assert "next" in payload["execution_note"].lower()
    assert payload["net_strength"] == 1.25
    assert payload["target_bar_evidence_codes"] == ["STOPPING_VOLUME"]
    assert payload["scoring_evidence_age"] == 0


def test_observation_signature_ignores_evaluation_timestamp() -> None:
    first = {
        "week": "2026-08-21",
        "signal_bar_index": 42,
        "signal_week": "2026-08-21",
        "signal_bar_anomaly": True,
        "signal_bar_anomaly_reason": "review adjusted data",
        "execution_bar_index": None,
        "execution_week": None,
        "execution_available": False,
        "execution_pending": False,
        "actionable": False,
        "qualification": "UNQUALIFIED",
        "net_strength": 0.0,
        "net_pressure": 0.0,
        "target_bar_evidence_codes": [],
        "scoring_evidence_codes": [],
    }
    second = dict(first)
    second["evaluated_at"] = "2026-09-07T18:00:00+00:00"

    assert _observation_signature(first) == _observation_signature(second)


def test_worker_count_is_bounded_by_symbol_count() -> None:
    assert _worker_count(("A",), 4) == 1
    assert _worker_count(("A", "B", "C"), 2) == 2
    assert _worker_count(("A", "B", "C"), 10) == 3


@pytest.mark.parametrize("max_workers", [0, -1])
def test_worker_count_rejects_non_positive_workers(max_workers: int) -> None:
    with pytest.raises(ValueError, match="max_workers"):
        _worker_count(("A",), max_workers)


def test_scan_symbols_parallel_preserves_input_order_and_isolates_errors(monkeypatch) -> None:
    def fake_scan_symbol(symbol: str, *, use_incremental: bool = True):
        if symbol == "BAD.NS":
            raise RuntimeError("download failed")
        return {
            "symbol": symbol,
            "week": f"week-{symbol}",
            "signal_bar_index": 1,
            "signal_bar_anomaly": False,
            "execution_bar_index": None,
            "actionable": False,
            "qualification": "UNQUALIFIED",
            "net_strength": 0.0,
            "net_pressure": 0.0,
            "target_bar_evidence_codes": [],
            "scoring_evidence_codes": [],
        }

    monkeypatch.setattr("live_scanner.scan_symbol", fake_scan_symbol)

    observations = scan_symbols_parallel(
        ("B.NS", "BAD.NS", "A.NS"),
        max_workers=3,
    )

    assert [item["symbol"] for item in observations] == ["B.NS", "BAD.NS", "A.NS"]
    assert observations[1]["qualification"] == "ERROR"
    assert observations[1]["error"] == "RuntimeError"
    assert "download failed" in observations[1]["reason"]


def test_run_once_prints_parallel_results_in_result_order(monkeypatch, capsys) -> None:
    observations = [
        {"symbol": "A.NS", "value": 1},
        {"symbol": "B.NS", "value": 2},
    ]
    printed: list[str] = []

    def fake_scan_symbols_parallel(symbols, *, use_incremental=True, max_workers=4):
        assert symbols == ("A.NS", "B.NS")
        assert max_workers == 2
        return observations

    def fake_print_observation(observation, as_json):
        assert as_json is True
        printed.append(observation["symbol"])

    monkeypatch.setattr("live_scanner.scan_symbols_parallel", fake_scan_symbols_parallel)
    monkeypatch.setattr("live_scanner._print_observation", fake_print_observation)

    result = run_once(("A.NS", "B.NS"), True, max_workers=2)

    assert result == observations
    assert printed == ["A.NS", "B.NS"]
    assert capsys.readouterr().out == ""
