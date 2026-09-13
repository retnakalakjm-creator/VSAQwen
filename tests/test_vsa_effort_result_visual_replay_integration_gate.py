from __future__ import annotations

import importlib.util
import json
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "audit"
    / "decide_effort_result_visual_replay_integration_gate.py"
)
spec = importlib.util.spec_from_file_location("visual_replay_gate", MODULE_PATH)
gate = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(gate)


def reviewed_case(**overrides: object) -> dict[str, object]:
    case: dict[str, object] = {
        "case_id": "LT.NS|2026-03-02|SUPPLY_PRESSURE",
        "source_sequence_id": "SUPPLY_PRESSURE|LT.NS|41",
        "target": "SUPPLY_PRESSURE",
        "symbol": "LT.NS",
        "event_week_beginning": "2026-03-02",
        "marker_labels": ["supply pressure"],
        "review_decision": "pass",
        "review_rationale": "Marker alignment and follow-through were manually confirmed.",
        "case_review_status": gate.PASSED_CASE_STATUS,
        "blockers": [],
        "manual_review_only": True,
        "automatic_promotion_allowed": False,
        "production_change_allowed": False,
        "may_change_scoring": False,
        "may_change_ranking": False,
        "may_change_actionability": False,
        "may_activate_detector": False,
        "may_change_scanner_state": False,
        "may_change_persistence": False,
        "may_change_broker_orders": False,
        "may_change_account_state": False,
        "may_change_api": False,
        "may_change_frontend": False,
    }
    case.update(overrides)
    return case


def reviewer_summary(**overrides: object) -> dict[str, object]:
    cases = list(overrides.pop("case_reviews", [reviewed_case()]))
    passed = sum(1 for case in cases if case.get("case_review_status") == gate.PASSED_CASE_STATUS)
    failed = sum(1 for case in cases if case.get("case_review_status") == gate.FAILED_CASE_STATUS)
    undecided = sum(
        1 for case in cases if case.get("case_review_status") == gate.NEEDS_ATTENTION_CASE_STATUS
    )
    report: dict[str, object] = {
        "report_type": gate.SOURCE_REPORT_TYPE,
        "report_schema_version": 1,
        "source_report_type": "effort_result_visual_replay_casebook",
        "source_casebook_status": "visual_replay_casebook_ready",
        "source_casebook_ready": True,
        "reviewed_case_count": len(cases),
        "passed_case_count": passed,
        "failed_case_count": failed,
        "undecided_case_count": undecided,
        "minimum_passed_cases": 1,
        "maximum_failed_cases": 0,
        "review_summary_status": gate.SOURCE_READY_STATUS,
        "review_summary_ready": True,
        "integration_candidate_ready": failed == 0 and undecided == 0 and passed >= 1,
        "blockers": [],
        "integration_blockers": [] if failed == 0 and passed >= 1 else ["failed_cases_exceed_threshold"],
        "case_reviews": cases,
        "next_stage": gate.SOURCE_NEXT_STAGE,
        "automatic_promotion_allowed": False,
        "audit_only": True,
        "reviewer_summary_only": True,
        "manual_review_only": True,
        "offline_replay_only": True,
        "production_change_allowed": False,
        "may_change_scoring": False,
        "may_change_ranking": False,
        "may_change_actionability": False,
        "may_activate_detector": False,
        "may_change_scanner_state": False,
        "may_change_persistence": False,
        "may_change_broker_orders": False,
        "may_change_account_state": False,
        "may_change_api": False,
        "may_change_frontend": False,
    }
    report.update(overrides)
    return report


def test_ready_summary_allows_only_separate_shadow_integration_gate_step() -> None:
    report = gate.decide_effort_result_visual_replay_integration_gate(reviewer_summary())

    assert report["report_type"] == gate.REPORT_TYPE
    assert report["gate_ready"] is True
    assert report["gate_decision"] == gate.READY_FOR_SHADOW_INTEGRATION_DECISION
    assert report["gate_status"] == gate.GATE_READY_STATUS
    assert report["allowed_next_step"] == "separate_shadow_dev_replay_workflow_integration_pr"
    assert report["automatic_promotion_allowed"] is False
    assert report["production_change_allowed"] is False
    assert report["may_change_scoring"] is False
    assert report["may_change_ranking"] is False
    assert report["may_change_actionability"] is False
    assert report["may_activate_detector"] is False
    assert report["may_change_api"] is False
    assert report["may_change_frontend"] is False
    assert "production_scoring_change" in report["disallowed_next_steps"]
    assert not report["blockers"]


