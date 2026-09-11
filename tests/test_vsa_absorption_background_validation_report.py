from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from vsa_absorption_background_validation_report import (
    build_vsa_absorption_background_validation_report,
    render_vsa_absorption_background_validation_casebook_csv,
    render_vsa_absorption_background_validation_report_markdown,
)


def _payload() -> dict:
    return {
        "results": [
            {
                "symbol": "XYZ",
                "rows": [
                    {
                        "replay_week": "2026-01-05",
                        "replay_bar_index": 10,
                        "qualification": "persistent_bearish",
                        "target_event_codes": ["increasing_supply"],
                    },
                    {
                        "replay_week": "2026-01-12",
                        "replay_bar_index": 11,
                        "qualification": "persistent_bearish",
                        "target_event_codes": ["supply_absorption"],
                        "detector_diagnostics": ["review_potential_absorption"],
                    },
                    {
                        "replay_week": "2026-01-19",
                        "replay_bar_index": 12,
                        "qualification": "persistent_bearish",
                        "target_event_codes": ["demand_coming_in"],
                    },
                ],
            }
        ]
    }


def test_absorption_validation_report_summarizes_casebook_and_production_only() -> None:
    report = build_vsa_absorption_background_validation_report(
        _payload(),
        lookback_rows=1,
        lookahead_rows=1,
    )

    payload = report.to_dict()

    assert payload["audit_only"] is True
    assert payload["production_safe"] is True
    assert payload["total_input_rows"] == 3
    assert payload["total_casebook_rows"] == 1
    assert payload["status_counts"] == {"absorption_background_review": 1}
    assert payload["seed_type_counts"] == {"absorption_seed": 1}
    assert payload["diagnostic_hint_counts"] == {"review_potential_absorption": 1}
    assert payload["production_only"]["total_casebook_rows"] == 1
    assert payload["production_only"]["status_counts"] == {
        "absorption_background_review": 1,
    }
    assert "Selling pressure may be getting absorbed" in payload["plain_english"]


def test_absorption_validation_markdown_keeps_plain_english_contract() -> None:
    report = build_vsa_absorption_background_validation_report(
        _payload(),
        lookback_rows=1,
        lookahead_rows=1,
    )

    markdown = render_vsa_absorption_background_validation_report_markdown(report)

    assert "# 6D Absorption Background Saved-Output Validation" in markdown
    assert "Plain-English frontend contract" in markdown
    assert "Selling pressure may be getting absorbed" in markdown
    assert "- Saved replay rows checked: 3" in markdown
    assert "- absorption_background_review: 1" in markdown
    assert "not an automatic bullish flip" in markdown


def test_absorption_validation_casebook_csv_uses_report_rows() -> None:
    report = build_vsa_absorption_background_validation_report(
        _payload(),
        lookback_rows=1,
        lookahead_rows=1,
    )

    csv_text = render_vsa_absorption_background_validation_casebook_csv(report)

    assert "casebook_id,symbol,seed_type" in csv_text
    assert "absorption_background_review" in csv_text
    assert "Selling pressure may be getting absorbed" in csv_text


def test_absorption_validation_cli_runs_from_repo_root(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    input_path = tmp_path / "input.json"
    json_output = tmp_path / "validation.json"
    report_output = tmp_path / "validation.md"
    casebook_json_output = tmp_path / "casebook.json"
    casebook_csv_output = tmp_path / "casebook.csv"

    input_path.write_text(json.dumps(_payload()), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "scripts/vsa_absorption_background_validation_report.py",
            str(input_path),
            "--json-output",
            str(json_output),
            "--report-output",
            str(report_output),
            "--casebook-json-output",
            str(casebook_json_output),
            "--casebook-csv-output",
            str(casebook_csv_output),
            "--lookback-rows",
            "1",
            "--lookahead-rows",
            "1",
        ],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )

    output_payload = json.loads(json_output.read_text(encoding="utf-8"))
    assert output_payload["total_casebook_rows"] == 1
    assert output_payload["status_counts"] == {"absorption_background_review": 1}
    assert "Plain-English frontend contract" in report_output.read_text(encoding="utf-8")
    assert "absorption_background_review" in casebook_json_output.read_text(encoding="utf-8")
    assert "absorption_background_review" in casebook_csv_output.read_text(encoding="utf-8")
