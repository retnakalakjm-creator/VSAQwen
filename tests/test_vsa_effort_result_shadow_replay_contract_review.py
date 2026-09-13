import json
import subprocess
import sys
from pathlib import Path

from audit.review_effort_result_shadow_replay_contract import (
    CONTRACT_NEEDS_ATTENTION_STATUS,
    CONTRACT_READY_STATUS,
    REPORT_TYPE,
    build_shadow_replay_contract_review,
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


def test_ready_contract_review_for_valid_replay_dataset():
    report = build_shadow_replay_contract_review(_dataset())

    assert report["report_type"] == REPORT_TYPE
    assert report["contract_status"] == CONTRACT_READY_STATUS
    assert report["next_stage"] == "separate_frontend_replay_scaffold_pr"
    assert report["frontend_replay_contract"]["marker_field"] == "shadow_marker"


def test_blocks_unsafe_frontend_or_api_surface():
    report = build_shadow_replay_contract_review(_dataset(may_change_frontend=True))

    assert report["contract_status"] == CONTRACT_NEEDS_ATTENTION_STATUS
    assert "report_production_boundary_closed" in report["blockers"]
    assert "frontend_behavior_still_disabled" in report["blockers"]


def test_cli_writes_json_output(tmp_path):
    dataset_path = tmp_path / "replay.json"
    output = tmp_path / "review.json"
    dataset_path.write_text(json.dumps(_dataset()), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "-m",
            "audit.review_effort_result_shadow_replay_contract",
            str(dataset_path),
            "--format",
            "json",
            "--output",
            str(output),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["report_type"] == REPORT_TYPE
    assert payload["contract_status"] == CONTRACT_READY_STATUS
