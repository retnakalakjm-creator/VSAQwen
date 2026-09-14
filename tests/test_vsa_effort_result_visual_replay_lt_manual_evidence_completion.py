from __future__ import annotations

import json
from pathlib import Path

import pytest

from audit.decide_effort_result_visual_replay_lt_manual_evidence_completion import (
    COMPLETION_BLOCKED_STATUS,
    COMPLETION_READY_STATUS,
    FAIL,
    PASS,
    decide_effort_result_visual_replay_lt_manual_evidence_completion,
    main,
    render_effort_result_visual_replay_lt_manual_evidence_completion_markdown,
)

FIXTURE_DIR = Path("audit/fixtures")
PENDING_PACKET = FIXTURE_DIR / "effort_result_visual_replay_lt_manual_evidence_review_packet_pending.json"
PENDING_FIXTURE = FIXTURE_DIR / "effort_result_visual_replay_lt_manual_evidence_completion_pending.json"


def _pending_packet() -> dict[str, object]:
    return json.loads(PENDING_PACKET.read_text(encoding="utf-8"))


def _completed_packet(outcomes: tuple[str, str] = (PASS, PASS)) -> dict[str, object]:
    packet = _pending_packet()
    packet["evidence_packet_status"] = "lt_visual_replay_manual_evidence_packet_ready"
    packet["evidence_packet_decision"] = "ready_for_manual_lt_visual_replay_review_result_capture"
    packet["evidence_packet_ready"] = True
    packet["manual_review_complete"] = True
    packet["shadow_validation_candidate_ready"] = outcomes == (PASS, PASS)
    packet["allowed_next_step"] = "run_manual_lt_visual_replay_review_result_capture"
    packet["blockers"] = []
    packet["complete_case_count"] = 2
    packet["passed_case_count"] = sum(1 for outcome in outcomes if outcome == PASS)
    packet["failed_case_count"] = sum(1 for outcome in outcomes if outcome == FAIL)
    packet["undecided_case_count"] = 0
    packet["evidence_artifact_count"] = 2

    for index, case in enumerate(packet["case_packets"]):
        outcome = outcomes[index]
        case["blockers"] = []
        case["review_outcome"] = outcome
        case["reviewer"] = "manual-reviewer"
        case["reviewed_at"] = "2026-09-14T10:30:00+05:30"
        case["reviewer_notes_recorded"] = True
        case["evidence_artifact"] = f"audit/evidence/{case['case_id'].replace('|', '_')}.md"
        case["manual_review_complete"] = True
        case["lane_results"] = {lane: PASS for lane in case["review_lanes"]}
        if outcome == FAIL:
            case["lane_results"]["vsa_smc_quality_judgment"] = FAIL
            case["downstream_integration_blocked"] = True
        else:
            case["downstream_integration_blocked"] = False
        case["undecided_lane_results"] = []
        case["missing_lane_results"] = []
        case["invalid_lane_results"] = []

    return packet


def test_all_pass_packet_completes_and_allows_result_capture() -> None:
    report = decide_effort_result_visual_replay_lt_manual_evidence_completion(_completed_packet())

    assert report["completion_status"] == COMPLETION_READY_STATUS
    assert report["completion_ready"] is True
    assert report["manual_review_complete"] is True
    assert report["shadow_validation_candidate_ready"] is True
    assert report["downstream_integration_blocked"] is False
    assert report["allowed_next_step"] == "run_manual_lt_visual_replay_review_result_capture"
    assert report["completed_case_count"] == 2
    assert report["passed_case_count"] == 2
    assert report["failed_case_count"] == 0


def test_failed_completed_case_is_complete_but_blocks_shadow_validation() -> None:
    report = decide_effort_result_visual_replay_lt_manual_evidence_completion(
        _completed_packet((PASS, FAIL))
    )

    assert report["completion_ready"] is True
    assert report["manual_review_complete"] is True
    assert report["shadow_validation_candidate_ready"] is False
    assert report["downstream_integration_blocked"] is True
    assert report["failed_cases_require_resolution"] is True
    failed_cases = [
        case for case in report["completion_cases"] if case["review_outcome"] == FAIL
    ]
    assert failed_cases
    assert failed_cases[0]["manual_review_complete"] is True


