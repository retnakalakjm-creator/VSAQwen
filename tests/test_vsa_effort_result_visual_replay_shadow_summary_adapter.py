import json
import subprocess
import sys
from pathlib import Path

from audit.adapt_effort_result_visual_replay_shadow_review_summary import (
    adapt_effort_result_visual_replay_shadow_review_summary_input,
    render_effort_result_visual_replay_shadow_review_summary_input_markdown,
)


def _review_case(case_id, outcome="pass", *, ready=True):
    return {
        "case_id": case_id,
        "symbol": "LT.NS",
        "event_week_beginning": case_id.split("|")[1],
        "target": case_id.split("|")[2],
        "review_outcome": outcome,
        "reviewer": "manual-reviewer",
        "reviewed_at": "2026-09-13T17:45:00Z",
        "evidence_artifact": f"audit/evidence/{case_id}.md",
        "review_case_ready": ready,
        "blockers": [] if ready else ["manual_review_case_blockers_present"],
        "automatic_promotion_allowed": False,
        "production_change_allowed": False,
        "manual_review_only": True,
        "offline_replay_only": True,
    }


def _ready_completion_gate(*, second_outcome="pass"):
    return {
        "report_type": "effort_result_visual_replay_shadow_review_completion_gate",
        "completion_status": "visual_replay_shadow_review_completion_ready",
        "completion_decision": "ready_for_visual_replay_reviewer_pass_fail_summary",
        "completion_ready": True,
        "allowed_next_step": "run_visual_replay_reviewer_pass_fail_summary",
        "blockers": [],
        "review_cases": [
            _review_case("LT.NS|2025-02-24|STRUCTURAL_WEAKENING"),
            _review_case("LT.NS|2026-03-02|RESULT_GT_EFFORT", second_outcome),
        ],
        "automatic_promotion_allowed": False,
        "production_change_allowed": False,
        "manual_review_only": True,
        "offline_replay_only": True,
    }


def test_all_pass_completion_gate_creates_ready_summary_input():
    report = adapt_effort_result_visual_replay_shadow_review_summary_input(_ready_completion_gate())

    assert report["summary_input_ready"] is True
    assert report["summary_input_status"] == "visual_replay_shadow_review_summary_input_ready"
    assert report["summary_input_decision"] == "ready_to_run_visual_replay_reviewer_pass_fail_summary"
    assert report["allowed_next_step"] == "run_visual_replay_reviewer_pass_fail_summary"
    assert report["completed_case_count"] == 2
    assert report["passed_case_count"] == 2
    assert report["failed_case_count"] == 0
    assert report["downstream_integration_blocked"] is False
    assert all(case["summary_case_ready"] is True for case in report["summary_cases"])


def test_failed_completed_case_is_preserved_but_blocks_downstream_integration():
    report = adapt_effort_result_visual_replay_shadow_review_summary_input(
        _ready_completion_gate(second_outcome="fail")
    )

    assert report["summary_input_ready"] is True
    assert report["completed_case_count"] == 2
    assert report["passed_case_count"] == 1
    assert report["failed_case_count"] == 1
    assert report["downstream_integration_blocked"] is True
    failed = [case for case in report["summary_cases"] if case["review_outcome"] == "fail"]
    assert len(failed) == 1
    assert failed[0]["integration_blocked"] is True


def test_pending_completion_gate_blocks_summary_input():
    source = _ready_completion_gate()
    source.update(
        {
            "completion_status": "visual_replay_shadow_review_completion_blocked",
            "completion_decision": "blocked_from_visual_replay_reviewer_pass_fail_summary",
            "completion_ready": False,
            "allowed_next_step": "complete_manual_shadow_replay_reviews",
            "blockers": ["undecided_review_results_present"],
        }
    )
    source["review_cases"] = [
        _review_case("LT.NS|2025-02-24|STRUCTURAL_WEAKENING", "undecided", ready=False),
        _review_case("LT.NS|2026-03-02|RESULT_GT_EFFORT", "undecided", ready=False),
    ]

    report = adapt_effort_result_visual_replay_shadow_review_summary_input(source)

    assert report["summary_input_ready"] is False
    assert "source_completion_ready_false" in report["blockers"]
    assert "source_completion_blockers_present" in report["blockers"]
    assert "undecided_summary_cases_present" in report["blockers"]
    assert report["allowed_next_step"] == "resolve_shadow_review_summary_input_blockers"


