from __future__ import annotations

from collections import Counter
from typing import Any

from vsa_audit_candidate_events import (
    CANDIDATE_ABSORPTION,
    CANDIDATE_EFFORT_GT_RESULT,
    CANDIDATE_HIGH_VOLUME_REVERSAL,
)

OUTCOME_FOLLOW_THROUGH_VISIBLE = "follow_through_visible"
OUTCOME_INVALIDATED_BY_LATER_EVIDENCE = "invalidated_by_later_evidence"
OUTCOME_MIXED_FOLLOW_THROUGH_CONFLICT = "mixed_follow_through_conflict"
ACTION_REVIEW_FOR_CONTINUATION = "review_for_event_continuation_or_active_lifecycle"
ACTION_REVIEW_FOR_INVALIDATION = "review_for_event_invalidation_or_supersession"
ACTION_REVIEW_MIXED_CLUSTER = "review_mixed_event_cluster_before_activation"

FAMILY_EFFORT_VS_RESULT = "effort_vs_result"
FAMILY_ABSORPTION = "absorption"
FAMILY_HIGH_VOLUME_REVERSAL = "high_volume_reversal"

SOURCE_BUCKET_CLEAN = "clean_candidate"
SOURCE_BUCKET_CLUSTER = "overlapping_candidate_cluster"
SOURCE_BUCKET_CONTRADICTORY = "contradictory_production_evidence"
SOURCE_BUCKET_NOISY = "likely_noisy_diagnostic"

CAUSALITY_V2_EVENT_COUNTS = {
    CANDIDATE_ABSORPTION: 33,
    CANDIDATE_EFFORT_GT_RESULT: 48,
    CANDIDATE_HIGH_VOLUME_REVERSAL: 38,
    "audit_qualification_conflict_candidate": 15,
}

FOLLOW_THROUGH_FAMILY_COUNTS = {
    FAMILY_EFFORT_VS_RESULT: 5,
    FAMILY_HIGH_VOLUME_REVERSAL: 4,
    FAMILY_ABSORPTION: 3,
}

EFFORT_VS_RESULT_BACKLOG_ROWS = [
    {
        "symbol": "BAJFINANCE.NS",
        "replay_week": "2026-03-23 00:00:00",
        "replay_bar_index": 1238,
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
        "qualification": "unqualified",
        "source_bucket": SOURCE_BUCKET_CONTRADICTORY,
        "source_scoring_event_codes": ["increasing_supply"],
        "source_target_event_codes": [],
        "future_rows_checked": 1,
        "future_supporting_event_codes": ["demand_coming_in"],
        "future_opposing_event_codes": [],
    },
]


