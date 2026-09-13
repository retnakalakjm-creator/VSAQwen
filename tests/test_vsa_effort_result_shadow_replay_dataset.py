import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from audit.build_effort_result_shadow_replay_dataset import (
    REPLAY_DATASET_BLOCKED_STATUS,
    REPLAY_DATASET_READY_STATUS,
    REPORT_TYPE,
    build_effort_result_shadow_replay_dataset,
    render_shadow_replay_dataset_markdown,
    write_shadow_replay_dataset_csv,
)


def _validation_csv(path: Path) -> Path:
    rows = []
    for bar_index in range(1, 8):
        rows.append(
            {
                "symbol": "LT.NS",
                "bar_index": bar_index,
                "week_beginning": f"2026-03-{bar_index:02d}",
                "open": 100 + bar_index,
                "high": 102 + bar_index,
                "low": 99 + bar_index,
                "close": 101 + bar_index,
                "volume": 1000 + bar_index,
                "volume_ratio": 1.2 + bar_index / 10,
                "spread_ratio": 1.5 + bar_index / 10,
                "relationship": "high_effort_high_result",
                "effort_result_candidate": "EFFORT_RESULT",
                "existing_events": "[]",
            }
        )
    for bar_index in range(1, 5):
        rows.append(
            {
                "symbol": "HDFCBANK.NS",
                "bar_index": bar_index,
                "week_beginning": f"2026-04-{bar_index:02d}",
                "open": 200 + bar_index,
                "high": 204 + bar_index,
                "low": 199 + bar_index,
                "close": 202 + bar_index,
                "volume": 2000 + bar_index,
                "volume_ratio": 0.6,
                "spread_ratio": 1.8,
                "relationship": "low_effort_high_result",
                "effort_result_candidate": "RESULT_GT_EFFORT",
                "existing_events": "[]",
            }
        )
    csv_path = path / "validation.csv"
    pd.DataFrame(rows).to_csv(csv_path, index=False)
    return csv_path


def _observation(**overrides):
    row = {
        "target": "EFFORT_RESULT+SUPPLY_COMING_IN",
        "symbol": "LT.NS",
        "bar_index": 4,
        "week_beginning": "2026-03-04",
        "relationship": "high_effort_high_result",
        "effort_result_candidate": "EFFORT_RESULT",
        "event_labels": ["SUPPLY_COMING_IN"],
        "shadow_signal_role": "bearish_shadow_observation",
        "source_gate_status": "ready_for_separate_production_pr_review",
        "manual_review_status": "approved_for_calibration_experiment",
        "observation_status": "shadow_observation_ready",
        "shadow_mode": True,
        "observation_only": True,
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
        "forward_return_1": -0.01,
        "forward_up_1": False,
    }
    row.update(overrides)
    return row


def _observations_report(rows):
    return {
        "report_type": "effort_result_shadow_observations",
        "shadow_observation_status": "shadow_observation_ready",
        "observations": rows,
    }


def test_builds_replay_sequences_from_ready_shadow_observations(tmp_path):
    csv_path = _validation_csv(tmp_path)
    report = build_effort_result_shadow_replay_dataset(
        csv_path,
        _observations_report([_observation()]),
        lookback_bars=2,
        forward_bars=1,
    )

    assert report["report_type"] == REPORT_TYPE
    assert report["replay_dataset_status"] == REPLAY_DATASET_READY_STATUS
    assert report["sequence_count"] == 1
    sequence = report["replay_sequences"][0]
    assert sequence["sequence_id"] == "EFFORT_RESULT+SUPPLY_COMING_IN|LT.NS|4"
    assert [frame["bar_index"] for frame in sequence["frames"]] == [2, 3, 4, 5]
    assert report["next_stage"] == "shadow_replay_contract_review"


def test_event_frame_contains_one_shadow_marker_and_forward_outcomes(tmp_path):
    csv_path = _validation_csv(tmp_path)
    report = build_effort_result_shadow_replay_dataset(
        csv_path,
        _observations_report([_observation()]),
        lookback_bars=1,
        forward_bars=1,
    )
    frames = report["replay_sequences"][0]["frames"]
    event_frames = [frame for frame in frames if frame["has_shadow_marker"]]

    assert len(event_frames) == 1
    marker = event_frames[0]["shadow_marker"]
    assert marker["target"] == "EFFORT_RESULT+SUPPLY_COMING_IN"
    assert marker["shadow_signal_role"] == "bearish_shadow_observation"
    assert marker["forward_return_1"] == -0.01
    assert marker["include_in_scoring"] is False
    assert event_frames[0]["frontend_visible"] is False


def test_ignores_non_ready_or_unsafe_observations(tmp_path):
    csv_path = _validation_csv(tmp_path)
    report = build_effort_result_shadow_replay_dataset(
        csv_path,
        _observations_report(
            [
                _observation(observation_status="blocked_pending_shadow_mode_proposal"),
                _observation(bar_index=5, include_in_scoring=True),
            ]
        ),
    )

    assert report["replay_dataset_status"] == REPLAY_DATASET_BLOCKED_STATUS
    assert report["sequence_count"] == 0
    assert report["replay_sequences"] == []


