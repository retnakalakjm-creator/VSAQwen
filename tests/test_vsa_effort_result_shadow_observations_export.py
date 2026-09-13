from __future__ import annotations

import csv
import json
import math
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from audit.export_effort_result_shadow_observations import (
    SHADOW_OBSERVATION_STATUS,
    build_effort_result_shadow_observations,
    render_shadow_observations_markdown,
    write_shadow_observations_csv,
)


def _events(*codes: str) -> str:
    return json.dumps([{"code": code.lower()} for code in codes])


def _validation_csv(path: Path) -> Path:
    rows = [
        {
            "symbol": "AAA.NS",
            "bar_index": 1,
            "week_beginning": "2026-01-05",
            "open": 9.5,
            "high": 10.5,
            "low": 9.0,
            "close": 10.0,
            "volume": 100,
            "volume_ratio": 0.50,
            "spread_ratio": 1.80,
            "close_ratio": 0.75,
            "direction": 1,
            "trend_direction": "up",
            "trend_state": "markup",
            "existing_events": _events(),
        },
        {
            "symbol": "AAA.NS",
            "bar_index": 2,
            "week_beginning": "2026-01-12",
            "open": 10.0,
            "high": 11.2,
            "low": 9.8,
            "close": 11.0,
            "volume": 110,
            "volume_ratio": 1.0,
            "spread_ratio": 1.0,
            "close_ratio": 0.6,
            "direction": 1,
            "trend_direction": "up",
            "trend_state": "markup",
            "existing_events": _events(),
        },
        {
            "symbol": "AAA.NS",
            "bar_index": 3,
            "week_beginning": "2026-01-19",
            "open": 11.0,
            "high": 12.2,
            "low": 10.8,
            "close": 12.0,
            "volume": 120,
            "volume_ratio": 1.0,
            "spread_ratio": 1.0,
            "close_ratio": 0.6,
            "direction": 1,
            "trend_direction": "up",
            "trend_state": "markup",
            "existing_events": _events(),
        },
        {
            "symbol": "AAA.NS",
            "bar_index": 5,
            "week_beginning": "2026-02-02",
            "open": 12.0,
            "high": 14.2,
            "low": 11.8,
            "close": 14.0,
            "volume": 140,
            "volume_ratio": 1.0,
            "spread_ratio": 1.0,
            "close_ratio": 0.6,
            "direction": 1,
            "trend_direction": "up",
            "trend_state": "markup",
            "existing_events": _events(),
        },
        {
            "symbol": "BBB.NS",
            "bar_index": 10,
            "week_beginning": "2026-03-02",
            "open": 20.0,
            "high": 22.0,
            "low": 19.8,
            "close": 21.0,
            "volume": 210,
            "volume_ratio": 1.80,
            "spread_ratio": 1.70,
            "close_ratio": 0.5,
            "direction": -1,
            "trend_direction": "down",
            "trend_state": "distribution",
            "existing_events": _events("SUPPLY_COMING_IN"),
        },
        {
            "symbol": "BBB.NS",
            "bar_index": 11,
            "week_beginning": "2026-03-09",
            "open": 21.0,
            "high": 21.5,
            "low": 18.0,
            "close": 19.0,
            "volume": 220,
            "volume_ratio": 1.0,
            "spread_ratio": 1.0,
            "close_ratio": 0.4,
            "direction": -1,
            "trend_direction": "down",
            "trend_state": "distribution",
            "existing_events": _events(),
        },
        {
            "symbol": "CCC.NS",
            "bar_index": 20,
            "week_beginning": "2026-04-06",
            "open": 30.0,
            "high": 31.0,
            "low": 29.0,
            "close": 30.5,
            "volume": 300,
            "volume_ratio": 1.80,
            "spread_ratio": 1.70,
            "close_ratio": 0.5,
            "direction": -1,
            "trend_direction": "down",
            "trend_state": "distribution",
            "existing_events": _events("NO_DEMAND"),
        },
    ]
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def _shadow_proposal() -> dict[str, object]:
    return {
        "report_type": "effort_result_shadow_mode_integration_proposal",
        "proposal_status": "ready_for_shadow_mode_pr_review",
        "target_proposals": [
            {
                "target": "RESULT_GT_EFFORT",
                "proposal_status": "ready_for_shadow_mode_pr_review",
                "source_gate_status": "ready_for_separate_production_pr_review",
                "manual_review_status": "approved_for_calibration_experiment",
                "shadow_signal_role": "direction_sensitive_shadow_observation",
                "reviewed_examples": 5,
                "reviewed_symbols": ["AAA.NS"],
                "reviewed_weeks": ["2026-01-05"],
                "shadow_mode_observation": {"emit_observation": True},
            },
            {
                "target": "EFFORT_RESULT+SUPPLY_COMING_IN",
                "proposal_status": "ready_for_shadow_mode_pr_review",
                "source_gate_status": "ready_for_separate_production_pr_review",
                "manual_review_status": "approved_for_calibration_experiment",
                "shadow_signal_role": "bearish_shadow_observation",
                "reviewed_examples": 7,
                "reviewed_symbols": ["BBB.NS"],
                "reviewed_weeks": ["2026-03-02"],
                "shadow_mode_observation": {"emit_observation": True},
            },
            {
                "target": "EFFORT_GT_RESULT",
                "proposal_status": "blocked_pending_passed_gate",
                "shadow_signal_role": "manual_shadow_observation",
            },
        ],
    }


