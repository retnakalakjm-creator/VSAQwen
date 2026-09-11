from __future__ import annotations

import json

from vsa_recovery_sequence_label_firing_audit import (
    EXPECTATION_MATCHED,
    EXPECTATION_MISMATCHED,
    EXPECTATION_UNSPECIFIED,
    OUTCOME_BLOCKED,
    OUTCOME_FIRED,
    OUTCOME_NEEDS_FOLLOW_THROUGH,
    OUTCOME_NOT_FIRED,
    STATUS_BLOCKED,
    STATUS_NEEDS_FOLLOW_THROUGH,
    STATUS_NONE,
    STATUS_REVIEW,
    build_vsa_recovery_sequence_label_firing_audit,
    render_vsa_recovery_sequence_label_firing_audit_csv,
)


def test_label_firing_audit_summarizes_saved_casebook_outcomes() -> None:
    payload = {
        "rows": [
            {
                "symbol": "LT.NS",
                "cluster_id": "LT.NS:234-237",
                "casebook_id": "LT.NS:recovery_sequence_review:LT.NS:234-237",
                "recovery_sequence_status": STATUS_REVIEW,
                "review_marker": STATUS_REVIEW,
                "expected_recovery_sequence_status": STATUS_REVIEW,
                "qualification": "persistent_bearish",
                "start_week": "2026-03-02",
                "end_week": "2026-03-23",
                "start_bar_index": 234,
                "end_bar_index": 237,
                "prior_weakness_codes": ["persistent_bearish", "increasing_supply"],
                "stopping_volume_codes": ["stopping_volume"],
                "spring_shakeout_codes": ["shakeout"],
                "follow_through_codes": ["demand_coming_in"],
            },
            {
                "symbol": "DRREDDY.NS",
                "cluster_id": "DRREDDY.NS:236-238",
                "recovery_sequence_status": STATUS_BLOCKED,
                "expected_status": STATUS_REVIEW,
                "blocker_codes": ["structural_progression_weakening"],
                "prior_weakness_codes": ["persistent_bearish"],
                "stopping_volume_codes": ["supply_absorption"],
                "spring_shakeout_codes": ["spring"],
                "follow_through_codes": ["increasing_demand"],
            },
            {
                "symbol": "GRASIM.NS",
                "cluster_id": "GRASIM.NS:233-233",
                "recovery_sequence_status": STATUS_NEEDS_FOLLOW_THROUGH,
                "follow_through_codes": ["demand_coming_in"],
                "follow_through_evidence_age": 4,
            },
            {
                "symbol": "BRITANNIA.NS",
                "cluster_id": "BRITANNIA.NS:238-238",
                "recovery_sequence_status": STATUS_NONE,
                "ignored_audit_only_codes": ["audit_high_volume_reversal_candidate"],
            },
        ]
    }

    summary = build_vsa_recovery_sequence_label_firing_audit(payload)

    assert summary.audit_only is True
    assert summary.production_safe is True
    assert summary.total_input_rows == 4
    assert summary.fired_count == 1
    assert summary.blocked_count == 1
    assert summary.needs_follow_through_count == 1
    assert summary.not_fired_count == 1
    assert summary.matched_expectation_count == 1
    assert summary.mismatched_expectation_count == 1
    assert summary.unspecified_expectation_count == 2
    assert summary.outcome_counts == {
        OUTCOME_FIRED: 1,
        OUTCOME_BLOCKED: 1,
        OUTCOME_NEEDS_FOLLOW_THROUGH: 1,
        OUTCOME_NOT_FIRED: 1,
    }
    assert summary.expectation_counts == {
        EXPECTATION_MATCHED: 1,
        EXPECTATION_MISMATCHED: 1,
        EXPECTATION_UNSPECIFIED: 2,
    }
    assert summary.top_mismatches[0]["symbol"] == "DRREDDY.NS"
    assert summary.top_fired_items[0]["symbol"] == "LT.NS"


