from __future__ import annotations

from typing import Any

from vsa_absorption_background_casebook import (
    CASE_ABSORPTION_BACKGROUND_NONE,
    RECOMMENDED_ACTION_NONE,
    SEED_TYPE_DIAGNOSTIC,
)
from vsa_absorption_background_validation_report import (
    build_vsa_absorption_background_validation_report,
)
from vsa_audit_batch_review import build_vsa_audit_batch_review
from vsa_audit_candidate_events import (
    CANDIDATE_ABSORPTION,
    CANDIDATE_EFFORT_GT_RESULT,
    CANDIDATE_HIGH_VOLUME_REVERSAL,
    CANDIDATE_STALE_EVIDENCE,
)


def _audit_row(**overrides: Any) -> dict[str, Any]:
    row = {
        "symbol": "LT.NS",
        "replay_week": "2026-03-02 00:00:00",
        "replay_bar_index": 233,
        "event_count": 0,
        "target_event_codes": [],
        "scoring_event_codes": [],
        "qualifying_event_codes": ["structural_progression_weakening"],
        "campaign_event_codes": [],
        "structural_event_codes": [],
        "vsa_event_codes": [],
        "qualification": "persistent_bearish",
        "actionable": False,
        "used_fallback_evidence": False,
        "scoring_evidence_age": None,
        "net_pressure": -0.7,
        "confidence": 0.442,
        "audit_flags": [],
        "detector_diagnostics": [],
        "notes": [],
    }
    row.update(overrides)
    return row


def _lt_2025_saved_audit_payload() -> dict[str, Any]:
    """Representative rows from Library file LT_2025-02-24.txt."""

    return {
        "symbols": ["LT.NS"],
        "timeframe": "1W",
        "start_week": "2025-02-24",
        "horizon_weeks": 20,
        "results": [
            {
                "symbol": "LT.NS",
                "timeframe": "1W",
                "start_week": "2025-02-24 00:00:00",
                "end_week": "2025-07-07 00:00:00",
                "replay_weeks": 20,
                "rows": [
                    _audit_row(
                        replay_week="2025-02-24 00:00:00",
                        replay_bar_index=180,
                        target_event_codes=[],
                        scoring_event_codes=["supply_coming_in", "increasing_supply"],
                        campaign_event_codes=["supply_coming_in", "increasing_supply"],
                        vsa_event_codes=[],
                        actionable=True,
                        used_fallback_evidence=True,
                        scoring_evidence_age=3,
                        net_pressure=-1,
                        confidence=0.68,
                        notes=[
                            "No event fired on the replay week.",
                            "Scanner is using earlier scoring evidence; inspect event age.",
                            "Scoring evidence is not on the replay week.",
                            "Actionable candidate in audit output; review manually before any production interpretation.",
                        ],
                    ),
                    _audit_row(
                        replay_week="2025-03-10 00:00:00",
                        replay_bar_index=182,
                        event_count=1,
                        target_event_codes=["supply_drying_up"],
                        scoring_event_codes=["supply_drying_up"],
                        campaign_event_codes=[
                            "supply_coming_in",
                            "increasing_supply",
                            "supply_drying_up",
                        ],
                        vsa_event_codes=["supply_drying_up"],
                        scoring_evidence_age=0,
                        net_pressure=-0.6,
                        confidence=0.52,
                    ),
                ],
                "audit_only": True,
            }
        ],
        "errors": {},
        "audit_only": True,
    }


