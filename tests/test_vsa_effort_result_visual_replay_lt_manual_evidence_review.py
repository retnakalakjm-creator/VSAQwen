from __future__ import annotations

import json
from pathlib import Path

import pytest

from audit.prepare_effort_result_visual_replay_lt_manual_evidence_review import (
    FAIL,
    PASS,
    REQUIRED_REVIEW_LANES,
    prepare_effort_result_visual_replay_lt_manual_evidence_review,
    render_effort_result_visual_replay_lt_manual_evidence_review_markdown,
    main,
)

PENDING_SOURCE = Path("audit/fixtures/effort_result_visual_replay_shadow_coverage_lt_plan.json")
PENDING_REVIEWS = Path("audit/fixtures/effort_result_visual_replay_shadow_review_results_pending.json")
PENDING_FIXTURE = Path(
    "audit/fixtures/effort_result_visual_replay_lt_manual_evidence_review_packet_pending.json"
)
SOURCE = Path("audit/prepare_effort_result_visual_replay_lt_manual_evidence_review.py")


def _coverage_plan() -> dict[str, object]:
    return json.loads(PENDING_SOURCE.read_text(encoding="utf-8"))


def _pending_reviews() -> list[dict[str, object]]:
    return json.loads(PENDING_REVIEWS.read_text(encoding="utf-8"))


def _complete_review(case_id: str, outcome: str = PASS) -> dict[str, object]:
    lane_results = {lane: PASS for lane in REQUIRED_REVIEW_LANES}
    if outcome == FAIL:
        lane_results["vsa_smc_quality_judgment"] = FAIL

    return {
        "case_id": case_id,
        "review_outcome": outcome,
        "lane_results": lane_results,
        "reviewer": "Manual LT Reviewer",
        "reviewed_at": "2026-09-14T10:15:00+05:30",
        "reviewer_notes": "Manual dev-only replay evidence inspected for all required lanes.",
        "evidence_artifact": f"audit/evidence/{case_id.replace('|', '_')}.md",
        "automatic_promotion_allowed": False,
        "production_change_allowed": False,
        "manual_review_only": True,
        "offline_replay_only": True,
    }


def _complete_reviews(outcome: str = PASS) -> list[dict[str, object]]:
    return [
        _complete_review("LT.NS|2025-02-24|STRUCTURAL_WEAKENING", outcome),
        _complete_review("LT.NS|2026-03-02|RESULT_GT_EFFORT", outcome),
    ]


def test_pending_reviews_build_blocked_manual_evidence_packet() -> None:
    report = prepare_effort_result_visual_replay_lt_manual_evidence_review(
        _coverage_plan(),
        _pending_reviews(),
    )

    assert report["evidence_packet_ready"] is False
    assert report["manual_review_complete"] is False
    assert report["allowed_next_step"] == "perform_manual_lt_visual_replay_review"
    assert report["selected_case_count"] == 2
    assert report["undecided_case_count"] == 2
    assert report["evidence_artifact_count"] == 0
    assert report["downstream_integration_blocked"] is True
    assert report["production_change_allowed"] is False
    assert "manual_review_evidence_incomplete" in report["blockers"]


def test_pending_fixture_matches_current_pending_sources() -> None:
    expected = json.loads(PENDING_FIXTURE.read_text(encoding="utf-8"))

    assert (
        prepare_effort_result_visual_replay_lt_manual_evidence_review(
            _coverage_plan(),
            _pending_reviews(),
        )
        == expected
    )


def test_completed_all_pass_reviews_make_capture_ready_but_not_production_ready() -> None:
    report = prepare_effort_result_visual_replay_lt_manual_evidence_review(
        _coverage_plan(),
        _complete_reviews(PASS),
    )

    assert report["evidence_packet_ready"] is True
    assert report["manual_review_complete"] is True
    assert report["shadow_validation_candidate_ready"] is True
    assert report["downstream_integration_blocked"] is False
    assert report["allowed_next_step"] == "run_shadow_review_result_capture"
    assert report["passed_case_count"] == 2
    assert report["production_change_allowed"] is False
    assert report["automatic_promotion_allowed"] is False
    assert report["requires_separate_production_pr"] is True


def test_completed_failed_reviews_preserve_failure_and_block_integration() -> None:
    reviews = _complete_reviews(PASS)
    reviews[1] = _complete_review("LT.NS|2026-03-02|RESULT_GT_EFFORT", FAIL)

    report = prepare_effort_result_visual_replay_lt_manual_evidence_review(
        _coverage_plan(),
        reviews,
    )

    assert report["evidence_packet_ready"] is True
    assert report["manual_review_complete"] is True
    assert report["shadow_validation_candidate_ready"] is False
    assert report["downstream_integration_blocked"] is True
    assert report["failed_case_count"] == 1
    assert report["case_packets"][1]["review_outcome"] == FAIL
    assert report["case_packets"][1]["downstream_integration_blocked"] is True