def test_deduplicates_observations_by_target_symbol_and_bar(tmp_path):
    csv_path = _validation_csv(tmp_path)
    report = build_effort_result_shadow_replay_dataset(
        csv_path,
        _observations_report([_observation(), _observation()]),
    )

    assert report["sequence_count"] == 1


def test_target_summaries_group_sequences_by_target(tmp_path):
    csv_path = _validation_csv(tmp_path)
    report = build_effort_result_shadow_replay_dataset(
        csv_path,
        _observations_report(
            [
                _observation(),
                _observation(
                    target="RESULT_GT_EFFORT",
                    symbol="HDFCBANK.NS",
                    bar_index=2,
                    week_beginning="2026-04-02",
                    shadow_signal_role="direction_sensitive_shadow_observation",
                ),
            ]
        ),
        lookback_bars=1,
        forward_bars=1,
    )

    assert report["sequence_count"] == 2
    summaries = {row["target"]: row for row in report["target_summaries"]}
    assert summaries["EFFORT_RESULT+SUPPLY_COMING_IN"]["symbols"] == ["LT.NS"]
    assert summaries["RESULT_GT_EFFORT"]["symbols"] == ["HDFCBANK.NS"]
    assert all(row["production_surfaces_disabled"] for row in summaries.values())


def test_production_boundary_remains_closed(tmp_path):
    csv_path = _validation_csv(tmp_path)
    report = build_effort_result_shadow_replay_dataset(
        csv_path,
        _observations_report([_observation()]),
    )

    assert report["audit_only"] is True
    assert report["shadow_mode_only"] is True
    assert report["replay_dataset_only"] is True
    assert report["production_change_allowed"] is False
    assert report["may_change_scoring"] is False
    assert report["may_change_ranking"] is False
    assert report["may_change_actionability"] is False
    assert report["may_activate_detector"] is False
    assert report["may_change_api"] is False
    assert report["may_change_frontend"] is False


@pytest.mark.parametrize(
    "kwargs,error",
    [
        ({"lookback_bars": -1}, "lookback_bars must be non-negative"),
        ({"forward_bars": -1}, "forward_bars must be non-negative"),
        ({"max_sequences": 0}, "max_sequences must be positive"),
    ],
)
def test_rejects_invalid_replay_bounds(tmp_path, kwargs, error):
    csv_path = _validation_csv(tmp_path)
    with pytest.raises(ValueError, match=error):
        build_effort_result_shadow_replay_dataset(
            csv_path,
            _observations_report([_observation()]),
            **kwargs,
        )


def test_markdown_renderer_includes_replay_contract_and_disabled_surfaces(tmp_path):
    csv_path = _validation_csv(tmp_path)
    report = build_effort_result_shadow_replay_dataset(
        csv_path,
        _observations_report([_observation()]),
    )
    markdown = render_shadow_replay_dataset_markdown(report)

    assert "# Effort/Result Shadow Replay Dataset" in markdown
    assert "EFFORT_RESULT+SUPPLY_COMING_IN" in markdown
    assert "Production change allowed: false" in markdown
    assert "A later frontend PR can consume this dataset shape" in markdown


def test_csv_writer_flattens_replay_frames(tmp_path):
    csv_path = _validation_csv(tmp_path)
    report = build_effort_result_shadow_replay_dataset(
        csv_path,
        _observations_report([_observation()]),
        lookback_bars=0,
        forward_bars=0,
    )
    output = tmp_path / "replay.csv"

    write_shadow_replay_dataset_csv(report, output)

    written = output.read_text(encoding="utf-8")
    assert "sequence_id,target,symbol" in written
    assert "EFFORT_RESULT+SUPPLY_COMING_IN|LT.NS|4" in written
    assert "bearish_shadow_observation" in written


def test_cli_writes_json_and_markdown_outputs(tmp_path):
    csv_path = _validation_csv(tmp_path)
    observations_path = tmp_path / "observations.json"
    json_output = tmp_path / "replay.json"
    markdown_output = tmp_path / "replay.md"
    observations_path.write_text(
        json.dumps(_observations_report([_observation()])),
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            "-m",
            "audit.build_effort_result_shadow_replay_dataset",
            str(csv_path),
            str(observations_path),
            "--lookback-bars",
            "1",
            "--forward-bars",
            "1",
            "--format",
            "json",
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
            "audit.build_effort_result_shadow_replay_dataset",
            str(csv_path),
            str(observations_path),
            "--format",
            "markdown",
            "--output",
            str(markdown_output),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
    )

    payload = json.loads(json_output.read_text(encoding="utf-8"))
    assert payload["report_type"] == REPORT_TYPE
    assert payload["sequence_count"] == 1
    assert "Shadow Replay Dataset" in markdown_output.read_text(encoding="utf-8")