def _lt_latest_saved_audit_payload() -> dict[str, Any]:
    """Representative rows from latest upload LT_New(1).txt."""

    return {
        "symbols": ["LT.NS"],
        "timeframe": "1W",
        "start_week": "2026-03-02",
        "end_week": None,
        "horizon_weeks": 8,
        "results": [
            {
                "symbol": "LT.NS",
                "timeframe": "1W",
                "start_week": "2026-03-02 00:00:00",
                "end_week": "2026-04-20 00:00:00",
                "replay_weeks": 8,
                "rows": [
                    _audit_row(
                        replay_bar_index=233,
                        replay_week="2026-03-02 00:00:00",
                        event_count=1,
                        target_event_codes=["increasing_supply"],
                        scoring_event_codes=["increasing_supply"],
                        campaign_event_codes=[
                            "supply_coming_in",
                            "buying_climax",
                            "upthrust",
                            "increasing_supply",
                        ],
                        vsa_event_codes=["increasing_supply"],
                        actionable=True,
                        used_fallback_evidence=False,
                        scoring_evidence_age=0,
                        audit_flags=["actionable_audit_row"],
                        detector_diagnostics=[
                            "review_potential_stopping_volume",
                            "review_potential_effort_gt_result",
                            "review_potential_absorption",
                            "review_high_volume_reversal_without_bullish_event",
                        ],
                        notes=[
                            "High-volume down bar closed off the low; review why Stopping Volume did not fire.",
                            "Very-high-volume effort produced muted downside result; review Effort vs Result calibration.",
                            "High-volume bar in bearish context closed off the low/midpoint; review possible absorption.",
                            "High-volume reversal candidate has no same-week bullish VSA event.",
                            "Actionable candidate in audit output; review manually before any production interpretation.",
                        ],
                    ),
                    _audit_row(
                        replay_bar_index=235,
                        replay_week="2026-03-16 00:00:00",
                        event_count=1,
                        target_event_codes=["structural_progression_weakening"],
                        scoring_event_codes=["increasing_supply"],
                        campaign_event_codes=[
                            "buying_climax",
                            "upthrust",
                            "increasing_supply",
                            "structural_progression_weakening",
                        ],
                        structural_event_codes=["structural_progression_weakening"],
                        vsa_event_codes=[],
                        actionable=True,
                        used_fallback_evidence=True,
                        scoring_evidence_age=2,
                        confidence=0.544,
                        audit_flags=[
                            "fallback_scoring_evidence",
                            "actionable_audit_row",
                            "structural_event_without_vsa_confirmation",
                        ],
                        detector_diagnostics=["review_potential_effort_gt_result"],
                        notes=[
                            "Scoring evidence is not on the replay week.",
                            "Structural event fired without same-week non-structural VSA confirmation.",
                            "Very-high-volume effort produced muted downside result; review Effort vs Result calibration.",
                            "Actionable candidate in audit output; review manually before any production interpretation.",
                        ],
                    ),
                    _audit_row(
                        replay_bar_index=236,
                        replay_week="2026-03-23 00:00:00",
                        event_count=1,
                        target_event_codes=["demand_coming_in"],
                        scoring_event_codes=["demand_coming_in"],
                        campaign_event_codes=[
                            "buying_climax",
                            "upthrust",
                            "increasing_supply",
                            "demand_coming_in",
                        ],
                        vsa_event_codes=["demand_coming_in"],
                        used_fallback_evidence=False,
                        scoring_evidence_age=0,
                        net_pressure=0,
                        confidence=0.264,
                        audit_flags=["bullish_vsa_against_bearish_qualification"],
                        detector_diagnostics=[
                            "review_potential_effort_gt_result",
                            "review_potential_spring_or_shakeout",
                        ],
                        notes=[
                            "Bullish VSA evidence appeared while qualification remained bearish.",
                            "Very-high-volume effort produced muted downside result; review Effort vs Result calibration.",
                            "Bar interacted with prior support and recovered; review Spring/Shakeout criteria.",
                        ],
                    ),
                    _audit_row(
                        replay_bar_index=238,
                        replay_week="2026-04-06 00:00:00",
                        event_count=2,
                        target_event_codes=["increasing_demand", "demand_coming_in"],
                        scoring_event_codes=["increasing_demand", "demand_coming_in"],
                        campaign_event_codes=[
                            "increasing_supply",
                            "increasing_demand",
                            "demand_coming_in",
                        ],
                        vsa_event_codes=["increasing_demand", "demand_coming_in"],
                        used_fallback_evidence=False,
                        scoring_evidence_age=0,
                        net_pressure=0,
                        confidence=0.264,
                        audit_flags=["bullish_vsa_against_bearish_qualification"],
                        detector_diagnostics=["review_potential_effort_gt_result"],
                    ),
                    _audit_row(
                        replay_bar_index=239,
                        replay_week="2026-04-13 00:00:00",
                        event_count=0,
                        target_event_codes=[],
                        scoring_event_codes=["increasing_supply"],
                        campaign_event_codes=["increasing_supply"],
                        vsa_event_codes=[],
                        used_fallback_evidence=True,
                        scoring_evidence_age=6,
                        confidence=0.584,
                        audit_flags=[
                            "no_target_event",
                            "fallback_scoring_evidence",
                            "stale_scoring_evidence",
                        ],
                        detector_diagnostics=[
                            "review_potential_absorption",
                            "review_high_volume_reversal_without_bullish_event",
                        ],
                        notes=[
                            "No event fired on the replay week.",
                            "Scanner is using earlier scoring evidence; inspect event age.",
                            "Scoring evidence is not on the replay week.",
                            "Scoring evidence is older than the maximum actionable VSA age.",
                            "High-volume bar in bearish context closed off the low/midpoint; review possible absorption.",
                            "High-volume reversal candidate has no same-week bullish VSA event.",
                        ],
                    ),
                ],
                "audit_only": True,
            }
        ],
        "errors": {},
        "audit_only": True,
    }


