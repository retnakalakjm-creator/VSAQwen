import json
import subprocess
import sys
from pathlib import Path

from audit.compile_effort_result_visual_replay_evidence import (
    EVIDENCE_NEEDS_ATTENTION_STATUS,
    EVIDENCE_READY_STATUS,
    REPORT_TYPE,
    SEQUENCE_CONFIRMED_STATUS,
    compile_effort_result_visual_replay_evidence,
    render_effort_result_visual_replay_evidence_markdown,
)


def _sequence(**overrides):
    sequence = {
        "sequence_id": "EFFORT_RESULT+SUPPLY_COMING_IN|LT.NS|4",
        "symbol": "LT.NS",
        "target": "EFFORT_RESULT+SUPPLY_COMING_IN",
        "event_week_beginning": "2026-03-04",
        "marker_labels": ["SUPPLY_COMING_IN"],
        "marker_alignment_status": "confirmed",
        "pre_event_context_status": "confirmed",
        "post_event_follow_through_status": "confirmed",
        "counterfactual_scan_status": "confirmed",
        "vsa_smc_quality_status": "confirmed",
        "reviewer_notes": "Marker aligned with supply entering after effort/result divergence.",
        "screenshot_filename": "LT_NS_2026-03-04_supply.png",
        "production_change_allowed": False,
    }
    sequence.update(overrides)
    return sequence


def _draft(**overrides):
    report = {
        "report_type": "effort_result_visual_replay_evidence_draft",
        "report_schema_version": 1,
        "review_mode": "manual_visual_replay",
        "evidence_status": "all_sequences_confirmed",
        "sequence_count": 1,
        "confirmed_sequence_count": 1,
        "sequence_evidence": [_sequence()],
        "manual_review_only": True,
        "offline_preview_only": True,
        "export_only": True,
        "persistence_allowed": False,
        "upload_allowed": False,
        "live_data_allowed": False,
        "production_change_allowed": False,
        "scoring_allowed": False,
        "ranking_allowed": False,
        "actionability_allowed": False,
        "detector_activation_allowed": False,
        "alerting_allowed": False,
        "order_execution_allowed": False,
    }
    report.update(overrides)
    return report


def test_compiles_confirmed_visual_replay_evidence():
    report = compile_effort_result_visual_replay_evidence(_draft())

    assert report["report_type"] == REPORT_TYPE
    assert report["evidence_compilation_status"] == EVIDENCE_READY_STATUS
    assert report["evidence_ready"] is True
    assert report["confirmed_sequence_count"] == 1
    assert report["next_stage"] == "offline_replay_casebook_runner"
    assert report["sequence_reviews"][0]["evidence_status"] == SEQUENCE_CONFIRMED_STATUS
    assert report["production_change_allowed"] is False
    assert report["may_change_scoring"] is False
    assert report["may_change_frontend"] is False


def test_blocks_in_progress_source_and_non_confirmed_sequence():
    source = _draft(
        evidence_status="draft_in_progress",
        confirmed_sequence_count=0,
        sequence_evidence=[
            _sequence(
                marker_alignment_status="needs_attention",
                reviewer_notes="Marker appears one bar late.",
            )
        ],
    )

    report = compile_effort_result_visual_replay_evidence(source)

    assert report["evidence_compilation_status"] == EVIDENCE_NEEDS_ATTENTION_STATUS
    assert report["evidence_ready"] is False
    assert "source_evidence_not_all_confirmed" in report["blockers"]
    assert "sequence_evidence_blockers_present" in report["blockers"]
    assert "required_status_not_confirmed" in report["sequence_reviews"][0]["blockers"]


def test_blocks_unsafe_report_boundary():
    report = compile_effort_result_visual_replay_evidence(
        _draft(live_data_allowed=True, production_change_allowed=True)
    )

    assert report["evidence_compilation_status"] == EVIDENCE_NEEDS_ATTENTION_STATUS
    assert "report_production_boundary_open" in report["blockers"]
    assert report["production_change_allowed"] is False
    assert report["may_change_api"] is False


def test_blocks_sequence_missing_marker_labels_and_observation_attachment():
    report = compile_effort_result_visual_replay_evidence(
        _draft(
            sequence_evidence=[
                _sequence(marker_labels=[], reviewer_notes="", screenshot_filename="")
            ]
        )
    )
    sequence_review = report["sequence_reviews"][0]

    assert report["evidence_ready"] is False
    assert "sequence_evidence_blockers_present" in report["blockers"]
    assert "missing_marker_labels" in sequence_review["blockers"]
    assert "missing_reviewer_notes_or_screenshot" in sequence_review["blockers"]


def test_markdown_renders_evidence_summary_and_boundaries():
    report = compile_effort_result_visual_replay_evidence(_draft())
    markdown = render_effort_result_visual_replay_evidence_markdown(report)

    assert "# Effort/Result Visual Replay Evidence Compilation" in markdown
    assert "Evidence ready: true" in markdown
    assert "Production change allowed: false" in markdown
    assert "Requires separate casebook runner PR: true" in markdown
    assert "marker_alignment_status: `confirmed`" in markdown
    assert "separate production PR" in markdown


def test_cli_writes_markdown_output(tmp_path):
    draft_path = tmp_path / "visual_replay_evidence.json"
    output_path = tmp_path / "compiled_evidence.md"
    draft_path.write_text(json.dumps(_draft()), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "-m",
            "audit.compile_effort_result_visual_replay_evidence",
            str(draft_path),
            "--format",
            "markdown",
            "--output",
            str(output_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
    )

    text = output_path.read_text(encoding="utf-8")
    assert "Effort/Result Visual Replay Evidence Compilation" in text
    assert "visual_replay_evidence_ready" in text
