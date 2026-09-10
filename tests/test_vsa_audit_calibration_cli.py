from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


SCRIPT = Path("scripts/vsa_audit_calibration_summary.py")


def _audit_payload() -> dict[str, object]:
    return {
        "symbols": ["LT.NS"],
        "timeframe": "1W",
        "results": [
            {
                "symbol": "LT.NS",
                "rows": [
                    {
                        "symbol": "LT.NS",
                        "replay_week": "2026-03-02 00:00:00",
                        "replay_bar_index": 233,
                        "target_event_codes": ["increasing_supply"],
                        "scoring_event_codes": ["increasing_supply"],
                        "qualification": "persistent_bearish",
                        "audit_flags": [],
                        "detector_diagnostics": [
                            "review_potential_effort_gt_result",
                            "review_potential_absorption",
                        ],
                    },
                    {
                        "symbol": "LT.NS",
                        "replay_week": "2026-03-09 00:00:00",
                        "replay_bar_index": 234,
                        "target_event_codes": [],
                        "scoring_event_codes": ["increasing_supply"],
                        "qualification": "persistent_bearish",
                        "audit_flags": [],
                        "detector_diagnostics": [],
                    },
                ],
            }
        ],
        "errors": {},
        "audit_only": True,
    }


def test_calibration_cli_writes_summary_to_stdout(tmp_path: Path) -> None:
    audit_file = tmp_path / "LT_New.txt"
    audit_file.write_text(json.dumps(_audit_payload()), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(audit_file)],
        check=True,
        capture_output=True,
        text=True,
    )

    body = json.loads(result.stdout)
    assert body["audit_only"] is True
    assert body["priority_counts"] == {"high": 1}
    assert body["symbol_counts"] == {"LT.NS": 1}
    assert body["rows"][0]["symbol"] == "LT.NS"
    assert body["rows"][0]["priority"] == "high"
    assert "effort_gt_result_candidate" in body["rows"][0]["calibration_tags"]
    assert "absorption_candidate" in body["rows"][0]["calibration_tags"]
    assert "not_confirmed_by_current_detector" in body["rows"][0]["calibration_tags"]


def test_calibration_cli_writes_summary_file(tmp_path: Path) -> None:
    audit_file = tmp_path / "audit.json"
    output_file = tmp_path / "summary" / "calibration.json"
    audit_file.write_text(json.dumps(_audit_payload()), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(audit_file), "--output", str(output_file)],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout == ""
    body = json.loads(output_file.read_text(encoding="utf-8"))
    assert body["diagnostic_counts"] == {
        "review_potential_absorption": 1,
        "review_potential_effort_gt_result": 1,
    }


def test_calibration_cli_rejects_invalid_json(tmp_path: Path) -> None:
    audit_file = tmp_path / "bad.txt"
    audit_file.write_text("not json", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(audit_file)],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "not valid JSON" in result.stderr
