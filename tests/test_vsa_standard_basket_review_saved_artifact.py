from __future__ import annotations

import csv
from io import StringIO

from vsa_audit_batch_review import (
    build_vsa_audit_batch_review,
    render_vsa_audit_batch_review_csv,
)
from vsa_audit_candidate_events import (
    CANDIDATE_ABSORPTION,
    CANDIDATE_CONTEXT_CONFLICT,
    CANDIDATE_EFFORT_GT_RESULT,
    CANDIDATE_HIGH_VOLUME_REVERSAL,
)


CSV_COLUMNS = [
    "symbol",
    "replay_week",
    "replay_bar_index",
    "candidate_family",
    "candidate_code",
    "priority",
    "direction",
    "qualification",
    "production_status",
    "target_event_codes",
    "scoring_event_codes",
    "source_diagnostics",
    "source_audit_flags",
    "reason",
]


STANDARD_BASKET_REVIEW_COUNTS = {
    "candidate_counts": {
        CANDIDATE_ABSORPTION: 33,
        CANDIDATE_EFFORT_GT_RESULT: 48,
        CANDIDATE_HIGH_VOLUME_REVERSAL: 38,
        CANDIDATE_CONTEXT_CONFLICT: 15,
    },
    "family_counts": {
        "absorption": 33,
        "effort_vs_result": 48,
        "high_volume_reversal": 38,
        "qualification_lifecycle": 15,
    },
    "high_priority_rows": 134,
    "medium_priority_rows": 0,
    "priority_counts": {"high": 134},
}


STANDARD_BASKET_REVIEW_FOCUS = [
    {
        "candidate_code": CANDIDATE_EFFORT_GT_RESULT,
        "candidate_family": "effort_vs_result",
        "high_priority_rows": 48,
        "medium_priority_rows": 0,
        "total_rows": 48,
        "symbols": [
            "ADANIPORTS.NS",
            "ASIANPAINT.NS",
            "AXISBANK.NS",
            "BAJFINANCE.NS",
            "BHARTIARTL.NS",
            "CIPLA.NS",
            "COALINDIA.NS",
            "DRREDDY.NS",
            "GRASIM.NS",
            "HINDUNILVR.NS",
            "ICICIBANK.NS",
            "JSWSTEEL.NS",
            "LT.NS",
            "M&M.NS",
            "MARUTI.NS",
            "NTPC.NS",
            "ONGC.NS",
            "RELIANCE.NS",
            "SBIN.NS",
            "SRF.NS",
            "SUNPHARMA.NS",
            "TCS.NS",
            "ULTRACEMCO.NS",
        ],
    },
    {
        "candidate_code": CANDIDATE_HIGH_VOLUME_REVERSAL,
        "candidate_family": "high_volume_reversal",
        "high_priority_rows": 38,
        "medium_priority_rows": 0,
        "total_rows": 38,
        "symbols": [
            "AXISBANK.NS",
            "BAJFINANCE.NS",
            "BHARTIARTL.NS",
            "DRREDDY.NS",
            "GRASIM.NS",
            "HDFCBANK.NS",
            "HINDUNILVR.NS",
            "ICICIBANK.NS",
            "INFY.NS",
            "JSWSTEEL.NS",
            "KOTAKBANK.NS",
            "LT.NS",
            "M&M.NS",
            "MARUTI.NS",
            "NTPC.NS",
            "ONGC.NS",
            "RELIANCE.NS",
            "SBIN.NS",
            "SUNPHARMA.NS",
            "TCS.NS",
            "ULTRACEMCO.NS",
        ],
    },
    {
        "candidate_code": CANDIDATE_ABSORPTION,
        "candidate_family": "absorption",
        "high_priority_rows": 33,
        "medium_priority_rows": 0,
        "total_rows": 33,
        "symbols": [
            "AXISBANK.NS",
            "BAJFINANCE.NS",
            "BHARTIARTL.NS",
            "DRREDDY.NS",
            "GRASIM.NS",
            "HDFCBANK.NS",
            "HINDUNILVR.NS",
            "ICICIBANK.NS",
            "INFY.NS",
            "JSWSTEEL.NS",
            "KOTAKBANK.NS",
            "LT.NS",
            "M&M.NS",
            "MARUTI.NS",
            "NTPC.NS",
            "ONGC.NS",
            "RELIANCE.NS",
            "SBIN.NS",
            "SUNPHARMA.NS",
            "TCS.NS",
        ],
    },
    {
        "candidate_code": CANDIDATE_CONTEXT_CONFLICT,
        "candidate_family": "qualification_lifecycle",
        "high_priority_rows": 15,
        "medium_priority_rows": 0,
        "total_rows": 15,
        "symbols": [
            "DRREDDY.NS",
            "GRASIM.NS",
            "HDFCBANK.NS",
            "ICICIBANK.NS",
            "LT.NS",
            "MARUTI.NS",
            "POWERGRID.NS",
            "SUNPHARMA.NS",
            "TATASTEEL.NS",
            "TCS.NS",
        ],
    },
]


