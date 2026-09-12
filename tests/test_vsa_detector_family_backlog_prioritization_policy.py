from __future__ import annotations

from collections import Counter
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
OUTCOME_MIXED_FOLLOW_THROUGH_CONFLICT = "mixed_follow_through_conflict"
ACTION_REVIEW_FOR_CONTINUATION = "review_for_event_continuation_or_active_lifecycle"

FAMILY_EFFORT_VS_RESULT = "effort_vs_result"
FAMILY_HIGH_VOLUME_REVERSAL = "high_volume_reversal"
FAMILY_ABSORPTION = "absorption"

SOURCE_BUCKET_CLEAN = "clean_candidate"
SOURCE_BUCKET_CLUSTER = "overlapping_candidate_cluster"
SOURCE_BUCKET_CONTRADICTORY = "contradictory_production_evidence"
SOURCE_BUCKET_NOISY = "likely_noisy_diagnostic"

DETECTOR_FAMILY_BACKLOG_ORDER = [
    FAMILY_EFFORT_VS_RESULT,
    FAMILY_HIGH_VOLUME_REVERSAL,
    FAMILY_ABSORPTION,
]

NON_DETECTOR_CANDIDATES = frozenset(
    {
        CANDIDATE_CONTEXT_CONFLICT,
        CANDIDATE_STALE_EVIDENCE,
    }
)

