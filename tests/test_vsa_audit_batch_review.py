from __future__ import annotations

import csv
import json
import subprocess
import sys
from io import StringIO
from pathlib import Path

from vsa_audit_batch_review import (
    build_vsa_audit_batch_review,
    render_vsa_audit_batch_review_csv,
)
from vsa_audit_candidate_events import (
    CANDIDATE_ABSORPTION,
    CANDIDATE_EFFORT_GT_RESULT,
    CANDIDATE_HIGH_VOLUME_REVERSAL,
    CANDIDATE_STALE_EVIDENCE,
)


def _row(**overrides):
    base = {
        "symbol": "LT.NS",
        "replay_week": "2026-03-02 00:00:00",
        "replay_bar_index": 233,
        "target_event_codes": ["increasing_supply"],
        "scoring_event_codes": ["increasing_supply"],
        "qualification": "persistent_bearish",
        "audit_flags": [],
        "detector_diagnostics": [],
    }
    base.update(overrides)
    return base


def test_batch_review_accepts_raw_audit_payload_and_summarizes_symbols() -> None:
    payload = {
        "audit_only": True,
        "results": [
            {
                "symbol": "LT.NS",
                "rows": [
                    _row(
                        detector_diagnostics=[
                            "review_potential_effort_gt_result",
                            "review_potential_absorption",
                        ]
                    )
                ],
            },
            {
                "symbol": "SRF.NS",
                "rows": [
                    _row(
                        symbol="SRF.NS",
                        replay_week="2026-04-13 00:00:00",
                        replay_bar_index=239,
                        target_event_codes=[],
                        detector_diagnostics=[
                            "review_high_volume_reversal_without_bullish_event"
                        ],
                    )
                ],
            },
            {
                "symbol": "INFY.NS",
                "rows": [
                    _row(
                        symbol="INFY.NS",
                        replay_week="2026-04-20 00:00:00",
                        replay_bar_index=240,
                        target_event_codes=[],
                        detector_diagnostics=[],
                        audit_flags=["stale_scoring_evidence"],
                    )
                ],
            },
        ],
    }

    review = build_vsa_audit_batch_review(payload).to_dict()

    assert review["audit_only"] is True
    assert review["source_candidate_rows"] == 4
    assert review["total_review_rows"] == 4
    assert review["high_priority_rows"] == 3
    assert review["medium_priority_rows"] == 1
    assert review["candidate_counts"] == {
        CANDIDATE_EFFORT_GT_RESULT: 1,
        CANDIDATE_ABSORPTION: 1,
        CANDIDATE_HIGH_VOLUME_REVERSAL: 1,
        CANDIDATE_STALE_EVIDENCE: 1,
    }
    assert review["family_counts"]["effort_vs_result"] == 1
    assert review["symbol_counts"] == {"INFY.NS": 1, "LT.NS": 2, "SRF.NS": 1}
    assert review["symbols_with_candidates"] == ["INFY.NS", "LT.NS", "SRF.NS"]
    assert review["top_review_symbols"][0]["symbol"] == "LT.NS"
    assert review["review_focus"][0]["high_priority_rows"] >= 1


def test_batch_review_high_priority_filter_excludes_medium_lifecycle_rows() -> None:
    payload = [
        _row(detector_diagnostics=["review_potential_effort_gt_result"]),
        _row(target_event_codes=[], audit_flags=["stale_scoring_evidence"]),
    ]

    review = build_vsa_audit_batch_review(payload, min_priority="high").to_dict()

    assert review["source_candidate_rows"] == 2
    assert review["total_review_rows"] == 1
    assert review["candidate_counts"] == {CANDIDATE_EFFORT_GT_RESULT: 1}
    assert review["priority_counts"] == {"high": 1}
    assert review["rows"][0]["candidate_code"] == CANDIDATE_EFFORT_GT_RESULT


def test_batch_review_accepts_candidate_event_summary_payload() -> None:
    candidate_payload = {
        "audit_only": True,
        "rows": [
            {
                "symbol": "LT.NS",
                "replay_week": "2026-03-02 00:00:00",
                "replay_bar_index": 233,
                "candidate_code": CANDIDATE_EFFORT_GT_RESULT,
                "candidate_family": "effort_vs_result",
                "direction": "bullish_reversal_review",
                "priority": "high",
                "production_status": "not_confirmed_by_current_detector",
                "qualification": "persistent_bearish",
                "target_event_codes": ["increasing_supply"],
                "scoring_event_codes": ["increasing_supply"],
                "source_diagnostics": ["review_potential_effort_gt_result"],
                "source_audit_flags": [],
                "reason": "review effort vs result",
                "audit_only": True,
            }
        ],
    }

    review = build_vsa_audit_batch_review(candidate_payload).to_dict()

    assert review["source_candidate_rows"] == 1
    assert review["total_review_rows"] == 1
    assert review["review_focus"][0]["candidate_code"] == CANDIDATE_EFFORT_GT_RESULT
    assert review["review_focus"][0]["symbols"] == ["LT.NS"]


def test_batch_review_csv_renders_flat_review_rows() -> None:
    review = build_vsa_audit_batch_review(
        [_row(detector_diagnostics=["review_potential_effort_gt_result"])]
    )

    body = render_vsa_audit_batch_review_csv(review)
    rows = list(csv.DictReader(StringIO(body)))

    assert len(rows) == 1
    assert rows[0]["symbol"] == "LT.NS"
    assert rows[0]["candidate_code"] == CANDIDATE_EFFORT_GT_RESULT
    assert rows[0]["target_event_codes"] == "increasing_supply"
    assert rows[0]["source_diagnostics"] == "review_potential_effort_gt_result"


def test_batch_review_cli_writes_json_and_csv(tmp_path: Path) -> None:
    input_file = tmp_path / "basket_audit.json"
    json_output = tmp_path / "basket_review.json"
    csv_output = tmp_path / "basket_review.csv"
    input_file.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "rows": [
                            _row(
                                detector_diagnostics=[
                                    "review_potential_effort_gt_result"
                                ]
                            ),
                            _row(
                                target_event_codes=[],
                                detector_diagnostics=[],
                                audit_flags=["stale_scoring_evidence"],
                            ),
                        ]
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/vsa_audit_batch_review.py",
            str(input_file),
            "--json-output",
            str(json_output),
            "--csv-output",
            str(csv_output),
            "--min-priority",
            "high",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    json_body = json.loads(json_output.read_text(encoding="utf-8"))
    csv_rows = list(csv.DictReader(StringIO(csv_output.read_text(encoding="utf-8"))))
    assert json_body["candidate_counts"] == {CANDIDATE_EFFORT_GT_RESULT: 1}
    assert json_body["total_review_rows"] == 1
    assert len(csv_rows) == 1
    assert csv_rows[0]["priority"] == "high"
