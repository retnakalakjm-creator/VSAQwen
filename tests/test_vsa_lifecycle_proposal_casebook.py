from __future__ import annotations

import csv
import json
import subprocess
import sys
from io import StringIO
from pathlib import Path

from vsa_lifecycle_proposal_casebook import (
    CASE_CONFLICT_PENDING_SUPERSESSION,
    CASE_SUPERSESSION_RULE_CANDIDATE,
    CHART_REVIEW_STATUS_PENDING,
    MANUAL_REVIEW_STATUS_UNREVIEWED,
    PRODUCTION_DECISION_STATUS_PENDING,
    TRANSITION_MARK_BEARISH_CONFLICTED,
    TRANSITION_SUPERSEDE_BEARISH_WITH_DEMAND,
    build_vsa_lifecycle_proposal_casebook,
    render_vsa_lifecycle_proposal_casebook_csv,
)


def _proposal_payload() -> dict[str, object]:
    return {
        "audit_only": True,
        "rows": [
            {
                "audit_only": True,
                "symbol": "LT.NS",
                "cluster_id": "LT.NS:233-236",
                "grade": "A",
                "proposal_confidence": 100,
                "source_priority_score": 100,
                "source_review_type": "bearish_context_demand_reversal_cluster",
                "proposed_transition": TRANSITION_MARK_BEARISH_CONFLICTED,
                "next_audit_step": "chart_review_conflict_before_invalidation_or_supersession",
                "start_week": "2026-03-02 00:00:00",
                "end_week": "2026-03-23 00:00:00",
                "start_bar_index": 233,
                "end_bar_index": 236,
                "demand_evidence_codes": ["demand_coming_in", "increasing_demand"],
                "caution_evidence_codes": ["structural_progression_weakening", "increasing_supply"],
                "opposing_evidence_codes": ["structural_progression_weakening", "increasing_supply"],
                "event_families": ["absorption", "effort_vs_result", "high_volume_reversal"],
                "proposal_reasons": [
                    "persistent bearish qualification is challenged by demand/reversal evidence",
                    "bearish structure evidence remains",
                ],
            },
            {
                "audit_only": True,
                "symbol": "DRREDDY.NS",
                "cluster_id": "DRREDDY.NS:236-238",
                "grade": "A",
                "proposal_confidence": 100,
                "source_priority_score": 99,
                "source_review_type": "bearish_context_demand_reversal_cluster",
                "proposed_transition": TRANSITION_SUPERSEDE_BEARISH_WITH_DEMAND,
                "next_audit_step": "chart_confirm_supersession_rule_candidate",
                "start_week": "2026-03-23 00:00:00",
                "end_week": "2026-04-06 00:00:00",
                "start_bar_index": 236,
                "end_bar_index": 238,
                "demand_evidence_codes": ["increasing_demand", "demand_coming_in"],
                "caution_evidence_codes": ["increasing_supply"],
                "opposing_evidence_codes": ["increasing_supply"],
                "event_families": ["absorption", "high_volume_reversal"],
                "proposal_reasons": [
                    "persistent bearish qualification is challenged by demand/reversal evidence",
                ],
            },
            {
                "audit_only": True,
                "symbol": "GRASIM.NS",
                "cluster_id": "GRASIM.NS:233-233",
                "grade": "A",
                "proposal_confidence": 100,
                "source_priority_score": 91,
                "source_review_type": "bearish_context_demand_reversal_cluster",
                "proposed_transition": TRANSITION_MARK_BEARISH_CONFLICTED,
                "next_audit_step": "chart_review_conflict_before_invalidation_or_supersession",
                "start_week": "2026-03-02 00:00:00",
                "end_week": "2026-03-02 00:00:00",
                "start_bar_index": 233,
                "end_bar_index": 233,
                "demand_evidence_codes": ["increasing_demand", "demand_coming_in"],
                "caution_evidence_codes": ["hidden_supply"],
                "opposing_evidence_codes": ["hidden_supply"],
                "event_families": ["absorption", "effort_vs_result", "high_volume_reversal"],
                "proposal_reasons": [
                    "persistent bearish qualification is challenged by demand/reversal evidence",
                ],
            },
        ],
    }