FOLLOW_THROUGH_VISIBLE_ROWS = [
    {
        "symbol": "BAJFINANCE.NS",
        "replay_week": "2026-03-23 00:00:00",
        "replay_bar_index": 1238,
        "event_code": CANDIDATE_ABSORPTION,
        "event_family": FAMILY_ABSORPTION,
        "qualification": "unqualified",
        "source_bucket": SOURCE_BUCKET_CLUSTER,
        "future_rows_checked": 1,
        "future_supporting_event_codes": ["increasing_demand", "demand_coming_in"],
        "future_opposing_event_codes": [],
        "source_target_event_codes": ["buying_climax", "upthrust"],
        "source_scoring_event_codes": ["buying_climax", "upthrust"],
    },
    {
        "symbol": "BAJFINANCE.NS",
        "replay_week": "2026-03-23 00:00:00",
        "replay_bar_index": 1238,
        "event_code": CANDIDATE_EFFORT_GT_RESULT,
        "event_family": FAMILY_EFFORT_VS_RESULT,
        "qualification": "unqualified",
        "source_bucket": SOURCE_BUCKET_CLUSTER,
        "future_rows_checked": 1,
        "future_supporting_event_codes": ["increasing_demand", "demand_coming_in"],
        "future_opposing_event_codes": [],
        "source_target_event_codes": ["buying_climax", "upthrust"],
        "source_scoring_event_codes": ["buying_climax", "upthrust"],
    },
    {
        "symbol": "BAJFINANCE.NS",
        "replay_week": "2026-03-23 00:00:00",
        "replay_bar_index": 1238,
        "event_code": CANDIDATE_HIGH_VOLUME_REVERSAL,
        "event_family": FAMILY_HIGH_VOLUME_REVERSAL,
        "qualification": "unqualified",
        "source_bucket": SOURCE_BUCKET_CLUSTER,
        "future_rows_checked": 1,
        "future_supporting_event_codes": ["increasing_demand", "demand_coming_in"],
        "future_opposing_event_codes": [],
        "source_target_event_codes": ["buying_climax", "upthrust"],
        "source_scoring_event_codes": ["buying_climax", "upthrust"],
    },
    {
        "symbol": "CIPLA.NS",
        "replay_week": "2026-04-06 00:00:00",
        "replay_bar_index": 238,
        "event_code": CANDIDATE_EFFORT_GT_RESULT,
        "event_family": FAMILY_EFFORT_VS_RESULT,
        "qualification": "unqualified",
        "source_bucket": SOURCE_BUCKET_CLEAN,
        "future_rows_checked": 1,
        "future_supporting_event_codes": ["increasing_demand", "demand_coming_in"],
        "future_opposing_event_codes": [],
        "source_target_event_codes": ["increasing_demand", "demand_coming_in"],
        "source_scoring_event_codes": ["increasing_demand", "demand_coming_in"],
    },
    {
        "symbol": "COALINDIA.NS",
        "replay_week": "2026-03-02 00:00:00",
        "replay_bar_index": 800,
        "event_code": CANDIDATE_EFFORT_GT_RESULT,
        "event_family": FAMILY_EFFORT_VS_RESULT,
        "qualification": "persistent_bullish",
        "source_bucket": SOURCE_BUCKET_NOISY,
        "future_rows_checked": 1,
        "future_supporting_event_codes": ["demand_coming_in"],
        "future_opposing_event_codes": [],
        "source_target_event_codes": ["increasing_demand"],
        "source_scoring_event_codes": ["increasing_demand"],
    },
    {
        "symbol": "DRREDDY.NS",
        "replay_week": "2026-04-13 00:00:00",
        "replay_bar_index": 239,
        "event_code": CANDIDATE_ABSORPTION,
        "event_family": FAMILY_ABSORPTION,
        "qualification": "persistent_bearish",
        "source_bucket": SOURCE_BUCKET_CONTRADICTORY,
        "future_rows_checked": 2,
        "future_supporting_event_codes": ["increasing_demand", "demand_coming_in"],
        "future_opposing_event_codes": [],
        "source_target_event_codes": [],
        "source_scoring_event_codes": ["increasing_supply"],
    },
    {
        "symbol": "DRREDDY.NS",
        "replay_week": "2026-04-13 00:00:00",
        "replay_bar_index": 239,
        "event_code": CANDIDATE_HIGH_VOLUME_REVERSAL,
        "event_family": FAMILY_HIGH_VOLUME_REVERSAL,
        "qualification": "persistent_bearish",
        "source_bucket": SOURCE_BUCKET_CONTRADICTORY,
        "future_rows_checked": 2,
        "future_supporting_event_codes": ["increasing_demand", "demand_coming_in"],
        "future_opposing_event_codes": [],
        "source_target_event_codes": [],
        "source_scoring_event_codes": ["increasing_supply"],
    },
    {
        "symbol": "GRASIM.NS",
        "replay_week": "2026-03-16 00:00:00",
        "replay_bar_index": 235,
        "event_code": CANDIDATE_EFFORT_GT_RESULT,
        "event_family": FAMILY_EFFORT_VS_RESULT,
        "qualification": "persistent_bearish",
        "source_bucket": SOURCE_BUCKET_CONTRADICTORY,
        "future_rows_checked": 2,
        "future_supporting_event_codes": ["increasing_demand", "demand_coming_in"],
        "future_opposing_event_codes": [],
        "source_target_event_codes": ["hidden_supply"],
        "source_scoring_event_codes": ["hidden_supply"],
    },
    {
        "symbol": "HINDUNILVR.NS",
        "replay_week": "2026-04-13 00:00:00",
        "replay_bar_index": 239,
        "event_code": CANDIDATE_ABSORPTION,
        "event_family": FAMILY_ABSORPTION,
        "qualification": "unqualified",
        "source_bucket": SOURCE_BUCKET_CONTRADICTORY,
        "future_rows_checked": 1,
        "future_supporting_event_codes": ["increasing_demand"],
        "future_opposing_event_codes": [],
        "source_target_event_codes": [],
        "source_scoring_event_codes": ["hidden_supply"],
    },
    {
        "symbol": "HINDUNILVR.NS",
        "replay_week": "2026-04-13 00:00:00",
        "replay_bar_index": 239,
        "event_code": CANDIDATE_HIGH_VOLUME_REVERSAL,
        "event_family": FAMILY_HIGH_VOLUME_REVERSAL,
        "qualification": "unqualified",
        "source_bucket": SOURCE_BUCKET_CONTRADICTORY,
        "future_rows_checked": 1,
        "future_supporting_event_codes": ["increasing_demand"],
        "future_opposing_event_codes": [],
        "source_target_event_codes": [],
        "source_scoring_event_codes": ["hidden_supply"],
    },
    {
        "symbol": "ULTRACEMCO.NS",
        "replay_week": "2026-03-16 00:00:00",
        "replay_bar_index": 235,
        "event_code": CANDIDATE_EFFORT_GT_RESULT,
        "event_family": FAMILY_EFFORT_VS_RESULT,
        "qualification": "unqualified",
        "source_bucket": SOURCE_BUCKET_CONTRADICTORY,
        "future_rows_checked": 1,
        "future_supporting_event_codes": ["demand_coming_in"],
        "future_opposing_event_codes": [],
        "source_target_event_codes": [],
        "source_scoring_event_codes": ["increasing_supply"],
    },
    {
        "symbol": "ULTRACEMCO.NS",
        "replay_week": "2026-03-16 00:00:00",
        "replay_bar_index": 235,
        "event_code": CANDIDATE_HIGH_VOLUME_REVERSAL,
        "event_family": FAMILY_HIGH_VOLUME_REVERSAL,
        "qualification": "unqualified",
        "source_bucket": SOURCE_BUCKET_CONTRADICTORY,
        "future_rows_checked": 1,
        "future_supporting_event_codes": ["demand_coming_in"],
        "future_opposing_event_codes": [],
        "source_target_event_codes": [],
        "source_scoring_event_codes": ["increasing_supply"],
    },
]


