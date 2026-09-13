import json
import subprocess
import sys
from pathlib import Path

import pytest

from audit.decide_effort_result_visual_replay_shadow_integration_gate_input import (
    BLOCKED_STATUS,
    FAIL,
    PASS,
    READY_STATUS,
    REPORT_TYPE,
    prepare_effort_result_visual_replay_shadow_integration_gate_input,
    render_effort_result_visual_replay_shadow_integration_gate_input_markdown,
)

FIXTURES = Path(__file__).resolve().parents[1] / "audit" / "fixtures"
PENDING_FIXTURE = FIXTURES / "effort_result_visual_replay_shadow_integration_gate_input_pending.json"
MODULE = Path(__file__).resolve().parents[1] / "audit" / "decide_effort_result_visual_replay_shadow_integration_gate_input.py"


def _case(case_id: str, week: str, target: str, outcome: str = PASS) -> dict[str, object]:
    return {
        "case_id": case_id,
        "symbol": "LT.NS",
        "event_week_beginning": week,
        "target": target,
        "review_outcome": outcome,
        "reviewer": "manual-reviewer",
        "reviewed_at": "2026-09-13T18:30:00Z",
        "evidence_artifact": f"audit/evidence/{case_id}.json",
        "reviewer_case_ready": True,
        "integration_blocked": outcome != PASS,
        "blockers": [] if outcome == PASS else ["failed_review_outcome"],
        "audit_only": True,
        "reviewer_summary_report_only": True,
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


def _ready_reviewer_summary() -> dict[str, object]:
    return {
        "report_type": "effort_result_visual_replay_shadow_reviewer_summary_report",
        "reviewer_summary_status": "visual_replay_shadow_reviewer_summary_ready",
        "reviewer_summary_decision": "ready_for_shadow_visual_replay_integration_gate",
        "reviewer_summary_ready": True,
        "shadow_validation_passed": True,
        "downstream_integration_blocked": False,
        "allowed_next_step": "run_shadow_visual_replay_integration_gate",
        "blockers": [],
        "case_summaries": [
            _case("LT.NS|2025-02-24|STRUCTURAL_WEAKENING", "2025-02-24", "STRUCTURAL_WEAKENING"),
            _case("LT.NS|2026-03-02|RESULT_GT_EFFORT", "2026-03-02", "RESULT_GT_EFFORT"),
        ],
        "audit_only": True,
        "reviewer_summary_report_only": True,
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


def test_all_pass_reviewer_summary_becomes_integration_gate_input_ready():
    report = prepare_effort_result_visual_replay_shadow_integration_gate_input(_ready_reviewer_summary())

    assert report["report_type"] == REPORT_TYPE
    assert report["integration_gate_input_status"] == READY_STATUS
    assert report["integration_gate_input_ready"] is True
    assert report["shadow_validation_passed"] is True
    assert report["downstream_integration_blocked"] is False
    assert report["allowed_next_step"] == "run_shadow_visual_replay_integration_gate"
    assert report["passed_case_count"] == 2
    assert report["failed_case_count"] == 0
    assert report["undecided_case_count"] == 0
    assert report["automatic_promotion_allowed"] is False
    assert report["production_change_allowed"] is False


def test_failed_reviewer_summary_blocks_integration_gate_input():
    source = _ready_reviewer_summary()
    source["shadow_validation_passed"] = False
    source["downstream_integration_blocked"] = True
    source["reviewer_summary_decision"] = "blocked_by_failed_shadow_visual_replay_cases"
    source["allowed_next_step"] = "resolve_failed_shadow_visual_replay_cases"
    source["case_summaries"] = [
        _case("LT.NS|2025-02-24|STRUCTURAL_WEAKENING", "2025-02-24", "STRUCTURAL_WEAKENING", PASS),
        _case("LT.NS|2026-03-02|RESULT_GT_EFFORT", "2026-03-02", "RESULT_GT_EFFORT", FAIL),
    ]

    report = prepare_effort_result_visual_replay_shadow_integration_gate_input(source)

    assert report["integration_gate_input_status"] == BLOCKED_STATUS
    assert report["integration_gate_input_ready"] is False
    assert report["failed_case_count"] == 1
    assert "source_shadow_validation_not_passed" in report["blockers"]
    assert "failed_gate_cases_present" in report["blockers"]
    assert report["allowed_next_step"] == "resolve_shadow_integration_gate_input_blockers"


def test_pending_fixture_stays_blocked_until_manual_evidence_exists():
    report = json.loads(PENDING_FIXTURE.read_text(encoding="utf-8"))

    assert report["integration_gate_input_status"] == BLOCKED_STATUS
    assert report["integration_gate_input_ready"] is False
    assert report["undecided_case_count"] == 2
    assert "undecided_gate_cases_present" in report["blockers"]
    assert all(case["gate_case_ready"] is False for case in report["gate_cases"])


def test_pending_fixture_matches_generated_report_from_pending_reviewer_summary():
    pending_reviewer_summary = json.loads(
        (FIXTURES / "effort_result_visual_replay_shadow_reviewer_summary_pending.json").read_text(
            encoding="utf-8"
        )
    )
    expected = json.loads(PENDING_FIXTURE.read_text(encoding="utf-8"))

    assert prepare_effort_result_visual_replay_shadow_integration_gate_input(pending_reviewer_summary) == expected


def test_blocks_unsafe_source_boundary_even_when_cases_pass():
    source = _ready_reviewer_summary()
    source["may_change_scoring"] = True

    report = prepare_effort_result_visual_replay_shadow_integration_gate_input(source)

    assert report["integration_gate_input_ready"] is False
    assert "source_production_boundary_open" in report["blockers"]


def test_blocks_unsafe_case_boundary_even_when_source_is_ready():
    source = _ready_reviewer_summary()
    source["case_summaries"][0]["may_change_frontend"] = True

    report = prepare_effort_result_visual_replay_shadow_integration_gate_input(source)

    assert report["integration_gate_input_ready"] is False
    assert "gate_case_blockers_present" in report["blockers"]
    assert "case_production_boundary_open" in report["gate_cases"][0]["blockers"]


def test_symbol_filter_keeps_lt_cases_only():
    source = _ready_reviewer_summary()
    source["case_summaries"].append(
        {
            **_case("SBIN.NS|2026-01-05|OTHER", "2026-01-05", "OTHER"),
            "symbol": "SBIN.NS",
        }
    )

    report = prepare_effort_result_visual_replay_shadow_integration_gate_input(source, required_symbols=["LT.NS"])

    assert report["source_case_count"] == 3
    assert report["selected_case_count"] == 2
    assert {case["symbol"] for case in report["gate_cases"]} == {"LT.NS"}


def test_min_gate_cases_must_be_positive():
    with pytest.raises(ValueError, match="min_gate_cases must be positive"):
        prepare_effort_result_visual_replay_shadow_integration_gate_input(
            _ready_reviewer_summary(),
            min_gate_cases=0,
        )


def test_markdown_renders_gate_input_rules_and_cases():
    report = prepare_effort_result_visual_replay_shadow_integration_gate_input(_ready_reviewer_summary())
    markdown = render_effort_result_visual_replay_shadow_integration_gate_input_markdown(report)

    assert "# Effort/Result Visual Replay Shadow Integration Gate Input" in markdown
    assert "LT.NS|2025-02-24|STRUCTURAL_WEAKENING" in markdown
    assert "Only all-pass reviewer summaries can become ready integration-gate input." in markdown
    assert "Production change allowed: false" in markdown


def test_cli_writes_pending_json_and_markdown(tmp_path):
    json_output = tmp_path / "gate-input.json"
    markdown_output = tmp_path / "gate-input.md"
    pending_reviewer_summary = FIXTURES / "effort_result_visual_replay_shadow_reviewer_summary_pending.json"

    subprocess.run(
        [
            sys.executable,
            "-m",
            "audit.decide_effort_result_visual_replay_shadow_integration_gate_input",
            str(pending_reviewer_summary),
            "--output",
            str(json_output),
        ],
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "audit.decide_effort_result_visual_replay_shadow_integration_gate_input",
            str(pending_reviewer_summary),
            "--format",
            "markdown",
            "--output",
            str(markdown_output),
        ],
        check=True,
    )

    assert json.loads(json_output.read_text(encoding="utf-8")) == json.loads(
        PENDING_FIXTURE.read_text(encoding="utf-8")
    )
    assert "blocked_from_shadow_visual_replay_integration_gate_input" in markdown_output.read_text(
        encoding="utf-8"
    )


def test_source_contains_no_live_fetch_or_storage_side_effects():
    source = MODULE.read_text(encoding="utf-8")
    forbidden_tokens = [
        "requests.",
        "urlopen",
        "sqlite3",
        "yfinance",
        "place" + "_" + "order",
        "emit" + "_" + "alert",
        "insert_signal",
        "update_score",
        "rank_symbols",
    ]

    for token in forbidden_tokens:
        assert token not in source