def _candidate_row(**overrides: Any) -> dict[str, Any]:
    row = {
        "audit_only": True,
        "candidate_code": CANDIDATE_EFFORT_GT_RESULT,
        "candidate_family": "effort_vs_result",
        "direction": "bullish_reversal_review",
        "priority": "high",
        "production_status": "not_confirmed_by_current_detector",
        "qualification": "persistent_bearish",
        "reason": "Audit diagnostics suggest very-high-volume effort with muted result; review as an Effort-vs-Result candidate before changing production rules.",
        "replay_bar_index": 233,
        "replay_week": "2026-03-02 00:00:00",
        "scoring_event_codes": ["increasing_supply"],
        "source_audit_flags": [],
        "source_diagnostics": ["review_potential_effort_gt_result"],
        "symbol": "LT.NS",
        "target_event_codes": ["increasing_supply"],
    }
    row.update(overrides)
    return row


def _lt_candidate_events_high_payload() -> dict[str, Any]:
    """Summary shape from Library file LT_candidate_events_high.json."""

    return {
        "audit_only": True,
        "candidate_counts": {
            CANDIDATE_ABSORPTION: 2,
            CANDIDATE_EFFORT_GT_RESULT: 4,
            CANDIDATE_HIGH_VOLUME_REVERSAL: 2,
            "audit_qualification_conflict_candidate": 2,
        },
        "family_counts": {
            "absorption": 2,
            "effort_vs_result": 4,
            "high_volume_reversal": 2,
            "qualification_lifecycle": 2,
        },
        "priority_counts": {"high": 10},
        "rows": [
            _candidate_row(
                candidate_code=CANDIDATE_EFFORT_GT_RESULT,
                candidate_family="effort_vs_result",
                replay_bar_index=233,
                source_diagnostics=["review_potential_effort_gt_result"],
            ),
            _candidate_row(
                candidate_code=CANDIDATE_ABSORPTION,
                candidate_family="absorption",
                replay_bar_index=233,
                source_diagnostics=["review_potential_absorption"],
            ),
            _candidate_row(
                candidate_code=CANDIDATE_HIGH_VOLUME_REVERSAL,
                candidate_family="high_volume_reversal",
                replay_bar_index=233,
                source_diagnostics=["review_high_volume_reversal_without_bullish_event"],
            ),
            _candidate_row(
                candidate_code="audit_qualification_conflict_candidate",
                candidate_family="qualification_lifecycle",
                direction="context_review",
                replay_bar_index=236,
                replay_week="2026-03-23 00:00:00",
                source_audit_flags=["bullish_vsa_against_bearish_qualification"],
                source_diagnostics=[],
                target_event_codes=["demand_coming_in"],
                scoring_event_codes=["demand_coming_in"],
                reason="Audit flags show current VSA evidence conflicting with active qualification; review lifecycle or invalidation behavior.",
            ),
            _candidate_row(
                candidate_code=CANDIDATE_ABSORPTION,
                candidate_family="absorption",
                replay_bar_index=239,
                replay_week="2026-04-13 00:00:00",
                source_diagnostics=["review_potential_absorption"],
                target_event_codes=[],
                scoring_event_codes=["increasing_supply"],
            ),
            _candidate_row(
                candidate_code=CANDIDATE_HIGH_VOLUME_REVERSAL,
                candidate_family="high_volume_reversal",
                replay_bar_index=239,
                replay_week="2026-04-13 00:00:00",
                source_diagnostics=["review_high_volume_reversal_without_bullish_event"],
                target_event_codes=[],
                scoring_event_codes=["increasing_supply"],
            ),
        ],
        "symbol_counts": {"LT.NS": 10},
    }


