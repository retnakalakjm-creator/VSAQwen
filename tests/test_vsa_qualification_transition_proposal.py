from __future__ import annotations

import csv
import json
import subprocess
import sys
from io import StringIO
from pathlib import Path

from vsa_qualification_lifecycle_audit import (
    LIFECYCLE_ACTIVE,
    LIFECYCLE_CONFLICTED,
    LIFECYCLE_EXPIRED_REVIEW,
    LIFECYCLE_INVALIDATED_REVIEW,
    LIFECYCLE_NEEDS_FOLLOW_THROUGH,
)
from vsa_qualification_transition_proposal import (
    TRANSITION_EXPIRE_QUALIFICATION,
    TRANSITION_INVALIDATE_QUALIFICATION,
    TRANSITION_KEEP_ACTIVE,
    TRANSITION_MARK_CONFLICTED,
    TRANSITION_WAIT_FOR_FOLLOW_THROUGH,
    build_qualification_transition_proposals,
    render_qualification_transition_proposals_csv,
)


def _lifecycle_row(**overrides):
    base = {
        "symbol": "LT.NS",
        "replay_week": "2026-04-06 00:00:00",
        "replay_bar_index": 238,
        "qualification": "persistent_bearish",
        "qualification_side": "bearish",
        "current_vsa_bias": "bullish",
        "lifecycle_status": LIFECYCLE_INVALIDATED_REVIEW,
        "severity_grade": "A",
        "severity_score": 96,
        "source_row_count": 2,
        "candidate_families": ["qualification_lifecycle", "effort_vs_result"],
        "candidate_codes": [
            "audit_qualification_conflict_candidate",
            "audit_effort_gt_result_candidate",
        ],
        "triage_buckets": ["qualification_lifecycle_issue", "clean_candidate"],
        "triage_grades": ["A"],
        "target_event_codes": ["increasing_demand", "demand_coming_in"],
        "scoring_event_codes": ["increasing_demand", "demand_coming_in"],
        "supporting_event_codes": [],
        "opposing_event_codes": ["increasing_demand", "demand_coming_in"],
        "source_audit_flags": ["bullish_vsa_against_bearish_qualification"],
        "recommended_action": "review qualification invalidation or expiry rule",
        "reason": "bearish qualification has opposing bullish VSA evidence without same-side support in the reviewed bar.",
        "audit_only": True,
    }
    base.update(overrides)
    return base


def test_transition_proposal_maps_invalidated_lifecycle_to_invalidate_action() -> None:
    payload = {"rows": [_lifecycle_row()], "total_input_rows": 134}

    summary = build_qualification_transition_proposals(payload).to_dict()

    assert summary["total_input_rows"] == 134
    assert summary["total_proposal_rows"] == 1
    assert summary["action_counts"] == {TRANSITION_INVALIDATE_QUALIFICATION: 1}
    row = summary["rows"][0]
    assert row["proposed_action"] == TRANSITION_INVALIDATE_QUALIFICATION
    assert row["proposal_grade"] == "A"
    assert row["proposal_confidence"] == "high"
    assert row["audit_only"] is True
    assert "completed weekly bars" in " ".join(row["guardrails"])


def test_transition_proposal_maps_conflicted_rows_to_mark_conflicted() -> None:
    payload = {
        "rows": [
            _lifecycle_row(
                symbol="SUNPHARMA.NS",
                current_vsa_bias="mixed",
                lifecycle_status=LIFECYCLE_CONFLICTED,
                supporting_event_codes=["buying_climax"],
                opposing_event_codes=["demand_coming_in"],
            )
        ]
    }

    summary = build_qualification_transition_proposals(payload).to_dict()

    assert summary["action_counts"] == {TRANSITION_MARK_CONFLICTED: 1}
    row = summary["rows"][0]
    assert row["recommended_action"] == "design conflicted-state story label before changing qualification"
    assert row["proposal_score"] == 92


def test_transition_proposal_maps_expired_rows_to_expire_action() -> None:
    payload = {
        "rows": [
            _lifecycle_row(
                symbol="ICICIBANK.NS",
                current_vsa_bias="none",
                lifecycle_status=LIFECYCLE_EXPIRED_REVIEW,
                target_event_codes=[],
                scoring_event_codes=[],
                opposing_event_codes=[],
                candidate_families=["absorption", "high_volume_reversal"],
            )
        ]
    }

    summary = build_qualification_transition_proposals(payload).to_dict()

    assert summary["action_counts"] == {TRANSITION_EXPIRE_QUALIFICATION: 1}
    row = summary["rows"][0]
    assert row["proposal_grade"] == "B"
    assert row["proposal_confidence"] == "medium"
    assert "fresh supporting evidence is absent" in row["proposal_reason"]


