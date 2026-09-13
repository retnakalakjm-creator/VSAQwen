import json
import subprocess
import sys
from pathlib import Path

from audit.prepare_effort_result_visual_replay_shadow_workflow import (
    BLOCKED_DECISION,
    READY_DECISION,
    REPORT_TYPE,
    WORKFLOW_BLOCKED_STATUS,
    WORKFLOW_READY_STATUS,
    prepare_effort_result_visual_replay_shadow_workflow,
    render_effort_result_visual_replay_shadow_workflow_markdown,
)


def _ready_gate_report():
    return {
        "report_type": "effort_result_visual_replay_integration_gate",
        "report_schema_version": 1,
        "source_report_type": "effort_result_visual_replay_reviewer_summary",
        "source_review_summary_status": "reviewer_pass_fail_summary_ready",
        "source_review_summary_ready": True,
        "source_integration_candidate_ready": True,
        "reviewed_case_count": 2,
        "passed_case_count": 2,
        "failed_case_count": 0,
        "undecided_case_count": 0,
        "gate_status": "visual_replay_shadow_integration_gate_ready",
        "gate_decision": "ready_for_shadow_integration",
        "gate_ready": True,
        "blockers": [],
        "case_review_blockers": [],
        "allowed_next_step": "separate_shadow_dev_replay_workflow_integration_pr",
        "disallowed_next_steps": [
            "production_scoring_change",
            "production_ranking_change",
            "production_actionability_change",
            "detector_activation",
            "scanner_state_mutation",
            "live_data_api_wiring",
            "alerting_or_order_execution",
        ],
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


def test_ready_gate_creates_shadow_workflow_manifest():
    report = prepare_effort_result_visual_replay_shadow_workflow(_ready_gate_report())

    assert report["report_type"] == REPORT_TYPE
    assert report["workflow_status"] == WORKFLOW_READY_STATUS
    assert report["workflow_decision"] == READY_DECISION
    assert report["shadow_workflow_ready"] is True
    assert report["allowed_next_step"] == "run_shadow_dev_visual_replay_workflow"
    assert report["dev_route"] == "/replay/effort-result"
    assert report["required_symbols"] == ["LT.NS"]
    assert report["blockers"] == []
    assert "open_dev_only_visual_replay_preview" in report["shadow_workflow_stages"]
    assert "manual_visual_evidence_export" in report["allowed_shadow_surfaces"]
    assert "production_signal_persistence" in report["disallowed_production_surfaces"]


def test_manifest_preserves_manual_offline_production_boundary():
    report = prepare_effort_result_visual_replay_shadow_workflow(_ready_gate_report())

    assert report["audit_only"] is True
    assert report["shadow_workflow_manifest_only"] is True
    assert report["manual_review_only"] is True
    assert report["offline_replay_only"] is True
    assert report["dev_preview_route_reference_only"] is True
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


def test_blocks_non_ready_gate_decision():
    source = _ready_gate_report()
    source["gate_decision"] = "blocked_by_failed_cases"
    source["gate_ready"] = False

    report = prepare_effort_result_visual_replay_shadow_workflow(source)

    assert report["workflow_status"] == WORKFLOW_BLOCKED_STATUS
    assert report["workflow_decision"] == BLOCKED_DECISION
    assert report["shadow_workflow_ready"] is False
    assert "source_gate_decision_not_ready" in report["blockers"]
    assert "source_gate_ready_false" in report["blockers"]


def test_blocks_source_gate_blockers_and_case_review_blockers():
    source = _ready_gate_report()
    source["blockers"] = ["failed_review_cases_present"]
    source["case_review_blockers"] = [
        {"case_id": "LT.NS|2025-03-03|RESULT_GT_EFFORT", "blockers": ["case_has_existing_review_blockers"]}
    ]

    report = prepare_effort_result_visual_replay_shadow_workflow(source)

    assert report["shadow_workflow_ready"] is False
    assert "source_gate_blockers_present" in report["blockers"]
    assert "source_case_review_blockers_present" in report["blockers"]


def test_blocks_unsafe_production_boundary_fields():
    source = _ready_gate_report()
    source["production_change_allowed"] = True

    report = prepare_effort_result_visual_replay_shadow_workflow(source)

    assert report["shadow_workflow_ready"] is False
    assert "source_production_boundary_open" in report["blockers"]


def test_blocks_invalid_dev_route_and_missing_symbols():
    report = prepare_effort_result_visual_replay_shadow_workflow(
        _ready_gate_report(), required_symbols=[], dev_route="/scanner/live"
    )

    assert report["shadow_workflow_ready"] is False
    assert "missing_required_symbols" in report["blockers"]
    assert "dev_route_not_replay_preview_route" in report["blockers"]


def test_markdown_renders_ready_manifest_rules():
    report = prepare_effort_result_visual_replay_shadow_workflow(_ready_gate_report())
    markdown = render_effort_result_visual_replay_shadow_workflow_markdown(report)

    assert "# Effort/Result Visual Replay Shadow Workflow Manifest" in markdown
    assert "ready_to_run_shadow_dev_replay_workflow" in markdown
    assert "open_dev_only_visual_replay_preview" in markdown
    assert "manual_visual_evidence_export" in markdown
    assert "production_signal_persistence" in markdown
    assert "A separate production PR is required" in markdown


def test_cli_writes_json_and_markdown(tmp_path):
    source_path = tmp_path / "gate.json"
    json_output = tmp_path / "shadow_workflow.json"
    markdown_output = tmp_path / "shadow_workflow.md"
    source_path.write_text(json.dumps(_ready_gate_report()), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "-m",
            "audit.prepare_effort_result_visual_replay_shadow_workflow",
            str(source_path),
            "--output",
            str(json_output),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "audit.prepare_effort_result_visual_replay_shadow_workflow",
            str(source_path),
            "--format",
            "markdown",
            "--output",
            str(markdown_output),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
    )

    rendered_json = json.loads(json_output.read_text(encoding="utf-8"))
    rendered_markdown = markdown_output.read_text(encoding="utf-8")
    assert rendered_json["report_type"] == REPORT_TYPE
    assert rendered_json["shadow_workflow_ready"] is True
    assert "Shadow Workflow Stages" in rendered_markdown


def test_source_contains_no_live_fetch_or_storage_side_effects():
    source = Path("audit/prepare_effort_result_visual_replay_shadow_workflow.py").read_text(
        encoding="utf-8"
    )

    forbidden = [
        "requests.",
        "urllib.request",
        "httpx.",
        "fetch(",
        "localStorage",
        "sessionStorage",
        "emit_alert(",
        "place_order(",
        "activate_detector(",
    ]
    assert not any(token in source for token in forbidden)
