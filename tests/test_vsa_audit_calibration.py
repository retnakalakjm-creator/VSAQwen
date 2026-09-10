from __future__ import annotations

from vsa_audit_calibration import build_effort_absorption_calibration_summary


def test_effort_absorption_calibration_summary_selects_high_priority_rows() -> None:
    audit_payload = {
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
                        "audit_flags": ["actionable_audit_row"],
                        "detector_diagnostics": [
                            "review_potential_stopping_volume",
                            "review_potential_effort_gt_result",
                            "review_potential_absorption",
                            "review_high_volume_reversal_without_bullish_event",
                        ],
                    },
                    {
                        "symbol": "LT.NS",
                        "replay_week": "2026-03-09 00:00:00",
                        "replay_bar_index": 234,
                        "target_event_codes": [],
                        "scoring_event_codes": ["increasing_supply"],
                        "qualification": "persistent_bearish",
                        "audit_flags": [
                            "no_target_event",
                            "fallback_scoring_evidence",
                        ],
                        "detector_diagnostics": [],
                    },
                    {
                        "symbol": "LT.NS",
                        "replay_week": "2026-03-23 00:00:00",
                        "replay_bar_index": 236,
                        "target_event_codes": ["demand_coming_in"],
                        "scoring_event_codes": ["demand_coming_in"],
                        "qualification": "persistent_bearish",
                        "audit_flags": [
                            "bullish_vsa_against_bearish_qualification",
                        ],
                        "detector_diagnostics": [
                            "review_potential_spring_or_shakeout",
                        ],
                    },
                ],
            }
        ]
    }

    summary = build_effort_absorption_calibration_summary(audit_payload)

    assert summary.audit_only is True
    assert len(summary.rows) == 2
    assert summary.priority_counts == {"high": 2}
    assert summary.symbol_counts == {"LT.NS": 2}
    assert summary.diagnostic_counts["review_potential_effort_gt_result"] == 1
    assert summary.diagnostic_counts["review_potential_spring_or_shakeout"] == 1

    first = summary.rows[0]
    assert first.priority == "high"
    assert first.calibration_tags == (
        "effort_gt_result_candidate",
        "absorption_candidate",
        "missing_bullish_reversal_event",
        "stopping_volume_candidate",
        "not_confirmed_by_current_detector",
    )
    assert "current target events did not confirm" in first.reason
    assert "order" not in first.to_dict()

    second = summary.rows[1]
    assert second.priority == "high"
    assert second.calibration_tags == (
        "spring_shakeout_candidate",
        "qualification_conflict",
        "not_confirmed_by_current_detector",
    )


def test_calibration_summary_accepts_flattened_rows_and_counts_tags() -> None:
    rows = [
        {
            "symbol": "A.NS",
            "replay_week": "2026-01-05 00:00:00",
            "replay_bar_index": 10,
            "target_event_codes": ["absorption"],
            "scoring_event_codes": ["absorption"],
            "qualification": "unqualified",
            "audit_flags": [],
            "detector_diagnostics": ["review_potential_absorption"],
        },
        {
            "symbol": "B.NS",
            "replay_week": "2026-01-12 00:00:00",
            "replay_bar_index": 11,
            "target_event_codes": [],
            "scoring_event_codes": ["increasing_supply"],
            "qualification": "persistent_bearish",
            "audit_flags": ["stale_scoring_evidence"],
            "detector_diagnostics": [],
        },
    ]

    summary = build_effort_absorption_calibration_summary(rows)

    assert [row.symbol for row in summary.rows] == ["A.NS", "B.NS"]
    assert summary.priority_counts == {"medium": 2}
    assert summary.tag_counts["absorption_candidate"] == 1
    assert summary.tag_counts["stale_evidence_review"] == 1
    assert "not_confirmed_by_current_detector" not in summary.rows[0].calibration_tags
