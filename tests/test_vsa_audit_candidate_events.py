from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from vsa_audit_candidate_events import (
    CANDIDATE_ABSORPTION,
    CANDIDATE_CONTEXT_CONFLICT,
    CANDIDATE_EFFORT_GT_RESULT,
    CANDIDATE_HIGH_VOLUME_REVERSAL,
    CANDIDATE_SPRING_OR_SHAKEOUT,
    CANDIDATE_STALE_EVIDENCE,
    CANDIDATE_STOPPING_VOLUME,
    build_audit_candidate_event_summary,
    build_audit_candidate_events_for_row,
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


def test_candidate_events_convert_diagnostics_to_structured_objects() -> None:
    events = build_audit_candidate_events_for_row(
        _row(
            detector_diagnostics=[
                "review_potential_stopping_volume",
                "review_potential_effort_gt_result",
                "review_potential_absorption",
                "review_high_volume_reversal_without_bullish_event",
            ]
        )
    )

    codes = [event.candidate_code for event in events]
    assert codes == [
        CANDIDATE_STOPPING_VOLUME,
        CANDIDATE_EFFORT_GT_RESULT,
        CANDIDATE_ABSORPTION,
        CANDIDATE_HIGH_VOLUME_REVERSAL,
    ]
    assert all(event.audit_only is True for event in events)
    assert all(event.production_status == "not_confirmed_by_current_detector" for event in events)
    assert events[1].candidate_family == "effort_vs_result"
    assert events[1].direction == "bullish_reversal_review"
    assert events[1].priority == "high"
    assert "production rules" in events[1].reason


def test_candidate_events_add_context_and_lifecycle_candidates() -> None:
    events = build_audit_candidate_events_for_row(
        _row(
            replay_week="2026-03-23 00:00:00",
            replay_bar_index=236,
            target_event_codes=["demand_coming_in"],
            scoring_event_codes=["demand_coming_in"],
            audit_flags=[
                "bullish_vsa_against_bearish_qualification",
                "structural_event_without_vsa_confirmation",
            ],
            detector_diagnostics=[
                "review_potential_effort_gt_result",
                "review_potential_spring_or_shakeout",
            ],
        )
    )

    codes = [event.candidate_code for event in events]
    assert codes == [
        CANDIDATE_EFFORT_GT_RESULT,
        CANDIDATE_SPRING_OR_SHAKEOUT,
        CANDIDATE_CONTEXT_CONFLICT,
        CANDIDATE_STALE_EVIDENCE,
    ]
    context_event = events[2]
    assert context_event.priority == "high"
    assert context_event.source_audit_flags == (
        "bullish_vsa_against_bearish_qualification",
    )
    assert "lifecycle" in context_event.reason.lower()


def test_candidate_events_suppress_already_confirmed_production_event() -> None:
    events = build_audit_candidate_events_for_row(
        _row(
            target_event_codes=["effort_gt_result"],
            detector_diagnostics=["review_potential_effort_gt_result"],
        )
    )

    assert events == ()


def test_candidate_event_summary_accepts_full_audit_payload() -> None:
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
                    ),
                    _row(
                        replay_week="2026-04-20 00:00:00",
                        replay_bar_index=240,
                        target_event_codes=[],
                        detector_diagnostics=[],
                        audit_flags=["stale_scoring_evidence"],
                    ),
                ],
            }
        ],
    }

    summary = build_audit_candidate_event_summary(payload).to_dict()

    assert summary["audit_only"] is True
    assert summary["candidate_counts"] == {
        CANDIDATE_EFFORT_GT_RESULT: 1,
        CANDIDATE_ABSORPTION: 1,
        CANDIDATE_STALE_EVIDENCE: 1,
    }
    assert summary["priority_counts"] == {"high": 2, "medium": 1}
    assert summary["symbol_counts"] == {"LT.NS": 3}
    assert len(summary["rows"]) == 3


def test_candidate_event_cli_writes_high_priority_only(tmp_path: Path) -> None:
    audit_file = tmp_path / "LT_New.txt"
    output_file = tmp_path / "candidate_events.json"
    audit_file.write_text(
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
            "scripts/vsa_audit_candidate_events.py",
            str(audit_file),
            "--output",
            str(output_file),
            "--min-priority",
            "high",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    body = json.loads(output_file.read_text(encoding="utf-8"))
    assert body["candidate_counts"] == {CANDIDATE_EFFORT_GT_RESULT: 1}
    assert body["priority_counts"] == {"high": 1}
    assert len(body["rows"]) == 1