def _saved_follow_through_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "audit_only": True,
        "event_direction": "bullish",
        "future_lifecycle_actions": [],
        "outcome_label": OUTCOME_FOLLOW_THROUGH_VISIBLE,
        "recommended_action": ACTION_REVIEW_FOR_CONTINUATION,
        "review_horizon_rows": 8,
        "source_priority": "high",
        **row,
    }


def _backlog_decision(row: dict[str, Any]) -> dict[str, Any]:
    has_support = bool(row.get("future_supporting_event_codes"))
    has_opposition = bool(row.get("future_opposing_event_codes"))
    is_detector_family = row.get("event_code") not in NON_DETECTOR_CANDIDATES
    is_follow_through = row.get("outcome_label") == OUTCOME_FOLLOW_THROUGH_VISIBLE
    expected_action = row.get("recommended_action") == ACTION_REVIEW_FOR_CONTINUATION

    may_enter_backlog_review = (
        bool(row.get("audit_only"))
        and is_follow_through
        and expected_action
        and is_detector_family
        and has_support
        and not has_opposition
    )

    return {
        "family": row["event_family"],
        "source_bucket": row["source_bucket"],
        "may_enter_backlog_review": may_enter_backlog_review,
        "may_activate_production_detector": False,
        "requires_family_specific_chart_review": may_enter_backlog_review,
    }


def _rank_families(rows: list[dict[str, Any]]) -> list[tuple[str, int]]:
    family_counts = Counter(row["event_family"] for row in rows)
    return sorted(
        family_counts.items(),
        key=lambda item: (
            -item[1],
            DETECTOR_FAMILY_BACKLOG_ORDER.index(item[0]),
        ),
    )


def test_follow_through_rows_rank_effort_vs_result_as_first_family() -> None:
    rows = [_saved_follow_through_row(row) for row in FOLLOW_THROUGH_VISIBLE_ROWS]

    assert len(rows) == 12
    assert {row["outcome_label"] for row in rows} == {OUTCOME_FOLLOW_THROUGH_VISIBLE}
    assert all(row["recommended_action"] == ACTION_REVIEW_FOR_CONTINUATION for row in rows)
    assert all(row["review_horizon_rows"] == 8 for row in rows)
    assert all(row["future_supporting_event_codes"] for row in rows)
    assert all(not row["future_opposing_event_codes"] for row in rows)

    assert Counter(row["event_family"] for row in rows) == {
        FAMILY_EFFORT_VS_RESULT: 5,
        FAMILY_HIGH_VOLUME_REVERSAL: 4,
        FAMILY_ABSORPTION: 3,
    }
    assert _rank_families(rows) == [
        (FAMILY_EFFORT_VS_RESULT, 5),
        (FAMILY_HIGH_VOLUME_REVERSAL, 4),
        (FAMILY_ABSORPTION, 3),
    ]


