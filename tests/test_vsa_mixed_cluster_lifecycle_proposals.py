from __future__ import annotations

import csv
import json
import subprocess
import sys
from io import StringIO
from pathlib import Path

from vsa_mixed_cluster_lifecycle_proposals import (
    PROPOSAL_INVALIDATE_BEARISH_QUALIFICATION,
    PROPOSAL_MARK_BEARISH_CONFLICTED_PENDING_SUPERSESSION,
    PROPOSAL_SUPERSEDE_BEARISH_WITH_DEMAND_REVIEW,
    build_vsa_mixed_cluster_lifecycle_proposals,
    render_vsa_mixed_cluster_lifecycle_proposals_csv,
)


def _graded_cluster(**overrides):
    base = {
        "symbol": "LT.NS",
        "cluster_id": "LT.NS:233-236",
        "start_week": "2026-03-02 00:00:00",
        "end_week": "2026-03-23 00:00:00",
        "start_bar_index": 233,
        "end_bar_index": 236,
        "grade": "A",
        "review_type": "bearish_context_demand_reversal_cluster",
        "priority_score": 100,
        "recommended_action": "review_lifecycle_invalidation_or_supersession",
        "qualifications": ["persistent_bearish"],
        "event_families": ["absorption", "effort_vs_result", "high_volume_reversal"],
        "supporting_event_codes": ["demand_coming_in", "increasing_demand"],
        "opposing_event_codes": ["structural_progression_weakening", "increasing_supply"],
        "audit_only": True,
    }
    base.update(overrides)
    return base


def test_lifecycle_proposals_extract_persistent_bearish_candidates() -> None:
    payload = {
        "rows": [
            _graded_cluster(),
            _graded_cluster(
                symbol="AXISBANK.NS",
                cluster_id="AXISBANK.NS:1425-1427",
                review_type="unqualified_bidirectional_detector_conflict",
                priority_score=77,
                recommended_action="review_detector_gates_before_activation",
                qualifications=["unqualified"],
            ),
            _graded_cluster(
                symbol="MARUTI.NS",
                cluster_id="MARUTI.NS:1182-1184",
                review_type="bullish_context_supply_warning_cluster",
                priority_score=78,
                recommended_action="review_supply_warning_against_active_bullish_context",
                qualifications=["persistent_bullish"],
            ),
        ]
    }

    summary = build_vsa_mixed_cluster_lifecycle_proposals(payload).to_dict()

    assert summary["total_input_clusters"] == 3
    assert summary["total_lifecycle_proposals"] == 1
    assert summary["skipped_cluster_counts"] == {
        "active_bullish_supply_warning_review": 1,
        "detector_gate_review": 1,
    }
    assert summary["rows"][0]["symbol"] == "LT.NS"
    assert summary["rows"][0]["proposed_transition"] == PROPOSAL_MARK_BEARISH_CONFLICTED_PENDING_SUPERSESSION
    assert summary["rows"][0]["proposal_confidence"] == 100


def test_lifecycle_proposes_clean_invalidation_when_no_caution_evidence_remains() -> None:
    payload = {
        "rows": [
            _graded_cluster(
                cluster_id="TEST.NS:10-10",
                opposing_event_codes=[],
                priority_score=88,
                event_families=["absorption"],
            )
        ]
    }

    summary = build_vsa_mixed_cluster_lifecycle_proposals(payload).to_dict()

    assert summary["rows"][0]["proposed_transition"] == PROPOSAL_INVALIDATE_BEARISH_QUALIFICATION
    assert summary["rows"][0]["next_audit_step"] == "chart_confirm_bearish_invalidation_rule_candidate"


def test_lifecycle_proposes_supersession_when_demand_is_strong_and_no_structure_caution() -> None:
    payload = {
        "rows": [
            _graded_cluster(
                cluster_id="TEST.NS:20-22",
                opposing_event_codes=["increasing_supply"],
                priority_score=99,
                event_families=["absorption", "high_volume_reversal"],
            )
        ]
    }

    summary = build_vsa_mixed_cluster_lifecycle_proposals(payload).to_dict()

    assert summary["rows"][0]["proposed_transition"] == PROPOSAL_SUPERSEDE_BEARISH_WITH_DEMAND_REVIEW
    assert summary["rows"][0]["next_audit_step"] == "chart_confirm_supersession_rule_candidate"


def test_lifecycle_csv_renders_transition_columns() -> None:
    summary = build_vsa_mixed_cluster_lifecycle_proposals({"rows": [_graded_cluster()]})

    body = render_vsa_mixed_cluster_lifecycle_proposals_csv(summary)
    rows = list(csv.DictReader(StringIO(body)))

    assert len(rows) == 1
    assert rows[0]["symbol"] == "LT.NS"
    assert rows[0]["proposed_transition"] == PROPOSAL_MARK_BEARISH_CONFLICTED_PENDING_SUPERSESSION
    assert "proposal_read" in rows[0]


def test_lifecycle_cli_writes_json_and_csv(tmp_path: Path) -> None:
    input_file = tmp_path / "standard_basket_mixed_cluster_grades.json"
    json_output = tmp_path / "standard_basket_mixed_cluster_lifecycle_proposals.json"
    csv_output = tmp_path / "standard_basket_mixed_cluster_lifecycle_proposals.csv"
    input_file.write_text(json.dumps({"rows": [_graded_cluster()]}), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/vsa_mixed_cluster_lifecycle_proposals.py",
            str(input_file),
            "--json-output",
            str(json_output),
            "--csv-output",
            str(csv_output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    json_body = json.loads(json_output.read_text(encoding="utf-8"))
    csv_rows = list(csv.DictReader(StringIO(csv_output.read_text(encoding="utf-8"))))
    assert json_body["transition_counts"] == {PROPOSAL_MARK_BEARISH_CONFLICTED_PENDING_SUPERSESSION: 1}
    assert csv_rows[0]["proposed_transition"] == PROPOSAL_MARK_BEARISH_CONFLICTED_PENDING_SUPERSESSION
