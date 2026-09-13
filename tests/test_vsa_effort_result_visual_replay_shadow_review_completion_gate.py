import json
import subprocess
import sys
from pathlib import Path

from audit.decide_effort_result_visual_replay_shadow_review_completion import (
    BLOCKED_DECISION,
    COMPLETION_BLOCKED_STATUS,
    COMPLETION_READY_STATUS,
    READY_DECISION,
    REPORT_TYPE,
    decide_effort_result_visual_replay_shadow_review_completion,
    render_effort_result_visual_replay_shadow_review_completion_markdown,
)


REQUIRED_LANES = (
    "marker_alignment_recheck",
    "pre_event_context_recheck",
    "post_event_follow_through_recheck",
    "counterfactual_quality_check",
    "vsa_smc_quality_judgment",
    "evidence_artifact_traceability",
)


def _review_case(case_id, outcome="pass", *, target="STRUCTURAL_WEAKENING", week="2025-02-24"):
    lane_results = {lane: outcome for lane in REQUIRED_LANES}
    return {
        "case_id": case_id,
        "symbol": "LT.NS",
        "event_week_beginning": week,
        "target": target,
        "review_outcome": outcome,
        "review_case_ready": True,
        "blockers": [],
        "lane_results": lane_results,
        "automatic_promotion_allowed": False,
        "production_change_allowed": False,
    }


def _ready_review_results_report(outcomes=("pass", "pass")):
    cases = [
        _review_case(
            "LT.NS|2025-02-24|STRUCTURAL_WEAKENING",
            outcomes[0],
            target="STRUCTURAL_WEAKENING",
            week="2025-02-24",
        ),
        _review_case(
            "LT.NS|2026-03-02|RESULT_GT_EFFORT",
            outcomes[1],
            target="RESULT_GT_EFFORT",
            week="2026-03-02",
        ),
    ]
    return {
        "report_type": "effort_result_visual_replay_shadow_review_results",
        "report_schema_version": 1,
        "review_results_status": "visual_replay_shadow_review_results_ready",
        "review_results_decision": "ready_for_reviewer_pass_fail_summary",
        "review_results_ready": True,
        "allowed_next_step": "run_visual_replay_reviewer_pass_fail_summary",
        "selected_case_count": 2,
        "completed_review_count": 2,
        "passed_case_count": sum(1 for outcome in outcomes if outcome == "pass"),
        "failed_case_count": sum(1 for outcome in outcomes if outcome == "fail"),
        "undecided_case_count": 0,
        "blockers": [],
        "review_cases": cases,
        "automatic_promotion_allowed": False,
        "production_change_allowed": False,
    }


def _pending_review_results_report():
    cases = [
        {
            **_review_case(
                "LT.NS|2025-02-24|STRUCTURAL_WEAKENING",
                "undecided",
                target="STRUCTURAL_WEAKENING",
                week="2025-02-24",
            ),
            "review_case_ready": False,
            "blockers": ["manual_review_outcome_undecided"],
        },
        {
            **_review_case(
                "LT.NS|2026-03-02|RESULT_GT_EFFORT",
                "undecided",
                target="RESULT_GT_EFFORT",
                week="2026-03-02",
            ),
            "review_case_ready": False,
            "blockers": ["manual_review_outcome_undecided"],
        },
    ]
    return {
        "report_type": "effort_result_visual_replay_shadow_review_results",
        "report_schema_version": 1,
        "review_results_status": "visual_replay_shadow_review_results_blocked",
        "review_results_decision": "blocked_from_reviewer_pass_fail_summary",
        "review_results_ready": False,
        "allowed_next_step": "complete_manual_shadow_replay_reviews",
        "selected_case_count": 2,
        "completed_review_count": 0,
        "passed_case_count": 0,
        "failed_case_count": 0,
        "undecided_case_count": 2,
        "blockers": [
            "not_enough_completed_manual_reviews",
            "manual_review_case_blockers_present",
            "undecided_review_results_present",
        ],
        "review_cases": cases,
        "automatic_promotion_allowed": False,
        "production_change_allowed": False,
    }


def test_all_passed_reviews_open_reviewer_summary_handoff():
    report = decide_effort_result_visual_replay_shadow_review_completion(
        _ready_review_results_report()
    )

    assert report["report_type"] == REPORT_TYPE
    assert report["review_completion_status"] == COMPLETION_READY_STATUS
    assert report["review_completion_decision"] == READY_DECISION
    assert report["review_completion_ready"] is True
    assert report["allowed_next_step"] == "run_visual_replay_reviewer_pass_fail_summary"
    assert report["downstream_reviewer_summary_allowed"] is True
    assert report["downstream_integration_gate_should_block"] is False
    assert report["blockers"] == []


