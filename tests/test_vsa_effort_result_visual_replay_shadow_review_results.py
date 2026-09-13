import json
import subprocess
import sys
from pathlib import Path

from audit.capture_effort_result_visual_replay_shadow_review_results import (
    FAIL,
    PASS,
    REPORT_TYPE,
    REVIEW_RESULTS_BLOCKED_STATUS,
    REVIEW_RESULTS_READY_STATUS,
    UNDECIDED,
    capture_effort_result_visual_replay_shadow_review_results,
    render_effort_result_visual_replay_shadow_review_results_markdown,
)

FIXTURES = Path(__file__).resolve().parents[1] / "audit" / "fixtures"
COVERAGE_PLAN = FIXTURES / "effort_result_visual_replay_shadow_coverage_lt_plan.json"
PENDING_REVIEWS = FIXTURES / "effort_result_visual_replay_shadow_review_results_pending.json"

REQUIRED_LANES = (
    "marker_alignment_recheck",
    "pre_event_context_recheck",
    "post_event_follow_through_recheck",
    "counterfactual_quality_check",
    "vsa_smc_quality_judgment",
    "evidence_artifact_traceability",
)


def _coverage_plan():
    return json.loads(COVERAGE_PLAN.read_text(encoding="utf-8"))


def _pending_reviews():
    return json.loads(PENDING_REVIEWS.read_text(encoding="utf-8"))


def _lane_results(outcome=PASS, *, failed_lane=None):
    return {
        lane: (FAIL if lane == failed_lane else outcome)
        for lane in REQUIRED_LANES
    }


def _completed_reviews():
    return [
        {
            "case_id": "LT.NS|2025-02-24|STRUCTURAL_WEAKENING",
            "review_outcome": PASS,
            "lane_results": _lane_results(PASS),
            "reviewer": "manual_shadow_reviewer",
            "reviewed_at": "2026-09-13",
            "reviewer_notes": (
                "Manual replay review recorded marker alignment, pre-event context, "
                "post-event follow-through, counterfactual quality, VSA/SMC quality, "
                "and evidence traceability."
            ),
            "evidence_artifact": "manual-review/LT_2025-02-24-shadow-review.md",
            "automatic_promotion_allowed": False,
            "production_change_allowed": False,
        },
        {
            "case_id": "LT.NS|2026-03-02|RESULT_GT_EFFORT",
            "review_outcome": FAIL,
            "lane_results": _lane_results(PASS, failed_lane="post_event_follow_through_recheck"),
            "reviewer": "manual_shadow_reviewer",
            "reviewed_at": "2026-09-13",
            "reviewer_notes": (
                "Manual replay review found the post-event follow-through lane did "
                "not pass, so the failed case must block later integration gates."
            ),
            "evidence_artifact": "manual-review/LT_2026-03-02-shadow-review.md",
            "automatic_promotion_allowed": False,
            "production_change_allowed": False,
        },
    ]


def test_pending_review_fixture_blocks_summary_until_human_results_exist():
    report = capture_effort_result_visual_replay_shadow_review_results(
        _coverage_plan(),
        _pending_reviews(),
    )

    assert report["report_type"] == REPORT_TYPE
    assert report["review_results_status"] == REVIEW_RESULTS_BLOCKED_STATUS
    assert report["review_results_ready"] is False
    assert report["completed_review_count"] == 0
    assert report["passed_case_count"] == 0
    assert report["failed_case_count"] == 0
    assert report["undecided_case_count"] == 2
    assert report["allowed_next_step"] == "complete_manual_shadow_replay_reviews"
    assert "not_enough_completed_manual_reviews" in report["blockers"]
    assert "manual_review_case_blockers_present" in report["blockers"]
    assert "undecided_review_results_present" in report["blockers"]