def test_failed_review_case_blocks_shadow_integration_candidate() -> None:
    failed = reviewed_case(
        review_decision="fail",
        review_rationale="Follow-through did not confirm the marker.",
        case_review_status=gate.FAILED_CASE_STATUS,
    )
    summary = reviewer_summary(
        case_reviews=[failed],
        integration_candidate_ready=False,
        integration_blockers=["failed_cases_exceed_threshold"],
    )

    report = gate.decide_effort_result_visual_replay_integration_gate(summary)

    assert report["gate_ready"] is False
    assert report["gate_decision"] == gate.BLOCKED_BY_FAILED_CASES_DECISION
    assert "failed_cases_exceed_threshold" in report["blockers"]
    assert "failed_review_cases_present" in report["blockers"]


def test_missing_manual_review_blocks_gate() -> None:
    undecided = reviewed_case(
        review_decision="",
        review_rationale="",
        case_review_status=gate.NEEDS_ATTENTION_CASE_STATUS,
    )
    summary = reviewer_summary(
        case_reviews=[undecided],
        review_summary_status=gate.SOURCE_READY_STATUS,
        review_summary_ready=True,
        integration_candidate_ready=False,
        integration_blockers=["not_enough_passed_cases"],
    )

    report = gate.decide_effort_result_visual_replay_integration_gate(summary)

    assert report["gate_ready"] is False
    assert report["gate_decision"] == gate.BLOCKED_BY_MISSING_MANUAL_REVIEW_DECISION
    assert "undecided_review_cases_present" in report["blockers"]
    assert "case_review_boundary_or_status_blockers_present" in report["blockers"]


def test_truthy_production_boundary_blocks_gate() -> None:
    summary = reviewer_summary(production_change_allowed=True)

    report = gate.decide_effort_result_visual_replay_integration_gate(summary)

    assert report["gate_ready"] is False
    assert report["gate_decision"] == gate.BLOCKED_BY_PRODUCTION_BOUNDARY_DECISION
    assert "report_production_boundary_open" in report["blockers"]


def test_insufficient_passed_cases_blocks_gate() -> None:
    summary = reviewer_summary()

    report = gate.decide_effort_result_visual_replay_integration_gate(summary, min_passed_cases=2)

    assert report["gate_ready"] is False
    assert report["gate_decision"] == gate.BLOCKED_BY_INSUFFICIENT_PASSED_CASES_DECISION
    assert "not_enough_passed_cases" in report["blockers"]


def test_source_mismatch_is_not_ready() -> None:
    summary = reviewer_summary(report_type="wrong_report_type")

    report = gate.decide_effort_result_visual_replay_integration_gate(summary)

    assert report["gate_ready"] is False
    assert report["gate_decision"] == gate.NOT_READY_DECISION
    assert "source_report_type_mismatch" in report["blockers"]


def test_markdown_renders_decision_and_boundaries() -> None:
    report = gate.decide_effort_result_visual_replay_integration_gate(reviewer_summary())
    markdown = gate.render_effort_result_visual_replay_integration_gate_markdown(report)

    assert "# Effort/Result Visual Replay Integration Gate" in markdown
    assert "`ready_for_shadow_integration`" in markdown
    assert "Production change allowed: false" in markdown
    assert "Requires separate shadow integration PR: true" in markdown
    assert "production_scoring_change" in markdown


def test_cli_writes_json_and_markdown(tmp_path: Path) -> None:
    source = tmp_path / "summary.json"
    output_json = tmp_path / "gate.json"
    output_md = tmp_path / "gate.md"
    source.write_text(json.dumps(reviewer_summary()), encoding="utf-8")

    assert gate.main([str(source), "--output", str(output_json)]) == 0
    parsed = json.loads(output_json.read_text(encoding="utf-8"))
    assert parsed["gate_decision"] == gate.READY_FOR_SHADOW_INTEGRATION_DECISION

    assert gate.main([str(source), "--format", "markdown", "--output", str(output_md)]) == 0
    assert "Effort/Result Visual Replay Integration Gate" in output_md.read_text(encoding="utf-8")


def test_static_guardrails_keep_module_audit_only() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")

    assert "requests" not in source
    assert "httpx" not in source
    assert "urllib.request" not in source
    assert "subprocess" not in source
    assert "openai" not in source.lower()
    assert "place_order" in source
    assert '"production_change_allowed": False' in source
    assert '"may_change_scoring": False' in source
    assert '"may_change_api": False' in source
