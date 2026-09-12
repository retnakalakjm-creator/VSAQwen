from __future__ import annotations

import json

import pytest

from audit.audit_effort_result_decision_value import (
    CONSENSUS_CANDIDATE,
    CONSENSUS_INCONSISTENT_DIRECTION,
    CONSENSUS_INSUFFICIENT_SAMPLE,
)
from audit.review_effort_result_candidates import build_candidate_review_report


def _consensus_row(
    *,
    scope: str,
    condition: str,
    consensus: str,
    candidate_direction: str,
    candidate_horizons: list[int],
    candidate_bars: int,
) -> dict[str, object]:
    return {
        "scope": scope,
        "condition": condition,
        "consensus": consensus,
        "horizons_seen": [1, 2, 4],
        "candidate_horizons": candidate_horizons,
        "candidate_bars": candidate_bars,
        "candidate_direction": candidate_direction,
        "reason": "test reason",
        "may_change_scoring": False,
        "may_change_ranking": False,
        "may_change_actionability": False,
        "may_activate_detector": False,
        "requires_manual_case_review": True,
        "requires_separate_production_pr": True,
    }


def _audit_report() -> dict[str, object]:
    return {
        "source": "historical_effort_result_validation.csv",
        "rows": 7470,
        "outcome_rows": 22354,
        "horizons": [1, 2, 4],
        "thresholds": {
            "readiness": {"min_bars": 10, "min_abs_delta": 0.005},
            "consensus": {"min_horizons": 2, "min_candidate_bars": 20},
        },
        "readiness_consensus": [
            _consensus_row(
                scope="effort_result_relationship",
                condition="RESULT_GT_EFFORT",
                consensus=CONSENSUS_CANDIDATE,
                candidate_direction="negative",
                candidate_horizons=[1, 2, 4],
                candidate_bars=264,
            ),
            _consensus_row(
                scope="effort_result_relationship_plus_event",
                condition="EFFORT_RESULT+SUPPLY_COMING_IN",
                consensus=CONSENSUS_CANDIDATE,
                candidate_direction="negative",
                candidate_horizons=[1, 2, 4],
                candidate_bars=183,
            ),
            _consensus_row(
                scope="effort_result_relationship_plus_event",
                condition="EFFORT_RESULT+BUYING_CLIMAX",
                consensus=CONSENSUS_CANDIDATE,
                candidate_direction="negative",
                candidate_horizons=[1, 2],
                candidate_bars=238,
            ),
            _consensus_row(
                scope="effort_result_relationship_plus_event",
                condition="EFFORT_RESULT+UPTHRUST",
                consensus=CONSENSUS_INCONSISTENT_DIRECTION,
                candidate_direction="mixed",
                candidate_horizons=[1, 2, 4],
                candidate_bars=238,
            ),
            _consensus_row(
                scope="effort_result_event",
                condition="EFFORT_GT_RESULT",
                consensus=CONSENSUS_INSUFFICIENT_SAMPLE,
                candidate_direction="none",
                candidate_horizons=[],
                candidate_bars=0,
            ),
            _consensus_row(
                scope="event",
                condition="UPTHRUST",
                consensus=CONSENSUS_CANDIDATE,
                candidate_direction="negative",
                candidate_horizons=[1, 2, 4],
                candidate_bars=999,
            ),
        ],
        "audit_only": True,
    }


def test_candidate_review_report_ranks_effort_result_candidates() -> None:
    report = build_candidate_review_report(_audit_report())

    candidates = report["calibration_design_candidates"]

    assert report["report_type"] == "effort_result_candidate_review"
    assert report["report_schema_version"] == 1
    assert report["total_consensus_rows"] == 5
    assert report["total_candidate_count"] == 3
    assert report["candidate_count"] == 3
    assert [row["condition"] for row in candidates] == [
        "RESULT_GT_EFFORT",
        "EFFORT_RESULT+SUPPLY_COMING_IN",
        "EFFORT_RESULT+BUYING_CLIMAX",
    ]
    assert [row["priority"] for row in candidates] == ["high", "high", "medium"]


def test_candidate_review_report_separates_blockers_and_denies_production() -> None:
    report = build_candidate_review_report(_audit_report())

    blockers = report["blocked_or_observation_only"]

    assert report["audit_only"] is True
    assert report["may_change_scoring"] is False
    assert report["may_change_ranking"] is False
    assert report["may_change_actionability"] is False
    assert report["may_activate_detector"] is False
    assert report["requires_manual_case_review"] is True
    assert report["requires_separate_production_pr"] is True
    assert report["blocked_count"] == 2
    assert [row["condition"] for row in blockers] == [
        "EFFORT_RESULT+UPTHRUST",
        "EFFORT_GT_RESULT",
    ]
    assert all(row["may_change_scoring"] is False for row in blockers)
    assert all(row["requires_separate_production_pr"] is True for row in blockers)


def test_candidate_review_report_supports_bounded_candidate_output() -> None:
    report = build_candidate_review_report(_audit_report(), max_candidates=2)

    assert report["total_candidate_count"] == 3
    assert report["candidate_count"] == 2
    assert [
        row["condition"] for row in report["calibration_design_candidates"]
    ] == ["RESULT_GT_EFFORT", "EFFORT_RESULT+SUPPLY_COMING_IN"]


def test_candidate_review_report_is_json_serializable_and_validates_limit() -> None:
    report = build_candidate_review_report(_audit_report())
    json.dumps(report)

    with pytest.raises(ValueError, match="max_candidates"):
        build_candidate_review_report(_audit_report(), max_candidates=0)
