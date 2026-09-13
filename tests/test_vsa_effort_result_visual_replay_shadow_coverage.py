import json
import subprocess
import sys
from pathlib import Path

from audit.run_effort_result_visual_replay_shadow_coverage import (
    BLOCKED_DECISION,
    COVERAGE_BLOCKED_STATUS,
    COVERAGE_READY_STATUS,
    READY_DECISION,
    REPORT_TYPE,
    REQUIRED_REVIEW_LANES,
    plan_effort_result_visual_replay_shadow_coverage,
    render_effort_result_visual_replay_shadow_coverage_markdown,
)


def _ready_manifest():
    return {
        "report_type": "effort_result_visual_replay_shadow_workflow_manifest",
        "report_schema_version": 1,
        "workflow_status": "visual_replay_shadow_workflow_manifest_ready",
        "workflow_decision": "ready_to_run_shadow_dev_replay_workflow",
        "shadow_workflow_ready": True,
        "allowed_next_step": "run_shadow_dev_visual_replay_workflow",
        "blockers": [],
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


def _ready_cases():
    return [
        {
            "case_id": "LT.NS|2025-02-24|RESULT_GT_EFFORT",
            "symbol": "LT.NS",
            "event_week_beginning": "2025-02-24",
            "target": "RESULT_GT_EFFORT",
            "offline_dataset_fixture": "LT_2025-02-24.txt",
            "expected_marker_labels": ["effort_result_divergence", "structural_weakening"],
            "review_lanes": list(REQUIRED_REVIEW_LANES),
            "notes": "Validate pre-event context and follow-through on LT 2025 case.",
        },
        {
            "case_id": "LT.NS|2026-03-02|RESULT_GT_EFFORT",
            "symbol": "LT.NS",
            "event_week_beginning": "2026-03-02",
            "target": "RESULT_GT_EFFORT",
            "offline_dataset_fixture": "LT_2026-03-02.txt",
            "expected_marker_labels": ["effort_result_divergence", "follow_through_check"],
            "review_lanes": list(REQUIRED_REVIEW_LANES),
            "notes": "Validate marker alignment and follow-through on LT 2026 case.",
        },
    ]


def test_ready_manifest_and_lt_cases_create_shadow_coverage_plan():
    report = plan_effort_result_visual_replay_shadow_coverage(_ready_manifest(), _ready_cases())

    assert report["report_type"] == REPORT_TYPE
    assert report["coverage_status"] == COVERAGE_READY_STATUS
    assert report["coverage_decision"] == READY_DECISION
    assert report["shadow_coverage_ready"] is True
    assert report["allowed_next_step"] == "perform_manual_shadow_replay_case_review"
    assert report["required_symbols"] == ["LT.NS"]
    assert report["selected_case_count"] == 2
    assert report["ready_case_count"] == 2
    assert report["blocked_case_count"] == 0
    assert report["blockers"] == []


def test_plan_preserves_manual_offline_production_boundary():
    report = plan_effort_result_visual_replay_shadow_coverage(_ready_manifest(), _ready_cases())

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


def test_blocks_non_ready_shadow_workflow_manifest():
    manifest = _ready_manifest()
    manifest["workflow_decision"] = "blocked_from_shadow_dev_replay_workflow"
    manifest["shadow_workflow_ready"] = False

    report = plan_effort_result_visual_replay_shadow_coverage(manifest, _ready_cases())

    assert report["coverage_status"] == COVERAGE_BLOCKED_STATUS
    assert report["coverage_decision"] == BLOCKED_DECISION
    assert report["shadow_coverage_ready"] is False
    assert "source_workflow_decision_not_ready" in report["blockers"]
    assert "source_shadow_workflow_ready_false" in report["blockers"]


def test_blocks_missing_required_case_fields_and_lanes():
    cases = _ready_cases()
    cases[0]["offline_dataset_fixture"] = ""
    cases[0]["review_lanes"] = ["marker_alignment_recheck"]

    report = plan_effort_result_visual_replay_shadow_coverage(_ready_manifest(), cases)

    assert report["shadow_coverage_ready"] is False
    assert report["blocked_case_count"] == 1
    assert "coverage_case_blockers_present" in report["blockers"]
    blocked_case = report["coverage_cases"][0]
    assert "missing_offline_dataset_fixture" in blocked_case["blockers"]
    assert "missing_required_review_lanes" in blocked_case["blockers"]


def test_blocks_unsafe_manifest_and_case_fields():
    manifest = _ready_manifest()
    manifest["production_change_allowed"] = True
    cases = _ready_cases()
    cases[0]["automatic_promotion_allowed"] = True

    report = plan_effort_result_visual_replay_shadow_coverage(manifest, cases)

    assert report["shadow_coverage_ready"] is False
    assert "source_production_boundary_open" in report["blockers"]
    assert "coverage_case_blockers_present" in report["blockers"]
    assert "case_production_boundary_open" in report["coverage_cases"][0]["blockers"]


def test_blocks_when_minimum_ready_case_count_not_met():
    report = plan_effort_result_visual_replay_shadow_coverage(
        _ready_manifest(), _ready_cases(), min_cases=3
    )

    assert report["shadow_coverage_ready"] is False
    assert "not_enough_ready_coverage_cases" in report["blockers"]


def test_symbol_filter_selects_only_requested_offline_cases():
    report = plan_effort_result_visual_replay_shadow_coverage(
        _ready_manifest(), _ready_cases(), required_symbols=["OTHER.NS"], min_cases=1
    )

    assert report["shadow_coverage_ready"] is False
    assert report["selected_case_count"] == 0
    assert "no_matching_symbol_cases" in report["blockers"]


def test_markdown_renders_coverage_rules_and_cases():
    report = plan_effort_result_visual_replay_shadow_coverage(_ready_manifest(), _ready_cases())
    markdown = render_effort_result_visual_replay_shadow_coverage_markdown(report)

    assert "# Effort/Result Visual Replay Shadow Coverage Plan" in markdown
    assert "ready_for_manual_shadow_replay_coverage_review" in markdown
    assert "LT_2025-02-24.txt" in markdown
    assert "marker_alignment_recheck" in markdown
    assert "A separate production PR is required" in markdown


def test_cli_writes_json_and_markdown(tmp_path):
    manifest_path = tmp_path / "shadow_workflow.json"
    cases_path = tmp_path / "coverage_cases.json"
    json_output = tmp_path / "coverage.json"
    markdown_output = tmp_path / "coverage.md"
    manifest_path.write_text(json.dumps(_ready_manifest()), encoding="utf-8")
    cases_path.write_text(json.dumps(_ready_cases()), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "-m",
            "audit.run_effort_result_visual_replay_shadow_coverage",
            str(manifest_path),
            str(cases_path),
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
            "audit.run_effort_result_visual_replay_shadow_coverage",
            str(manifest_path),
            str(cases_path),
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
    assert rendered_json["shadow_coverage_ready"] is True
    assert "Coverage Cases" in rendered_markdown


def test_source_contains_no_live_fetch_or_storage_side_effects():
    source = Path("audit/run_effort_result_visual_replay_shadow_coverage.py").read_text(
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