def _candidate_row(
    *,
    symbol: str,
    replay_week: str,
    replay_bar_index: int,
    candidate_code: str,
    candidate_family: str,
    qualification: str,
    target_event_codes: list[str],
    scoring_event_codes: list[str],
    source_diagnostics: list[str] | None = None,
    source_audit_flags: list[str] | None = None,
) -> dict[str, object]:
    is_context = candidate_code == CANDIDATE_CONTEXT_CONFLICT
    return {
        "audit_only": True,
        "candidate_code": candidate_code,
        "candidate_family": candidate_family,
        "direction": "context_review" if is_context else "bullish_reversal_review",
        "priority": "high",
        "production_status": "not_confirmed_by_current_detector",
        "qualification": qualification,
        "reason": "saved standard-basket review row for manual chart review",
        "replay_bar_index": replay_bar_index,
        "replay_week": replay_week,
        "scoring_event_codes": scoring_event_codes,
        "source_audit_flags": source_audit_flags or [],
        "source_diagnostics": source_diagnostics or [],
        "symbol": symbol,
        "target_event_codes": target_event_codes,
    }


def _standard_basket_review_payload() -> dict[str, object]:
    return {
        "audit_only": True,
        **STANDARD_BASKET_REVIEW_COUNTS,
        "review_focus": STANDARD_BASKET_REVIEW_FOCUS,
        "rows": [
            _candidate_row(
                symbol="ADANIPORTS.NS",
                replay_week="2026-03-16 00:00:00",
                replay_bar_index=955,
                candidate_code=CANDIDATE_EFFORT_GT_RESULT,
                candidate_family="effort_vs_result",
                qualification="unqualified",
                target_event_codes=["hidden_supply"],
                scoring_event_codes=["hidden_supply"],
                source_diagnostics=["review_potential_effort_gt_result"],
            ),
            _candidate_row(
                symbol="AXISBANK.NS",
                replay_week="2026-03-30 00:00:00",
                replay_bar_index=1170,
                candidate_code=CANDIDATE_HIGH_VOLUME_REVERSAL,
                candidate_family="high_volume_reversal",
                qualification="persistent_bearish",
                target_event_codes=[],
                scoring_event_codes=["increasing_supply"],
                source_diagnostics=[
                    "review_high_volume_reversal_without_bullish_event"
                ],
            ),
            _candidate_row(
                symbol="BHARTIARTL.NS",
                replay_week="2026-03-02 00:00:00",
                replay_bar_index=233,
                candidate_code=CANDIDATE_ABSORPTION,
                candidate_family="absorption",
                qualification="unqualified",
                target_event_codes=[],
                scoring_event_codes=["increasing_supply"],
                source_diagnostics=["review_potential_absorption"],
            ),
            _candidate_row(
                symbol="LT.NS",
                replay_week="2026-04-06 00:00:00",
                replay_bar_index=238,
                candidate_code=CANDIDATE_CONTEXT_CONFLICT,
                candidate_family="qualification_lifecycle",
                qualification="persistent_bearish",
                target_event_codes=["increasing_demand", "demand_coming_in"],
                scoring_event_codes=["increasing_demand", "demand_coming_in"],
                source_audit_flags=["bullish_vsa_against_bearish_qualification"],
            ),
        ],
    }


