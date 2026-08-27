from types import SimpleNamespace

from live_scanner import _candidate_payload, _observation_signature


def test_candidate_payload_exposes_decision_boundary() -> None:
    candidate = SimpleNamespace(
        bar_index=42,
        week="2026-08-21",
        qualification="PERSISTENT_BULLISH",
        actionable=True,
        reason="confirmed",
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
    assert payload["actionable"] is True
    assert payload["net_strength"] == 1.25
    assert payload["target_bar_evidence_codes"] == ["STOPPING_VOLUME"]
    assert payload["scoring_evidence_age"] == 0


def test_observation_signature_ignores_evaluation_timestamp() -> None:
    first = {
        "week": "2026-08-21",
        "actionable": False,
        "qualification": "UNQUALIFIED",
        "net_strength": 0.0,
        "net_pressure": 0.0,
        "target_bar_evidence_codes": [],
        "scoring_evidence_codes": [],
    }
    second = dict(first)

    assert _observation_signature(first) == _observation_signature(second)