def test_builds_only_ready_shadow_observations(tmp_path: Path) -> None:
    report = build_effort_result_shadow_observations(
        _validation_csv(tmp_path / "validation.csv"),
        _shadow_proposal(),
    )

    assert report["shadow_observation_status"] == SHADOW_OBSERVATION_STATUS
    assert report["target_count"] == 2
    assert report["blocked_target_count"] == 1
    assert report["total_observations"] == 2
    assert {row["target"] for row in report["observations"]} == {
        "RESULT_GT_EFFORT",
        "EFFORT_RESULT+SUPPLY_COMING_IN",
    }


def test_event_filtered_target_requires_supply_coming_in(tmp_path: Path) -> None:
    report = build_effort_result_shadow_observations(
        _validation_csv(tmp_path / "validation.csv"),
        _shadow_proposal(),
    )

    supply_rows = [
        row
        for row in report["observations"]
        if row["target"] == "EFFORT_RESULT+SUPPLY_COMING_IN"
    ]
    assert len(supply_rows) == 1
    assert supply_rows[0]["symbol"] == "BBB.NS"
    assert supply_rows[0]["event_labels"] == ["SUPPLY_COMING_IN"]


def test_forward_outcomes_are_included_without_scoring(tmp_path: Path) -> None:
    report = build_effort_result_shadow_observations(
        _validation_csv(tmp_path / "validation.csv"),
        _shadow_proposal(),
        horizons=(1, 2, 4),
    )
    result_row = next(
        row for row in report["observations"] if row["target"] == "RESULT_GT_EFFORT"
    )

    assert math.isclose(result_row["forward_return_1"], 0.10)
    assert math.isclose(result_row["forward_return_2"], 0.20)
    assert math.isclose(result_row["forward_return_4"], 0.40)
    assert result_row["include_in_scoring"] is False
    assert result_row["include_in_ranking"] is False
    assert result_row["include_in_actionability"] is False
    assert result_row["activate_detector"] is False
    assert result_row["api_visible"] is False
    assert result_row["frontend_visible"] is False
    assert result_row["production_change_allowed"] is False


def test_max_observations_per_target_limits_output(tmp_path: Path) -> None:
    report = build_effort_result_shadow_observations(
        _validation_csv(tmp_path / "validation.csv"),
        _shadow_proposal(),
        max_observations_per_target=1,
    )

    assert report["total_observations"] == 2
    assert all(row["matched_observations"] == 1 for row in report["target_summaries"])


def test_blocks_when_no_ready_proposal(tmp_path: Path) -> None:
    proposal = _shadow_proposal()
    proposal["target_proposals"] = [
        {"target": "RESULT_GT_EFFORT", "proposal_status": "blocked_pending_passed_gate"}
    ]

    report = build_effort_result_shadow_observations(
        _validation_csv(tmp_path / "validation.csv"),
        proposal,
    )

    assert report["target_count"] == 0
    assert report["blocked_target_count"] == 1
    assert report["total_observations"] == 0
    assert report["shadow_observation_status"] == "blocked_pending_shadow_mode_proposal"
    assert report["next_stage"] == "complete_shadow_mode_integration_proposal"
    assert report["production_change_allowed"] is False


def test_markdown_renderer_declares_shadow_boundary(tmp_path: Path) -> None:
    report = build_effort_result_shadow_observations(
        _validation_csv(tmp_path / "validation.csv"),
        _shadow_proposal(),
    )
    markdown = render_shadow_observations_markdown(report)

    assert "# Effort/Result Shadow Observations" in markdown
    assert "Production change allowed: false" in markdown
    assert "RESULT_GT_EFFORT" in markdown
    assert "EFFORT_RESULT+SUPPLY_COMING_IN" in markdown


def test_write_shadow_observations_csv(tmp_path: Path) -> None:
    report = build_effort_result_shadow_observations(
        _validation_csv(tmp_path / "validation.csv"),
        _shadow_proposal(),
    )
    output = tmp_path / "shadow.csv"

    write_shadow_observations_csv(report, output)

    rows = list(csv.DictReader(output.open(newline="", encoding="utf-8")))
    assert len(rows) == 2
    assert rows[0]["production_change_allowed"] == "False"
    assert "target" in rows[0]
    assert "shadow_signal_role" in rows[0]


def test_cli_writes_json_and_csv(tmp_path: Path) -> None:
    validation_path = _validation_csv(tmp_path / "validation.csv")
    proposal_path = tmp_path / "proposal.json"
    proposal_path.write_text(json.dumps(_shadow_proposal()), encoding="utf-8")
    json_output = tmp_path / "shadow.json"
    csv_output = tmp_path / "shadow.csv"

    subprocess.run(
        [
            sys.executable,
            "-m",
            "audit.export_effort_result_shadow_observations",
            str(validation_path),
            str(proposal_path),
            "--format",
            "json",
            "--output",
            str(json_output),
        ],
        cwd=Path(__file__).parents[1],
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "audit.export_effort_result_shadow_observations",
            str(validation_path),
            str(proposal_path),
            "--format",
            "csv",
            "--output",
            str(csv_output),
        ],
        cwd=Path(__file__).parents[1],
        check=True,
    )

    assert json.loads(json_output.read_text(encoding="utf-8"))["total_observations"] == 2
    assert csv_output.read_text(encoding="utf-8").startswith("target,symbol")


def test_validates_horizons_and_limits(tmp_path: Path) -> None:
    validation_path = _validation_csv(tmp_path / "validation.csv")
    with pytest.raises(ValueError, match="horizons"):
        build_effort_result_shadow_observations(
            validation_path,
            _shadow_proposal(),
            horizons=(0,),
        )
    with pytest.raises(ValueError, match="max_observations"):
        build_effort_result_shadow_observations(
            validation_path,
            _shadow_proposal(),
            max_observations_per_target=0,
        )
