from __future__ import annotations

import json

import pytest

from audit.review_effort_result_calibration_proposal import (
    APPROVED_MANUAL_REVIEW_STATUS,
    GATE_BLOCKED_STATUS,
    GATE_READY_STATUS,
    build_calibration_proposal_gate_report,
    render_calibration_proposal_gate_markdown,
)


def _proposal() -> dict[str, object]:
    return {
        "report_type": "effort_result_calibration_design_proposal",
        "source": "historical_effort_result_validation.csv",
        "rows": 7470,
        "targets": ["RESULT_GT_EFFORT", "EFFORT_RESULT+SUPPLY_COMING_IN"],
        "target_proposals": [
            {
                "target": "RESULT_GT_EFFORT",
                "proposal_status": "ready_for_calibration_design_review",
                "candidate_direction": "mixed",
                "proposed_signal_role": "direction_sensitive_calibration_candidate",
                "matched_bars": 88,
                "exported_examples": 20,
            },
            {
                "target": "EFFORT_RESULT+SUPPLY_COMING_IN",
                "proposal_status": "ready_for_calibration_design_review",
                "candidate_direction": "negative",
                "proposed_signal_role": "bearish_calibration_candidate",
                "matched_bars": 61,
                "exported_examples": 20,
            },
        ],
    }


def _evidence() -> dict[str, dict[str, object]]:
    return {
        "RESULT_GT_EFFORT": {
            "manual_review_status": APPROVED_MANUAL_REVIEW_STATUS,
            "reviewer": "manual-reviewer",
            "review_date": "2026-09-12",
            "reviewed_examples": 8,
            "reviewed_symbols": ["COALINDIA.NS", "HDFCBANK.NS"],
            "reviewed_weeks": ["2024-03-18", "2023-11-06"],
        },
        "EFFORT_RESULT+SUPPLY_COMING_IN": {
            "manual_review_status": APPROVED_MANUAL_REVIEW_STATUS,
            "reviewer": "manual-reviewer",
            "review_date": "2026-09-12",
            "reviewed_examples": 7,
            "reviewed_symbols": ["GODREJPROP.NS"],
            "reviewed_weeks": ["2024-09-23"],
        },
    }


def test_gate_blocks_without_manual_review_evidence() -> None:
    report = build_calibration_proposal_gate_report(_proposal())

    assert report["report_type"] == "effort_result_calibration_proposal_gate"
    assert report["gate_status"] == "needs_attention"
    assert report["ready_gate_count"] == 0
    assert report["blocked_gate_count"] == 2
    assert report["automatic_promotion_allowed"] is False
    assert report["production_change_allowed"] is False
    assert report["may_change_scoring"] is False
    assert report["may_change_ranking"] is False
    assert report["may_change_actionability"] is False
    assert report["may_activate_detector"] is False
    assert all(row["gate_status"] == GATE_BLOCKED_STATUS for row in report["target_gates"])
    assert "manual_review_status" in report["target_gates"][0]["missing_evidence_fields"]


def test_gate_can_mark_ready_for_separate_production_pr_review_only() -> None:
    report = build_calibration_proposal_gate_report(
        _proposal(), manual_review_evidence=_evidence(), min_reviewed_examples_per_target=5
    )

    assert report["gate_status"] == GATE_READY_STATUS
    assert report["ready_gate_count"] == 2
    assert report["blocked_gate_count"] == 0
    assert report["next_stage"] == "separate_production_pr_review"
    assert report["production_change_allowed"] is False
    assert report["requires_separate_production_pr"] is True
    assert all(row["gate_status"] == GATE_READY_STATUS for row in report["target_gates"])
    assert all(
        row["manual_review_status"] == APPROVED_MANUAL_REVIEW_STATUS
        for row in report["target_gates"]
    )


def test_gate_blocks_partial_evidence_and_records_failed_checks() -> None:
    evidence = _evidence()
    evidence["RESULT_GT_EFFORT"] = {
        "manual_review_status": "pending",
        "reviewer": "manual-reviewer",
        "review_date": "2026-09-12",
        "reviewed_examples": 2,
        "reviewed_symbols": ["COALINDIA.NS"],
        "reviewed_weeks": ["2024-03-18"],
    }

    report = build_calibration_proposal_gate_report(
        _proposal(), manual_review_evidence=evidence, min_reviewed_examples_per_target=5
    )
    first_gate = report["target_gates"][0]

    assert report["gate_status"] == "needs_attention"
    assert first_gate["gate_status"] == GATE_BLOCKED_STATUS
    assert "manual_review_status_approved" in first_gate["failed_gate_checks"]
    assert "minimum_examples_reviewed" in first_gate["failed_gate_checks"]


def test_gate_blocks_not_ready_source_proposal() -> None:
    proposal = _proposal()
    proposal["target_proposals"][0]["proposal_status"] = "blocked_pending_manual_review_inputs"

    report = build_calibration_proposal_gate_report(
        proposal, manual_review_evidence=_evidence()
    )

    assert report["target_gates"][0]["gate_status"] == GATE_BLOCKED_STATUS
    assert "proposal_ready" in report["target_gates"][0]["failed_gate_checks"]


def test_gate_renders_markdown_and_validates_threshold() -> None:
    report = build_calibration_proposal_gate_report(
        _proposal(), manual_review_evidence=_evidence()
    )
    markdown = render_calibration_proposal_gate_markdown(report)

    assert "# Effort/Result Calibration Proposal Gate" in markdown
    assert "Production change allowed: false" in markdown
    assert "Automatic promotion allowed: false" in markdown
    assert "RESULT_GT_EFFORT" in markdown

    with pytest.raises(ValueError, match="min_reviewed_examples_per_target"):
        build_calibration_proposal_gate_report(_proposal(), min_reviewed_examples_per_target=0)


def test_gate_cli_reads_json_inputs(tmp_path, monkeypatch) -> None:
    from audit.review_effort_result_calibration_proposal import main

    proposal_path = tmp_path / "proposal.json"
    evidence_path = tmp_path / "evidence.json"
    output_path = tmp_path / "gate.json"
    proposal_path.write_text(json.dumps(_proposal()), encoding="utf-8")
    evidence_path.write_text(json.dumps(_evidence()), encoding="utf-8")

    monkeypatch.setattr(
        "sys.argv",
        [
            "review_effort_result_calibration_proposal.py",
            str(proposal_path),
            "--manual-review-evidence",
            str(evidence_path),
            "--format",
            "json",
            "--output",
            str(output_path),
        ],
    )
    main()

    parsed = json.loads(output_path.read_text(encoding="utf-8"))
    assert parsed["gate_status"] == GATE_READY_STATUS