def test_label_firing_audit_row_preserves_saved_casebook_fields() -> None:
    summary = build_vsa_recovery_sequence_label_firing_audit(
        {
            "rows": [
                {
                    "symbol": "AMBUJACEM.NS",
                    "cluster_id": "AMBUJACEM.NS:235-235",
                    "casebook_id": "AMBUJACEM.NS:recovery_sequence_review:AMBUJACEM.NS:235-235",
                    "recovery_sequence_status": STATUS_REVIEW,
                    "review_marker": STATUS_REVIEW,
                    "recommended_casebook_action": "chart_review_recovery_sequence_candidate",
                    "qualification": "persistent_bearish",
                    "start_week": "2026-03-02",
                    "end_week": "2026-03-02",
                    "start_bar_index": "235",
                    "end_bar_index": "235",
                    "prior_weakness_codes": ["persistent_bearish", "increasing_supply"],
                    "stopping_volume_codes": ["stopping_volume"],
                    "spring_shakeout_codes": ["spring"],
                    "follow_through_codes": ["increasing_demand"],
                    "follow_through_evidence_age": "0",
                    "used_fallback_evidence": "false",
                    "expected_status": STATUS_REVIEW,
                }
            ]
        }
    )

    row = summary.rows[0]

    assert row.symbol == "AMBUJACEM.NS"
    assert row.cluster_id == "AMBUJACEM.NS:235-235"
    assert row.casebook_id == "AMBUJACEM.NS:recovery_sequence_review:AMBUJACEM.NS:235-235"
    assert row.label_firing_outcome == OUTCOME_FIRED
    assert row.expectation_result == EXPECTATION_MATCHED
    assert row.start_bar_index == 235
    assert row.end_bar_index == 235
    assert row.follow_through_evidence_age == 0
    assert row.used_fallback_evidence is False
    assert row.prior_weakness_codes == ("persistent_bearish", "increasing_supply")
    assert row.stopping_volume_codes == ("stopping_volume",)
    assert row.spring_shakeout_codes == ("spring",)
    assert row.follow_through_codes == ("increasing_demand",)
    assert "6C label fired" in row.audit_note
    assert row.to_dict()["audit_only"] is True
    assert row.to_dict()["production_safe"] is True


def test_label_firing_audit_marks_unexpected_absence_as_mismatch() -> None:
    summary = build_vsa_recovery_sequence_label_firing_audit(
        {
            "symbol": "GODREJCP.NS",
            "cluster_id": "GODREJCP.NS:238-238",
            "status": STATUS_NONE,
            "expected_status": STATUS_REVIEW,
            "prior_weakness_codes": ["persistent_bearish"],
            "stopping_volume_codes": [],
            "spring_shakeout_codes": ["shakeout"],
            "follow_through_codes": ["demand_coming_in"],
            "ignored_audit_only_codes": ["audit_absorption_candidate"],
        }
    )

    row = summary.rows[0]

    assert row.label_firing_outcome == OUTCOME_NOT_FIRED
    assert row.expectation_result == EXPECTATION_MISMATCHED
    assert summary.not_fired_count == 1
    assert summary.mismatched_expectation_count == 1
    assert "stopping-volume anchor" in row.audit_note
    assert "production anchor after ignoring audit-only candidates" in row.audit_note


def test_label_firing_audit_serializes_to_json_and_csv() -> None:
    summary = build_vsa_recovery_sequence_label_firing_audit(
        [
            {
                "symbol": "LT.NS",
                "cluster_id": "LT.NS:234-237",
                "recovery_sequence_status": STATUS_REVIEW,
                "review_marker": STATUS_REVIEW,
                "expected_status": STATUS_REVIEW,
                "prior_weakness_codes": ["persistent_bearish"],
                "stopping_volume_codes": ["stopping_volume"],
                "spring_shakeout_codes": ["shakeout"],
                "follow_through_codes": ["demand_coming_in"],
            }
        ]
    )

    payload = summary.to_dict()
    assert json.dumps(payload)
    assert payload["rows"][0]["label_firing_outcome"] == OUTCOME_FIRED
    assert payload["rows"][0]["expectation_result"] == EXPECTATION_MATCHED

    csv_text = render_vsa_recovery_sequence_label_firing_audit_csv(summary)
    assert "symbol,cluster_id,casebook_id,recovery_sequence_status" in csv_text
    assert "LT.NS,LT.NS:234-237" in csv_text
    assert STATUS_REVIEW in csv_text
    assert OUTCOME_FIRED in csv_text


def test_label_firing_audit_accepts_alternate_row_collection_names() -> None:
    for collection_name in ("casebook_rows", "audit_rows", "results"):
        summary = build_vsa_recovery_sequence_label_firing_audit(
            {
                collection_name: [
                    {
                        "symbol": "DRREDDY.NS",
                        "recovery_sequence_status": STATUS_BLOCKED,
                        "blocker_codes": ["increasing_supply"],
                    }
                ]
            }
        )

        assert summary.total_input_rows == 1
        assert summary.blocked_count == 1
        assert summary.rows[0].label_firing_outcome == OUTCOME_BLOCKED
        assert "blocked" in summary.rows[0].audit_note
