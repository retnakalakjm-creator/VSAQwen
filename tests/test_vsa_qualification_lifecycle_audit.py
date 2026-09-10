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
    build_qualification_lifecycle_audit,
    render_qualification_lifecycle_audit_csv,
)


def _triage_row(**overrides):
    base = {
        "symbol": "LT.NS",
        "replay_week": "2026-04-06 00:00:00",
        "replay_bar_index": 238,
        "candidate_code": "audit_qualification_conflict_candidate",
        "candidate_family": "qualification_lifecycle",
        "candidate_families": ["qualification_lifecycle"],
        "direction": "context_review",
        "priority": "high",
        "qualification": "persistent_bearish",
        "target_event_codes": ["increasing_demand", "demand_coming_in"],
        "scoring_event_codes": ["increasing_demand", "demand_coming_in"],
        "source_diagnostics": [],
        "source_audit_flags": ["bullish_vsa_against_bearish_qualification"],
        "triage_bucket": "qualification_lifecycle_issue",
        "triage_grade": "A",
        "triage_score": 95,
        "recommended_action": "prioritize lifecycle/qualification invalidation rules",
        "audit_only": True,
    }
    base.update(overrides)
    return base


def test_lifecycle_audit_marks_opposing_evidence_for_invalidation_review() -> None:
    summary = build_qualification_lifecycle_audit({"rows": [_triage_row()]}).to_dict()

    assert summary["audit_only"] is True
    assert summary["total_input_rows"] == 1
    assert summary["total_lifecycle_rows"] == 1
    assert summary["status_counts"] == {LIFECYCLE_INVALIDATED_REVIEW: 1}
    row = summary["rows"][0]
    assert row["qualification_side"] == "bearish"
    assert row["current_vsa_bias"] == "bullish"
    assert row["supporting_event_codes"] == []
    assert row["opposing_event_codes"] == ["increasing_demand", "demand_coming_in"]
    assert row["severity_grade"] == "A"
    assert "invalidation" in row["recommended_action"]


def test_lifecycle_audit_keeps_mixed_evidence_as_conflicted() -> None:
    row = _triage_row(
        symbol="MARUTI.NS",
        replay_week="2026-03-02 00:00:00",
        qualification="persistent_bullish",
        target_event_codes=["increasing_supply", "stopping_volume", "selling_climax"],
        scoring_event_codes=["increasing_supply", "stopping_volume", "selling_climax"],
        source_audit_flags=["bearish_vsa_against_bullish_qualification"],
    )

    summary = build_qualification_lifecycle_audit({"rows": [row]}).to_dict()

    assert summary["status_counts"] == {LIFECYCLE_CONFLICTED: 1}
    selected = summary["rows"][0]
    assert selected["qualification_side"] == "bullish"
    assert selected["current_vsa_bias"] == "mixed"
    assert selected["supporting_event_codes"] == ["stopping_volume", "selling_climax"]
    assert selected["opposing_event_codes"] == ["increasing_supply"]


def test_lifecycle_audit_can_include_active_supported_qualification() -> None:
    active = _triage_row(
        symbol="POWERGRID.NS",
        candidate_code="audit_effort_gt_result_candidate",
        candidate_family="effort_vs_result",
        candidate_families=["effort_vs_result"],
        qualification="persistent_bullish",
        target_event_codes=["no_supply"],
        scoring_event_codes=["no_supply"],
        source_audit_flags=[],
        triage_bucket="clean_candidate",
        triage_grade="A",
    )

    default_summary = build_qualification_lifecycle_audit({"rows": [active]}).to_dict()
    active_summary = build_qualification_lifecycle_audit(
        {"rows": [active]},
        include_active=True,
    ).to_dict()

    assert default_summary["total_lifecycle_rows"] == 0
    assert active_summary["status_counts"] == {LIFECYCLE_ACTIVE: 1}
    assert active_summary["rows"][0]["supporting_event_codes"] == ["no_supply"]


def test_lifecycle_audit_marks_stale_qualification_for_expiry_review() -> None:
    stale = _triage_row(
        symbol="SRF.NS",
        candidate_code="audit_stale_evidence_candidate",
        candidate_family="evidence_lifecycle",
        candidate_families=["evidence_lifecycle"],
        qualification="persistent_bearish",
        target_event_codes=[],
        scoring_event_codes=[],
        source_audit_flags=["qualification_without_current_evidence"],
        triage_bucket="manual_chart_review",
        triage_grade="C",
    )

    summary = build_qualification_lifecycle_audit({"rows": [stale]}).to_dict()

    assert summary["status_counts"] == {LIFECYCLE_EXPIRED_REVIEW: 1}
    assert summary["rows"][0]["severity_grade"] == "B"
    assert "expire" in summary["rows"][0]["recommended_action"]


def test_lifecycle_audit_groups_same_symbol_week_before_classifying() -> None:
    qualification = _triage_row()
    sibling = _triage_row(
        candidate_code="audit_effort_gt_result_candidate",
        candidate_family="effort_vs_result",
        candidate_families=["effort_vs_result"],
        source_audit_flags=[],
        triage_bucket="clean_candidate",
        triage_grade="A",
    )

    summary = build_qualification_lifecycle_audit({"rows": [qualification, sibling]}).to_dict()

    assert summary["total_input_rows"] == 2
    assert summary["total_lifecycle_rows"] == 1
    row = summary["rows"][0]
    assert row["source_row_count"] == 2
    assert row["candidate_codes"] == [
        "audit_qualification_conflict_candidate",
        "audit_effort_gt_result_candidate",
    ]
    assert row["lifecycle_status"] == LIFECYCLE_INVALIDATED_REVIEW


def test_lifecycle_audit_marks_candidate_challenge_as_needing_follow_through() -> None:
    challenge = _triage_row(
        candidate_code="audit_effort_gt_result_candidate",
        candidate_family="effort_vs_result",
        candidate_families=["effort_vs_result"],
        qualification="persistent_bearish",
        source_audit_flags=[],
        triage_bucket="clean_candidate",
        triage_grade="A",
    )

    summary = build_qualification_lifecycle_audit({"rows": [challenge]}).to_dict()

    assert summary["status_counts"] == {LIFECYCLE_NEEDS_FOLLOW_THROUGH: 1}
    assert "follow-through" in summary["rows"][0]["recommended_action"]


def test_lifecycle_audit_csv_renders_lifecycle_columns() -> None:
    summary = build_qualification_lifecycle_audit({"rows": [_triage_row()]})

    body = render_qualification_lifecycle_audit_csv(summary)
    rows = list(csv.DictReader(StringIO(body)))

    assert len(rows) == 1
    assert rows[0]["symbol"] == "LT.NS"
    assert rows[0]["lifecycle_status"] == LIFECYCLE_INVALIDATED_REVIEW
    assert rows[0]["opposing_event_codes"] == "increasing_demand|demand_coming_in"


def test_lifecycle_audit_cli_writes_json_and_csv(tmp_path: Path) -> None:
    input_file = tmp_path / "standard_basket_triage.json"
    json_output = tmp_path / "qualification_lifecycle_audit.json"
    csv_output = tmp_path / "qualification_lifecycle_audit.csv"
    input_file.write_text(json.dumps({"rows": [_triage_row()]}), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/vsa_qualification_lifecycle_audit.py",
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
    assert json_body["status_counts"] == {LIFECYCLE_INVALIDATED_REVIEW: 1}
    assert csv_rows[0]["lifecycle_status"] == LIFECYCLE_INVALIDATED_REVIEW
