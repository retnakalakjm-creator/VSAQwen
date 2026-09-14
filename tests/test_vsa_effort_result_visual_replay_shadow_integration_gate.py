import json
import subprocess
import sys
from pathlib import Path

import pytest

from audit.run_effort_result_visual_replay_shadow_integration_gate import (
    BLOCKED_STATUS,
    PASS,
    READY_STATUS,
    REPORT_TYPE,
    run_effort_result_visual_replay_shadow_integration_gate,
    render_effort_result_visual_replay_shadow_integration_gate_markdown,
)

FIXTURES = Path("audit/fixtures")
PENDING_INPUT = FIXTURES / "effort_result_visual_replay_shadow_integration_gate_input_pending.json"
PENDING_GATE = FIXTURES / "effort_result_visual_replay_shadow_integration_gate_pending.json"


def _ready_input_report():
    cases = [
        {
            "case_id": "LT.NS|2025-02-24|STRUCTURAL_WEAKENING",
            "symbol": "LT.NS",
            "event_week_beginning": "2025-02-24",
            "target": "STRUCTURAL_WEAKENING",
            "review_outcome": PASS,
            "reviewer": "manual-reviewer",
            "reviewed_at": "2026-09-13T18:30:00Z",
            "evidence_artifact": "audit/evidence/LT_2025-02-24.md",
            "gate_case_ready": True,
            "integration_blocked": False,
            "blockers": [],
            "automatic_promotion_allowed": False,
            "production_change_allowed": False,
        },
        {
            "case_id": "LT.NS|2026-03-02|RESULT_GT_EFFORT",
            "symbol": "LT.NS",
            "event_week_beginning": "2026-03-02",
            "target": "RESULT_GT_EFFORT",
            "review_outcome": PASS,
            "reviewer": "manual-reviewer",
            "reviewed_at": "2026-09-13T18:35:00Z",
            "evidence_artifact": "audit/evidence/LT_2026-03-02.md",
            "gate_case_ready": True,
            "integration_blocked": False,
            "blockers": [],
            "automatic_promotion_allowed": False,
            "production_change_allowed": False,
        },
    ]
    return {
        "report_type": "effort_result_visual_replay_shadow_integration_gate_input",
        "report_schema_version": 1,
        "integration_gate_input_status": "visual_replay_shadow_integration_gate_input_ready",
        "integration_gate_input_decision": "ready_to_run_shadow_visual_replay_integration_gate",
        "integration_gate_input_ready": True,
        "shadow_validation_passed": True,
        "downstream_integration_blocked": False,
        "allowed_next_step": "run_shadow_visual_replay_integration_gate",
        "required_symbols": ["LT.NS"],
        "minimum_gate_cases": 2,
        "selected_case_count": 2,
        "ready_case_count": 2,
        "passed_case_count": 2,
        "failed_case_count": 0,
        "undecided_case_count": 0,
        "blockers": [],
        "gate_cases": cases,
        "audit_only": True,
        "manual_review_only": True,
        "offline_replay_only": True,
        "production_change_allowed": False,
        "automatic_promotion_allowed": False,
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


def test_pending_fixture_blocks_shadow_integration_gate():
    source = json.loads(PENDING_INPUT.read_text(encoding="utf-8"))
    report = run_effort_result_visual_replay_shadow_integration_gate(source)

    assert report["report_type"] == REPORT_TYPE
    assert report["shadow_integration_gate_status"] == BLOCKED_STATUS
    assert report["shadow_integration_gate_passed"] is False
    assert report["shadow_validation_passed"] is False
    assert report["downstream_production_blocked"] is True
    assert report["accepted_case_count"] == 0
    assert report["undecided_case_count"] == 2
    assert "undecided_gate_cases_present" in report["blockers"]
    assert report["allowed_next_step"] == "resolve_shadow_integration_gate_blockers"


def test_checked_in_pending_gate_fixture_matches_generated_report():
    source = json.loads(PENDING_INPUT.read_text(encoding="utf-8"))
    expected = json.loads(PENDING_GATE.read_text(encoding="utf-8"))

    assert run_effort_result_visual_replay_shadow_integration_gate(source) == expected


def test_all_pass_gate_input_passes_shadow_gate_but_not_production():
    report = run_effort_result_visual_replay_shadow_integration_gate(_ready_input_report())

    assert report["shadow_integration_gate_status"] == READY_STATUS
    assert report["shadow_integration_gate_passed"] is True
    assert report["shadow_validation_passed"] is True
    assert report["accepted_case_count"] == 2
    assert report["failed_case_count"] == 0
    assert report["undecided_case_count"] == 0
    assert report["blockers"] == []
    assert report["allowed_next_step"] == "open_separate_production_pr_after_manual_approval"
    assert report["downstream_production_blocked"] is True
    assert report["automatic_promotion_allowed"] is False
    assert report["production_change_allowed"] is False


def test_failed_case_blocks_shadow_gate():
    source = _ready_input_report()
    source["gate_cases"][1]["review_outcome"] = "fail"
    source["gate_cases"][1]["integration_blocked"] = True
    source["gate_cases"][1]["blockers"] = ["failed_review_outcome"]
    source["passed_case_count"] = 1
    source["failed_case_count"] = 1
    source["shadow_validation_passed"] = False
    source["downstream_integration_blocked"] = True

    report = run_effort_result_visual_replay_shadow_integration_gate(source)

    assert report["shadow_integration_gate_passed"] is False
    assert "source_shadow_validation_not_passed" in report["blockers"]
    assert "source_downstream_integration_blocked" in report["blockers"]
    assert "failed_gate_cases_present" in report["blockers"]
    assert report["integration_cases"][1]["production_blocked"] is True


def test_unsafe_source_boundary_blocks_gate():
    source = _ready_input_report()
    source["production_change_allowed"] = True

    report = run_effort_result_visual_replay_shadow_integration_gate(source)

    assert report["shadow_integration_gate_passed"] is False
    assert "source_production_boundary_open" in report["blockers"]


def test_unsafe_case_boundary_blocks_gate_case():
    source = _ready_input_report()
    source["gate_cases"][0]["automatic_promotion_allowed"] = True

    report = run_effort_result_visual_replay_shadow_integration_gate(source)

    assert report["shadow_integration_gate_passed"] is False
    assert "shadow_gate_case_blockers_present" in report["blockers"]
    assert "case_production_boundary_open" in report["integration_cases"][0]["blockers"]


def test_symbol_filter_requires_selected_cases():
    report = run_effort_result_visual_replay_shadow_integration_gate(
        _ready_input_report(),
        required_symbols=["SBIN.NS"],
    )

    assert report["selected_case_count"] == 0
    assert "missing_selected_gate_cases" in report["blockers"]


def test_min_gate_cases_must_be_positive():
    with pytest.raises(ValueError, match="min_gate_cases must be positive"):
        run_effort_result_visual_replay_shadow_integration_gate(
            _ready_input_report(),
            min_gate_cases=0,
        )


def test_markdown_renders_gate_rules_and_blockers():
    report = run_effort_result_visual_replay_shadow_integration_gate(
        json.loads(PENDING_INPUT.read_text(encoding="utf-8"))
    )
    markdown = render_effort_result_visual_replay_shadow_integration_gate_markdown(report)

    assert "Effort/Result Visual Replay Shadow Integration Gate" in markdown
    assert "blocked_from_shadow_visual_replay_validation" in markdown
    assert "undecided_gate_cases_present" in markdown
    assert "separate production PR" in markdown
    assert "LT.NS|2026-03-02|RESULT_GT_EFFORT" in markdown


def test_cli_writes_pending_json_and_markdown(tmp_path):
    json_output = tmp_path / "gate.json"
    markdown_output = tmp_path / "gate.md"

    subprocess.run(
        [
            sys.executable,
            "-m",
            "audit.run_effort_result_visual_replay_shadow_integration_gate",
            str(PENDING_INPUT),
            "--output",
            str(json_output),
        ],
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "audit.run_effort_result_visual_replay_shadow_integration_gate",
            str(PENDING_INPUT),
            "--format",
            "markdown",
            "--output",
            str(markdown_output),
        ],
        check=True,
    )

    assert json.loads(json_output.read_text(encoding="utf-8")) == json.loads(
        PENDING_GATE.read_text(encoding="utf-8")
    )
    assert "Shadow integration gate passed: false" in markdown_output.read_text(encoding="utf-8")


def test_source_contains_no_live_fetch_or_storage_side_effects():
    source = Path("audit/run_effort_result_visual_replay_shadow_integration_gate.py").read_text(
        encoding="utf-8"
    )

    forbidden_tokens = [
        "requests.",
        "yfinance",
        "sqlite3.connect",
        "openpyxl",
        ".to_sql",
        "insert into",
        "update scanner",
        "delete from",
        "fetch_live",
        "place" + "_" + "order",
        "emit" + "_" + "alert",
    ]
    lowered = source.lower()
    for token in forbidden_tokens:
        assert token not in lowered
