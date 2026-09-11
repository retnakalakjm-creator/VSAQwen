from __future__ import annotations

import json

from vsa_recovery_sequence_stage_seed import (
    STAGE_SEED_ANCHOR,
    STAGE_SEED_DIAGNOSTIC,
    build_vsa_recovery_sequence_stage_seed,
    render_vsa_recovery_sequence_stage_seed_csv,
)


STATUS_REVIEW = "stopping_volume_spring_shakeout_review"
STATUS_BLOCKED = "stopping_volume_spring_shakeout_blocked"
STATUS_NEEDS_FOLLOW_THROUGH = "stopping_volume_spring_shakeout_needs_follow_through"
STATUS_NONE = "none"


def test_stage_seed_normalizes_production_recovery_sequence_from_saved_replay_rows() -> None:
    payload = {
        "results": [
            {
                "symbol": "LT.NS",
                "rows": [
                    {
                        "symbol": "LT.NS",
                        "replay_bar_index": 234,
                        "replay_week": "2026-03-02 00:00:00",
                        "target_event_codes": ["increasing_supply"],
                        "qualification": "persistent_bearish",
                    },
                    {
                        "symbol": "LT.NS",
                        "replay_bar_index": 235,
                        "replay_week": "2026-03-09 00:00:00",
                        "target_event_codes": ["stopping_volume"],
                        "qualification": "persistent_bearish",
                    },
                    {
                        "symbol": "LT.NS",
                        "replay_bar_index": 236,
                        "replay_week": "2026-03-16 00:00:00",
                        "target_event_codes": ["shakeout"],
                        "qualification": "persistent_bearish",
                    },
                    {
                        "symbol": "LT.NS",
                        "replay_bar_index": 237,
                        "replay_week": "2026-03-23 00:00:00",
                        "target_event_codes": ["demand_coming_in"],
                        "qualification": "persistent_bearish",
                    },
                ],
            }
        ]
    }

    summary = build_vsa_recovery_sequence_stage_seed(payload)

    assert summary.audit_only is True
    assert summary.production_safe is True
    assert summary.total_input_rows == 4
    assert summary.total_stage_seed_rows == 2
    assert summary.status_counts == {STATUS_REVIEW: 2}

    anchor_row = next(row for row in summary.rows if row.stage_seed_type == STAGE_SEED_ANCHOR)
    assert anchor_row.symbol == "LT.NS"
    assert anchor_row.replay_week == "2026-03-09"
    assert anchor_row.start_week == "2026-03-02"
    assert anchor_row.end_week == "2026-03-23"
    assert anchor_row.prior_weakness_codes == ("persistent_bearish", "increasing_supply")
    assert anchor_row.stopping_volume_codes == ("stopping_volume",)
    assert anchor_row.spring_shakeout_codes == ("shakeout",)
    assert anchor_row.follow_through_codes == ("demand_coming_in",)
    assert anchor_row.recovery_sequence_status == STATUS_REVIEW
    assert anchor_row.review_marker == STATUS_REVIEW
    assert "review-only recovery-sequence candidate" in anchor_row.audit_note


def test_stage_seed_keeps_diagnostic_hints_separate_from_production_codes() -> None:
    summary = build_vsa_recovery_sequence_stage_seed(
        {
            "rows": [
                {
                    "symbol": "TMPV.NS",
                    "replay_bar_index": 10,
                    "replay_week": "2026-03-02 00:00:00",
                    "target_event_codes": ["increasing_supply"],
                    "qualification": "persistent_bearish",
                },
                {
                    "symbol": "TMPV.NS",
                    "replay_bar_index": 11,
                    "replay_week": "2026-03-09 00:00:00",
                    "detector_diagnostics": [
                        "review_potential_stopping_volume",
                        "review_potential_spring_or_shakeout",
                    ],
                    "qualification": "persistent_bearish",
                },
                {
                    "symbol": "TMPV.NS",
                    "replay_bar_index": 12,
                    "replay_week": "2026-03-16 00:00:00",
                    "target_event_codes": ["demand_coming_in"],
                    "qualification": "persistent_bearish",
                },
            ]
        }
    )

    assert summary.total_stage_seed_rows == 1
    row = summary.rows[0]
    assert row.stage_seed_type == STAGE_SEED_DIAGNOSTIC
    assert row.diagnostic_hint_codes == (
        "review_potential_stopping_volume",
        "review_potential_spring_or_shakeout",
    )
    assert row.stopping_volume_codes == ()
    assert row.spring_shakeout_codes == ()
    assert row.follow_through_codes == ("demand_coming_in",)
    assert row.recovery_sequence_status == STATUS_NONE
    assert row.review_marker is None
    assert "Diagnostic hints" in row.audit_note


