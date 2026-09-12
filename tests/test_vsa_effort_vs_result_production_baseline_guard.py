from __future__ import annotations

from collections import Counter
from typing import Any

from vsa_audit_candidate_events import (
    CANDIDATE_ABSORPTION,
    CANDIDATE_DIRECTIONS,
    CANDIDATE_EFFORT_GT_RESULT,
    CANDIDATE_FAMILIES,
    CANDIDATE_HIGH_VOLUME_REVERSAL,
    DIAGNOSTIC_POTENTIAL_EFFORT_GT_RESULT,
    DIAGNOSTIC_TO_CANDIDATE,
    PRODUCTION_EVENTS_BY_CANDIDATE,
)

PRODUCTION_EFFORT_GT_RESULT = "effort_gt_result"
FAMILY_EFFORT_VS_RESULT = "effort_vs_result"
DIRECTION_BULLISH_REVERSAL_REVIEW = "bullish_reversal_review"

OUTCOME_FOLLOW_THROUGH_VISIBLE = "follow_through_visible"
OUTCOME_INVALIDATED_BY_LATER_EVIDENCE = "invalidated_by_later_evidence"
OUTCOME_MIXED_FOLLOW_THROUGH_CONFLICT = "mixed_follow_through_conflict"
ACTION_REVIEW_FOR_CONTINUATION = "review_for_event_continuation_or_active_lifecycle"

SOURCE_BUCKET_CLEAN = "clean_candidate"
SOURCE_BUCKET_CLUSTER = "overlapping_candidate_cluster"
SOURCE_BUCKET_CONTRADICTORY = "contradictory_production_evidence"
SOURCE_BUCKET_NOISY = "likely_noisy_diagnostic"

REVIEW_FOCUS_BY_SOURCE_BUCKET = {
    SOURCE_BUCKET_CLEAN: "candidate_threshold_calibration",
    SOURCE_BUCKET_CLUSTER: "cluster_context_before_single_detector_change",
    SOURCE_BUCKET_CONTRADICTORY: "production_gate_conflict_review",
    SOURCE_BUCKET_NOISY: "continuation_or_redundant_signal_review",
}

CAUSALITY_V2_EVENT_COUNTS = {
    CANDIDATE_EFFORT_GT_RESULT: 48,
    CANDIDATE_HIGH_VOLUME_REVERSAL: 38,
    CANDIDATE_ABSORPTION: 33,
    "audit_qualification_conflict_candidate": 15,
}

EFFORT_VS_RESULT_FOLLOW_THROUGH_ROWS = [
    {
        "symbol": "BAJFINANCE.NS",
        "replay_week": "2026-03-23 00:00:00",
        "replay_bar_index": 1238,
        "audit_only": True,
        "event_code": CANDIDATE_EFFORT_GT_RESULT,
        "event_family": FAMILY_EFFORT_VS_RESULT,
        "event_direction": "bullish",
        "outcome_label": OUTCOME_FOLLOW_THROUGH_VISIBLE,
        "recommended_action": ACTION_REVIEW_FOR_CONTINUATION,
        "qualification": "unqualified",
        "source_bucket": SOURCE_BUCKET_CLUSTER,
        "source_scoring_event_codes": ["buying_climax", "upthrust"],
        "source_target_event_codes": ["buying_climax", "upthrust"],
        "future_rows_checked": 1,
        "future_supporting_event_codes": ["increasing_demand", "demand_coming_in"],
        "future_opposing_event_codes": [],
    },
    {
        "symbol": "CIPLA.NS",
        "replay_week": "2026-04-06 00:00:00",
        "replay_bar_index": 238,
        "audit_only": True,
        "event_code": CANDIDATE_EFFORT_GT_RESULT,
        "event_family": FAMILY_EFFORT_VS_RESULT,
        "event_direction": "bullish",
        "outcome_label": OUTCOME_FOLLOW_THROUGH_VISIBLE,
        "recommended_action": ACTION_REVIEW_FOR_CONTINUATION,
        "qualification": "unqualified",
        "source_bucket": SOURCE_BUCKET_CLEAN,
        "source_scoring_event_codes": ["increasing_demand", "demand_coming_in"],
        "source_target_event_codes": ["increasing_demand", "demand_coming_in"],
        "future_rows_checked": 1,
        "future_supporting_event_codes": ["increasing_demand", "demand_coming_in"],
        "future_opposing_event_codes": [],
    },
    {
        "symbol": "COALINDIA.NS",
        "replay_week": "2026-03-02 00:00:00",
        "replay_bar_index": 800,
        "audit_only": True,
        "event_code": CANDIDATE_EFFORT_GT_RESULT,
        "event_family": FAMILY_EFFORT_VS_RESULT,
        "event_direction": "bullish",
        "outcome_label": OUTCOME_FOLLOW_THROUGH_VISIBLE,
        "recommended_action": ACTION_REVIEW_FOR_CONTINUATION,
        "qualification": "persistent_bullish",
        "source_bucket": SOURCE_BUCKET_NOISY,
        "source_scoring_event_codes": ["increasing_demand"],
        "source_target_event_codes": ["increasing_demand"],
        "future_rows_checked": 1,
        "future_supporting_event_codes": ["demand_coming_in"],
        "future_opposing_event_codes": [],
    },
    {
        "symbol": "GRASIM.NS",
        "replay_week": "2026-03-16 00:00:00",
        "replay_bar_index": 235,
        "audit_only": True,
        "event_code": CANDIDATE_EFFORT_GT_RESULT,
        "event_family": FAMILY_EFFORT_VS_RESULT,
        "event_direction": "bullish",
        "outcome_label": OUTCOME_FOLLOW_THROUGH_VISIBLE,
        "recommended_action": ACTION_REVIEW_FOR_CONTINUATION,
        "qualification": "persistent_bearish",
        "source_bucket": SOURCE_BUCKET_CONTRADICTORY,
        "source_scoring_event_codes": ["hidden_supply"],
        "source_target_event_codes": ["hidden_supply"],
        "future_rows_checked": 2,
        "future_supporting_event_codes": ["increasing_demand", "demand_coming_in"],
        "future_opposing_event_codes": [],
    },
    {
        "symbol": "ULTRACEMCO.NS",
        "replay_week": "2026-03-16 00:00:00",
        "replay_bar_index": 235,
        "audit_only": True,
        "event_code": CANDIDATE_EFFORT_GT_RESULT,
        "event_family": FAMILY_EFFORT_VS_RESULT,
        "event_direction": "bullish",
        "outcome_label": OUTCOME_FOLLOW_THROUGH_VISIBLE,
        "recommended_action": ACTION_REVIEW_FOR_CONTINUATION,
        "qualification": "unqualified",
        "source_bucket": SOURCE_BUCKET_CONTRADICTORY,
        "source_scoring_event_codes": ["increasing_supply"],
        "source_target_event_codes": [],
        "future_rows_checked": 1,
        "future_supporting_event_codes": ["demand_coming_in"],
        "future_opposing_event_codes": [],
    },
]


