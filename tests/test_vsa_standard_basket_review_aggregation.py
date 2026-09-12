from __future__ import annotations

import csv
from io import StringIO
from typing import Any

from vsa_audit_batch_review import (
    build_vsa_audit_batch_review,
    render_vsa_audit_batch_review_csv,
)
from vsa_audit_candidate_events import (
    CANDIDATE_ABSORPTION,
    CANDIDATE_CONTEXT_CONFLICT,
    CANDIDATE_EFFORT_GT_RESULT,
    CANDIDATE_HIGH_VOLUME_REVERSAL,
    CANDIDATE_SPRING_OR_SHAKEOUT,
    CANDIDATE_STALE_EVIDENCE,
    CANDIDATE_STOPPING_VOLUME,
)
from vsa_standard_audit_basket import STANDARD_VSA_AUDIT_SYMBOLS


def _row(symbol: str, index: int, **overrides: Any) -> dict[str, Any]:
    row = {
        "symbol": symbol,
        "replay_week": f"2026-03-{2 + index:02d} 00:00:00",
        "replay_bar_index": 300 + index,
        "target_event_codes": [],
        "scoring_event_codes": [],
        "qualification": "neutral",
        "audit_flags": [],
        "detector_diagnostics": [],
    }
    row.update(overrides)
    return row


def _standard_basket_saved_output_payload() -> dict[str, Any]:
    """Build a saved-output-shaped standard basket without loading market data."""

    symbols = STANDARD_VSA_AUDIT_SYMBOLS
    rows = [
        _row(
            symbols[0],
            0,
            target_event_codes=["increasing_supply"],
            scoring_event_codes=["increasing_supply"],
            qualification="persistent_bearish",
            detector_diagnostics=[
                "review_potential_effort_gt_result",
                "review_potential_absorption",
            ],
        ),
        _row(
            symbols[1],
            1,
            scoring_event_codes=["increasing_supply"],
            qualification="persistent_bearish",
            detector_diagnostics=["review_high_volume_reversal_without_bullish_event"],
        ),
        _row(
            symbols[2],
            2,
            target_event_codes=["demand_coming_in"],
            scoring_event_codes=["demand_coming_in"],
            qualification="persistent_bearish",
            audit_flags=["bullish_vsa_against_bearish_qualification"],
        ),
        _row(
            symbols[3],
            3,
            target_event_codes=["supply_coming_in"],
            scoring_event_codes=["supply_coming_in"],
            qualification="persistent_bullish",
            audit_flags=["bearish_vsa_against_bullish_qualification"],
        ),
        _row(
            symbols[4],
            4,
            qualification="persistent_bearish",
            detector_diagnostics=["review_potential_stopping_volume"],
        ),
        _row(
            symbols[5],
            5,
            qualification="persistent_bearish",
            detector_diagnostics=["review_potential_spring_or_shakeout"],
        ),
        _row(
            symbols[6],
            6,
            scoring_event_codes=["increasing_supply"],
            qualification="persistent_bearish",
            audit_flags=["stale_scoring_evidence"],
        ),
        _row(
            symbols[7],
            7,
            target_event_codes=["structural_progression_weakening"],
            qualification="persistent_bearish",
            audit_flags=["structural_event_without_vsa_confirmation"],
        ),
        _row(
            symbols[8],
            8,
            target_event_codes=["effort_gt_result"],
            scoring_event_codes=["effort_gt_result"],
            qualification="persistent_bearish",
            detector_diagnostics=["review_potential_effort_gt_result"],
        ),
    ]
    rows.extend(_row(symbol, index) for index, symbol in enumerate(symbols[9:], start=9))

    return {
        "audit_only": True,
        "symbols": list(symbols),
        "timeframe": "1W",
        "start_week": "2026-03-02",
        "horizon_weeks": 8,
        "results": [
            {
                "symbol": row["symbol"],
                "rows": [row],
                "audit_only": True,
            }
            for row in rows
        ],
    }


def test_standard_basket_saved_output_aggregation_keeps_basket_context() -> None:
    payload = _standard_basket_saved_output_payload()

    review = build_vsa_audit_batch_review(payload).to_dict()

    assert payload["audit_only"] is True
    assert len(payload["symbols"]) == 30
    assert len(payload["results"]) == 30
    assert {result["symbol"] for result in payload["results"]} == set(STANDARD_VSA_AUDIT_SYMBOLS)

    assert review["audit_only"] is True
    assert review["source_candidate_rows"] == 9
    assert review["total_review_rows"] == 9
    assert review["high_priority_rows"] == 5
    assert review["medium_priority_rows"] == 4
    assert review["candidate_counts"] == {
        CANDIDATE_EFFORT_GT_RESULT: 1,
        CANDIDATE_ABSORPTION: 1,
        CANDIDATE_HIGH_VOLUME_REVERSAL: 1,
        CANDIDATE_CONTEXT_CONFLICT: 2,
        CANDIDATE_STOPPING_VOLUME: 1,
        CANDIDATE_SPRING_OR_SHAKEOUT: 1,
        CANDIDATE_STALE_EVIDENCE: 2,
    }
    assert review["priority_counts"] == {"high": 5, "medium": 4}
    assert review["top_review_symbols"][0]["symbol"] == STANDARD_VSA_AUDIT_SYMBOLS[0]
    assert review["top_review_symbols"][0]["high_priority_rows"] == 2
    assert review["symbols_with_candidates"] == sorted(STANDARD_VSA_AUDIT_SYMBOLS[:8])
    assert STANDARD_VSA_AUDIT_SYMBOLS[8] not in review["symbol_counts"]


def test_standard_basket_high_priority_review_filters_medium_and_clean_symbols() -> None:
    payload = _standard_basket_saved_output_payload()

    review = build_vsa_audit_batch_review(payload, min_priority="high").to_dict()

    assert review["source_candidate_rows"] == 9
    assert review["total_review_rows"] == 5
    assert review["high_priority_rows"] == 5
    assert review["medium_priority_rows"] == 0
    assert review["candidate_counts"] == {
        CANDIDATE_EFFORT_GT_RESULT: 1,
        CANDIDATE_ABSORPTION: 1,
        CANDIDATE_HIGH_VOLUME_REVERSAL: 1,
        CANDIDATE_CONTEXT_CONFLICT: 2,
    }
    assert review["symbols_with_candidates"] == sorted(STANDARD_VSA_AUDIT_SYMBOLS[:4])
    assert {row["priority"] for row in review["rows"]} == {"high"}
    assert all(row["audit_only"] is True for row in review["rows"])
    assert all(
        row["production_status"] == "not_confirmed_by_current_detector"
        for row in review["rows"]
    )


def test_standard_basket_review_csv_preserves_manual_review_columns() -> None:
    payload = _standard_basket_saved_output_payload()
    review = build_vsa_audit_batch_review(payload, min_priority="high")

    csv_rows = list(csv.DictReader(StringIO(render_vsa_audit_batch_review_csv(review))))

    assert len(csv_rows) == 5
    assert {
        "symbol",
        "replay_week",
        "candidate_family",
        "candidate_code",
        "priority",
        "production_status",
        "target_event_codes",
        "scoring_event_codes",
        "source_diagnostics",
        "source_audit_flags",
        "reason",
    }.issubset(csv_rows[0].keys())
    assert {row["priority"] for row in csv_rows} == {"high"}
    assert CANDIDATE_STOPPING_VOLUME not in {row["candidate_code"] for row in csv_rows}
    assert CANDIDATE_STALE_EVIDENCE not in {row["candidate_code"] for row in csv_rows}
