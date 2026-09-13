import json
import subprocess
import sys
from pathlib import Path

from audit.run_effort_result_visual_replay_shadow_coverage import (
    READY_DECISION,
    REPORT_TYPE,
    plan_effort_result_visual_replay_shadow_coverage,
    render_effort_result_visual_replay_shadow_coverage_markdown,
)

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "audit" / "fixtures"
LT_CASES_FIXTURE = FIXTURE_DIR / "effort_result_visual_replay_shadow_coverage_lt_cases.json"
LT_PLAN_FIXTURE = FIXTURE_DIR / "effort_result_visual_replay_shadow_coverage_lt_plan.json"

REQUIRED_REVIEW_LANES = {
    "marker_alignment_recheck",
    "pre_event_context_recheck",
    "post_event_follow_through_recheck",
    "counterfactual_quality_check",
    "vsa_smc_quality_judgment",
    "evidence_artifact_traceability",
}


def _ready_shadow_workflow_manifest():
    return {
        "report_type": "effort_result_visual_replay_shadow_workflow_manifest",
        "report_schema_version": 1,
        "source_report_type": "effort_result_visual_replay_integration_gate",
        "source_gate_status": "visual_replay_shadow_integration_gate_ready",
        "source_gate_decision": "ready_for_shadow_integration",
        "source_gate_ready": True,
        "source_allowed_next_step": "separate_shadow_dev_replay_workflow_integration_pr",
        "reviewed_case_count": 2,
        "passed_case_count": 2,
        "failed_case_count": 0,
        "undecided_case_count": 0,
        "required_symbols": ["LT.NS"],
        "dev_route": "/replay/effort-result",
        "workflow_status": "visual_replay_shadow_workflow_manifest_ready",
        "workflow_decision": "ready_to_run_shadow_dev_replay_workflow",
        "shadow_workflow_ready": True,
        "blockers": [],
        "case_review_blockers": [],
        "shadow_workflow_stages": [
            "confirm_integration_gate_ready",
            "load_offline_shadow_replay_dataset_fixture",
            "open_dev_only_visual_replay_preview",
            "collect_manual_visual_evidence_draft",
            "compile_visual_replay_evidence",
            "run_visual_replay_casebook",
            "summarize_manual_reviewer_pass_fail_decisions",
            "rerun_visual_replay_integration_gate",
        ],
        "allowed_shadow_surfaces": [
            "dev_only_replay_preview_route_reference",
            "offline_dataset_fixture_reference",
            "manual_visual_evidence_export",
            "audit_evidence_compiler_report",
            "audit_casebook_report",
            "audit_reviewer_summary_report",
            "audit_integration_gate_report",
        ],
        "disallowed_production_surfaces": [
            "live_market_data_fetch",
            "scanner_state_mutation",
            "production_signal_persistence",
            "production_api_wiring",
            "production_frontend_activation",
            "detector_activation",
            "scoring_change",
            "ranking_change",
            "actionability_change",
            "alerting",
            "order_execution",
        ],
        "allowed_next_step": "run_shadow_dev_visual_replay_workflow",
        "manual_revalidation_required_after_run": True,
        "production_pr_required_after_shadow_validation": True,
        "automatic_promotion_allowed": False,
        "audit_only": True,
        "shadow_workflow_manifest_only": True,
        "manual_review_only": True,
        "offline_replay_only": True,
        "dev_preview_route_reference_only": True,
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
        "requires_visual_replay_integration_gate": True,
        "requires_offline_shadow_dataset_fixture": True,
        "requires_manual_evidence_export": True,
        "requires_separate_production_pr": True,
    }


def _load_lt_cases():
    return json.loads(LT_CASES_FIXTURE.read_text(encoding="utf-8"))