def _observed_source_event_codes(row: dict[str, Any]) -> frozenset[str]:
    return frozenset(row.get("source_target_event_codes") or ()) | frozenset(
        row.get("source_scoring_event_codes") or ()
    )


def _effort_vs_result_baseline_guard(row: dict[str, Any]) -> dict[str, Any]:
    """Audit-only baseline guard before any Effort-vs-Result detector change.

    This executable spec keeps the existing audit/backlog candidate boundary
    separate from production event confirmation. It can identify rows that need
    detector-design review, but it never activates a production detector.
    """

    production_codes = PRODUCTION_EVENTS_BY_CANDIDATE[CANDIDATE_EFFORT_GT_RESULT]
    observed_codes = _observed_source_event_codes(row)
    is_effort_slice = (
        row.get("event_code") == CANDIDATE_EFFORT_GT_RESULT
        and row.get("event_family") == FAMILY_EFFORT_VS_RESULT
    )
    already_confirmed = bool(production_codes & observed_codes)

    may_enter_baseline_review = (
        bool(row.get("audit_only"))
        and is_effort_slice
        and row.get("outcome_label") == OUTCOME_FOLLOW_THROUGH_VISIBLE
        and row.get("recommended_action") == ACTION_REVIEW_FOR_CONTINUATION
        and bool(row.get("future_rows_checked"))
        and bool(row.get("future_supporting_event_codes") or ())
        and not bool(row.get("future_opposing_event_codes") or ())
        and not already_confirmed
    )

    return {
        "production_event_code": PRODUCTION_EFFORT_GT_RESULT,
        "production_mapping_exists": PRODUCTION_EFFORT_GT_RESULT
        in production_codes,
        "observed_source_event_codes": observed_codes,
        "already_confirmed_by_current_events": already_confirmed,
        "audit_candidate_is_production_code": row.get("event_code")
        == PRODUCTION_EFFORT_GT_RESULT,
        "may_enter_effort_vs_result_baseline_review": may_enter_baseline_review,
        "may_activate_production_detector": False,
        "requires_separate_detector_pr": True,
        "review_focus": REVIEW_FOCUS_BY_SOURCE_BUCKET[row["source_bucket"]],
    }


def test_effort_candidate_mapping_is_baseline_reference_not_activation() -> None:
    production_codes = PRODUCTION_EVENTS_BY_CANDIDATE[CANDIDATE_EFFORT_GT_RESULT]

    assert DIAGNOSTIC_TO_CANDIDATE[DIAGNOSTIC_POTENTIAL_EFFORT_GT_RESULT] == (
        CANDIDATE_EFFORT_GT_RESULT
    )
    assert CANDIDATE_FAMILIES[CANDIDATE_EFFORT_GT_RESULT] == FAMILY_EFFORT_VS_RESULT
    assert CANDIDATE_DIRECTIONS[CANDIDATE_EFFORT_GT_RESULT] == (
        DIRECTION_BULLISH_REVERSAL_REVIEW
    )
    assert production_codes == frozenset({PRODUCTION_EFFORT_GT_RESULT})
    assert CANDIDATE_EFFORT_GT_RESULT != PRODUCTION_EFFORT_GT_RESULT


