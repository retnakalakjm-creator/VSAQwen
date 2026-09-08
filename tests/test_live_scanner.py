from types import SimpleNamespace

from live_scanner import _candidate_payload, _observation_signature


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
