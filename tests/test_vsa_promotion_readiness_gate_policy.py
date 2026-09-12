from __future__ import annotations

from typing import Any

from vsa_audit_candidate_events import (
    CANDIDATE_ABSORPTION,
    CANDIDATE_CONTEXT_CONFLICT,
    CANDIDATE_EFFORT_GT_RESULT,
    CANDIDATE_HIGH_VOLUME_REVERSAL,
    CANDIDATE_STALE_EVIDENCE,
)

OUTCOME_FOLLOW_THROUGH_VISIBLE = "follow_through_visible"
OUTCOME_INVALIDATED_BY_LATER_EVIDENCE = "invalidated_by_later_evidence"
OUTCOME_LIFECYCLE_TRANSITION_REVIEW = "lifecycle_transition_review"
OUTCOME_MIXED_FOLLOW_THROUGH_CONFLICT = "mixed_follow_through_conflict"
OUTCOME_NO_LATER_SELECTED_AUDIT_ROWS = "no_later_selected_audit_rows"
OUTCOME_PENDING_INSUFFICIENT_FUTURE_ROWS = "pending_insufficient_future_rows"

ACTION_REVIEW_FOR_CONTINUATION = "review_for_event_continuation_or_active_lifecycle"
ACTION_REVIEW_FOR_INVALIDATION = "review_for_event_invalidation_or_supersession"
ACTION_REVIEW_CONTEXT_LIFECYCLE = "review_context_lifecycle_transition"
ACTION_REVIEW_MIXED_CLUSTER = "review_mixed_event_cluster_before_activation"
ACTION_RERUN_WIDER_CONTEXT = "rerun_with_wider_same_symbol_audit_context"
ACTION_WAIT_FOR_MORE_BARS = "wait_for_more_completed_bars"

PROMOTION_GATE_POLICY = {
    OUTCOME_FOLLOW_THROUGH_VISIBLE: {
        "gate": "detector_backlog_review_candidate",
        "expected_action": ACTION_REVIEW_FOR_CONTINUATION,
        "may_enter_detector_backlog": True,
        "requires_wider_audit_context": False,
        "requires_more_completed_bars": False,
    },
    OUTCOME_MIXED_FOLLOW_THROUGH_CONFLICT: {
        "gate": "manual_review_only_mixed_cluster",
        "expected_action": ACTION_REVIEW_MIXED_CLUSTER,
        "may_enter_detector_backlog": False,
        "requires_wider_audit_context": False,
        "requires_more_completed_bars": False,
    },
    OUTCOME_INVALIDATED_BY_LATER_EVIDENCE: {
        "gate": "blocked_by_later_opposing_evidence",
        "expected_action": ACTION_REVIEW_FOR_INVALIDATION,
        "may_enter_detector_backlog": False,
        "requires_wider_audit_context": False,
        "requires_more_completed_bars": False,
    },
    OUTCOME_LIFECYCLE_TRANSITION_REVIEW: {
        "gate": "qualification_lifecycle_review_only",
        "expected_action": ACTION_REVIEW_CONTEXT_LIFECYCLE,
        "may_enter_detector_backlog": False,
        "requires_wider_audit_context": False,
        "requires_more_completed_bars": False,
    },
    OUTCOME_NO_LATER_SELECTED_AUDIT_ROWS: {
        "gate": "rerun_required_before_promotion_review",
        "expected_action": ACTION_RERUN_WIDER_CONTEXT,
        "may_enter_detector_backlog": False,
        "requires_wider_audit_context": True,
        "requires_more_completed_bars": False,
    },
    OUTCOME_PENDING_INSUFFICIENT_FUTURE_ROWS: {
        "gate": "wait_for_more_completed_bars",
        "expected_action": ACTION_WAIT_FOR_MORE_BARS,
        "may_enter_detector_backlog": False,
        "requires_wider_audit_context": False,
        "requires_more_completed_bars": True,
    },
}

CAUSALITY_V2_OUTCOME_COUNTS = {
    OUTCOME_FOLLOW_THROUGH_VISIBLE: 12,
    OUTCOME_INVALIDATED_BY_LATER_EVIDENCE: 36,
    OUTCOME_LIFECYCLE_TRANSITION_REVIEW: 15,
    OUTCOME_MIXED_FOLLOW_THROUGH_CONFLICT: 28,
    OUTCOME_NO_LATER_SELECTED_AUDIT_ROWS: 40,
    OUTCOME_PENDING_INSUFFICIENT_FUTURE_ROWS: 3,
}

CAUSALITY_V2_EVENT_COUNTS = {
    CANDIDATE_ABSORPTION: 33,
    CANDIDATE_EFFORT_GT_RESULT: 48,
    CANDIDATE_HIGH_VOLUME_REVERSAL: 38,
    CANDIDATE_CONTEXT_CONFLICT: 15,
}

CAUSALITY_V2_DIRECTION_COUNTS = {"bullish": 125, "bearish": 9}

NON_DETECTOR_CANDIDATES = frozenset(
    {
        CANDIDATE_CONTEXT_CONFLICT,
        CANDIDATE_STALE_EVIDENCE,
    }
)