def test_transition_proposal_maps_follow_through_rows_to_wait_action() -> None:
    payload = {
        "rows": [
            _lifecycle_row(
                symbol="HDFCBANK.NS",
                qualification="persistent_bullish",
                qualification_side="bullish",
                current_vsa_bias="bearish",
                lifecycle_status=LIFECYCLE_NEEDS_FOLLOW_THROUGH,
                opposing_event_codes=["increasing_supply"],
            )
        ]
    }

    summary = build_qualification_transition_proposals(payload).to_dict()

    assert summary["action_counts"] == {TRANSITION_WAIT_FOR_FOLLOW_THROUGH: 1}
    row = summary["rows"][0]
    assert row["proposal_score"] == 74
    assert "follow-through" in row["recommended_action"]


def test_transition_proposal_excludes_active_rows_by_default() -> None:
    payload = {
        "rows": [
            _lifecycle_row(
                lifecycle_status=LIFECYCLE_ACTIVE,
                current_vsa_bias="bearish",
                supporting_event_codes=["increasing_supply"],
                opposing_event_codes=[],
            )
        ]
    }

    summary = build_qualification_transition_proposals(payload).to_dict()

    assert summary["total_proposal_rows"] == 0
    assert summary["rows"] == []


def test_transition_proposal_can_include_active_baseline_rows() -> None:
    payload = {
        "rows": [
            _lifecycle_row(
                lifecycle_status=LIFECYCLE_ACTIVE,
                current_vsa_bias="bearish",
                supporting_event_codes=["increasing_supply"],
                opposing_event_codes=[],
            )
        ]
    }

    summary = build_qualification_transition_proposals(
        payload,
        include_active=True,
    ).to_dict()

    assert summary["action_counts"] == {TRANSITION_KEEP_ACTIVE: 1}
    assert summary["rows"][0]["proposal_grade"] == "C"
    assert summary["rows"][0]["proposal_confidence"] == "low"


def test_transition_proposal_builds_focus_and_symbol_summary() -> None:
    payload = {
        "rows": [
            _lifecycle_row(symbol="LT.NS"),
            _lifecycle_row(symbol="LT.NS", replay_week="2026-03-23 00:00:00"),
            _lifecycle_row(
                symbol="MARUTI.NS",
                lifecycle_status=LIFECYCLE_CONFLICTED,
                current_vsa_bias="mixed",
            ),
        ]
    }

    summary = build_qualification_transition_proposals(payload).to_dict()

    assert summary["action_counts"] == {
        TRANSITION_INVALIDATE_QUALIFICATION: 2,
        TRANSITION_MARK_CONFLICTED: 1,
    }
    assert summary["transition_focus"][0]["proposed_action"] == TRANSITION_INVALIDATE_QUALIFICATION
    assert summary["transition_focus"][0]["total_rows"] == 2
    assert summary["top_transition_symbols"][0]["symbol"] == "LT.NS"
    assert summary["top_transition_symbols"][0]["total_rows"] == 2


def test_transition_proposal_csv_renders_proposal_columns() -> None:
    summary = build_qualification_transition_proposals({"rows": [_lifecycle_row()]})

    body = render_qualification_transition_proposals_csv(summary)
    rows = list(csv.DictReader(StringIO(body)))

    assert len(rows) == 1
    assert rows[0]["symbol"] == "LT.NS"
    assert rows[0]["proposed_action"] == TRANSITION_INVALIDATE_QUALIFICATION
    assert rows[0]["proposal_grade"] == "A"
    assert "audit-only" in rows[0]["guardrails"]


def test_transition_proposal_cli_writes_json_and_csv(tmp_path: Path) -> None:
    input_file = tmp_path / "standard_basket_qualification_lifecycle.json"
    json_output = tmp_path / "standard_basket_qualification_transitions.json"
    csv_output = tmp_path / "standard_basket_qualification_transitions.csv"
    input_file.write_text(
        json.dumps({"rows": [_lifecycle_row()], "total_input_rows": 134}),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/vsa_qualification_transition_proposal.py",
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
    assert json_body["action_counts"] == {TRANSITION_INVALIDATE_QUALIFICATION: 1}
    assert csv_rows[0]["proposed_action"] == TRANSITION_INVALIDATE_QUALIFICATION