def test_lt_2025_and_latest_saved_audit_shapes_remain_audit_only() -> None:
    lt_2025 = _lt_2025_saved_audit_payload()
    lt_latest = _lt_latest_saved_audit_payload()

    assert lt_2025["audit_only"] is True
    assert lt_2025["results"][0]["rows"][0]["replay_week"] == "2025-02-24 00:00:00"
    assert lt_2025["results"][0]["rows"][0]["target_event_codes"] == []
    assert lt_2025["results"][0]["rows"][0]["scoring_event_codes"] == [
        "supply_coming_in",
        "increasing_supply",
    ]
    assert lt_2025["results"][0]["rows"][0]["used_fallback_evidence"] is True

    assert lt_latest["audit_only"] is True
    assert lt_latest["start_week"] == "2026-03-02"
    assert lt_latest["horizon_weeks"] == 8
    rows = lt_latest["results"][0]["rows"]
    assert [row["replay_bar_index"] for row in rows] == [233, 235, 236, 238, 239]

    first_row = rows[0]
    assert first_row["replay_week"] == "2026-03-02 00:00:00"
    assert first_row["target_event_codes"] == ["increasing_supply"]
    assert first_row["vsa_event_codes"] == ["increasing_supply"]
    assert first_row["audit_flags"] == ["actionable_audit_row"]
    assert first_row["detector_diagnostics"] == [
        "review_potential_stopping_volume",
        "review_potential_effort_gt_result",
        "review_potential_absorption",
        "review_high_volume_reversal_without_bullish_event",
    ]

    structural_row = rows[1]
    assert structural_row["target_event_codes"] == ["structural_progression_weakening"]
    assert structural_row["structural_event_codes"] == ["structural_progression_weakening"]
    assert structural_row["vsa_event_codes"] == []
    assert "structural_event_without_vsa_confirmation" in structural_row["audit_flags"]

    demand_row = rows[2]
    assert demand_row["target_event_codes"] == ["demand_coming_in"]
    assert demand_row["vsa_event_codes"] == ["demand_coming_in"]
    assert demand_row["audit_flags"] == ["bullish_vsa_against_bearish_qualification"]
    assert demand_row["qualification"] == "persistent_bearish"

    stale_absorption_row = rows[-1]
    assert stale_absorption_row["target_event_codes"] == []
    assert stale_absorption_row["used_fallback_evidence"] is True
    assert stale_absorption_row["scoring_evidence_age"] == 6
    assert stale_absorption_row["audit_flags"] == [
        "no_target_event",
        "fallback_scoring_evidence",
        "stale_scoring_evidence",
    ]
    assert stale_absorption_row["detector_diagnostics"] == [
        "review_potential_absorption",
        "review_high_volume_reversal_without_bullish_event",
    ]


def test_lt_candidate_events_high_saved_output_feeds_batch_review_contract() -> None:
    candidate_summary = _lt_candidate_events_high_payload()

    review = build_vsa_audit_batch_review(
        candidate_summary,
        min_priority="high",
    ).to_dict()

    assert candidate_summary["audit_only"] is True
    assert candidate_summary["candidate_counts"] == {
        CANDIDATE_ABSORPTION: 2,
        CANDIDATE_EFFORT_GT_RESULT: 4,
        CANDIDATE_HIGH_VOLUME_REVERSAL: 2,
        "audit_qualification_conflict_candidate": 2,
    }
    assert candidate_summary["priority_counts"] == {"high": 10}
    assert all(row["audit_only"] is True for row in candidate_summary["rows"])
    assert all(
        row["production_status"] == "not_confirmed_by_current_detector"
        for row in candidate_summary["rows"]
    )

    assert review["audit_only"] is True
    assert review["source_candidate_rows"] == 6
    assert review["total_review_rows"] == 6
    assert review["high_priority_rows"] == 6
    assert review["medium_priority_rows"] == 0
    assert review["candidate_counts"] == {
        CANDIDATE_ABSORPTION: 2,
        CANDIDATE_EFFORT_GT_RESULT: 1,
        CANDIDATE_HIGH_VOLUME_REVERSAL: 2,
        "audit_qualification_conflict_candidate": 1,
    }
    assert review["symbol_counts"] == {"LT.NS": 6}
    assert review["top_review_symbols"][0]["symbol"] == "LT.NS"
    assert CANDIDATE_STALE_EVIDENCE not in {
        row["candidate_code"] for row in review["rows"]
    }


def test_latest_lt_diagnostic_absorption_stays_review_context_without_production_absorption() -> None:
    rows = _lt_latest_saved_audit_payload()["results"][0]["rows"]
    payload = {
        "audit_only": True,
        "results": [
            {
                "symbol": "LT.NS",
                "rows": [rows[0], rows[2]],
            }
        ],
    }

    report = build_vsa_absorption_background_validation_report(
        payload,
        lookback_rows=1,
        lookahead_rows=1,
    ).to_dict()

    assert report["audit_only"] is True
    assert report["production_safe"] is True
    assert report["total_input_rows"] == 2
    assert report["total_casebook_rows"] == 1
    assert report["status_counts"] == {"none": 1}
    assert report["production_only"]["total_casebook_rows"] == 0
    assert report["production_only"]["status_counts"] == {}

    row = report["rows"][0]
    assert row["symbol"] == "LT.NS"
    assert row["replay_week"] == "2026-03-02"
    assert row["seed_type"] == SEED_TYPE_DIAGNOSTIC
    assert row["case_type"] == CASE_ABSORPTION_BACKGROUND_NONE
    assert row["review_marker"] is None
    assert row["recommended_casebook_action"] == RECOMMENDED_ACTION_NONE
    assert row["diagnostic_hint_codes"] == ["review_potential_absorption"]
    assert row["absorption_codes"] == []
    assert row["follow_through_codes"] == ["demand_coming_in"]
    assert "increasing_supply" in row["blocker_codes"]
    assert set(row["blocker_codes"]) == {
        "increasing_supply",
        "structural_progression_weakening",
        "supply_coming_in",
    }
    assert "not yet a confirmed bullish reversal" in row["plain_english"]