def test_blocks_wrong_source_report_type_and_unsafe_flags():
    source = _ready_completion_gate()
    source["report_type"] = "wrong_report"
    source["may_change_scoring"] = True

    report = adapt_effort_result_visual_replay_shadow_review_summary_input(source)

    assert report["summary_input_ready"] is False
    assert "source_report_type_mismatch" in report["blockers"]
    assert "source_production_boundary_open" in report["blockers"]


def test_blocks_when_minimum_completed_cases_not_met():
    source = _ready_completion_gate()
    source["review_cases"] = source["review_cases"][:1]

    report = adapt_effort_result_visual_replay_shadow_review_summary_input(source)

    assert report["summary_input_ready"] is False
    assert "not_enough_summary_ready_cases" in report["blockers"]


def test_symbol_filter_selects_matching_cases_only():
    source = _ready_completion_gate()
    source["review_cases"].append(
        {
            **_review_case("RELIANCE.NS|2026-03-02|RESULT_GT_EFFORT"),
            "symbol": "RELIANCE.NS",
        }
    )

    report = adapt_effort_result_visual_replay_shadow_review_summary_input(
        source,
        required_symbols=["RELIANCE.NS"],
        min_completed_cases=1,
    )

    assert report["summary_input_ready"] is True
    assert report["selected_case_count"] == 1
    assert report["summary_cases"][0]["symbol"] == "RELIANCE.NS"


def test_markdown_renders_summary_rules_and_cases():
    report = adapt_effort_result_visual_replay_shadow_review_summary_input(_ready_completion_gate())
    markdown = render_effort_result_visual_replay_shadow_review_summary_input_markdown(report)

    assert "Effort/Result Visual Replay Shadow Review Summary Input" in markdown
    assert "run_visual_replay_reviewer_pass_fail_summary" in markdown
    assert "LT.NS|2025-02-24|STRUCTURAL_WEAKENING" in markdown
    assert "separate production PR" in markdown


def test_cli_writes_json_and_markdown(tmp_path):
    source_path = tmp_path / "completion.json"
    json_out = tmp_path / "summary.json"
    md_out = tmp_path / "summary.md"
    source_path.write_text(json.dumps(_ready_completion_gate()), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "-m",
            "audit.adapt_effort_result_visual_replay_shadow_review_summary",
            str(source_path),
            "--output",
            str(json_out),
        ],
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "audit.adapt_effort_result_visual_replay_shadow_review_summary",
            str(source_path),
            "--format",
            "markdown",
            "--output",
            str(md_out),
        ],
        check=True,
    )

    assert json.loads(json_out.read_text(encoding="utf-8"))["summary_input_ready"] is True
    assert "Summary Input" in md_out.read_text(encoding="utf-8")


def test_pending_fixture_is_blocked():
    fixture = Path(
        "audit/fixtures/effort_result_visual_replay_shadow_summary_input_pending.json"
    )
    report = json.loads(fixture.read_text(encoding="utf-8"))

    assert report["summary_input_ready"] is False
    assert report["summary_input_status"] == "visual_replay_shadow_review_summary_input_blocked"
    assert "undecided_summary_cases_present" in report["blockers"]
    assert report["automatic_promotion_allowed"] is False
    assert report["production_change_allowed"] is False


def test_source_contains_no_live_fetch_or_storage_side_effects():
    source = Path(
        "audit/adapt_effort_result_visual_replay_shadow_review_summary.py"
    ).read_text(encoding="utf-8")
    forbidden_tokens = [
        "requests.",
        "yfinance",
        "sqlite3",
        "psycopg",
        "sqlalchemy",
        "fetch(",
        "insert(",
        "update(",
        "delete(",
        "place_order",
        "emit_alert",
    ]

    for token in forbidden_tokens:
        assert token not in source
