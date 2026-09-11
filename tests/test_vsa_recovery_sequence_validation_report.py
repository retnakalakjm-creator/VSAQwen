from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from vsa_recovery_sequence_validation_report import (
    build_vsa_recovery_sequence_validation_artifacts,
    build_vsa_recovery_sequence_validation_report,
    render_vsa_recovery_sequence_validation_markdown,
)


STATUS_REVIEW = "stopping_volume_spring_shakeout_review"
STATUS_NONE = "none"
OUTCOME_FIRED = "fired"
OUTCOME_NOT_FIRED = "not_fired"


def test_validation_report_runs_complete_saved_output_chain() -> None:
    payload = {
        "results": [
            {
                "symbol": "LT.NS",
                "rows": [
                    {
                        "symbol": "LT.NS",
                        "replay_bar_index": 234,
                        "replay_week": "2026-03-02 00:00:00",
                        "target_event_codes": ["increasing_supply"],
                        "qualification": "persistent_bearish",
                    },
                    {
                        "symbol": "LT.NS",
                        "replay_bar_index": 235,
                        "replay_week": "2026-03-09 00:00:00",
                        "target_event_codes": ["stopping_volume"],
                        "qualification": "persistent_bearish",
                    },
                    {
                        "symbol": "LT.NS",
                        "replay_bar_index": 236,
                        "replay_week": "2026-03-16 00:00:00",
                        "target_event_codes": ["shakeout"],
                        "qualification": "persistent_bearish",
                    },
                    {
                        "symbol": "LT.NS",
                        "replay_bar_index": 237,
                        "replay_week": "2026-03-23 00:00:00",
                        "target_event_codes": ["demand_coming_in"],
                        "qualification": "persistent_bearish",
                    },
                ],
            }
        ]
    }

    report = build_vsa_recovery_sequence_validation_report(payload)
    data = report.to_dict()

    assert data["audit_only"] is True
    assert data["production_safe"] is True
    assert data["stage_seed"]["total_input_rows"] == 4
    assert data["stage_seed"]["total_stage_seed_rows"] == 2
    assert data["stage_seed"]["status_counts"] == {STATUS_REVIEW: 2}
    assert data["production_only_stage_seed"]["total_stage_seed_rows"] == 2
    assert data["casebook"]["total_casebook_rows"] == 2
    assert data["casebook"]["status_counts"] == {STATUS_REVIEW: 2}
    assert data["label_firing_audit"]["fired_count"] == 2
    assert data["label_firing_audit"]["outcome_counts"] == {OUTCOME_FIRED: 2}


def test_validation_report_keeps_diagnostic_hints_from_promoting_labels() -> None:
    report = build_vsa_recovery_sequence_validation_report(
        {
            "rows": [
                {
                    "symbol": "TMPV.NS",
                    "replay_bar_index": 10,
                    "replay_week": "2026-03-02 00:00:00",
                    "target_event_codes": ["increasing_supply"],
                    "qualification": "persistent_bearish",
                },
                {
                    "symbol": "TMPV.NS",
                    "replay_bar_index": 11,
                    "replay_week": "2026-03-09 00:00:00",
                    "detector_diagnostics": [
                        "review_potential_stopping_volume",
                        "review_potential_spring_or_shakeout",
                    ],
                    "qualification": "persistent_bearish",
                },
                {
                    "symbol": "TMPV.NS",
                    "replay_bar_index": 12,
                    "replay_week": "2026-03-16 00:00:00",
                    "target_event_codes": ["demand_coming_in"],
                    "qualification": "persistent_bearish",
                },
            ]
        }
    )
    data = report.to_dict()

    assert data["stage_seed"]["total_stage_seed_rows"] == 1
    assert data["stage_seed"]["status_counts"] == {STATUS_NONE: 1}
    assert data["production_only_stage_seed"]["total_stage_seed_rows"] == 0
    assert data["casebook"]["status_counts"] == {STATUS_NONE: 1}
    assert data["label_firing_audit"]["outcome_counts"] == {OUTCOME_NOT_FIRED: 1}

    markdown = report.render_markdown()
    assert "Milestone 6C Saved-Output Validation Report" in markdown
    assert "Stage-seed rows: 1" in markdown
    assert "6C stage seeds were found, but no clean recovery-sequence label fired" in markdown


def test_validation_artifacts_include_json_csv_and_markdown() -> None:
    artifacts = build_vsa_recovery_sequence_validation_artifacts(
        {
            "rows": [
                {
                    "symbol": "AMBUJACEM.NS",
                    "replay_bar_index": 235,
                    "replay_week": "2026-03-02 00:00:00",
                    "target_event_codes": ["stopping_volume"],
                    "qualification": "persistent_bearish",
                },
                {
                    "symbol": "AMBUJACEM.NS",
                    "replay_bar_index": 236,
                    "replay_week": "2026-03-09 00:00:00",
                    "target_event_codes": ["shakeout"],
                    "qualification": "persistent_bearish",
                },
                {
                    "symbol": "AMBUJACEM.NS",
                    "replay_bar_index": 237,
                    "replay_week": "2026-03-16 00:00:00",
                    "target_event_codes": ["increasing_demand"],
                    "qualification": "persistent_bearish",
                },
            ]
        }
    )

    assert json.dumps(artifacts.stage_seed_json)
    assert json.dumps(artifacts.casebook_json)
    assert json.dumps(artifacts.label_firing_audit_json)
    assert "AMBUJACEM.NS" in artifacts.stage_seed_csv
    assert "AMBUJACEM.NS" in artifacts.casebook_csv
    assert OUTCOME_FIRED in artifacts.label_firing_audit_csv
    assert "# Milestone 6C Saved-Output Validation Report" in artifacts.report_markdown


def test_validation_report_cli_uses_root_modules_not_script_wrappers(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    input_path = tmp_path / "input.json"
    input_path.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "symbol": "LT.NS",
                        "replay_bar_index": 1,
                        "target_event_codes": ["stopping_volume"],
                        "qualification": "persistent_bearish",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/vsa_recovery_sequence_validation_report.py",
            str(input_path),
        ],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "Milestone 6C Saved-Output Validation Report" in result.stdout


def test_validation_markdown_accepts_plain_mapping() -> None:
    markdown = render_vsa_recovery_sequence_validation_markdown(
        {
            "validation_path": ["saved rows", "stage seed", "casebook", "label audit"],
            "stage_seed": {
                "total_input_rows": 1,
                "total_stage_seed_rows": 0,
                "status_counts": {},
                "stage_seed_type_counts": {},
                "diagnostic_hint_counts": {},
            },
            "casebook": {"total_casebook_rows": 0, "status_counts": {}},
            "label_firing_audit": {
                "total_input_rows": 0,
                "outcome_counts": {},
                "expectation_counts": {},
            },
        }
    )

    assert "1. saved rows" in markdown
    assert "No 6C stage seeds were found" in markdown
