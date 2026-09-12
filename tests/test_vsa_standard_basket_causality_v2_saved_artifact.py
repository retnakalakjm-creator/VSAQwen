from __future__ import annotations

from collections import Counter


STANDARD_BASKET_CAUSALITY_V2_COUNTS = {
    "direction_counts": {
        "bearish": 9,
        "bullish": 125,
    },
    "event_counts": {
        "audit_absorption_candidate": 33,
        "audit_effort_gt_result_candidate": 48,
        "audit_high_volume_reversal_candidate": 38,
        "audit_qualification_conflict_candidate": 15,
    },
    "outcome_counts": {
        "follow_through_visible": 12,
        "invalidated_by_later_evidence": 36,
        "lifecycle_transition_review": 15,
        "mixed_follow_through_conflict": 28,
        "no_later_selected_audit_rows": 40,
        "pending_insufficient_future_rows": 3,
    },
}

REVIEW_HORIZON_ROWS = 8

EXPECTED_RECOMMENDED_ACTIONS = {
    "follow_through_visible": "review_for_event_continuation_or_active_lifecycle",
    "invalidated_by_later_evidence": "review_for_event_invalidation_or_supersession",
    "lifecycle_transition_review": "review_context_lifecycle_transition",
    "mixed_follow_through_conflict": "review_mixed_event_cluster_before_activation",
    "no_later_selected_audit_rows": "rerun_with_wider_same_symbol_audit_context",
    "pending_insufficient_future_rows": "wait_for_more_completed_bars",
}


CANDIDATE_FAMILIES = {
    "audit_absorption_candidate": "absorption",
    "audit_effort_gt_result_candidate": "effort_vs_result",
    "audit_high_volume_reversal_candidate": "high_volume_reversal",
    "audit_qualification_conflict_candidate": "qualification_lifecycle",
}


def _causality_row(
    *,
    symbol: str,
    event_code: str,
    event_direction: str,
    qualification: str,
    outcome_label: str,
    recommended_action: str,
    replay_week: str,
    replay_bar_index: int,
    future_rows_checked: int,
    future_supporting_event_codes: list[str] | None = None,
    future_opposing_event_codes: list[str] | None = None,
    future_lifecycle_actions: list[str] | None = None,
    source_bucket: str = "manual_chart_review",
    source_scoring_event_codes: list[str] | None = None,
    source_target_event_codes: list[str] | None = None,
) -> dict[str, object]:
    return {
        "audit_only": True,
        "causal_read": f"Saved causality-v2 {outcome_label} representative row.",
        "event_code": event_code,
        "event_direction": event_direction,
        "event_family": CANDIDATE_FAMILIES[event_code],
        "future_lifecycle_actions": future_lifecycle_actions or [],
        "future_opposing_event_codes": future_opposing_event_codes or [],
        "future_rows_checked": future_rows_checked,
        "future_supporting_event_codes": future_supporting_event_codes or [],
        "outcome_label": outcome_label,
        "qualification": qualification,
        "recommended_action": recommended_action,
        "replay_bar_index": replay_bar_index,
        "replay_week": replay_week,
        "review_horizon_rows": REVIEW_HORIZON_ROWS,
        "source_bucket": source_bucket,
        "source_priority": "high",
        "source_reasons": [
            "saved standard-basket causality-v2 row for manual chart review"
        ],
        "source_scoring_event_codes": source_scoring_event_codes or [],
        "source_target_event_codes": source_target_event_codes or [],
        "symbol": symbol,
    }


