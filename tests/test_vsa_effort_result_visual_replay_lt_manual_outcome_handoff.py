import json
from copy import deepcopy
from pathlib import Path

import pytest

from audit.adapt_effort_result_visual_replay_lt_manual_outcome_handoff import (
    HANDOFF_BLOCKED_STATUS,
    HANDOFF_READY_STATUS,
    SOURCE_ALLOWED_NEXT_STEP,
    SOURCE_READY_DECISION,
    SOURCE_READY_STATUS,
    adapt_effort_result_visual_replay_lt_manual_outcome_handoff,
    main,
    render_effort_result_visual_replay_lt_manual_outcome_handoff_markdown,
)

ROOT = Path(__file__).resolve().parents[1]
PENDING_SOURCE = ROOT / "audit/fixtures/effort_result_visual_replay_lt_manual_evidence_completion_pending.json"
PENDING_FIXTURE = ROOT / "audit/fixtures/effort_result_visual_replay_lt_manual_outcome_handoff_pending.json"
MODULE = ROOT / "audit/adapt_effort_result_visual_replay_lt_manual_outcome_handoff.py"


def _pending_source() -> dict:
    return json.loads(PENDING_SOURCE.read_text(encoding="utf-8"))


def _ready_source(*, failed_case: bool = False) -> dict:
    source = deepcopy(_pending_source())
    source["completion_status"] = SOURCE_READY_STATUS
    source["completion_decision"] = SOURCE_READY_DECISION
    source["completion_ready"] = True
    source["manual_review_complete"] = True
    source["allowed_next_step"] = SOURCE_ALLOWED_NEXT_STEP
    source["blockers"] = []
    source["completed_case_count"] = 2
    source["passed_case_count"] = 1 if failed_case else 2
    source["failed_case_count"] = 1 if failed_case else 0
    source["undecided_case_count"] = 0
    source["evidence_artifact_count"] = 2
    source["shadow_validation_candidate_ready"] = not failed_case
    source["downstream_integration_blocked"] = failed_case
    source["failed_cases_require_resolution"] = failed_case

    for index, case in enumerate(source["completion_cases"]):
        case["completion_case_ready"] = True
        case["manual_review_complete"] = True
        case["reviewer"] = "manual-reviewer"
        case["reviewed_at"] = f"2026-09-14T10:0{index}:00+05:30"
        case["reviewer_notes_recorded"] = True
        case["evidence_artifact"] = f"audit/evidence/lt_case_{index + 1}.png"
        case["blockers"] = []
        case["missing_lane_results"] = []
        case["undecided_lane_results"] = []
        case["invalid_lane_results"] = []
        case["lane_results"] = {lane: "pass" for lane in case["review_lanes"]}
        case["review_outcome"] = "pass"
        case["downstream_integration_blocked"] = False

    if failed_case:
        fail_case = source["completion_cases"][1]
        fail_case["review_outcome"] = "fail"
        fail_case["lane_results"]["vsa_smc_quality_judgment"] = "fail"
        fail_case["downstream_integration_blocked"] = True

    return source


def test_pending_handoff_fixture_blocks_shadow_review_capture() -> None:
    report = adapt_effort_result_visual_replay_lt_manual_outcome_handoff(_pending_source())

    assert report["handoff_status"] == HANDOFF_BLOCKED_STATUS
    assert report["handoff_ready"] is False
    assert report["handoff_case_count"] == 0
    assert report["undecided_case_count"] == 2
    assert report["downstream_integration_blocked"] is True
    assert report["automatic_promotion_allowed"] is False
    assert report["production_change_allowed"] is False
    assert "source_completion_status_not_ready" in report["blockers"]
    assert "handoff_case_blockers_present" in report["blockers"]


def test_pending_fixture_matches_current_completion_gate_pending_source() -> None:
    source = _pending_source()
    expected = json.loads(PENDING_FIXTURE.read_text(encoding="utf-8"))

    assert adapt_effort_result_visual_replay_lt_manual_outcome_handoff(source) == expected


def test_all_pass_completion_gate_hands_off_payload_but_not_production() -> None:
    report = adapt_effort_result_visual_replay_lt_manual_outcome_handoff(_ready_source())

    assert report["handoff_status"] == HANDOFF_READY_STATUS
    assert report["handoff_ready"] is True
    assert report["handoff_case_count"] == 2
    assert report["passed_case_count"] == 2
    assert report["failed_case_count"] == 0
    assert report["shadow_validation_candidate_ready"] is True
    assert report["downstream_integration_blocked"] is False
    assert report["allowed_next_step"] == "run_visual_replay_reviewer_pass_fail_summary"
    assert report["automatic_promotion_allowed"] is False
    assert report["production_pr_required_after_shadow_validation"] is True

    payload = report["manual_review_results_payload"]
    assert len(payload) == 2
    assert payload[0]["review_outcome"] == "pass"
    assert payload[0]["reviewer_notes"].startswith("Reviewer notes recorded in evidence artifact:")


