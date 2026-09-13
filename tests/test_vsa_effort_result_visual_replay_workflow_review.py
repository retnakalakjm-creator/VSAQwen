import json
import subprocess
import sys
from pathlib import Path

from audit.review_effort_result_visual_replay_workflow import (
    REPORT_TYPE,
    WORKFLOW_NEEDS_ATTENTION_STATUS,
    WORKFLOW_READY_STATUS,
    build_effort_result_visual_replay_workflow_review,
    render_effort_result_visual_replay_workflow_markdown,
)


def _dataset(**overrides):
    marker = {
        "target": "EFFORT_RESULT+SUPPLY_COMING_IN",
        "symbol": "LT.NS",
        "bar_index": 4,
        "week_beginning": "2026-03-04",
        "event_labels": ["SUPPLY_COMING_IN"],
        "shadow_signal_role": "bearish_shadow_observation",
        "observation_status": "shadow_observation_ready",
        "include_in_scoring": False,
        "include_in_ranking": False,
        "include_in_actionability": False,
        "emit_alert": False,
        "place_order": False,
        "activate_detector": False,
        "api_visible": False,
        "frontend_visible": False,
        "persist_as_production_signal": False,
        "production_change_allowed": False,
        "automatic_promotion_allowed": False,
    }
    sequence = {
        "sequence_id": "EFFORT_RESULT+SUPPLY_COMING_IN|LT.NS|4",
        "target": "EFFORT_RESULT+SUPPLY_COMING_IN",
        "symbol": "LT.NS",
        "event_bar_index": 4,
        "event_week_beginning": "2026-03-04",
        "lookback_bars": 1,
        "forward_bars": 1,
        "frame_count": 3,
        "frames": [
            {
                "bar_index": 3,
                "replay_offset": -1,
                "week_beginning": "2026-03-03",
                "open": 100.0,
                "high": 102.0,
                "low": 99.0,
                "close": 101.0,
                "volume_ratio": 1.2,
                "spread_ratio": 1.5,
                "is_event_bar": False,
                "has_shadow_marker": False,
                "shadow_marker": None,
            },
            {
                "bar_index": 4,
                "replay_offset": 0,
                "week_beginning": "2026-03-04",
                "open": 101.0,
                "high": 103.0,
                "low": 100.0,
                "close": 102.0,
                "volume_ratio": 1.6,
                "spread_ratio": 1.8,
                "is_event_bar": True,
                "has_shadow_marker": True,
                "shadow_marker": marker,
            },
            {
                "bar_index": 5,
                "replay_offset": 1,
                "week_beginning": "2026-03-05",
                "open": 102.0,
                "high": 104.0,
                "low": 101.0,
                "close": 103.0,
                "volume_ratio": 1.1,
                "spread_ratio": 1.3,
                "is_event_bar": False,
                "has_shadow_marker": False,
                "shadow_marker": None,
            },
        ],
        "production_change_allowed": False,
        "automatic_promotion_allowed": False,
        "may_change_api": False,
        "may_change_frontend": False,
    }
    report = {
        "report_type": "effort_result_shadow_replay_dataset",
        "replay_dataset_status": "shadow_replay_dataset_ready",
        "sequence_count": 1,
        "total_frames": 3,
        "replay_sequences": [sequence],
        "production_change_allowed": False,
        "automatic_promotion_allowed": False,
        "may_change_api": False,
        "may_change_frontend": False,
    }
    report.update(overrides)
    return report


def test_ready_visual_replay_workflow_for_valid_dataset():
    report = build_effort_result_visual_replay_workflow_review(_dataset())

    assert report["report_type"] == REPORT_TYPE
    assert report["workflow_status"] == WORKFLOW_READY_STATUS
    assert report["next_stage"] == "manual_visual_replay_review"
    assert report["manual_review_required"] is True
    assert report["visual_replay_review_lanes"] == [
        "pre_event_context",
        "event_marker_alignment",
        "post_event_follow_through",
        "counterfactual_scan",
        "reviewer_notes_and_screenshot",
    ]
    assert report["sequence_reviews"][0]["event_marker_count"] == 1


def test_blocks_unsafe_report_boundary():
    report = build_effort_result_visual_replay_workflow_review(
        _dataset(may_change_frontend=True)
    )

    assert report["workflow_status"] == WORKFLOW_NEEDS_ATTENTION_STATUS
    assert "report_production_boundary_open" in report["blockers"]
    assert report["may_change_frontend"] is False
    assert report["production_change_allowed"] is False


def test_blocks_sequences_without_context_or_marker():
    source = _dataset()
    sequence = dict(source["replay_sequences"][0])
    sequence["frames"] = [
        {
            "bar_index": 4,
            "replay_offset": 0,
            "week_beginning": "2026-03-04",
            "is_event_bar": True,
            "has_shadow_marker": False,
            "shadow_marker": None,
        }
    ]
    source["replay_sequences"] = [sequence]

    report = build_effort_result_visual_replay_workflow_review(source)
    sequence_review = report["sequence_reviews"][0]

    assert report["workflow_status"] == WORKFLOW_NEEDS_ATTENTION_STATUS
    assert "sequence_workflow_blockers_present" in report["blockers"]
    assert "missing_shadow_marker" in sequence_review["blockers"]
    assert "missing_pre_event_context" in sequence_review["blockers"]
    assert "missing_post_event_context" in sequence_review["blockers"]


def test_markdown_renders_manual_visual_replay_checklist():
    report = build_effort_result_visual_replay_workflow_review(_dataset())
    markdown = render_effort_result_visual_replay_workflow_markdown(report)

    assert "# Effort/Result Visual Replay Workflow Review" in markdown
    assert "- [ ] pre_event_context" in markdown
    assert "- [ ] event_marker_alignment" in markdown
    assert "Production change allowed: false" in markdown
    assert "separate production PR" in markdown


def test_cli_writes_markdown_output(tmp_path):
    dataset_path = tmp_path / "replay.json"
    output = tmp_path / "workflow.md"
    dataset_path.write_text(json.dumps(_dataset()), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "-m",
            "audit.review_effort_result_visual_replay_workflow",
            str(dataset_path),
            "--format",
            "markdown",
            "--output",
            str(output),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
    )

    text = output.read_text(encoding="utf-8")
    assert "Effort/Result Visual Replay Workflow Review" in text
    assert "ready_for_manual_visual_replay" in text
