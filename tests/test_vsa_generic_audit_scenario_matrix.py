from __future__ import annotations

from typing import Any

from vsa_audit_batch_review import build_vsa_audit_batch_review
from vsa_audit_candidate_events import (
    CANDIDATE_ABSORPTION,
    CANDIDATE_CONTEXT_CONFLICT,
    CANDIDATE_EFFORT_GT_RESULT,
    CANDIDATE_HIGH_VOLUME_REVERSAL,
    CANDIDATE_SPRING_OR_SHAKEOUT,
    CANDIDATE_STALE_EVIDENCE,
    CANDIDATE_STOPPING_VOLUME,
    build_audit_candidate_event_summary,
)


def _audit_row(**overrides: Any) -> dict[str, Any]:
    row = {
        "symbol": "GENERIC.NS",
        "replay_week": "2026-01-05 00:00:00",
        "replay_bar_index": 1,
        "target_event_codes": [],
        "scoring_event_codes": [],
        "qualification": "persistent_bearish",
        "audit_flags": [],
        "detector_diagnostics": [],
    }
    row.update(overrides)
    return row


def _generic_audit_payload() -> dict[str, Any]:
    """Generic saved-output-shaped rows that are not tied to one stock pattern."""

    return {
        "audit_only": True,
        "results": [
            {
                "symbol": "AAA.NS",
                "rows": [
                    _audit_row(
                        symbol="AAA.NS",
                        replay_bar_index=10,
                        target_event_codes=["increasing_supply"],
                        scoring_event_codes=["increasing_supply"],
                        detector_diagnostics=[
                            "review_potential_stopping_volume",
                            "review_potential_effort_gt_result",
                            "review_potential_absorption",
                            "review_high_volume_reversal_without_bullish_event",
                        ],
                    )
                ],
            },
            {
                "symbol": "BBB.NS",
                "rows": [
                    _audit_row(
                        symbol="BBB.NS",
                        replay_week="2026-01-12 00:00:00",
                        replay_bar_index=20,
                        target_event_codes=["demand_coming_in"],
                        scoring_event_codes=["demand_coming_in"],
                        audit_flags=["bullish_vsa_against_bearish_qualification"],
                        detector_diagnostics=["review_potential_spring_or_shakeout"],
                    )
                ],
            },
            {
                "symbol": "CCC.NS",
                "rows": [
                    _audit_row(
                        symbol="CCC.NS",
                        replay_week="2026-01-19 00:00:00",
                        replay_bar_index=30,
                        scoring_event_codes=["increasing_supply"],
                        audit_flags=[
                            "stale_scoring_evidence",
                            "structural_event_without_vsa_confirmation",
                        ],
                    )
                ],
            },
            {
                "symbol": "DDD.NS",
                "rows": [
                    _audit_row(
                        symbol="DDD.NS",
                        replay_week="2026-01-26 00:00:00",
                        replay_bar_index=40,
                        target_event_codes=["absorption"],
                        scoring_event_codes=["absorption"],
                        detector_diagnostics=[
                            "review_potential_absorption",
                            "review_potential_effort_gt_result",
                        ],
                    )
                ],
            },
            {
                "symbol": "EEE.NS",
                "rows": [
                    _audit_row(
                        symbol="EEE.NS",
                        replay_week="2026-02-02 00:00:00",
                        replay_bar_index=50,
                        target_event_codes=["spring"],
                        scoring_event_codes=["spring"],
                        detector_diagnostics=["review_potential_spring_or_shakeout"],
                    )
                ],
            },
            {
                "symbol": "FFF.NS",
                "rows": [
                    _audit_row(
                        symbol="FFF.NS",
                        replay_week="2026-02-09 00:00:00",
                        replay_bar_index=60,
                        target_event_codes=["upthrust"],
                        scoring_event_codes=["upthrust"],
                        qualification="emerging_bullish",
                        audit_flags=["bearish_vsa_against_bullish_qualification"],
                    )
                ],
            },
        ],
    }