def test_standard_basket_saved_review_top_level_counts_match_real_artifact() -> None:
    payload = _standard_basket_review_payload()

    assert payload["audit_only"] is True
    assert payload["candidate_counts"] == STANDARD_BASKET_REVIEW_COUNTS[
        "candidate_counts"
    ]
    assert payload["family_counts"] == STANDARD_BASKET_REVIEW_COUNTS["family_counts"]
    assert payload["priority_counts"] == {"high": 134}
    assert payload["high_priority_rows"] == 134
    assert payload["medium_priority_rows"] == 0
    assert sum(payload["candidate_counts"].values()) == payload["high_priority_rows"]


def test_standard_basket_saved_review_focus_preserves_family_ranking() -> None:
    focus = _standard_basket_review_payload()["review_focus"]

    assert [row["candidate_code"] for row in focus] == [
        CANDIDATE_EFFORT_GT_RESULT,
        CANDIDATE_HIGH_VOLUME_REVERSAL,
        CANDIDATE_ABSORPTION,
        CANDIDATE_CONTEXT_CONFLICT,
    ]
    assert [row["total_rows"] for row in focus] == [48, 38, 33, 15]
    assert sum(row["total_rows"] for row in focus) == 134
    assert all(row["medium_priority_rows"] == 0 for row in focus)
    assert "LT.NS" in focus[0]["symbols"]
    assert "SRF.NS" in focus[0]["symbols"]
    assert "POWERGRID.NS" in focus[-1]["symbols"]


def test_standard_basket_representative_rows_rebuild_high_priority_review() -> None:
    rows = _standard_basket_review_payload()["rows"]

    review = build_vsa_audit_batch_review(
        {"audit_only": True, "rows": rows},
        min_priority="high",
    ).to_dict()

    assert review["audit_only"] is True
    assert review["source_candidate_rows"] == 4
    assert review["total_review_rows"] == 4
    assert review["high_priority_rows"] == 4
    assert review["medium_priority_rows"] == 0
    assert review["candidate_counts"] == {
        CANDIDATE_ABSORPTION: 1,
        CANDIDATE_CONTEXT_CONFLICT: 1,
        CANDIDATE_EFFORT_GT_RESULT: 1,
        CANDIDATE_HIGH_VOLUME_REVERSAL: 1,
    }
    assert review["symbols_with_candidates"] == [
        "ADANIPORTS.NS",
        "AXISBANK.NS",
        "BHARTIARTL.NS",
        "LT.NS",
    ]
    assert all(row["audit_only"] is True for row in review["rows"])
    assert all(
        row["production_status"] == "not_confirmed_by_current_detector"
        for row in review["rows"]
    )


def test_standard_basket_saved_review_csv_preserves_manual_review_columns() -> None:
    payload = _standard_basket_review_payload()

    body = render_vsa_audit_batch_review_csv(payload)
    rows = list(csv.DictReader(StringIO(body)))

    assert len(rows) == 4
    assert list(rows[0]) == CSV_COLUMNS
    assert rows[0]["symbol"] == "ADANIPORTS.NS"
    assert rows[0]["candidate_code"] == CANDIDATE_EFFORT_GT_RESULT
    assert rows[0]["source_diagnostics"] == "review_potential_effort_gt_result"
    assert rows[-1]["symbol"] == "LT.NS"
    assert rows[-1]["source_audit_flags"] == (
        "bullish_vsa_against_bearish_qualification"
    )
    assert all(row["priority"] == "high" for row in rows)