def test_failed_completed_case_hands_off_but_blocks_validation_candidate() -> None:
    report = adapt_effort_result_visual_replay_lt_manual_outcome_handoff(
        _ready_source(failed_case=True)
    )

    assert report["handoff_ready"] is True
    assert report["handoff_case_count"] == 2
    assert report["failed_case_count"] == 1
    assert report["shadow_validation_candidate_ready"] is False
    assert report["downstream_integration_blocked"] is True
    assert report["failed_cases_require_resolution"] is True

    payload = report["manual_review_results_payload"]
    assert payload[1]["review_outcome"] == "fail"
    assert payload[1]["lane_results"]["vsa_smc_quality_judgment"] == "fail"


def test_source_unsafe_boundary_blocks_handoff() -> None:
    source = _ready_source()
    source["production_change_allowed"] = True

    report = adapt_effort_result_visual_replay_lt_manual_outcome_handoff(source)

    assert report["handoff_ready"] is False
    assert "source_production_boundary_open" in report["blockers"]


def test_case_unsafe_boundary_blocks_case_handoff() -> None:
    source = _ready_source()
    source["completion_cases"][0]["may_change_scoring"] = True

    report = adapt_effort_result_visual_replay_lt_manual_outcome_handoff(source)

    assert report["handoff_ready"] is False
    assert "handoff_case_blockers_present" in report["blockers"]
    assert "case_production_boundary_open" in report["handoff_cases"][0]["blockers"]


def test_symbol_filter_requires_selected_cases() -> None:
    report = adapt_effort_result_visual_replay_lt_manual_outcome_handoff(
        _ready_source(),
        required_symbols=("RELIANCE.NS",),
    )

    assert report["selected_case_count"] == 0
    assert report["handoff_ready"] is False
    assert "missing_required_symbols" in report["blockers"]
    assert "no_manual_outcome_cases_selected" in report["blockers"]


def test_invalid_lane_result_blocks_handoff() -> None:
    source = _ready_source()
    source["completion_cases"][0]["lane_results"]["marker_alignment_recheck"] = "maybe"

    report = adapt_effort_result_visual_replay_lt_manual_outcome_handoff(source)

    assert report["handoff_ready"] is False
    assert "handoff_case_blockers_present" in report["blockers"]
    assert "undecided_required_lane_results" in report["handoff_cases"][0]["blockers"]


def test_min_handoff_cases_must_be_positive() -> None:
    with pytest.raises(ValueError, match="min_handoff_cases must be positive"):
        adapt_effort_result_visual_replay_lt_manual_outcome_handoff(
            _pending_source(),
            min_handoff_cases=0,
        )


def test_markdown_renders_decision_and_payload_context() -> None:
    report = adapt_effort_result_visual_replay_lt_manual_outcome_handoff(_pending_source())
    markdown = render_effort_result_visual_replay_lt_manual_outcome_handoff_markdown(report)

    assert "# LT Visual Replay Manual Outcome Handoff" in markdown
    assert "blocked_from_shadow_review_result_capture" in markdown
    assert "LT.NS|2025-02-24|STRUCTURAL_WEAKENING" in markdown
    assert "Production change allowed: false" in markdown


def test_cli_writes_json_and_markdown(tmp_path: Path) -> None:
    json_output = tmp_path / "handoff.json"
    md_output = tmp_path / "handoff.md"

    assert main([str(PENDING_SOURCE), "--output", str(json_output)]) == 0
    report = json.loads(json_output.read_text(encoding="utf-8"))
    assert report["handoff_status"] == HANDOFF_BLOCKED_STATUS

    assert main([str(PENDING_SOURCE), "--format", "markdown", "--output", str(md_output)]) == 0
    assert "# LT Visual Replay Manual Outcome Handoff" in md_output.read_text(encoding="utf-8")


def test_source_contains_no_live_fetch_storage_or_order_side_effects() -> None:
    source = MODULE.read_text(encoding="utf-8").lower()
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

    for token in forbidden_tokens:
        assert token not in source