def _causality_row(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "audit_only": True,
        "event_code": CANDIDATE_EFFORT_GT_RESULT,
        "event_direction": "bullish",
        "event_family": "effort_vs_result",
        "future_lifecycle_actions": [],
        "future_opposing_event_codes": [],
        "future_rows_checked": 2,
        "future_supporting_event_codes": ["increasing_demand", "demand_coming_in"],
        "outcome_label": OUTCOME_FOLLOW_THROUGH_VISIBLE,
        "qualification": "unqualified",
        "recommended_action": ACTION_REVIEW_FOR_CONTINUATION,
        "replay_bar_index": 1238,
        "replay_week": "2026-03-23 00:00:00",
        "review_horizon_rows": 8,
        "source_bucket": "overlapping_candidate_cluster",
        "source_priority": "high",
        "source_reasons": ["saved causality row for promotion-readiness review"],
        "source_scoring_event_codes": ["buying_climax", "upthrust"],
        "source_target_event_codes": ["buying_climax", "upthrust"],
        "symbol": "CIPLA.NS",
    }
    row.update(overrides)
    return row


def _promotion_readiness_gate(row: dict[str, Any]) -> dict[str, Any]:
    """Audit-only promotion-readiness gate for saved causality rows.

    This executable spec intentionally does not activate detector logic. It only
    records whether a causality outcome is eligible for a later human-reviewed
    detector backlog discussion.
    """

    outcome_label = row["outcome_label"]
    policy = dict(PROMOTION_GATE_POLICY[outcome_label])
    future_support = tuple(row.get("future_supporting_event_codes") or ())
    future_opposition = tuple(row.get("future_opposing_event_codes") or ())
    event_code = row.get("event_code")

    policy["may_activate_production_detector"] = False
    policy["keeps_audit_only_boundary"] = bool(row.get("audit_only"))
    policy["has_future_support"] = bool(future_support)
    policy["has_future_opposition"] = bool(future_opposition)
    policy["is_non_detector_context"] = event_code in NON_DETECTOR_CANDIDATES

    if policy["is_non_detector_context"]:
        policy["may_enter_detector_backlog"] = False

    if outcome_label == OUTCOME_FOLLOW_THROUGH_VISIBLE:
        policy["may_enter_detector_backlog"] = (
            policy["may_enter_detector_backlog"]
            and bool(future_support)
            and not bool(future_opposition)
            and event_code not in NON_DETECTOR_CANDIDATES
            and row.get("recommended_action") == policy["expected_action"]
        )

    return policy


def test_causality_v2_counts_feed_promotion_gate_without_mass_activation() -> None:
    total_rows = sum(CAUSALITY_V2_OUTCOME_COUNTS.values())

    assert total_rows == 134
    assert sum(CAUSALITY_V2_EVENT_COUNTS.values()) == total_rows
    assert sum(CAUSALITY_V2_DIRECTION_COUNTS.values()) == total_rows
    assert CAUSALITY_V2_OUTCOME_COUNTS[OUTCOME_FOLLOW_THROUGH_VISIBLE] == 12
    assert CAUSALITY_V2_OUTCOME_COUNTS[OUTCOME_MIXED_FOLLOW_THROUGH_CONFLICT] == 28
    assert CAUSALITY_V2_OUTCOME_COUNTS[OUTCOME_INVALIDATED_BY_LATER_EVIDENCE] == 36
    assert CAUSALITY_V2_OUTCOME_COUNTS[OUTCOME_NO_LATER_SELECTED_AUDIT_ROWS] == 40
    assert CAUSALITY_V2_OUTCOME_COUNTS[OUTCOME_PENDING_INSUFFICIENT_FUTURE_ROWS] == 3

    promotable_outcome_rows = CAUSALITY_V2_OUTCOME_COUNTS[OUTCOME_FOLLOW_THROUGH_VISIBLE]
    blocked_or_incomplete_rows = total_rows - promotable_outcome_rows

    assert promotable_outcome_rows == 12
    assert blocked_or_incomplete_rows == 122


