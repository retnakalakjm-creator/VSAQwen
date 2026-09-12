from __future__ import annotations

from typing import Any

from vsa_audit_candidate_events import (
    CANDIDATE_ABSORPTION,
    CANDIDATE_EFFORT_GT_RESULT,
    CANDIDATE_FAMILIES,
    CANDIDATE_HIGH_VOLUME_REVERSAL,
    PRODUCTION_EVENTS_BY_CANDIDATE,
)

PRODUCTION_EFFORT_GT_RESULT = "effort_gt_result"
FAMILY_EFFORT_VS_RESULT = "effort_vs_result"
DIAGNOSTIC_POTENTIAL_EFFORT_GT_RESULT = "review_potential_effort_gt_result"

VERY_HIGH_VOLUME_RATIO_MIN = 2.0
MUTED_RESULT_RATIO_MAX = 0.45
OFF_LOW_CLOSE_POSITION_MIN = 0.45

SOURCE_BUCKET_CLEAN = "clean_candidate"
SOURCE_BUCKET_CLUSTER = "overlapping_candidate_cluster"
SOURCE_BUCKET_CONTRADICTORY = "contradictory_production_evidence"
SOURCE_BUCKET_NOISY = "likely_noisy_diagnostic"

REVIEW_FOCUS_BY_SOURCE_BUCKET = {
    SOURCE_BUCKET_CLEAN: "minimum_detector_threshold_review",
    SOURCE_BUCKET_CLUSTER: "cluster_context_before_single_detector_change",
    SOURCE_BUCKET_CONTRADICTORY: "production_gate_conflict_review",
    SOURCE_BUCKET_NOISY: "continuation_or_redundant_signal_review",
}

MINIMUM_REQUIRED_EVIDENCE = (
    "audit_effort_vs_result_candidate",
    "not_already_confirmed_by_current_effort_code",
    "very_high_volume_effort",
    "muted_price_result",
    "close_off_the_low",
    "future_bullish_follow_through",
    "no_future_opposing_supply",
)


def _row(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "symbol": "LT.NS",
        "replay_week": "2026-03-02 00:00:00",
        "replay_bar_index": 233,
        "audit_only": True,
        "event_code": CANDIDATE_EFFORT_GT_RESULT,
        "event_family": FAMILY_EFFORT_VS_RESULT,
        "source_bucket": SOURCE_BUCKET_CLEAN,
        "source_diagnostics": [DIAGNOSTIC_POTENTIAL_EFFORT_GT_RESULT],
        "source_audit_flags": [],
        "source_target_event_codes": [],
        "source_scoring_event_codes": ["increasing_supply"],
        "qualification": "persistent_bearish",
        "volume_ratio": 2.4,
        "result_ratio": 0.30,
        "close_position": 0.58,
        "future_rows_checked": 2,
        "future_supporting_event_codes": ["increasing_demand"],
        "future_opposing_event_codes": [],
    }
    row.update(overrides)
    return row


def _observed_current_codes(row: dict[str, Any]) -> frozenset[str]:
    return frozenset(row.get("source_target_event_codes") or ()) | frozenset(
        row.get("source_scoring_event_codes") or ()
    )


def _effort_vs_result_detector_design_characterization(
    row: dict[str, Any],
) -> dict[str, Any]:
    """Executable detector-design spec for future production work.

    The characterization is intentionally test-local and audit-only. It defines
    the minimum evidence that a future production detector PR should consider,
    without activating that production detector here.
    """

    production_codes = PRODUCTION_EVENTS_BY_CANDIDATE[CANDIDATE_EFFORT_GT_RESULT]
    observed_codes = _observed_current_codes(row)

    is_effort_candidate = (
        row.get("event_code") == CANDIDATE_EFFORT_GT_RESULT
        and row.get("event_family") == FAMILY_EFFORT_VS_RESULT
    )
    already_confirmed = bool(production_codes & observed_codes)
    has_diagnostic_source = DIAGNOSTIC_POTENTIAL_EFFORT_GT_RESULT in (
        row.get("source_diagnostics") or ()
    )
    has_very_high_volume = (
        float(row.get("volume_ratio") or 0.0) >= VERY_HIGH_VOLUME_RATIO_MIN
    )
    has_muted_result = (
        float(row.get("result_ratio") or 1.0) <= MUTED_RESULT_RATIO_MAX
    )
    closes_off_low = (
        float(row.get("close_position") or 0.0) >= OFF_LOW_CLOSE_POSITION_MIN
    )
    has_follow_through = (
        int(row.get("future_rows_checked") or 0) > 0
        and bool(row.get("future_supporting_event_codes") or ())
    )
    has_future_supply_conflict = bool(row.get("future_opposing_event_codes") or ())

    minimum_evidence = {
        "audit_effort_vs_result_candidate": bool(row.get("audit_only"))
        and is_effort_candidate
        and has_diagnostic_source,
        "not_already_confirmed_by_current_effort_code": not already_confirmed,
        "very_high_volume_effort": has_very_high_volume,
        "muted_price_result": has_muted_result,
        "close_off_the_low": closes_off_low,
        "future_bullish_follow_through": has_follow_through,
        "no_future_opposing_supply": not has_future_supply_conflict,
    }

    return {
        "production_event_code": PRODUCTION_EFFORT_GT_RESULT,
        "candidate_code": CANDIDATE_EFFORT_GT_RESULT,
        "candidate_family": CANDIDATE_FAMILIES[CANDIDATE_EFFORT_GT_RESULT],
        "already_confirmed_by_current_effort_code": already_confirmed,
        "minimum_evidence": minimum_evidence,
        "eligible_for_detector_design_review": all(minimum_evidence.values()),
        "eligible_for_production_activation": False,
        "requires_separate_detector_pr": True,
        "review_focus": REVIEW_FOCUS_BY_SOURCE_BUCKET[row["source_bucket"]],
    }