def test_missing_manual_review_inputs_keep_packet_blocked_with_templates() -> None:
    report = prepare_effort_result_visual_replay_lt_manual_evidence_review(_coverage_plan(), [])

    assert report["manual_review_input_count"] == 0
    assert report["evidence_packet_ready"] is False
    assert report["manual_review_complete"] is False
    assert len(report["manual_review_results_template"]) == 2
    assert "manual_review_evidence_incomplete" in report["blockers"]
    assert "missing_manual_review_input" in report["case_packets"][0]["blockers"]


def test_wrong_source_contract_blocks_packet() -> None:
    source = _coverage_plan()
    source["report_type"] = "wrong"

    report = prepare_effort_result_visual_replay_lt_manual_evidence_review(
        source,
        _complete_reviews(PASS),
    )

    assert report["evidence_packet_ready"] is False
    assert "source_report_type_mismatch" in report["blockers"]


def test_unsafe_source_or_review_field_blocks_packet() -> None:
    source = _coverage_plan()
    source["may_change_scoring"] = True

    source_report = prepare_effort_result_visual_replay_lt_manual_evidence_review(
        source,
        _complete_reviews(PASS),
    )
    assert source_report["evidence_packet_ready"] is False
    assert "source_production_boundary_open" in source_report["blockers"]

    reviews = _complete_reviews(PASS)
    reviews[0]["may_change_ranking"] = True
    review_report = prepare_effort_result_visual_replay_lt_manual_evidence_review(
        _coverage_plan(),
        reviews,
    )
    assert review_report["evidence_packet_ready"] is False
    assert "manual_review_evidence_incomplete" in review_report["blockers"]
    assert "case_production_boundary_open" in review_report["case_packets"][0]["blockers"]


def test_symbol_filter_requires_lt_case_selection() -> None:
    report = prepare_effort_result_visual_replay_lt_manual_evidence_review(
        _coverage_plan(),
        _complete_reviews(PASS),
        required_symbols=("OTHER.NS",),
    )

    assert report["selected_case_count"] == 0
    assert report["evidence_packet_ready"] is False
    assert "missing_required_symbols" in report["blockers"]
    assert "not_enough_selected_cases" in report["blockers"]


def test_markdown_renders_cases_and_review_rules() -> None:
    report = prepare_effort_result_visual_replay_lt_manual_evidence_review(
        _coverage_plan(),
        _pending_reviews(),
    )

    markdown = render_effort_result_visual_replay_lt_manual_evidence_review_markdown(report)

    assert "LT Effort/Result Visual Replay Manual Evidence Review Packet" in markdown
    assert "LT.NS|2025-02-24|STRUCTURAL_WEAKENING" in markdown
    assert "LT.NS|2026-03-02|RESULT_GT_EFFORT" in markdown
    assert "Do not mark pass/fail until a human reviewer" in markdown
    assert "Production change allowed: false" in markdown


def test_cli_writes_json_and_markdown(tmp_path: Path) -> None:
    json_path = tmp_path / "packet.json"
    md_path = tmp_path / "packet.md"

    assert main(
        [
            "--coverage-plan",
            str(PENDING_SOURCE),
            "--manual-review-results",
            str(PENDING_REVIEWS),
            "--output",
            str(json_path),
        ]
    ) == 0
    assert json.loads(json_path.read_text(encoding="utf-8"))["report_type"] == (
        "effort_result_visual_replay_lt_manual_evidence_review_packet"
    )

    assert main(
        [
            "--coverage-plan",
            str(PENDING_SOURCE),
            "--manual-review-results",
            str(PENDING_REVIEWS),
            "--format",
            "markdown",
            "--output",
            str(md_path),
        ]
    ) == 0
    assert "Manual Evidence Review Packet" in md_path.read_text(encoding="utf-8")


def test_rejects_non_positive_min_cases() -> None:
    with pytest.raises(ValueError, match="min_cases must be positive"):
        prepare_effort_result_visual_replay_lt_manual_evidence_review(
            _coverage_plan(),
            _pending_reviews(),
            min_cases=0,
        )


def test_source_contains_no_live_or_production_side_effect_calls() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    forbidden_tokens = [
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
        "emit_alert",
        "place_order",
    ]

    for token in forbidden_tokens:
        assert token not in source