def test_pending_fixture_matches_generated_output() -> None:
    source = _pending_packet()
    expected = json.loads(PENDING_FIXTURE.read_text(encoding="utf-8"))

    assert decide_effort_result_visual_replay_lt_manual_evidence_completion(source) == expected


def test_pending_packet_is_blocked_until_human_evidence_is_complete() -> None:
    report = decide_effort_result_visual_replay_lt_manual_evidence_completion(_pending_packet())

    assert report["completion_status"] == COMPLETION_BLOCKED_STATUS
    assert report["completion_ready"] is False
    assert report["manual_review_complete"] is False
    assert report["allowed_next_step"] == "complete_manual_lt_visual_replay_evidence_packet"
    assert "source_evidence_packet_ready_false" in report["blockers"]
    assert "completion_case_blockers_present" in report["blockers"]
    assert "undecided_completion_cases_present" in report["blockers"]


def test_missing_required_symbol_blocks_completion() -> None:
    report = decide_effort_result_visual_replay_lt_manual_evidence_completion(
        _completed_packet(), required_symbols=("RELIANCE.NS",)
    )

    assert report["completion_ready"] is False
    assert "missing_required_symbol_cases" in report["blockers"]


def test_min_completed_cases_must_be_positive() -> None:
    with pytest.raises(ValueError, match="min_completed_cases"):
        decide_effort_result_visual_replay_lt_manual_evidence_completion(
            _completed_packet(), min_completed_cases=0
        )


def test_source_unsafe_field_blocks_completion() -> None:
    packet = _completed_packet()
    packet["may_change_scoring"] = True

    report = decide_effort_result_visual_replay_lt_manual_evidence_completion(packet)

    assert report["completion_ready"] is False
    assert "source_production_boundary_open" in report["blockers"]


def test_case_unsafe_field_blocks_completion() -> None:
    packet = _completed_packet()
    packet["case_packets"][0]["may_change_frontend"] = True

    report = decide_effort_result_visual_replay_lt_manual_evidence_completion(packet)

    assert report["completion_ready"] is False
    assert "completion_case_blockers_present" in report["blockers"]
    assert "case_production_boundary_open" in report["completion_cases"][0]["blockers"]


def test_pass_cannot_hide_failed_lane() -> None:
    packet = _completed_packet()
    packet["case_packets"][0]["lane_results"]["marker_alignment_recheck"] = FAIL

    report = decide_effort_result_visual_replay_lt_manual_evidence_completion(packet)

    assert report["completion_ready"] is False
    assert "pass_outcome_conflicts_with_failed_lane" in report["completion_cases"][0]["blockers"]


def test_markdown_renders_cases_and_boundaries() -> None:
    report = decide_effort_result_visual_replay_lt_manual_evidence_completion(_pending_packet())
    markdown = render_effort_result_visual_replay_lt_manual_evidence_completion_markdown(report)

    assert "LT Visual Replay Manual Evidence Completion Gate" in markdown
    assert "LT.NS|2025-02-24|STRUCTURAL_WEAKENING" in markdown
    assert "Production change allowed: false" in markdown
    assert "Requires a separate production PR" in markdown


def test_cli_writes_json_and_markdown(tmp_path: Path) -> None:
    output_json = tmp_path / "completion.json"
    output_markdown = tmp_path / "completion.md"

    exit_code = main(
        [
            str(PENDING_PACKET),
            "--output-json",
            str(output_json),
            "--output-markdown",
            str(output_markdown),
        ]
    )

    assert exit_code == 0
    assert json.loads(output_json.read_text(encoding="utf-8"))["completion_ready"] is False
    assert "Completion Gate" in output_markdown.read_text(encoding="utf-8")


def test_source_contains_no_live_fetch_or_storage_side_effects() -> None:
    source = Path(
        "audit/decide_effort_result_visual_replay_lt_manual_evidence_completion.py"
    ).read_text(encoding="utf-8")

    forbidden_tokens = (
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
    )

    assert not any(token in source for token in forbidden_tokens)