def _standard_basket_causality_v2_payload() -> dict[str, object]:
    return {
        "audit_only": True,
        **STANDARD_BASKET_CAUSALITY_V2_COUNTS,
        "review_horizon_rows": REVIEW_HORIZON_ROWS,
        "rows": [
            _causality_row(
                symbol="ADANIPORTS.NS",
                event_code="audit_effort_gt_result_candidate",
                event_direction="bullish",
                qualification="unqualified",
                outcome_label="mixed_follow_through_conflict",
                recommended_action="review_mixed_event_cluster_before_activation",
                replay_week="2026-03-16 00:00:00",
                replay_bar_index=955,
                future_rows_checked=2,
                future_supporting_event_codes=[
                    "increasing_demand",
                    "demand_coming_in",
                ],
                future_opposing_event_codes=[
                    "buying_climax",
                    "upthrust",
                    "structural_progression_weakening",
                ],
                source_bucket="contradictory_production_evidence",
                source_scoring_event_codes=["hidden_supply"],
                source_target_event_codes=["hidden_supply"],
            ),
            _causality_row(
                symbol="BAJFINANCE.NS",
                event_code="audit_absorption_candidate",
                event_direction="bullish",
                qualification="unqualified",
                outcome_label="follow_through_visible",
                recommended_action="review_for_event_continuation_or_active_lifecycle",
                replay_week="2026-03-23 00:00:00",
                replay_bar_index=1238,
                future_rows_checked=1,
                future_supporting_event_codes=[
                    "increasing_demand",
                    "demand_coming_in",
                ],
                source_bucket="overlapping_candidate_cluster",
                source_scoring_event_codes=["buying_climax", "upthrust"],
                source_target_event_codes=["buying_climax", "upthrust"],
            ),
            _causality_row(
                symbol="BHARTIARTL.NS",
                event_code="audit_absorption_candidate",
                event_direction="bullish",
                qualification="unqualified",
                outcome_label="invalidated_by_later_evidence",
                recommended_action="review_for_event_invalidation_or_supersession",
                replay_week="2026-03-02 00:00:00",
                replay_bar_index=233,
                future_rows_checked=2,
                future_opposing_event_codes=["increasing_supply"],
                source_bucket="overlapping_candidate_cluster",
                source_scoring_event_codes=["increasing_supply"],
            ),
            _causality_row(
                symbol="ASIANPAINT.NS",
                event_code="audit_effort_gt_result_candidate",
                event_direction="bullish",
                qualification="unqualified",
                outcome_label="no_later_selected_audit_rows",
                recommended_action="rerun_with_wider_same_symbol_audit_context",
                replay_week="2026-04-06 00:00:00",
                replay_bar_index=238,
                future_rows_checked=0,
                source_bucket="clean_candidate",
                source_scoring_event_codes=[
                    "increasing_demand",
                    "demand_coming_in",
                ],
                source_target_event_codes=[
                    "increasing_demand",
                    "demand_coming_in",
                ],
            ),
            _causality_row(
                symbol="GRASIM.NS",
                event_code="audit_qualification_conflict_candidate",
                event_direction="bullish",
                qualification="persistent_bearish",
                outcome_label="lifecycle_transition_review",
                recommended_action="review_context_lifecycle_transition",
                replay_week="2026-03-23 00:00:00",
                replay_bar_index=236,
                future_rows_checked=0,
                source_bucket="qualification_lifecycle_issue",
                source_scoring_event_codes=[
                    "increasing_demand",
                    "demand_coming_in",
                ],
                source_target_event_codes=[
                    "increasing_demand",
                    "demand_coming_in",
                ],
            ),
            _causality_row(
                symbol="HDFCBANK.NS",
                event_code="audit_qualification_conflict_candidate",
                event_direction="bearish",
                qualification="persistent_bullish",
                outcome_label="lifecycle_transition_review",
                recommended_action="review_context_lifecycle_transition",
                replay_week="2026-03-09 00:00:00",
                replay_bar_index=234,
                future_rows_checked=3,
                future_supporting_event_codes=["increasing_supply"],
                source_bucket="qualification_lifecycle_issue",
                source_scoring_event_codes=["increasing_supply"],
                source_target_event_codes=["increasing_supply"],
            ),
            _causality_row(
                symbol="SRF.NS",
                event_code="audit_effort_gt_result_candidate",
                event_direction="bullish",
                qualification="unqualified",
                outcome_label="pending_insufficient_future_rows",
                recommended_action="wait_for_more_completed_bars",
                replay_week="2026-03-16 00:00:00",
                replay_bar_index=1237,
                future_rows_checked=2,
                source_bucket="contradictory_production_evidence",
                source_scoring_event_codes=["increasing_supply"],
            ),
        ],
    }


def test_standard_basket_causality_v2_top_level_counts_match_real_artifact() -> None:
    payload = _standard_basket_causality_v2_payload()

    assert payload["audit_only"] is True
    assert payload["review_horizon_rows"] == REVIEW_HORIZON_ROWS
    assert payload["direction_counts"] == {"bearish": 9, "bullish": 125}
    assert payload["event_counts"] == {
        "audit_absorption_candidate": 33,
        "audit_effort_gt_result_candidate": 48,
        "audit_high_volume_reversal_candidate": 38,
        "audit_qualification_conflict_candidate": 15,
    }
    assert payload["outcome_counts"] == {
        "follow_through_visible": 12,
        "invalidated_by_later_evidence": 36,
        "lifecycle_transition_review": 15,
        "mixed_follow_through_conflict": 28,
        "no_later_selected_audit_rows": 40,
        "pending_insufficient_future_rows": 3,
    }
    assert sum(payload["direction_counts"].values()) == 134
    assert sum(payload["event_counts"].values()) == 134
    assert sum(payload["outcome_counts"].values()) == 134


