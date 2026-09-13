import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from audit.summarize_effort_result_visual_replay_reviews import (
    CASE_FAILED_STATUS,
    CASE_NEEDS_ATTENTION_STATUS,
    CASE_PASSED_STATUS,
    REPORT_TYPE,
    REVIEW_SUMMARY_NEEDS_ATTENTION_STATUS,
    REVIEW_SUMMARY_READY_STATUS,
    render_effort_result_visual_replay_reviewer_summary_markdown,
    summarize_effort_result_visual_replay_reviews,
)


def _casebook_case(**overrides):
    case = {
        "case_id": "LT.NS|2026-03-02|RESULT_GT_EFFORT",
        "source_sequence_id": "lt-result-gt-effort-2026-03-02",
        "target": "RESULT_GT_EFFORT",
        "symbol": "LT.NS",
        "event_week_beginning": "2026-03-02",
        "marker_labels": ["Result > Effort"],
        "case_status": "ready_for_casebook_review",
        "review_decision": "pass",
        "review_rationale": "Marker aligns with the event bar and follow-through confirms the visual read.",
        "manual_review_only": True,
        "automatic_promotion_allowed": False,
    }
    case.update(overrides)
    return case


def _casebook_report(*cases, **overrides):
    report = {
        "report_type": "effort_result_visual_replay_casebook",
        "report_schema_version": 1,
        "casebook_status": "visual_replay_casebook_ready",
        "casebook_ready": True,
        "casebook_case_count": len(cases),
        "ready_case_count": len(cases),
        "blocked_case_count": 0,
        "casebook_cases": list(cases),
        "audit_only": True,
        "casebook_only": True,
        "manual_review_only": True,
        "offline_replay_only": True,
        "automatic_promotion_allowed": False,
        "production_change_allowed": False,
    }
    report.update(overrides)
    return report


def test_all_passed_casebook_is_integration_candidate_ready():
    report = summarize_effort_result_visual_replay_reviews(
        _casebook_report(_casebook_case()),
        min_passed_cases=1,
    )

    assert report["report_type"] == REPORT_TYPE
    assert report["review_summary_status"] == REVIEW_SUMMARY_READY_STATUS
    assert report["review_summary_ready"] is True
    assert report["integration_candidate_ready"] is True
    assert report["passed_case_count"] == 1
    assert report["failed_case_count"] == 0
    assert report["undecided_case_count"] == 0
    assert report["next_stage"] == "integration_gate_decision"
    assert report["automatic_promotion_allowed"] is False
    assert report["production_change_allowed"] is False
    assert report["may_change_scoring"] is False
    assert report["may_change_ranking"] is False
    assert report["may_change_actionability"] is False
    assert report["may_activate_detector"] is False


def test_failed_case_is_summarized_but_blocks_integration_candidate_readiness():
    report = summarize_effort_result_visual_replay_reviews(
        _casebook_report(
            _casebook_case(
                review_decision="fail",
                failure_reason="Marker fires one bar too early versus the manual replay read.",
            )
        )
    )

    assert report["review_summary_ready"] is True
    assert report["integration_candidate_ready"] is False
    assert report["failed_case_count"] == 1
    assert report["case_reviews"][0]["case_review_status"] == CASE_FAILED_STATUS
    assert "failed_cases_exceed_threshold" in report["integration_blockers"]
    assert report["next_stage"] == "resolve_failed_or_insufficient_review_cases"


def test_missing_manual_decision_blocks_summary_readiness():
    case = _casebook_case()
    case.pop("review_decision")

    report = summarize_effort_result_visual_replay_reviews(_casebook_report(case))

    assert report["review_summary_status"] == REVIEW_SUMMARY_NEEDS_ATTENTION_STATUS
    assert report["review_summary_ready"] is False
    assert report["integration_candidate_ready"] is False
    assert report["undecided_case_count"] == 1
    assert report["case_reviews"][0]["case_review_status"] == CASE_NEEDS_ATTENTION_STATUS
    assert "missing_review_decision" in report["case_reviews"][0]["blockers"]
    assert "case_review_decision_blockers_present" in report["blockers"]
    assert report["next_stage"] == "complete_reviewer_casebook_decisions"


def test_invalid_source_or_unsafe_boundary_blocks_summary():
    report = summarize_effort_result_visual_replay_reviews(
        _casebook_report(
            _casebook_case(),
            report_type="wrong_report",
            casebook_status="visual_replay_casebook_needs_attention",
            casebook_ready=False,
            production_change_allowed=True,
        )
    )

    assert report["review_summary_ready"] is False
    assert report["integration_candidate_ready"] is False
    assert "source_report_type_mismatch" in report["blockers"]
    assert "source_casebook_not_ready" in report["blockers"]
    assert "source_casebook_ready_false" in report["blockers"]
    assert "report_production_boundary_open" in report["blockers"]


def test_case_with_invalid_decision_or_open_boundary_needs_attention():
    report = summarize_effort_result_visual_replay_reviews(
        _casebook_report(
            _casebook_case(
                review_decision="maybe",
                review_rationale="Needs another look.",
                activate_detector=True,
            )
        )
    )

    case_review = report["case_reviews"][0]
    assert case_review["case_review_status"] == CASE_NEEDS_ATTENTION_STATUS
    assert "invalid_review_decision" in case_review["blockers"]
    assert "case_production_boundary_open" in case_review["blockers"]
    assert report["review_summary_ready"] is False


def test_markdown_render_includes_summary_table_and_guardrails():
    report = summarize_effort_result_visual_replay_reviews(_casebook_report(_casebook_case()))
    markdown = render_effort_result_visual_replay_reviewer_summary_markdown(report)

    assert "# Effort/Result Visual Replay Reviewer Pass/Fail Summary" in markdown
    assert "| Case | Target | Symbol | Week | Decision | Status | Rationale | Blockers |" in markdown
    assert "Integration candidate ready: true" in markdown
    assert "Production change allowed: false" in markdown
    assert "Requires separate integration gate PR: true" in markdown
    assert "separate production PR is required" in markdown


def test_cli_writes_markdown_output(tmp_path):
    source = tmp_path / "casebook.json"
    output = tmp_path / "summary.md"
    source.write_text(json.dumps(_casebook_report(_casebook_case())), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "audit" / "summarize_effort_result_visual_replay_reviews.py"),
            str(source),
            "--format",
            "markdown",
            "--output",
            str(output),
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0
    written = output.read_text(encoding="utf-8")
    assert "Effort/Result Visual Replay Reviewer Pass/Fail Summary" in written
    assert "reviewer_pass_fail_summary_ready" in written
