from __future__ import annotations

import json
from pathlib import Path

import pytest

from audit.summarize_effort_result_visual_replay_shadow_review import (
    FAILED_DECISION,
    PASSING_DECISION,
    REPORT_TYPE,
    summarize_effort_result_visual_replay_shadow_review,
    render_effort_result_visual_replay_shadow_reviewer_summary_markdown,
    main,
)


def _case(case_id: str, target: str, outcome: str, *, ready: bool = True) -> dict[str, object]:
    return {
        "case_id": case_id,
        "symbol": "LT.NS",
        "event_week_beginning": case_id.split("|")[1],
        "target": target,
        "review_outcome": outcome,
        "reviewer": "manual-reviewer",
        "reviewed_at": "2026-09-13T18:00:00+05:30",
        "evidence_artifact": f"audit/evidence/{case_id}.json",
        "summary_case_ready": ready,
        "blockers": [] if ready else ["manual_review_case_blockers_present"],
        "automatic_promotion_allowed": False,
        "production_change_allowed": False,
    }


def _ready_summary_input(*, outcomes: tuple[str, str] = ("pass", "pass")) -> dict[str, object]:
    return {
        "report_type": "effort_result_visual_replay_shadow_review_summary_input",
        "summary_input_status": "visual_replay_shadow_review_summary_input_ready",
        "summary_input_decision": "ready_to_run_visual_replay_reviewer_pass_fail_summary",
        "summary_input_ready": True,
        "allowed_next_step": "run_visual_replay_reviewer_pass_fail_summary",
        "blockers": [],
        "required_symbols": ["LT.NS"],
        "selected_case_count": 2,
        "completed_case_count": 2,
        "passed_case_count": sum(1 for outcome in outcomes if outcome == "pass"),
        "failed_case_count": sum(1 for outcome in outcomes if outcome == "fail"),
        "undecided_case_count": sum(1 for outcome in outcomes if outcome == "undecided"),
        "automatic_promotion_allowed": False,
        "production_change_allowed": False,
        "summary_cases": [
            _case("LT.NS|2025-02-24|STRUCTURAL_WEAKENING", "STRUCTURAL_WEAKENING", outcomes[0]),
            _case("LT.NS|2026-03-02|RESULT_GT_EFFORT", "RESULT_GT_EFFORT", outcomes[1]),
        ],
    }


def test_all_pass_summary_is_ready_for_shadow_integration_gate() -> None:
    report = summarize_effort_result_visual_replay_shadow_review(_ready_summary_input())

    assert report["report_type"] == REPORT_TYPE
    assert report["reviewer_summary_ready"] is True
    assert report["reviewer_summary_decision"] == PASSING_DECISION
    assert report["shadow_validation_passed"] is True
    assert report["downstream_integration_blocked"] is False
    assert report["allowed_next_step"] == "run_shadow_visual_replay_integration_gate"
    assert report["passed_case_count"] == 2
    assert report["failed_case_count"] == 0
    assert report["undecided_case_count"] == 0
    assert report["automatic_promotion_allowed"] is False
    assert report["production_change_allowed"] is False


def test_failed_case_is_summarized_but_blocks_downstream_integration() -> None:
    report = summarize_effort_result_visual_replay_shadow_review(
        _ready_summary_input(outcomes=("pass", "fail"))
    )

    assert report["reviewer_summary_ready"] is True
    assert report["reviewer_summary_decision"] == FAILED_DECISION
    assert report["shadow_validation_passed"] is False
    assert report["downstream_integration_blocked"] is True
    assert report["allowed_next_step"] == "resolve_failed_shadow_visual_replay_cases"
    assert report["passed_case_count"] == 1
    assert report["failed_case_count"] == 1
    failed_case = [case for case in report["case_summaries"] if case["review_outcome"] == "fail"][0]
    assert failed_case["integration_blocked"] is True


def test_pending_summary_input_fixture_stays_blocked() -> None:
    fixture = json.loads(
        Path("audit/fixtures/effort_result_visual_replay_shadow_reviewer_summary_pending.json").read_text(
            encoding="utf-8"
        )
    )

    assert fixture["report_type"] == REPORT_TYPE
    assert fixture["reviewer_summary_ready"] is False
    assert fixture["reviewer_summary_status"] == "visual_replay_shadow_reviewer_summary_blocked"
    assert fixture["shadow_validation_passed"] is False
    assert fixture["downstream_integration_blocked"] is True
    assert "undecided_reviewer_cases_present" in fixture["blockers"]
    assert fixture["allowed_next_step"] == "resolve_shadow_reviewer_summary_blockers"