def test_generic_audit_matrix_covers_core_review_families_without_stock_assumptions() -> None:
    summary = build_audit_candidate_event_summary(_generic_audit_payload()).to_dict()

    assert summary["audit_only"] is True
    assert len(summary["rows"]) == 9
    assert summary["candidate_counts"] == {
        CANDIDATE_STOPPING_VOLUME: 1,
        CANDIDATE_EFFORT_GT_RESULT: 2,
        CANDIDATE_ABSORPTION: 1,
        CANDIDATE_HIGH_VOLUME_REVERSAL: 1,
        CANDIDATE_SPRING_OR_SHAKEOUT: 1,
        CANDIDATE_CONTEXT_CONFLICT: 2,
        CANDIDATE_STALE_EVIDENCE: 1,
    }
    assert summary["priority_counts"] == {"medium": 3, "high": 6}
    assert summary["family_counts"] == {
        "stopping_volume": 1,
        "effort_vs_result": 2,
        "absorption": 1,
        "high_volume_reversal": 1,
        "spring_or_shakeout": 1,
        "qualification_lifecycle": 2,
        "evidence_lifecycle": 1,
    }

    rows_by_symbol = {}
    for row in summary["rows"]:
        rows_by_symbol.setdefault(row["symbol"], []).append(row)

    assert [row["candidate_code"] for row in rows_by_symbol["AAA.NS"]] == [
        CANDIDATE_STOPPING_VOLUME,
        CANDIDATE_EFFORT_GT_RESULT,
        CANDIDATE_ABSORPTION,
        CANDIDATE_HIGH_VOLUME_REVERSAL,
    ]
    assert [row["candidate_code"] for row in rows_by_symbol["BBB.NS"]] == [
        CANDIDATE_SPRING_OR_SHAKEOUT,
        CANDIDATE_CONTEXT_CONFLICT,
    ]
    assert [row["candidate_code"] for row in rows_by_symbol["CCC.NS"]] == [
        CANDIDATE_STALE_EVIDENCE,
    ]
    assert [row["candidate_code"] for row in rows_by_symbol["DDD.NS"]] == [
        CANDIDATE_EFFORT_GT_RESULT,
    ]
    assert "EEE.NS" not in rows_by_symbol
    assert [row["candidate_code"] for row in rows_by_symbol["FFF.NS"]] == [
        CANDIDATE_CONTEXT_CONFLICT,
    ]

    assert all(row["audit_only"] is True for row in summary["rows"])
    assert all(
        row["production_status"] == "not_confirmed_by_current_detector"
        for row in summary["rows"]
    )


def test_generic_matrix_high_priority_review_filters_out_medium_lifecycle_noise() -> None:
    review = build_vsa_audit_batch_review(
        _generic_audit_payload(),
        min_priority="high",
    ).to_dict()

    assert review["audit_only"] is True
    assert review["source_candidate_rows"] == 9
    assert review["total_review_rows"] == 6
    assert review["high_priority_rows"] == 6
    assert review["medium_priority_rows"] == 0
    assert review["priority_counts"] == {"high": 6}
    assert review["candidate_counts"] == {
        CANDIDATE_EFFORT_GT_RESULT: 2,
        CANDIDATE_ABSORPTION: 1,
        CANDIDATE_HIGH_VOLUME_REVERSAL: 1,
        CANDIDATE_CONTEXT_CONFLICT: 2,
    }
    assert CANDIDATE_STOPPING_VOLUME not in review["candidate_counts"]
    assert CANDIDATE_SPRING_OR_SHAKEOUT not in review["candidate_counts"]
    assert CANDIDATE_STALE_EVIDENCE not in review["candidate_counts"]
    assert review["symbols_with_candidates"] == [
        "AAA.NS",
        "BBB.NS",
        "DDD.NS",
        "FFF.NS",
    ]


def test_generic_matrix_preserves_candidate_source_evidence_for_manual_review() -> None:
    review = build_vsa_audit_batch_review(
        _generic_audit_payload(),
        min_priority="medium",
    ).to_dict()

    assert review["source_candidate_rows"] == 9
    assert review["total_review_rows"] == 9

    stale_rows = [
        row for row in review["rows"] if row["candidate_code"] == CANDIDATE_STALE_EVIDENCE
    ]
    assert len(stale_rows) == 1
    assert stale_rows[0]["source_audit_flags"] == [
        "stale_scoring_evidence",
        "structural_event_without_vsa_confirmation",
    ]
    assert stale_rows[0]["scoring_event_codes"] == ["increasing_supply"]

    context_rows = [
        row for row in review["rows"] if row["candidate_code"] == CANDIDATE_CONTEXT_CONFLICT
    ]
    assert {tuple(row["source_audit_flags"]) for row in context_rows} == {
        ("bullish_vsa_against_bearish_qualification",),
        ("bearish_vsa_against_bullish_qualification",),
    }

    confirmed_spring_symbols = {
        row["symbol"]
        for row in review["rows"]
        if row["candidate_code"] == CANDIDATE_SPRING_OR_SHAKEOUT
    }
    assert confirmed_spring_symbols == {"BBB.NS"}

    assert "EEE.NS" not in review["symbol_counts"]