def test_only_clean_follow_through_can_enter_detector_backlog_review() -> None:
    rows = [
        _causality_row(
            outcome_label=OUTCOME_FOLLOW_THROUGH_VISIBLE,
            recommended_action=ACTION_REVIEW_FOR_CONTINUATION,
            future_supporting_event_codes=["increasing_demand", "demand_coming_in"],
            future_opposing_event_codes=[],
        ),
        _causality_row(
            outcome_label=OUTCOME_MIXED_FOLLOW_THROUGH_CONFLICT,
            recommended_action=ACTION_REVIEW_MIXED_CLUSTER,
            future_supporting_event_codes=["increasing_demand"],
            future_opposing_event_codes=["upthrust"],
        ),
        _causality_row(
            outcome_label=OUTCOME_INVALIDATED_BY_LATER_EVIDENCE,
            recommended_action=ACTION_REVIEW_FOR_INVALIDATION,
            future_supporting_event_codes=[],
            future_opposing_event_codes=["increasing_supply"],
        ),
        _causality_row(
            event_code=CANDIDATE_CONTEXT_CONFLICT,
            event_family="qualification_lifecycle",
            event_direction="bearish",
            qualification="persistent_bullish",
            outcome_label=OUTCOME_LIFECYCLE_TRANSITION_REVIEW,
            recommended_action=ACTION_REVIEW_CONTEXT_LIFECYCLE,
            future_supporting_event_codes=["increasing_supply"],
            future_opposing_event_codes=[],
        ),
        _causality_row(
            outcome_label=OUTCOME_NO_LATER_SELECTED_AUDIT_ROWS,
            recommended_action=ACTION_RERUN_WIDER_CONTEXT,
            future_rows_checked=0,
            future_supporting_event_codes=[],
            future_opposing_event_codes=[],
        ),
        _causality_row(
            outcome_label=OUTCOME_PENDING_INSUFFICIENT_FUTURE_ROWS,
            recommended_action=ACTION_WAIT_FOR_MORE_BARS,
            future_rows_checked=2,
            future_supporting_event_codes=[],
            future_opposing_event_codes=[],
        ),
    ]

    decisions = [_promotion_readiness_gate(row) for row in rows]

    assert [decision["gate"] for decision in decisions] == [
        "detector_backlog_review_candidate",
        "manual_review_only_mixed_cluster",
        "blocked_by_later_opposing_evidence",
        "qualification_lifecycle_review_only",
        "rerun_required_before_promotion_review",
        "wait_for_more_completed_bars",
    ]
    assert [decision["may_enter_detector_backlog"] for decision in decisions] == [
        True,
        False,
        False,
        False,
        False,
        False,
    ]
    assert all(
        decision["may_activate_production_detector"] is False for decision in decisions
    )
    assert all(decision["keeps_audit_only_boundary"] is True for decision in decisions)


def test_follow_through_requires_clean_future_support_before_backlog_review() -> None:
    no_support = _causality_row(
        outcome_label=OUTCOME_FOLLOW_THROUGH_VISIBLE,
        recommended_action=ACTION_REVIEW_FOR_CONTINUATION,
        future_supporting_event_codes=[],
        future_opposing_event_codes=[],
    )
    has_opposition = _causality_row(
        outcome_label=OUTCOME_FOLLOW_THROUGH_VISIBLE,
        recommended_action=ACTION_REVIEW_FOR_CONTINUATION,
        future_supporting_event_codes=["demand_coming_in"],
        future_opposing_event_codes=["upthrust"],
    )
    context_row = _causality_row(
        event_code=CANDIDATE_CONTEXT_CONFLICT,
        event_family="qualification_lifecycle",
        outcome_label=OUTCOME_FOLLOW_THROUGH_VISIBLE,
        recommended_action=ACTION_REVIEW_FOR_CONTINUATION,
        future_supporting_event_codes=["demand_coming_in"],
        future_opposing_event_codes=[],
    )

    assert _promotion_readiness_gate(no_support)["may_enter_detector_backlog"] is False
    assert _promotion_readiness_gate(has_opposition)["may_enter_detector_backlog"] is False
    assert _promotion_readiness_gate(context_row)["may_enter_detector_backlog"] is False


def test_rerun_and_pending_outcomes_remain_data_completeness_decisions() -> None:
    rerun_row = _causality_row(
        outcome_label=OUTCOME_NO_LATER_SELECTED_AUDIT_ROWS,
        recommended_action=ACTION_RERUN_WIDER_CONTEXT,
        future_rows_checked=0,
        future_supporting_event_codes=[],
        future_opposing_event_codes=[],
    )
    pending_row = _causality_row(
        outcome_label=OUTCOME_PENDING_INSUFFICIENT_FUTURE_ROWS,
        recommended_action=ACTION_WAIT_FOR_MORE_BARS,
        future_rows_checked=2,
        future_supporting_event_codes=[],
        future_opposing_event_codes=[],
    )

    rerun_decision = _promotion_readiness_gate(rerun_row)
    pending_decision = _promotion_readiness_gate(pending_row)

    assert rerun_decision["requires_wider_audit_context"] is True
    assert rerun_decision["requires_more_completed_bars"] is False
    assert rerun_decision["may_enter_detector_backlog"] is False

    assert pending_decision["requires_wider_audit_context"] is False
    assert pending_decision["requires_more_completed_bars"] is True
    assert pending_decision["may_enter_detector_backlog"] is False


def test_non_detector_context_candidates_cannot_be_promoted_as_price_events() -> None:
    for candidate_code in NON_DETECTOR_CANDIDATES:
        row = _causality_row(
            event_code=candidate_code,
            event_family="qualification_lifecycle",
            outcome_label=OUTCOME_FOLLOW_THROUGH_VISIBLE,
            recommended_action=ACTION_REVIEW_FOR_CONTINUATION,
            future_supporting_event_codes=["demand_coming_in"],
            future_opposing_event_codes=[],
        )
        decision = _promotion_readiness_gate(row)

        assert decision["is_non_detector_context"] is True
        assert decision["may_enter_detector_backlog"] is False
        assert decision["may_activate_production_detector"] is False