def test_representative_rows_cover_saved_outcomes_and_actions() -> None:
    payload = _standard_basket_causality_v2_payload()
    rows = payload["rows"]

    assert len(rows) < sum(payload["outcome_counts"].values())
    assert {row["outcome_label"] for row in rows} == set(
        payload["outcome_counts"]
    )
    assert {row["recommended_action"] for row in rows} == set(
        EXPECTED_RECOMMENDED_ACTIONS.values()
    )
    assert all(row["audit_only"] is True for row in rows)
    assert all(row["source_priority"] == "high" for row in rows)
    assert all(row["review_horizon_rows"] == REVIEW_HORIZON_ROWS for row in rows)
    assert all(row["future_rows_checked"] <= REVIEW_HORIZON_ROWS for row in rows)
    assert all(row["event_code"] in payload["event_counts"] for row in rows)
    assert all(row["event_direction"] in payload["direction_counts"] for row in rows)
    assert all(row["source_bucket"] for row in rows)



def test_future_evidence_outcomes_keep_directional_context() -> None:
    rows = {
        row["outcome_label"]: row
        for row in _standard_basket_causality_v2_payload()["rows"]
    }

    follow_through = rows["follow_through_visible"]
    assert follow_through["future_supporting_event_codes"] == [
        "increasing_demand",
        "demand_coming_in",
    ]
    assert follow_through["future_opposing_event_codes"] == []
    assert (
        follow_through["recommended_action"]
        == "review_for_event_continuation_or_active_lifecycle"
    )

    invalidated = rows["invalidated_by_later_evidence"]
    assert invalidated["future_supporting_event_codes"] == []
    assert invalidated["future_opposing_event_codes"] == ["increasing_supply"]
    assert (
        invalidated["recommended_action"]
        == "review_for_event_invalidation_or_supersession"
    )

    mixed = rows["mixed_follow_through_conflict"]
    assert mixed["future_supporting_event_codes"] == [
        "increasing_demand",
        "demand_coming_in",
    ]
    assert mixed["future_opposing_event_codes"] == [
        "buying_climax",
        "upthrust",
        "structural_progression_weakening",
    ]
    assert mixed["recommended_action"] == "review_mixed_event_cluster_before_activation"



def test_lifecycle_rows_remain_context_review_not_price_event_activation() -> None:
    rows = [
        row
        for row in _standard_basket_causality_v2_payload()["rows"]
        if row["event_family"] == "qualification_lifecycle"
    ]

    assert rows
    assert {row["event_code"] for row in rows} == {
        "audit_qualification_conflict_candidate"
    }
    assert {row["recommended_action"] for row in rows} == {
        "review_context_lifecycle_transition"
    }
    assert {row["outcome_label"] for row in rows} == {
        "lifecycle_transition_review"
    }
    assert {row["event_direction"] for row in rows} == {"bearish", "bullish"}
    assert any(
        row["qualification"] == "persistent_bullish"
        and row["future_supporting_event_codes"] == ["increasing_supply"]
        for row in rows
    )



def test_no_later_and_pending_outcomes_do_not_activate_candidates() -> None:
    rows = {
        row["outcome_label"]: row
        for row in _standard_basket_causality_v2_payload()["rows"]
    }

    no_later = rows["no_later_selected_audit_rows"]
    assert no_later["future_rows_checked"] == 0
    assert no_later["future_supporting_event_codes"] == []
    assert no_later["future_opposing_event_codes"] == []
    assert no_later["recommended_action"] == "rerun_with_wider_same_symbol_audit_context"

    pending = rows["pending_insufficient_future_rows"]
    assert pending["future_rows_checked"] == 2
    assert pending["future_supporting_event_codes"] == []
    assert pending["future_opposing_event_codes"] == []
    assert pending["recommended_action"] == "wait_for_more_completed_bars"

    actions = [row["recommended_action"] for row in rows.values()]
    assert all("activate" not in action for action in actions)
    assert all("production" not in action for action in actions)



def test_representative_row_distribution_is_intentionally_smaller_than_artifact() -> None:
    payload = _standard_basket_causality_v2_payload()
    rows = payload["rows"]

    assert len(rows) == 7
    assert len(rows) < sum(payload["outcome_counts"].values())
    assert Counter(row["event_code"] for row in rows) == {
        "audit_absorption_candidate": 2,
        "audit_effort_gt_result_candidate": 3,
        "audit_qualification_conflict_candidate": 2,
    }
    assert Counter(row["event_direction"] for row in rows) == {
        "bearish": 1,
        "bullish": 6,
    }
