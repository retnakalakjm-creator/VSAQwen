from __future__ import annotations

import json

from vsa_recovery_sequence_casebook import (
    CASE_RECOVERY_SEQUENCE_BLOCKED,
    CASE_RECOVERY_SEQUENCE_NEEDS_FOLLOW_THROUGH,
    CASE_RECOVERY_SEQUENCE_REVIEW,
    RECOMMENDED_ACTION_BLOCKED,
    RECOMMENDED_ACTION_FOLLOW_THROUGH,
    RECOMMENDED_ACTION_REVIEW,
    build_vsa_recovery_sequence_casebook,
    render_vsa_recovery_sequence_casebook_csv,
)


def test_recovery_sequence_casebook_marks_review_candidate_from_saved_rows() -> None:
    payload = {
        "rows": [
            {
                "symbol": "LT.NS",
                "cluster_id": "LT.NS:234-237",
                "qualification": "persistent_bearish",
                "start_week": "2026-03-02",
                "end_week": "2026-03-23",
                "start_bar_index": 234,
                "end_bar_index": 237,
                "prior_weakness_codes": ["increasing_supply"],
                "stopping_volume_evidence_codes": ["stopping_volume"],
                "spring_shakeout_evidence_codes": ["shakeout"],
                "follow_through_evidence_codes": ["demand_coming_in"],
                "follow_through_evidence_age": 0,
                "event_family": "recovery_sequence",
                "priority": "high",
            }
        ]
    }

    summary = build_vsa_recovery_sequence_casebook(payload)

    assert summary.audit_only is True
    assert summary.production_safe is True
    assert summary.total_input_rows == 1
    assert summary.total_casebook_rows == 1
    assert summary.status_counts == {"stopping_volume_spring_shakeout_review": 1}
    row = summary.rows[0]
    assert row.audit_only is True
    assert row.production_safe is True
    assert row.casebook_id == "LT.NS:recovery_sequence_review:LT.NS:234-237"
    assert row.case_type == CASE_RECOVERY_SEQUENCE_REVIEW
    assert row.review_marker == "stopping_volume_spring_shakeout_review"
    assert row.recommended_casebook_action == RECOMMENDED_ACTION_REVIEW
    assert row.prior_weakness_codes == ("persistent_bearish", "increasing_supply")
    assert row.stopping_volume_codes == ("stopping_volume",)
    assert row.spring_shakeout_codes == ("shakeout",)
    assert row.follow_through_codes == ("demand_coming_in",)
    assert row.blocker_codes == ()
    assert "Next action: chart_review_recovery_sequence_candidate" in row.case_read


def test_recovery_sequence_casebook_blocks_same_window_supply() -> None:
    summary = build_vsa_recovery_sequence_casebook(
        [
            {
                "symbol": "DRREDDY.NS",
                "cluster_id": "DRREDDY.NS:236-238",
                "qualification": "persistent_bearish",
                "prior_evidence_codes": ["supply_coming_in"],
                "anchor_evidence_codes": ["supply_absorption"],
                "test_evidence_codes": ["spring"],
                "demand_evidence_codes": ["increasing_demand"],
                "same_window_evidence_codes": [
                    "increasing_demand",
                    "structural_progression_weakening",
                ],
                "scoring_evidence_age": 0,
            }
        ]
    )

    row = summary.rows[0]
    assert row.case_type == CASE_RECOVERY_SEQUENCE_BLOCKED
    assert row.review_marker is None
    assert row.recommended_casebook_action == RECOMMENDED_ACTION_BLOCKED
    assert row.blocker_codes == ("structural_progression_weakening",)
    assert summary.recommended_action_counts == {RECOMMENDED_ACTION_BLOCKED: 1}


def test_recovery_sequence_casebook_waits_for_stale_or_fallback_follow_through() -> None:
    summary = build_vsa_recovery_sequence_casebook(
        {
            "symbol": "GRASIM.NS",
            "cluster_id": "GRASIM.NS:233-233",
            "qualification": "persistent_bearish",
            "prior_weakness_codes": ["hidden_supply"],
            "stopping_volume_codes": ["stopping_volume"],
            "spring_shakeout_codes": ["spring"],
            "follow_through_codes": ["demand_coming_in"],
            "follow_through_evidence_age": 4,
            "used_fallback_evidence": True,
        }
    )

    row = summary.rows[0]
    assert row.case_type == CASE_RECOVERY_SEQUENCE_NEEDS_FOLLOW_THROUGH
    assert row.review_marker is None
    assert row.recommended_casebook_action == RECOMMENDED_ACTION_FOLLOW_THROUGH
    assert row.used_fallback_evidence is True
    assert row.follow_through_evidence_age == 4


def test_recovery_sequence_casebook_ignores_audit_only_candidate_codes() -> None:
    summary = build_vsa_recovery_sequence_casebook(
        {
            "rows": [
                {
                    "symbol": "BRITANNIA.NS",
                    "qualification": "persistent_bearish",
                    "prior_weakness_codes": ["audit_absorption_candidate"],
                    "stopping_volume_evidence_codes": ["audit_high_volume_reversal_candidate"],
                    "spring_shakeout_evidence_codes": ["shakeout"],
                    "follow_through_evidence_codes": ["demand_coming_in"],
                    "follow_through_evidence_age": 0,
                }
            ]
        }
    )

    row = summary.rows[0]
    assert row.review_marker is None
    assert row.ignored_audit_only_codes == (
        "audit_absorption_candidate",
        "audit_high_volume_reversal_candidate",
    )
    assert row.stopping_volume_codes == ()
    assert row.to_dict()["audit_only"] is True
    assert row.to_dict()["production_safe"] is True


def test_recovery_sequence_casebook_renders_json_ready_dict_and_csv() -> None:
    summary = build_vsa_recovery_sequence_casebook(
        [
            {
                "symbol": "AMBUJACEM.NS",
                "cluster_id": "AMBUJACEM.NS:235-235",
                "qualification": "persistent_bearish",
                "prior_weakness_codes": ["increasing_supply"],
                "stopping_volume_evidence_codes": ["stopping_volume"],
                "spring_shakeout_evidence_codes": ["spring"],
                "follow_through_evidence_codes": ["increasing_demand"],
                "follow_through_evidence_age": 0,
            }
        ]
    )

    payload = summary.to_dict()
    assert json.dumps(payload)
    assert payload["top_casebook_items"][0]["recommended_casebook_action"] == RECOMMENDED_ACTION_REVIEW

    csv_text = render_vsa_recovery_sequence_casebook_csv(summary)
    assert "casebook_id,symbol,cluster_id,case_type" in csv_text
    assert "AMBUJACEM.NS:recovery_sequence_review:AMBUJACEM.NS:235-235" in csv_text
    assert "stopping_volume_spring_shakeout_review" in csv_text