def test_lt_shadow_review_package_fixture_is_ready():
    report = plan_effort_result_visual_replay_shadow_coverage(
        _ready_shadow_workflow_manifest(), _load_lt_cases(), min_cases=2
    )

    assert report["report_type"] == REPORT_TYPE
    assert report["coverage_decision"] == READY_DECISION
    assert report["shadow_coverage_ready"] is True
    assert report["selected_case_count"] == 2
    assert report["ready_case_count"] == 2
    assert report["blocked_case_count"] == 0
    assert report["blockers"] == []
    assert {case["case_id"] for case in report["coverage_cases"]} == {
        "LT.NS|2025-02-24|STRUCTURAL_WEAKENING",
        "LT.NS|2026-03-02|RESULT_GT_EFFORT",
    }


def test_lt_shadow_review_package_requires_all_manual_review_lanes():
    report = plan_effort_result_visual_replay_shadow_coverage(
        _ready_shadow_workflow_manifest(), _load_lt_cases(), min_cases=2
    )

    assert set(report["required_review_lanes"]) == REQUIRED_REVIEW_LANES
    for case in report["coverage_cases"]:
        assert set(case["review_lanes"]) == REQUIRED_REVIEW_LANES
        assert case["missing_review_lanes"] == []
        assert case["coverage_case_ready"] is True


def test_checked_in_plan_fixture_matches_generated_lt_review_package():
    generated = plan_effort_result_visual_replay_shadow_coverage(
        _ready_shadow_workflow_manifest(), _load_lt_cases(), min_cases=2
    )
    checked_in = json.loads(LT_PLAN_FIXTURE.read_text(encoding="utf-8"))

    assert checked_in == generated


def test_markdown_review_package_names_lt_cases_and_safety_rules():
    report = plan_effort_result_visual_replay_shadow_coverage(
        _ready_shadow_workflow_manifest(), _load_lt_cases(), min_cases=2
    )
    markdown = render_effort_result_visual_replay_shadow_coverage_markdown(report)

    assert "# Effort/Result Visual Replay Shadow Coverage Plan" in markdown
    assert "LT.NS|2025-02-24|STRUCTURAL_WEAKENING" in markdown
    assert "LT.NS|2026-03-02|RESULT_GT_EFFORT" in markdown
    assert "marker_alignment_recheck" in markdown
    assert "Production change allowed: false" in markdown
    assert "A separate production PR is required" in markdown


def test_cli_can_regenerate_checked_in_lt_plan_fixture(tmp_path):
    manifest_path = tmp_path / "shadow_workflow_manifest.json"
    output_path = tmp_path / "coverage_plan.json"
    manifest_path.write_text(json.dumps(_ready_shadow_workflow_manifest()), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "-m",
            "audit.run_effort_result_visual_replay_shadow_coverage",
            str(manifest_path),
            str(LT_CASES_FIXTURE),
            "--min-cases",
            "2",
            "--output",
            str(output_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
    )

    rendered = json.loads(output_path.read_text(encoding="utf-8"))
    checked_in = json.loads(LT_PLAN_FIXTURE.read_text(encoding="utf-8"))
    assert rendered == checked_in


def test_shadow_review_package_preserves_production_boundary():
    report = plan_effort_result_visual_replay_shadow_coverage(
        _ready_shadow_workflow_manifest(), _load_lt_cases(), min_cases=2
    )

    assert report["audit_only"] is True
    assert report["shadow_coverage_plan_only"] is True
    assert report["manual_review_only"] is True
    assert report["offline_replay_only"] is True
    assert report["production_change_allowed"] is False
    assert report["automatic_promotion_allowed"] is False
    assert report["may_change_scoring"] is False
    assert report["may_change_ranking"] is False
    assert report["may_change_actionability"] is False
    assert report["may_activate_detector"] is False
    assert report["may_change_scanner_state"] is False
    assert report["may_change_api"] is False
    assert report["may_change_frontend"] is False
    assert report["requires_separate_production_pr"] is True
    assert report["allowed_next_step"] == "perform_manual_shadow_replay_case_review"