def test_backlog_review_keeps_detector_family_work_manual_only() -> None:
    rows = [_saved_follow_through_row(row) for row in FOLLOW_THROUGH_VISIBLE_ROWS]
    decisions = [_backlog_decision(row) for row in rows]

    assert all(decision["may_enter_backlog_review"] is True for decision in decisions)
    assert all(
        decision["requires_family_specific_chart_review"] is True
        for decision in decisions
    )
    assert all(
        decision["may_activate_production_detector"] is False
        for decision in decisions
    )


def test_family_backlog_preserves_source_bucket_and_symbol_context() -> None:
    rows = [_saved_follow_through_row(row) for row in FOLLOW_THROUGH_VISIBLE_ROWS]

    assert Counter(row["symbol"] for row in rows) == {
        "BAJFINANCE.NS": 3,
        "CIPLA.NS": 1,
        "COALINDIA.NS": 1,
        "DRREDDY.NS": 2,
        "GRASIM.NS": 1,
        "HINDUNILVR.NS": 2,
        "ULTRACEMCO.NS": 2,
    }
    assert Counter(row["source_bucket"] for row in rows) == {
        SOURCE_BUCKET_CONTRADICTORY: 7,
        SOURCE_BUCKET_CLUSTER: 3,
        SOURCE_BUCKET_CLEAN: 1,
        SOURCE_BUCKET_NOISY: 1,
    }

    effort_rows = [
        row for row in rows if row["event_family"] == FAMILY_EFFORT_VS_RESULT
    ]
    assert Counter(row["source_bucket"] for row in effort_rows) == {
        SOURCE_BUCKET_CLUSTER: 1,
        SOURCE_BUCKET_CLEAN: 1,
        SOURCE_BUCKET_NOISY: 1,
        SOURCE_BUCKET_CONTRADICTORY: 2,
    }


def test_backlog_gate_rejects_non_detector_or_unclean_outcomes() -> None:
    valid = _saved_follow_through_row(FOLLOW_THROUGH_VISIBLE_ROWS[0])
    missing_support = {
        **valid,
        "future_supporting_event_codes": [],
    }
    opposing_future_evidence = {
        **valid,
        "future_opposing_event_codes": ["upthrust"],
    }
    mixed_outcome = {
        **valid,
        "outcome_label": OUTCOME_MIXED_FOLLOW_THROUGH_CONFLICT,
    }
    invalidated_outcome = {
        **valid,
        "outcome_label": OUTCOME_INVALIDATED_BY_LATER_EVIDENCE,
    }
    context_candidate = {
        **valid,
        "event_code": CANDIDATE_CONTEXT_CONFLICT,
        "event_family": "qualification_lifecycle",
    }

    assert _backlog_decision(valid)["may_enter_backlog_review"] is True
    assert _backlog_decision(missing_support)["may_enter_backlog_review"] is False
    assert (
        _backlog_decision(opposing_future_evidence)["may_enter_backlog_review"]
        is False
    )
    assert _backlog_decision(mixed_outcome)["may_enter_backlog_review"] is False
    assert _backlog_decision(invalidated_outcome)["may_enter_backlog_review"] is False
    assert _backlog_decision(context_candidate)["may_enter_backlog_review"] is False


def test_first_family_review_does_not_skip_high_volume_or_absorption_backlog() -> None:
    rows = [_saved_follow_through_row(row) for row in FOLLOW_THROUGH_VISIBLE_ROWS]
    ranked_families = _rank_families(rows)

    assert ranked_families[0] == (FAMILY_EFFORT_VS_RESULT, 5)
    assert ranked_families[1:] == [
        (FAMILY_HIGH_VOLUME_REVERSAL, 4),
        (FAMILY_ABSORPTION, 3),
    ]
    assert {family for family, _count in ranked_families} == set(
        DETECTOR_FAMILY_BACKLOG_ORDER
    )
