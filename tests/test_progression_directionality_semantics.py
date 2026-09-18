from __future__ import annotations

import json

import pandas as pd

from audit.genuine_daily_sequence_case import (
    ProductionWeeklySourceFingerprint,
)
from audit.progression_directionality_semantics import (
    PROGRESSION_DIRECTIONALITY_AUDIT_ID,
    ProgressionDirectionalityFailure,
    summarize_progression_directionality,
    write_progression_directionality_audit,
)
from audit.weekly_structural_progression_audit import (
    WeeklyStructuralProgressionAudit,
    WeeklyStructuralProgressionEventRow,
)
from background.qualification import PatternQualification


def _source(symbol: str) -> ProductionWeeklySourceFingerprint:
    return ProductionWeeklySourceFingerprint(
        symbol=symbol,
        row_count=10,
        first_week="2026-01-02T00:00:00",
        last_week="2026-03-06T00:00:00",
        sha256=f"sha256:{symbol}",
    )


def _row(
    *,
    bar: int,
    direction: str,
    trend: str,
    pattern: str,
) -> WeeklyStructuralProgressionEventRow:
    code = (
        "structural_progression_improving"
        if direction == "bullish"
        else "structural_progression_weakening"
    )
    return WeeklyStructuralProgressionEventRow(
        event_bar_index=bar,
        event_week=f"W{bar}",
        event_code=code,
        event_direction=direction,
        event_strength=0.5,
        progression_difference=0.1 if direction == "bullish" else -0.1,
        trend_direction=trend,
        trend_state="healthy",
        structural_pattern=pattern,
        structural_swing_count=6,
        latest_swing_type="high",
        latest_swing_label=None,
        latest_swing_pivot_index=bar - 2,
        latest_swing_confirmation_index=bar,
        latest_swing_week=f"W{bar}",
        latest_swing_grade="minor",
        latest_swing_professional_overall=0.6,
        previous_event_code=None,
        previous_event_bar_index=None,
        bars_since_previous_event=None,
        previous_same_direction_bar_index=None,
        bars_since_previous_same_direction=None,
        meets_min_same_direction_spacing=None,
        qualification_after_event=PatternQualification.UNQUALIFIED,
        qualification_actionable_after_event=False,
        event_used_in_qualification=False,
    )


def _audit(symbol: str, rows) -> WeeklyStructuralProgressionAudit:
    rows = tuple(rows)
    bullish = tuple(row for row in rows if row.event_direction == "bullish")
    bearish = tuple(row for row in rows if row.event_direction == "bearish")
    return WeeklyStructuralProgressionAudit(
        symbol=symbol,
        audit_id="fixture",
        source_fingerprint=_source(symbol),
        candidate_count=10,
        event_count=len(rows),
        improving_event_count=len(bullish),
        weakening_event_count=len(bearish),
        first_improving_week=None if not bullish else bullish[0].event_week,
        last_improving_week=None if not bullish else bullish[-1].event_week,
        first_weakening_week=None if not bearish else bearish[0].event_week,
        last_weakening_week=None if not bearish else bearish[-1].event_week,
        first_persistent_bullish_week=None,
        first_persistent_bearish_week=None,
        rows=rows,
    )


def test_summary_separates_alignment_from_event_direction() -> None:
    audit = summarize_progression_directionality(
        basket_name="fixture",
        requested_symbols=("AAA.NS",),
        audits=(
            _audit(
                "AAA.NS",
                (
                    _row(
                        bar=10,
                        direction="bullish",
                        trend="up",
                        pattern="improving",
                    ),
                    _row(
                        bar=20,
                        direction="bearish",
                        trend="up",
                        pattern="improving",
                    ),
                    _row(
                        bar=30,
                        direction="bearish",
                        trend="down",
                        pattern="breaking",
                    ),
                ),
            ),
        ),
    )

    assert audit.audit_id == PROGRESSION_DIRECTIONALITY_AUDIT_ID
    assert audit.event_direction_counts == {
        "bullish": 1,
        "bearish": 2,
    }
    assert audit.trend_alignment_counts == {
        "aligned": 2,
        "opposed": 1,
        "neutral": 0,
        "unknown": 0,
    }
    assert audit.structural_pattern_alignment_counts == {
        "aligned": 1,
        "opposed": 1,
        "ambiguous": 1,
    }
    assert audit.trend_direction_matrix["up"] == {
        "bullish": 1,
        "bearish": 1,
    }
    assert audit.is_actionable is False


def test_range_trend_and_breaking_pattern_remain_non_directional() -> None:
    audit = summarize_progression_directionality(
        basket_name="fixture",
        requested_symbols=("AAA.NS",),
        audits=(
            _audit(
                "AAA.NS",
                (
                    _row(
                        bar=10,
                        direction="bearish",
                        trend="range",
                        pattern="breaking",
                    ),
                ),
            ),
        ),
    )

    row = audit.rows[0]
    assert row.trend_alignment == "neutral"
    assert row.structural_pattern_alignment == "ambiguous"


def test_failures_are_counted_without_discarding_successful_symbols() -> None:
    audit = summarize_progression_directionality(
        basket_name="fixture",
        requested_symbols=("AAA.NS", "BBB.NS"),
        audits=(
            _audit(
                "AAA.NS",
                (
                    _row(
                        bar=10,
                        direction="bullish",
                        trend="up",
                        pattern="stable",
                    ),
                ),
            ),
        ),
        failures=(
            ProgressionDirectionalityFailure(
                symbol="BBB.NS",
                exception_type="RuntimeError",
                reason="fixture failure",
            ),
        ),
    )

    assert audit.requested_symbol_count == 2
    assert audit.successful_symbol_count == 1
    assert audit.failed_symbol_count == 1
    assert audit.event_count == 1


def test_writer_outputs_summary_events_symbols_and_failures(tmp_path) -> None:
    audit = summarize_progression_directionality(
        basket_name="fixture",
        requested_symbols=("AAA.NS",),
        audits=(
            _audit(
                "AAA.NS",
                (
                    _row(
                        bar=10,
                        direction="bullish",
                        trend="up",
                        pattern="improving",
                    ),
                ),
            ),
        ),
    )

    paths = write_progression_directionality_audit(audit, tmp_path)
    summary = json.loads(paths.summary_json.read_text(encoding="utf-8"))
    events = pd.read_csv(paths.event_ledger_csv)
    symbols = pd.read_csv(paths.symbol_summary_csv)
    failures = pd.read_csv(paths.failure_ledger_csv)

    assert summary["event_count"] == 1
    assert summary["is_actionable"] is False
    assert len(events) == 1
    assert len(symbols) == 1
    assert failures.empty