def test_build_casebook_preserves_lifecycle_proposal_fields() -> None:
    summary = build_vsa_lifecycle_proposal_casebook(_proposal_payload())
    payload = summary.to_dict()

    assert payload["audit_only"] is True
    assert payload["total_input_proposals"] == 3
    assert payload["total_casebook_rows"] == 3
    assert payload["case_type_counts"] == {
        CASE_CONFLICT_PENDING_SUPERSESSION: 2,
        CASE_SUPERSESSION_RULE_CANDIDATE: 1,
    }
    assert payload["proposed_transition_counts"] == {
        TRANSITION_MARK_BEARISH_CONFLICTED: 2,
        TRANSITION_SUPERSEDE_BEARISH_WITH_DEMAND: 1,
    }
    assert payload["review_status_counts"] == {MANUAL_REVIEW_STATUS_UNREVIEWED: 3}

    first = payload["rows"][0]
    assert first["symbol"] == "LT.NS"
    assert first["case_type"] == CASE_CONFLICT_PENDING_SUPERSESSION
    assert first["manual_review_status"] == MANUAL_REVIEW_STATUS_UNREVIEWED
    assert first["chart_review_status"] == CHART_REVIEW_STATUS_PENDING
    assert first["production_decision_status"] == PRODUCTION_DECISION_STATUS_PENDING
    assert first["manual_review_notes"] == ""
    assert first["demand_evidence_codes"] == ["demand_coming_in", "increasing_demand"]
    assert first["caution_evidence_codes"] == [
        "structural_progression_weakening",
        "increasing_supply",
    ]
    assert first["recommended_casebook_action"] == "chart_review_conflict_before_invalidation_or_supersession"


def test_casebook_export_sorts_by_confidence_then_source_priority() -> None:
    summary = build_vsa_lifecycle_proposal_casebook(_proposal_payload())
    rows = summary.to_dict()["rows"]

    assert [row["symbol"] for row in rows] == ["LT.NS", "DRREDDY.NS", "GRASIM.NS"]
    assert summary.to_dict()["top_casebook_items"][0]["symbol"] == "LT.NS"


def test_casebook_accepts_direct_sequence_payload() -> None:
    proposals = _proposal_payload()["rows"]
    summary = build_vsa_lifecycle_proposal_casebook(proposals)  # type: ignore[arg-type]

    assert summary.total_input_proposals == 3
    assert summary.total_casebook_rows == 3


def test_casebook_csv_renders_review_columns() -> None:
    summary = build_vsa_lifecycle_proposal_casebook(_proposal_payload())
    csv_text = render_vsa_lifecycle_proposal_casebook_csv(summary)
    parsed = list(csv.DictReader(StringIO(csv_text)))

    assert len(parsed) == 3
    assert parsed[0]["symbol"] == "LT.NS"
    assert parsed[0]["manual_review_status"] == MANUAL_REVIEW_STATUS_UNREVIEWED
    assert parsed[0]["chart_review_status"] == CHART_REVIEW_STATUS_PENDING
    assert parsed[0]["production_decision_status"] == PRODUCTION_DECISION_STATUS_PENDING
    assert parsed[0]["demand_evidence_codes"] == "demand_coming_in;increasing_demand"


def test_casebook_cli_writes_json_and_csv(tmp_path: Path) -> None:
    input_path = tmp_path / "lifecycle_proposals.json"
    json_output = tmp_path / "casebook.json"
    csv_output = tmp_path / "casebook.csv"
    input_path.write_text(json.dumps(_proposal_payload()), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/vsa_lifecycle_proposal_casebook.py",
            str(input_path),
            "--json-output",
            str(json_output),
            "--csv-output",
            str(csv_output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    payload = json.loads(json_output.read_text(encoding="utf-8"))
    assert payload["total_casebook_rows"] == 3
    assert payload["rows"][0]["symbol"] == "LT.NS"
    assert "manual_review_status" in csv_output.read_text(encoding="utf-8")


def test_empty_casebook_payload_is_safe() -> None:
    summary = build_vsa_lifecycle_proposal_casebook({"rows": []})

    assert summary.total_input_proposals == 0
    assert summary.total_casebook_rows == 0
    assert summary.to_dict()["rows"] == []