def test_effort_vs_result_characterization_starts_from_audit_candidate_boundary() -> None:
    production_codes = PRODUCTION_EVENTS_BY_CANDIDATE[CANDIDATE_EFFORT_GT_RESULT]

    assert CANDIDATE_EFFORT_GT_RESULT != PRODUCTION_EFFORT_GT_RESULT
    assert CANDIDATE_FAMILIES[CANDIDATE_EFFORT_GT_RESULT] == (
        FAMILY_EFFORT_VS_RESULT
    )
    assert production_codes == frozenset({PRODUCTION_EFFORT_GT_RESULT})
    assert PRODUCTION_EVENTS_BY_CANDIDATE[CANDIDATE_ABSORPTION] == frozenset(
        {"absorption"}
    )
    assert PRODUCTION_EVENTS_BY_CANDIDATE[CANDIDATE_HIGH_VOLUME_REVERSAL] != (
        production_codes
    )


def test_design_review_requires_high_effort_muted_result_and_follow_through() -> None:
    valid = _row()
    low_volume = _row(volume_ratio=1.99)
    strong_result = _row(result_ratio=0.46)
    weak_close = _row(close_position=0.44)
    missing_follow_through = _row(future_supporting_event_codes=[])
    opposing_future_supply = _row(future_opposing_event_codes=["upthrust"])

    assert _effort_vs_result_detector_design_characterization(valid)[
        "eligible_for_detector_design_review"
    ] is True

    rejected_rows = [
        low_volume,
        strong_result,
        weak_close,
        missing_follow_through,
        opposing_future_supply,
    ]
    assert all(
        _effort_vs_result_detector_design_characterization(row)[
            "eligible_for_detector_design_review"
        ]
        is False
        for row in rejected_rows
    )


def test_design_review_rejects_non_effort_or_already_confirmed_rows() -> None:
    wrong_candidate = _row(event_code=CANDIDATE_ABSORPTION, event_family="absorption")
    missing_diagnostic = _row(source_diagnostics=[])
    non_audit_row = _row(audit_only=False)
    already_confirmed = _row(
        source_target_event_codes=[PRODUCTION_EFFORT_GT_RESULT],
        source_scoring_event_codes=[PRODUCTION_EFFORT_GT_RESULT],
    )

    rejected_rows = [
        wrong_candidate,
        missing_diagnostic,
        non_audit_row,
        already_confirmed,
    ]

    assert all(
        _effort_vs_result_detector_design_characterization(row)[
            "eligible_for_detector_design_review"
        ]
        is False
        for row in rejected_rows
    )
    assert _effort_vs_result_detector_design_characterization(already_confirmed)[
        "already_confirmed_by_current_effort_code"
    ] is True


def test_characterization_preserves_review_focus_without_activation() -> None:
    rows = [
        _row(symbol="CIPLA.NS", source_bucket=SOURCE_BUCKET_CLEAN),
        _row(symbol="BAJFINANCE.NS", source_bucket=SOURCE_BUCKET_CLUSTER),
        _row(symbol="GRASIM.NS", source_bucket=SOURCE_BUCKET_CONTRADICTORY),
        _row(symbol="COALINDIA.NS", source_bucket=SOURCE_BUCKET_NOISY),
    ]

    decisions = {
        row["symbol"]: _effort_vs_result_detector_design_characterization(row)
        for row in rows
    }

    assert decisions["CIPLA.NS"]["review_focus"] == (
        "minimum_detector_threshold_review"
    )
    assert decisions["BAJFINANCE.NS"]["review_focus"] == (
        "cluster_context_before_single_detector_change"
    )
    assert decisions["GRASIM.NS"]["review_focus"] == (
        "production_gate_conflict_review"
    )
    assert decisions["COALINDIA.NS"]["review_focus"] == (
        "continuation_or_redundant_signal_review"
    )

    assert all(
        tuple(decision["minimum_evidence"]) == MINIMUM_REQUIRED_EVIDENCE
        for decision in decisions.values()
    )
    assert all(
        decision["eligible_for_production_activation"] is False
        for decision in decisions.values()
    )
    assert all(
        decision["requires_separate_detector_pr"] is True
        for decision in decisions.values()
    )