def test_failed_reviews_can_be_summarized_but_must_block_later_integration():
    report = decide_effort_result_visual_replay_shadow_review_completion(
        _ready_review_results_report(("pass", "fail"))
    )

    assert report["review_completion_ready"] is True
    assert report["failed_case_count"] == 1
    assert report["failed_cases_present"] is True
    assert report["downstream_reviewer_summary_allowed"] is True
    assert report["downstream_integration_gate_should_block"] is True
    assert report["failed_cases_must_be_preserved_in_summary"] is True


def test_pending_reviews_are_blocked_from_summary_handoff():
    report = decide_effort_result_visual_replay_shadow_review_completion(
        _pending_review_results_report()
    )

    assert report["review_completion_status"] == COMPLETION_BLOCKED_STATUS
    assert report["review_completion_decision"] == BLOCKED_DECISION
    assert report["review_completion_ready"] is False
    assert report["allowed_next_step"] == "complete_manual_shadow_replay_reviews_before_summary"
    assert "source_review_results_ready_false" in report["blockers"]
    assert "undecided_review_results_present" in report["blockers"]
    assert "review_case_completion_blockers_present" in report["blockers"]


def test_require_zero_failed_cases_blocks_failed_manual_results():
    report = decide_effort_result_visual_replay_shadow_review_completion(
        _ready_review_results_report(("pass", "fail")),
        require_zero_failed_cases=True,
    )

    assert report["review_completion_ready"] is False
    assert "failed_review_cases_present" in report["blockers"]


def test_blocks_source_blockers_and_unsafe_production_fields():
    source = _ready_review_results_report()
    source["blockers"] = ["manual_review_case_blockers_present"]
    source["production_change_allowed"] = True

    report = decide_effort_result_visual_replay_shadow_review_completion(source)

    assert report["review_completion_ready"] is False
    assert "source_review_result_blockers_present" in report["blockers"]
    assert "source_production_boundary_open" in report["blockers"]


def test_blocks_invalid_or_incomplete_case_rows():
    source = _ready_review_results_report()
    source["review_cases"][0]["case_id"] = ""
    source["review_cases"][1]["review_case_ready"] = False
    source["completed_review_count"] = 1

    report = decide_effort_result_visual_replay_shadow_review_completion(source)

    assert report["review_completion_ready"] is False
    assert "completed_review_count_mismatch" in report["blockers"]
    assert "review_case_completion_blockers_present" in report["blockers"]
    assert "missing_case_id" in report["completion_cases"][0]["blockers"]


def test_pending_fixture_matches_generated_completion_gate():
    fixture_path = Path(
        "audit/fixtures/effort_result_visual_replay_shadow_review_completion_pending.json"
    )
    expected = json.loads(fixture_path.read_text(encoding="utf-8"))

    report = decide_effort_result_visual_replay_shadow_review_completion(
        _pending_review_results_report()
    )

    assert report == expected


def test_markdown_renders_gate_rules_and_failure_boundary():
    report = decide_effort_result_visual_replay_shadow_review_completion(
        _ready_review_results_report(("pass", "fail"))
    )
    markdown = render_effort_result_visual_replay_shadow_review_completion_markdown(report)

    assert "# Effort/Result Visual Replay Shadow Review Completion Gate" in markdown
    assert "ready_to_summarize_manual_shadow_replay_results" in markdown
    assert "Downstream integration gate should block: true" in markdown
    assert "Failed completed cases must block later integration gates downstream" in markdown
    assert "Production change allowed: false" in markdown


def test_cli_writes_json_and_markdown(tmp_path):
    source_path = tmp_path / "review_results.json"
    json_output = tmp_path / "completion.json"
    markdown_output = tmp_path / "completion.md"
    source_path.write_text(json.dumps(_ready_review_results_report()), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "-m",
            "audit.decide_effort_result_visual_replay_shadow_review_completion",
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
            "audit.decide_effort_result_visual_replay_shadow_review_completion",
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
    assert rendered_json["review_completion_ready"] is True
    assert "Review Completion Gate" in rendered_markdown


def test_source_contains_no_live_fetch_or_storage_side_effects():
    source = Path(
        "audit/decide_effort_result_visual_replay_shadow_review_completion.py"
    ).read_text(encoding="utf-8")

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