def test_stage_seed_can_ignore_diagnostic_hint_rows_in_production_only_mode() -> None:
    summary = build_vsa_recovery_sequence_stage_seed(
        {
            "rows": [
                {
                    "symbol": "TMPV.NS",
                    "replay_bar_index": 11,
                    "detector_diagnostics": ["review_potential_spring_or_shakeout"],
                }
            ]
        },
        include_diagnostic_hints=False,
    )

    assert summary.total_input_rows == 1
    assert summary.total_stage_seed_rows == 0
    assert summary.status_counts == {}


def test_stage_seed_blocks_when_seed_row_has_same_window_supply_blocker() -> None:
    summary = build_vsa_recovery_sequence_stage_seed(
        [
            {
                "symbol": "DRREDDY.NS",
                "replay_bar_index": 1,
                "target_event_codes": ["supply_coming_in"],
                "qualification": "persistent_bearish",
            },
            {
                "symbol": "DRREDDY.NS",
                "replay_bar_index": 2,
                "target_event_codes": ["stopping_volume", "structural_progression_weakening"],
                "qualification": "persistent_bearish",
            },
            {
                "symbol": "DRREDDY.NS",
                "replay_bar_index": 3,
                "target_event_codes": ["spring"],
                "qualification": "persistent_bearish",
            },
            {
                "symbol": "DRREDDY.NS",
                "replay_bar_index": 4,
                "target_event_codes": ["increasing_demand"],
                "qualification": "persistent_bearish",
            },
        ]
    )

    anchor_row = next(row for row in summary.rows if row.stage_seed_type == STAGE_SEED_ANCHOR)
    assert anchor_row.recovery_sequence_status == STATUS_BLOCKED
    assert anchor_row.same_window_evidence_codes == ("structural_progression_weakening",)
    assert anchor_row.review_marker is None
    assert "remained blocked" in anchor_row.audit_note


def test_stage_seed_waits_when_follow_through_uses_fallback_evidence() -> None:
    summary = build_vsa_recovery_sequence_stage_seed(
        [
            {
                "symbol": "GRASIM.NS",
                "replay_bar_index": 1,
                "target_event_codes": ["increasing_supply"],
                "qualification": "persistent_bearish",
            },
            {
                "symbol": "GRASIM.NS",
                "replay_bar_index": 2,
                "target_event_codes": ["stopping_volume"],
                "qualification": "persistent_bearish",
            },
            {
                "symbol": "GRASIM.NS",
                "replay_bar_index": 3,
                "target_event_codes": ["spring"],
                "qualification": "persistent_bearish",
            },
            {
                "symbol": "GRASIM.NS",
                "replay_bar_index": 4,
                "target_event_codes": ["demand_coming_in"],
                "qualification": "persistent_bearish",
                "used_fallback_evidence": True,
            },
        ]
    )

    anchor_row = next(row for row in summary.rows if row.stage_seed_type == STAGE_SEED_ANCHOR)
    assert anchor_row.recovery_sequence_status == STATUS_NEEDS_FOLLOW_THROUGH
    assert anchor_row.used_fallback_evidence is True
    assert anchor_row.follow_through_evidence_age == 0
    assert "needs fresh non-fallback demand follow-through" in anchor_row.audit_note


def test_stage_seed_serializes_to_json_and_csv() -> None:
    summary = build_vsa_recovery_sequence_stage_seed(
        {
            "rows": [
                {
                    "symbol": "AMBUJACEM.NS",
                    "replay_bar_index": 235,
                    "replay_week": "2026-03-02 00:00:00",
                    "target_event_codes": ["stopping_volume"],
                    "qualification": "persistent_bearish",
                },
                {
                    "symbol": "AMBUJACEM.NS",
                    "replay_bar_index": 236,
                    "replay_week": "2026-03-09 00:00:00",
                    "target_event_codes": ["shakeout"],
                    "qualification": "persistent_bearish",
                },
                {
                    "symbol": "AMBUJACEM.NS",
                    "replay_bar_index": 237,
                    "replay_week": "2026-03-16 00:00:00",
                    "target_event_codes": ["increasing_demand"],
                    "qualification": "persistent_bearish",
                },
            ]
        }
    )

    payload = summary.to_dict()
    assert json.dumps(payload)
    assert payload["rows"][0]["audit_only"] is True
    assert payload["rows"][0]["production_safe"] is True

    csv_text = render_vsa_recovery_sequence_stage_seed_csv(summary)
    assert "casebook_id,symbol,stage_seed_type,replay_week" in csv_text
    assert "AMBUJACEM.NS" in csv_text
    assert STATUS_REVIEW in csv_text