def test_pending_fixture_matches_generated_pending_summary_input() -> None:
    source = json.loads(
        Path("audit/fixtures/effort_result_visual_replay_shadow_summary_input_pending.json").read_text(
            encoding="utf-8"
        )
    )
    expected = json.loads(
        Path("audit/fixtures/effort_result_visual_replay_shadow_reviewer_summary_pending.json").read_text(
            encoding="utf-8"
        )
    )

    assert summarize_effort_result_visual_replay_shadow_review(source) == expected


def test_unsafe_source_field_blocks_summary() -> None:
    source = _ready_summary_input()
    source["emit" + "_" + "alert"] = True

    report = summarize_effort_result_visual_replay_shadow_review(source)

    assert report["reviewer_summary_ready"] is False
    assert "source_production_boundary_open" in report["blockers"]


def test_unsafe_case_field_blocks_summary() -> None:
    source = _ready_summary_input()
    source["summary_cases"][0]["place" + "_" + "order"] = True

    report = summarize_effort_result_visual_replay_shadow_review(source)

    assert report["reviewer_summary_ready"] is False
    assert "reviewer_case_blockers_present" in report["blockers"]
    assert "case_production_boundary_open" in report["case_summaries"][0]["blockers"]


def test_symbol_filter_blocks_when_required_symbol_has_no_cases() -> None:
    report = summarize_effort_result_visual_replay_shadow_review(
        _ready_summary_input(),
        required_symbols=("RELIANCE.NS",),
    )

    assert report["reviewer_summary_ready"] is False
    assert "missing_selected_summary_cases" in report["blockers"]


def test_markdown_names_cases_and_keeps_safety_rules() -> None:
    markdown = render_effort_result_visual_replay_shadow_reviewer_summary_markdown(
        summarize_effort_result_visual_replay_shadow_review(_ready_summary_input())
    )

    assert "Effort/Result Visual Replay Shadow Reviewer Summary" in markdown
    assert "LT.NS|2025-02-24|STRUCTURAL_WEAKENING" in markdown
    assert "LT.NS|2026-03-02|RESULT_GT_EFFORT" in markdown
    assert "Production change allowed: false" in markdown
    assert "Requires separate production PR: true" in markdown


def test_cli_can_regenerate_pending_fixture(tmp_path: Path) -> None:
    output = tmp_path / "summary.json"
    assert main(
        [
            "audit/fixtures/effort_result_visual_replay_shadow_summary_input_pending.json",
            "--output",
            str(output),
        ]
    ) == 0

    generated = json.loads(output.read_text(encoding="utf-8"))
    expected = json.loads(
        Path("audit/fixtures/effort_result_visual_replay_shadow_reviewer_summary_pending.json").read_text(
            encoding="utf-8"
        )
    )
    assert generated == expected


def test_cli_can_render_markdown(tmp_path: Path) -> None:
    output = tmp_path / "summary.md"
    assert main(
        [
            "audit/fixtures/effort_result_visual_replay_shadow_summary_input_pending.json",
            "--format",
            "markdown",
            "--output",
            str(output),
        ]
    ) == 0

    rendered = output.read_text(encoding="utf-8")
    assert "Reviewer summary decision" in rendered
    assert "resolve_shadow_reviewer_summary_blockers" in rendered


def test_rejects_non_positive_min_summary_cases() -> None:
    with pytest.raises(ValueError, match="min_summary_cases must be positive"):
        summarize_effort_result_visual_replay_shadow_review(
            _ready_summary_input(),
            min_summary_cases=0,
        )


def test_summary_source_does_not_use_forbidden_runtime_calls() -> None:
    source = Path("audit/summarize_effort_result_visual_replay_shadow_review.py").read_text(
        encoding="utf-8"
    )

    forbidden_fragments = (
        "requests.",
        "urllib.",
        "subprocess.",
        "yfinance",
        ".to_csv(",
        ".to_sql(",
        ".to_parquet(",
        "open(",
        "sqlite3",
        "fetch(",
        "emit" + "_" + "alert",
        "place" + "_" + "order",
    )
    assert not any(fragment in source for fragment in forbidden_fragments)