def test_effort_follow_through_rows_are_not_currently_confirmed_by_effort_code() -> None:
    decisions = [
        _effort_vs_result_baseline_guard(row)
        for row in EFFORT_VS_RESULT_FOLLOW_THROUGH_ROWS
    ]

    assert len(decisions) == 5
    assert CAUSALITY_V2_EVENT_COUNTS[CANDIDATE_EFFORT_GT_RESULT] == 48
    assert len(decisions) < CAUSALITY_V2_EVENT_COUNTS[CANDIDATE_EFFORT_GT_RESULT]
    assert all(decision["production_mapping_exists"] is True for decision in decisions)
    assert all(
        decision["audit_candidate_is_production_code"] is False
        for decision in decisions
    )
    assert all(
        decision["already_confirmed_by_current_events"] is False
        for decision in decisions
    )
    assert all(
        decision["may_enter_effort_vs_result_baseline_review"] is True
        for decision in decisions
    )
    assert all(
        decision["may_activate_production_detector"] is False
        for decision in decisions
    )
    assert all(decision["requires_separate_detector_pr"] is True for decision in decisions)


def test_existing_production_confirmation_is_kept_separate_from_backlog_gap() -> None:
    already_confirmed_row = {
        **EFFORT_VS_RESULT_FOLLOW_THROUGH_ROWS[0],
        "source_target_event_codes": [PRODUCTION_EFFORT_GT_RESULT],
        "source_scoring_event_codes": [PRODUCTION_EFFORT_GT_RESULT],
    }

    decision = _effort_vs_result_baseline_guard(already_confirmed_row)

    assert decision["already_confirmed_by_current_events"] is True
    assert decision["may_enter_effort_vs_result_baseline_review"] is False
    assert decision["may_activate_production_detector"] is False
    assert decision["requires_separate_detector_pr"] is True


def test_baseline_guard_rejects_non_slice_or_incomplete_rows() -> None:
    valid = EFFORT_VS_RESULT_FOLLOW_THROUGH_ROWS[0]
    wrong_candidate = {
        **valid,
        "event_code": CANDIDATE_ABSORPTION,
        "event_family": "absorption",
    }
    wrong_family = {
        **valid,
        "event_code": CANDIDATE_HIGH_VOLUME_REVERSAL,
        "event_family": "high_volume_reversal",
    }
    mixed_outcome = {
        **valid,
        "outcome_label": OUTCOME_MIXED_FOLLOW_THROUGH_CONFLICT,
    }
    invalidated_outcome = {
        **valid,
        "outcome_label": OUTCOME_INVALIDATED_BY_LATER_EVIDENCE,
    }
    missing_support = {
        **valid,
        "future_supporting_event_codes": [],
    }
    opposing_future_evidence = {
        **valid,
        "future_opposing_event_codes": ["upthrust"],
    }
    no_future_rows_checked = {
        **valid,
        "future_rows_checked": 0,
    }
    non_audit_row = {
        **valid,
        "audit_only": False,
    }

    rejected_rows = [
        wrong_candidate,
        wrong_family,
        mixed_outcome,
        invalidated_outcome,
        missing_support,
        opposing_future_evidence,
        no_future_rows_checked,
        non_audit_row,
    ]

    assert _effort_vs_result_baseline_guard(valid)[
        "may_enter_effort_vs_result_baseline_review"
    ] is True
    assert all(
        _effort_vs_result_baseline_guard(row)[
            "may_enter_effort_vs_result_baseline_review"
        ]
        is False
        for row in rejected_rows
    )
    assert all(
        _effort_vs_result_baseline_guard(row)["may_activate_production_detector"]
        is False
        for row in [valid, *rejected_rows]
    )


def test_baseline_preserves_bucket_context_for_detector_design_review() -> None:
    decisions_by_symbol = {
        row["symbol"]: _effort_vs_result_baseline_guard(row)
        for row in EFFORT_VS_RESULT_FOLLOW_THROUGH_ROWS
    }

    assert decisions_by_symbol["CIPLA.NS"]["review_focus"] == (
        "candidate_threshold_calibration"
    )
    assert decisions_by_symbol["BAJFINANCE.NS"]["review_focus"] == (
        "cluster_context_before_single_detector_change"
    )
    assert decisions_by_symbol["COALINDIA.NS"]["review_focus"] == (
        "continuation_or_redundant_signal_review"
    )
    assert decisions_by_symbol["GRASIM.NS"]["review_focus"] == (
        "production_gate_conflict_review"
    )
    assert decisions_by_symbol["ULTRACEMCO.NS"]["review_focus"] == (
        "production_gate_conflict_review"
    )

    assert Counter(row["source_bucket"] for row in EFFORT_VS_RESULT_FOLLOW_THROUGH_ROWS) == {
        SOURCE_BUCKET_CONTRADICTORY: 2,
        SOURCE_BUCKET_CLUSTER: 1,
        SOURCE_BUCKET_CLEAN: 1,
        SOURCE_BUCKET_NOISY: 1,
    }
