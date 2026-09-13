import json
import subprocess
import sys
from pathlib import Path

from audit.run_effort_result_visual_replay_casebook import (
    CASEBOOK_NEEDS_ATTENTION_STATUS,
    CASEBOOK_READY_STATUS,
    DEFAULT_SYMBOL_FILTER,
    REPORT_TYPE,
    render_effort_result_visual_replay_casebook_markdown,
    run_effort_result_visual_replay_casebook,
)


def _sequence(**overrides):
    sequence = {
        "sequence_id": "EFFORT_RESULT+SUPPLY_COMING_IN|LT.NS|2026-03-04",
        "target": "EFFORT_RESULT+SUPPLY_COMING_IN",
        "symbol": "LT.NS",
        "event_week_beginning": "2026-03-04",
        "marker_labels": ["SUPPLY_COMING_IN"],
        "required_statuses": {
            "marker_alignment_status": "confirmed",
            "pre_event_context_status": "confirmed",
            "post_event_follow_through_status": "confirmed",
            "counterfactual_scan_status": "confirmed",
            "vsa_smc_quality_status": "confirmed",
        },
        "reviewer_notes_recorded": True,
        "screenshot_filename_recorded": False,
        "reviewer_notes": "Marker aligns with supply coming in after weak follow-through.",
        "screenshot_filename": "",
        "evidence_status": "confirmed_visual_replay_evidence",
        "manual_review_only": True,
        "production_change_allowed": False,
        "automatic_promotion_allowed": False,
    }
    sequence.update(overrides)
    return sequence


def _compiled_report(**overrides):
    report = {
        "report_type": "effort_result_visual_replay_evidence_compilation",
        "report_schema_version": 1,
        "source_report_type": "effort_result_visual_replay_evidence_draft",
        "source_evidence_status": "all_sequences_confirmed",
        "reviewed_sequence_count": 1,
        "confirmed_sequence_count": 1,
        "evidence_compilation_status": "visual_replay_evidence_ready",
        "evidence_ready": True,
        "sequence_reviews": [_sequence()],
        "manual_review_only": True,
        "offline_replay_only": True,
        "production_change_allowed": False,
        "automatic_promotion_allowed": False,
        "may_change_api": False,
        "may_change_frontend": False,
    }
    report.update(overrides)
    return report


def test_ready_lt_visual_replay_casebook_from_confirmed_evidence():
    report = run_effort_result_visual_replay_casebook(_compiled_report())

    assert report["report_type"] == REPORT_TYPE
    assert report["casebook_status"] == CASEBOOK_READY_STATUS
    assert report["casebook_ready"] is True
    assert report["symbol_filter"] == list(DEFAULT_SYMBOL_FILTER)
    assert report["ready_case_count"] == 1
    assert report["casebook_cases"][0]["case_id"] == "LT.NS|2026-03-04|EFFORT_RESULT+SUPPLY_COMING_IN"
    assert report["next_stage"] == "reviewer_pass_fail_summary_report"
    assert report["production_change_allowed"] is False
    assert report["may_change_scoring"] is False
    assert report["may_change_api"] is False


def test_blocks_wrong_source_or_unready_compilation():
    report = run_effort_result_visual_replay_casebook(
        _compiled_report(
            report_type="wrong_report",
            evidence_compilation_status="visual_replay_evidence_needs_attention",
            evidence_ready=False,
        )
    )

    assert report["casebook_status"] == CASEBOOK_NEEDS_ATTENTION_STATUS
    assert report["casebook_ready"] is False
    assert "source_report_type_mismatch" in report["blockers"]
    assert "source_evidence_compilation_not_ready" in report["blockers"]
    assert "source_evidence_not_ready" in report["blockers"]


def test_filters_to_lt_sample_cases_only_by_default():
    source = _compiled_report(
        reviewed_sequence_count=2,
        confirmed_sequence_count=2,
        sequence_reviews=[
            _sequence(),
            _sequence(
                sequence_id="OTHER|RELIANCE.NS|2026-03-04",
                symbol="RELIANCE.NS",
                target="EFFORT_RESULT+NO_DEMAND",
            ),
        ],
    )

    report = run_effort_result_visual_replay_casebook(source)

    assert report["selected_sequence_count"] == 1
    assert report["casebook_case_count"] == 1
    assert report["casebook_cases"][0]["symbol"] == "LT.NS"


def test_blocks_when_no_lt_symbol_matches():
    source = _compiled_report(sequence_reviews=[_sequence(symbol="RELIANCE.NS")])

    report = run_effort_result_visual_replay_casebook(source)

    assert report["casebook_status"] == CASEBOOK_NEEDS_ATTENTION_STATUS
    assert "no_matching_symbol_sequences" in report["blockers"]
    assert "not_enough_ready_casebook_cases" in report["blockers"]


def test_blocks_unconfirmed_case_and_preserves_closed_boundary():
    source = _compiled_report(
        sequence_reviews=[
            _sequence(
                evidence_status="visual_replay_sequence_needs_attention",
                marker_labels=[],
                required_statuses={
                    "marker_alignment_status": "confirmed",
                    "pre_event_context_status": "needs_attention",
                },
                reviewer_notes_recorded=False,
                reviewer_notes="",
                screenshot_filename_recorded=False,
                screenshot_filename="",
                production_change_allowed=True,
            )
        ],
        may_change_api=True,
    )

    report = run_effort_result_visual_replay_casebook(source)
    case = report["casebook_cases"][0]

    assert report["casebook_status"] == CASEBOOK_NEEDS_ATTENTION_STATUS
    assert "report_production_boundary_open" in report["blockers"]
    assert "casebook_case_blockers_present" in report["blockers"]
    assert "source_sequence_not_confirmed" in case["blockers"]
    assert "required_replay_status_not_confirmed" in case["blockers"]
    assert "missing_marker_labels" in case["blockers"]
    assert "missing_evidence_artifact_trace" in case["blockers"]
    assert "sequence_production_boundary_open" in case["blockers"]
    assert report["production_change_allowed"] is False
    assert report["may_change_api"] is False
    assert case["production_change_allowed"] is False


def test_markdown_renders_casebook_review_lanes_and_rules():
    report = run_effort_result_visual_replay_casebook(_compiled_report())
    markdown = render_effort_result_visual_replay_casebook_markdown(report)

    assert "# Effort/Result Visual Replay Casebook" in markdown
    assert "LT.NS" in markdown
    assert "reviewer_pass_fail_summary_report" in markdown
    assert "- [ ] marker_alignment_recheck" in markdown
    assert "Production change allowed: false" in markdown
    assert "separate production PR" in markdown


def test_cli_writes_markdown_output(tmp_path):
    source = tmp_path / "compiled_evidence.json"
    output = tmp_path / "casebook.md"
    source.write_text(json.dumps(_compiled_report()), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "-m",
            "audit.run_effort_result_visual_replay_casebook",
            str(source),
            "--format",
            "markdown",
            "--output",
            str(output),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
    )

    text = output.read_text(encoding="utf-8")
    assert "Effort/Result Visual Replay Casebook" in text
    assert "visual_replay_casebook_ready" in text
