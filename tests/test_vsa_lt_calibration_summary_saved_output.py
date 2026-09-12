from __future__ import annotations

from typing import Any

from vsa_audit_calibration import build_effort_absorption_calibration_summary


def _row(**overrides: Any) -> dict[str, Any]:
    row = {
        "symbol": "LT.NS",
        "replay_week": "2026-03-02 00:00:00",
        "replay_bar_index": 233,
        "target_event_codes": [],
        "scoring_event_codes": [],
        "qualification": "persistent_bearish",
        "audit_flags": [],
        "detector_diagnostics": [],
    }
    row.update(overrides)
    return row


def _lt_saved_audit_payload_for_calibration() -> dict[str, Any]:
    """Representative saved-output rows behind Library file LT_calibration_summary.json."""

    return {
        "audit_only": True,
        "results": [
            {
                "symbol": "LT.NS",
                "rows": [
                    _row(
                        replay_bar_index=233,
                        replay_week="2026-03-02 00:00:00",
                        target_event_codes=["increasing_supply"],
                        scoring_event_codes=["increasing_supply"],
                        detector_diagnostics=[
                            "review_potential_stopping_volume",
                            "review_potential_effort_gt_result",
                            "review_potential_absorption",
                            "review_high_volume_reversal_without_bullish_event",
                        ],
                    ),
                    _row(
                        replay_bar_index=234,
                        replay_week="2026-03-09 00:00:00",
                        target_event_codes=[],
                        scoring_event_codes=["increasing_supply"],
                    ),
                    _row(
                        replay_bar_index=235,
                        replay_week="2026-03-16 00:00:00",
                        target_event_codes=["structural_progression_weakening"],
                        scoring_event_codes=["increasing_supply"],
                        audit_flags=["structural_event_without_vsa_confirmation"],
                        detector_diagnostics=["review_potential_effort_gt_result"],
                    ),
                    _row(
                        replay_bar_index=236,
                        replay_week="2026-03-23 00:00:00",
                        target_event_codes=["demand_coming_in"],
                        scoring_event_codes=["demand_coming_in"],
                        audit_flags=["bullish_vsa_against_bearish_qualification"],
                        detector_diagnostics=[
                            "review_potential_effort_gt_result",
                            "review_potential_spring_or_shakeout",
                        ],
                    ),
                    _row(
                        replay_bar_index=237,
                        replay_week="2026-03-30 00:00:00",
                        target_event_codes=[],
                        scoring_event_codes=["increasing_supply"],
                        audit_flags=["stale_scoring_evidence"],
                    ),
                    _row(
                        replay_bar_index=238,
                        replay_week="2026-04-06 00:00:00",
                        target_event_codes=["increasing_demand", "demand_coming_in"],
                        scoring_event_codes=["increasing_demand", "demand_coming_in"],
                        audit_flags=["bullish_vsa_against_bearish_qualification"],
                        detector_diagnostics=["review_potential_effort_gt_result"],
                    ),
                    _row(
                        replay_bar_index=239,
                        replay_week="2026-04-13 00:00:00",
                        target_event_codes=[],
                        scoring_event_codes=["increasing_supply"],
                        audit_flags=["stale_scoring_evidence"],
                        detector_diagnostics=[
                            "review_potential_absorption",
                            "review_high_volume_reversal_without_bullish_event",
                        ],
                    ),
                    _row(
                        replay_bar_index=240,
                        replay_week="2026-04-20 00:00:00",
                        target_event_codes=[],
                        scoring_event_codes=["increasing_supply"],
                        audit_flags=["stale_scoring_evidence"],
                    ),
                ],
            }
        ],
    }


def test_lt_saved_audit_payload_rebuilds_library_calibration_summary_counts() -> None:
    summary = build_effort_absorption_calibration_summary(
        _lt_saved_audit_payload_for_calibration()
    ).to_dict()

    assert summary["audit_only"] is True
    assert summary["priority_counts"] == {"high": 5, "medium": 2}
    assert summary["symbol_counts"] == {"LT.NS": 7}
    assert summary["diagnostic_counts"] == {
        "review_high_volume_reversal_without_bullish_event": 2,
        "review_potential_absorption": 2,
        "review_potential_effort_gt_result": 4,
        "review_potential_spring_or_shakeout": 1,
        "review_potential_stopping_volume": 1,
    }
    assert summary["tag_counts"] == {
        "absorption_candidate": 2,
        "effort_gt_result_candidate": 4,
        "missing_bullish_reversal_event": 2,
        "not_confirmed_by_current_detector": 7,
        "qualification_conflict": 2,
        "spring_shakeout_candidate": 1,
        "stale_evidence_review": 3,
        "stopping_volume_candidate": 1,
    }

    rows = summary["rows"]
    assert [row["replay_bar_index"] for row in rows] == [233, 235, 236, 237, 238, 239, 240]
    assert [row["priority"] for row in rows] == [
        "high",
        "high",
        "high",
        "medium",
        "high",
        "high",
        "medium",
    ]


def test_lt_calibration_rows_keep_review_context_without_promoting_events() -> None:
    summary = build_effort_absorption_calibration_summary(
        _lt_saved_audit_payload_for_calibration()
    ).to_dict()
    rows_by_index = {row["replay_bar_index"]: row for row in summary["rows"]}

    first = rows_by_index[233]
    assert first["calibration_tags"] == [
        "effort_gt_result_candidate",
        "absorption_candidate",
        "missing_bullish_reversal_event",
        "stopping_volume_candidate",
        "not_confirmed_by_current_detector",
    ]
    assert first["target_event_codes"] == ["increasing_supply"]
    assert "current target events did not confirm" in first["reason"]

    structural = rows_by_index[235]
    assert structural["audit_flags"] == ["structural_event_without_vsa_confirmation"]
    assert structural["calibration_tags"] == [
        "effort_gt_result_candidate",
        "not_confirmed_by_current_detector",
    ]

    conflict = rows_by_index[236]
    assert conflict["audit_flags"] == ["bullish_vsa_against_bearish_qualification"]
    assert "qualification_conflict" in conflict["calibration_tags"]
    assert conflict["qualification"] == "persistent_bearish"

    stale_only = rows_by_index[237]
    assert stale_only["priority"] == "medium"
    assert stale_only["calibration_tags"] == [
        "stale_evidence_review",
        "not_confirmed_by_current_detector",
    ]

    stale_with_diagnostics = rows_by_index[239]
    assert stale_with_diagnostics["priority"] == "high"
    assert stale_with_diagnostics["calibration_tags"] == [
        "absorption_candidate",
        "missing_bullish_reversal_event",
        "stale_evidence_review",
        "not_confirmed_by_current_detector",
    ]
    assert stale_with_diagnostics["target_event_codes"] == []