def _saved_effort_row(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    row: dict[str, Any] = {
        "audit_only": True,
        "causal_read": "Audit effort gt result candidate has later same-side VSA evidence.",
        "event_code": CANDIDATE_EFFORT_GT_RESULT,
        "event_direction": "bullish",
        "event_family": FAMILY_EFFORT_VS_RESULT,
        "future_lifecycle_actions": [],
        "future_opposing_event_codes": [],
        "future_rows_checked": 1,
        "future_supporting_event_codes": ["increasing_demand", "demand_coming_in"],
        "outcome_label": OUTCOME_FOLLOW_THROUGH_VISIBLE,
        "qualification": "unqualified",
        "recommended_action": ACTION_REVIEW_FOR_CONTINUATION,
        "replay_bar_index": 238,
        "replay_week": "2026-04-06 00:00:00",
        "review_horizon_rows": 8,
        "source_bucket": SOURCE_BUCKET_CLEAN,
        "source_priority": "high",
        "source_reasons": [
            "saved effort-vs-result follow-through row for detector-family backlog review"
        ],
        "source_scoring_event_codes": ["increasing_demand", "demand_coming_in"],
        "source_target_event_codes": ["increasing_demand", "demand_coming_in"],
        "symbol": "CIPLA.NS",
    }
    if overrides:
        row.update(overrides)
    return row


def _saved_backlog_rows() -> list[dict[str, Any]]:
    return [_saved_effort_row(row) for row in EFFORT_VS_RESULT_BACKLOG_ROWS]


def _effort_vs_result_backlog_gate(row: dict[str, Any]) -> dict[str, Any]:
    future_support = tuple(row.get("future_supporting_event_codes") or ())
    future_opposition = tuple(row.get("future_opposing_event_codes") or ())
    source_bucket = row.get("source_bucket")

    is_effort_follow_through_slice = (
        row.get("audit_only") is True
        and row.get("event_code") == CANDIDATE_EFFORT_GT_RESULT
        and row.get("event_family") == FAMILY_EFFORT_VS_RESULT
        and row.get("outcome_label") == OUTCOME_FOLLOW_THROUGH_VISIBLE
        and row.get("recommended_action") == ACTION_REVIEW_FOR_CONTINUATION
        and row.get("source_priority") == "high"
        and row.get("review_horizon_rows") == 8
        and int(row.get("future_rows_checked") or 0) > 0
        and bool(future_support)
        and not bool(future_opposition)
    )

    review_focus_by_bucket = {
        SOURCE_BUCKET_CLEAN: "calibrate_conditions_against_follow_through",
        SOURCE_BUCKET_CLUSTER: "review_cluster_before_single_family_change",
        SOURCE_BUCKET_CONTRADICTORY: "inspect_detector_gates_before_activation",
        SOURCE_BUCKET_NOISY: "treat_as_continuation_or_redundant_signal",
    }

    return {
        "may_enter_effort_vs_result_backlog_review": is_effort_follow_through_slice,
        "may_activate_production_detector": False,
        "requires_human_chart_review": is_effort_follow_through_slice,
        "review_focus": review_focus_by_bucket.get(source_bucket, "unknown_source_bucket"),
        "has_future_support": bool(future_support),
        "has_future_opposition": bool(future_opposition),
        "source_bucket": source_bucket,
    }


def test_effort_vs_result_slice_uses_only_saved_follow_through_rows() -> None:
    rows = _saved_backlog_rows()

    assert len(rows) == FOLLOW_THROUGH_FAMILY_COUNTS[FAMILY_EFFORT_VS_RESULT] == 5
    assert FOLLOW_THROUGH_FAMILY_COUNTS == {
        FAMILY_EFFORT_VS_RESULT: 5,
        FAMILY_HIGH_VOLUME_REVERSAL: 4,
        FAMILY_ABSORPTION: 3,
    }
    assert CAUSALITY_V2_EVENT_COUNTS[CANDIDATE_EFFORT_GT_RESULT] == 48
    assert len(rows) < CAUSALITY_V2_EVENT_COUNTS[CANDIDATE_EFFORT_GT_RESULT]

    assert [row["symbol"] for row in rows] == [
        "BAJFINANCE.NS",
        "CIPLA.NS",
        "COALINDIA.NS",
        "GRASIM.NS",
        "ULTRACEMCO.NS",
    ]
    assert {(row["symbol"], row["replay_week"], row["replay_bar_index"]) for row in rows} == {
        ("BAJFINANCE.NS", "2026-03-23 00:00:00", 1238),
        ("CIPLA.NS", "2026-04-06 00:00:00", 238),
        ("COALINDIA.NS", "2026-03-02 00:00:00", 800),
        ("GRASIM.NS", "2026-03-16 00:00:00", 235),
        ("ULTRACEMCO.NS", "2026-03-16 00:00:00", 235),
    }


def test_effort_vs_result_slice_preserves_bucket_and_qualification_context() -> None:
    rows = _saved_backlog_rows()

    assert Counter(row["source_bucket"] for row in rows) == {
        SOURCE_BUCKET_CONTRADICTORY: 2,
        SOURCE_BUCKET_CLUSTER: 1,
        SOURCE_BUCKET_CLEAN: 1,
        SOURCE_BUCKET_NOISY: 1,
    }
    assert Counter(row["qualification"] for row in rows) == {
        "unqualified": 3,
        "persistent_bullish": 1,
        "persistent_bearish": 1,
    }
    assert Counter(tuple(row["future_supporting_event_codes"]) for row in rows) == {
        ("increasing_demand", "demand_coming_in"): 3,
        ("demand_coming_in",): 2,
    }
    assert all(row["future_opposing_event_codes"] == [] for row in rows)


def test_effort_vs_result_rows_enter_backlog_review_without_activation() -> None:
    decisions = [_effort_vs_result_backlog_gate(row) for row in _saved_backlog_rows()]

    assert all(
        decision["may_enter_effort_vs_result_backlog_review"] is True
        for decision in decisions
    )
    assert all(
        decision["may_activate_production_detector"] is False for decision in decisions
    )
    assert all(decision["requires_human_chart_review"] is True for decision in decisions)


def test_effort_vs_result_bucket_focus_is_not_flattened() -> None:
    decisions_by_symbol = {
        row["symbol"]: _effort_vs_result_backlog_gate(row)
        for row in _saved_backlog_rows()
    }

    assert decisions_by_symbol["CIPLA.NS"]["review_focus"] == (
        "calibrate_conditions_against_follow_through"
    )
    assert decisions_by_symbol["BAJFINANCE.NS"]["review_focus"] == (
        "review_cluster_before_single_family_change"
    )
    assert decisions_by_symbol["COALINDIA.NS"]["review_focus"] == (
        "treat_as_continuation_or_redundant_signal"
    )
    assert decisions_by_symbol["GRASIM.NS"]["review_focus"] == (
        "inspect_detector_gates_before_activation"
    )
    assert decisions_by_symbol["ULTRACEMCO.NS"]["review_focus"] == (
        "inspect_detector_gates_before_activation"
    )


def test_effort_vs_result_slice_rejects_non_slice_or_incomplete_rows() -> None:
    valid = _saved_effort_row()
    wrong_family = {
        **valid,
        "event_code": CANDIDATE_HIGH_VOLUME_REVERSAL,
        "event_family": FAMILY_HIGH_VOLUME_REVERSAL,
    }
    wrong_candidate = {
        **valid,
        "event_code": CANDIDATE_ABSORPTION,
        "event_family": FAMILY_ABSORPTION,
    }
    mixed_outcome = {
        **valid,
        "outcome_label": OUTCOME_MIXED_FOLLOW_THROUGH_CONFLICT,
        "recommended_action": ACTION_REVIEW_MIXED_CLUSTER,
    }
    invalidated_outcome = {
        **valid,
        "outcome_label": OUTCOME_INVALIDATED_BY_LATER_EVIDENCE,
        "recommended_action": ACTION_REVIEW_FOR_INVALIDATION,
    }
    missing_future_support = {
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
    production_path_row = {
        **valid,
        "audit_only": False,
    }

    rejected_rows = [
        wrong_family,
        wrong_candidate,
        mixed_outcome,
        invalidated_outcome,
        missing_future_support,
        opposing_future_evidence,
        no_future_rows_checked,
        production_path_row,
    ]

    assert _effort_vs_result_backlog_gate(valid)[
        "may_enter_effort_vs_result_backlog_review"
    ] is True
    assert all(
        _effort_vs_result_backlog_gate(row)[
            "may_enter_effort_vs_result_backlog_review"
        ]
        is False
        for row in rejected_rows
    )
    assert all(
        _effort_vs_result_backlog_gate(row)["may_activate_production_detector"]
        is False
        for row in [valid, *rejected_rows]
    )