def test_completed_pass_and_fail_reviews_are_ready_for_summary_not_promotion():
    report = capture_effort_result_visual_replay_shadow_review_results(
        _coverage_plan(),
        _completed_reviews(),
    )

    assert report["review_results_status"] == REVIEW_RESULTS_READY_STATUS
    assert report["review_results_ready"] is True
    assert report["completed_review_count"] == 2
    assert report["passed_case_count"] == 1
    assert report["failed_case_count"] == 1
    assert report["undecided_case_count"] == 0
    assert report["blockers"] == []
    assert report["allowed_next_step"] == "run_visual_replay_reviewer_pass_fail_summary"
    assert report["automatic_promotion_allowed"] is False
    assert report["production_change_allowed"] is False
    assert report["may_change_scoring"] is False
    assert report["may_change_ranking"] is False
    assert report["may_change_actionability"] is False
    assert report["may_activate_detector"] is False
    assert report["may_change_scanner_state"] is False


def test_blocks_fake_pass_without_reviewer_notes_or_evidence():
    reviews = _completed_reviews()
    reviews[0]["reviewer_notes"] = ""
    reviews[0]["evidence_artifact"] = ""

    report = capture_effort_result_visual_replay_shadow_review_results(
        _coverage_plan(),
        reviews,
    )

    first_case = report["review_cases"][0]
    assert report["review_results_ready"] is False
    assert "manual_review_case_blockers_present" in report["blockers"]
    assert "missing_reviewer_notes" in first_case["blockers"]
    assert "missing_evidence_artifact" in first_case["blockers"]


def test_blocks_pass_outcome_with_failed_lane():
    reviews = _completed_reviews()
    reviews[0]["lane_results"]["marker_alignment_recheck"] = FAIL

    report = capture_effort_result_visual_replay_shadow_review_results(
        _coverage_plan(),
        reviews,
    )

    first_case = report["review_cases"][0]
    assert report["review_results_ready"] is False
    assert "pass_outcome_conflicts_with_failed_lane" in first_case["blockers"]


def test_blocks_unsafe_production_boundary_in_review_input():
    reviews = _completed_reviews()
    reviews[0]["production_change_allowed"] = True

    report = capture_effort_result_visual_replay_shadow_review_results(
        _coverage_plan(),
        reviews,
    )

    assert report["review_results_ready"] is False
    assert "review_production_boundary_open" in report["review_cases"][0]["blockers"]


def test_symbol_filter_keeps_lt_shadow_review_cases_only():
    report = capture_effort_result_visual_replay_shadow_review_results(
        _coverage_plan(),
        _completed_reviews(),
        required_symbols=["LT.NS"],
    )

    assert report["required_symbols"] == ["LT.NS"]
    assert report["selected_case_count"] == 2
    assert {case["symbol"] for case in report["review_cases"]} == {"LT.NS"}


def test_markdown_renders_pending_review_rules():
    report = capture_effort_result_visual_replay_shadow_review_results(
        _coverage_plan(),
        _pending_reviews(),
    )
    markdown = render_effort_result_visual_replay_shadow_review_results_markdown(report)

    assert "# Effort/Result Visual Replay Shadow Review Results" in markdown
    assert "blocked_from_reviewer_pass_fail_summary" in markdown
    assert "LT.NS|2025-02-24|STRUCTURAL_WEAKENING" in markdown
    assert "LT.NS|2026-03-02|RESULT_GT_EFFORT" in markdown
    assert "Failed cases may proceed to reviewer-summary reporting" in markdown
    assert "This report does not approve production behavior changes" in markdown


def test_cli_writes_pending_json_and_markdown(tmp_path):
    json_output = tmp_path / "review_results.json"
    markdown_output = tmp_path / "review_results.md"

    subprocess.run(
        [
            sys.executable,
            "-m",
            "audit.capture_effort_result_visual_replay_shadow_review_results",
            str(COVERAGE_PLAN),
            str(PENDING_REVIEWS),
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
            "audit.capture_effort_result_visual_replay_shadow_review_results",
            str(COVERAGE_PLAN),
            str(PENDING_REVIEWS),
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
    assert rendered_json["review_results_ready"] is False
    assert rendered_json["undecided_case_count"] == 2
    assert "Shadow Review Results" in rendered_markdown


def test_source_contains_no_live_fetch_or_storage_side_effects():
    source = Path("audit/capture_effort_result_visual_replay_shadow_review_results.py").read_text(
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
