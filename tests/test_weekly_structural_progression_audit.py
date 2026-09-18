from __future__ import annotations

import json
from types import SimpleNamespace

import pandas as pd

from audit.genuine_daily_sequence_case import (
    ProductionWeeklySourceFingerprint,
)
from audit.weekly_structural_progression_audit import (
    WEEKLY_STRUCTURAL_PROGRESSION_AUDIT_ID,
    audit_weekly_structural_progression_candidates,
    write_weekly_structural_progression_audit,
)
from background.qualification import (
    PatternQualification,
    PatternQualificationResult,
)
from models import Evidence, EvidenceCategory, EvidenceCode, EvidenceDirection


def _fingerprint() -> ProductionWeeklySourceFingerprint:
    return ProductionWeeklySourceFingerprint(
        symbol="LT.NS",
        row_count=10,
        first_week="2026-01-02T00:00:00",
        last_week="2026-03-06T00:00:00",
        sha256="sha256:test-weekly",
    )


def _event(
    code: EvidenceCode,
    bar_index: int,
    week: str,
) -> Evidence:
    direction = (
        EvidenceDirection.BULLISH
        if code is EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING
        else EvidenceDirection.BEARISH
    )
    return Evidence(
        code=code,
        category=EvidenceCategory.TREND,
        direction=direction,
        strength=0.8,
        weight=1.0,
        observation="progression",
        description="progression",
        bar_index=bar_index,
        week_beginning=week,
    )


def _structural_swing(
    *,
    confirmation_index: int,
    overall: float,
    swing_type: str = "low",
    label: str = "ll",
):
    return SimpleNamespace(
        swing=SimpleNamespace(
            confirmation_index=confirmation_index,
            bar_index=confirmation_index - 2,
            week_beginning=f"W{confirmation_index}",
            type=SimpleNamespace(value=swing_type),
            label=SimpleNamespace(value=label),
        ),
        grade=SimpleNamespace(name="MAJOR"),
        evaluation=SimpleNamespace(
            professional=SimpleNamespace(overall=overall)
        ),
    )


def _candidate(
    *,
    bar_index: int,
    week: str,
    event: Evidence | None,
    qualification: PatternQualification,
    structural_scores: tuple[float, ...],
):
    swings = tuple(
        _structural_swing(
            confirmation_index=(
                bar_index
                if index == len(structural_scores) - 1
                else bar_index - (len(structural_scores) - 1 - index) * 2
            ),
            overall=score,
        )
        for index, score in enumerate(structural_scores)
    )
    target = () if event is None else (event,)
    qualifying = (
        target
        if event is not None
        and qualification is not PatternQualification.UNQUALIFIED
        else ()
    )
    return SimpleNamespace(
        bar_index=bar_index,
        week=week,
        qualification=qualification,
        qualification_result=PatternQualificationResult(
            qualification=qualification,
            is_actionable_evidence=(
                qualification is not PatternQualification.UNQUALIFIED
            ),
            reason="fixture",
        ),
        target_bar_evidence=target,
        qualifying_evidence=qualifying,
        evidence=SimpleNamespace(
            context=SimpleNamespace(
                structural_swings=swings,
                trend=SimpleNamespace(
                    direction=SimpleNamespace(value="down"),
                    state=SimpleNamespace(value="healthy"),
                ),
                structural_pattern=SimpleNamespace(name="WEAKENING"),
            )
        ),
    )


def test_event_audit_keeps_improving_and_weakening_streams_separate() -> None:
    candidates = (
        _candidate(
            bar_index=20,
            week="2026-01-05",
            event=_event(
                EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING,
                20,
                "2026-01-05",
            ),
            qualification=PatternQualification.UNQUALIFIED,
            structural_scores=(0.2, 0.2, 0.2, 0.8, 0.8, 0.8),
        ),
        _candidate(
            bar_index=25,
            week="2026-02-09",
            event=_event(
                EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING,
                25,
                "2026-02-09",
            ),
            qualification=PatternQualification.PERSISTENT_BEARISH,
            structural_scores=(0.8, 0.8, 0.8, 0.2, 0.2, 0.2),
        ),
    )

    audit = audit_weekly_structural_progression_candidates(
        symbol="lt.ns",
        candidates=candidates,
        source_fingerprint=_fingerprint(),
    )

    assert audit.symbol == "LT.NS"
    assert audit.audit_id == WEEKLY_STRUCTURAL_PROGRESSION_AUDIT_ID
    assert audit.event_count == 2
    assert audit.improving_event_count == 1
    assert audit.weakening_event_count == 1
    assert audit.first_improving_week == "2026-01-05"
    assert audit.first_weakening_week == "2026-02-09"
    assert audit.first_persistent_bearish_week == "2026-02-09"
    assert audit.first_persistent_bullish_week is None
    assert audit.rows[0].trend_direction == "down"
    assert audit.rows[0].trend_state == "healthy"
    assert audit.rows[0].structural_pattern == "weakening"
    assert audit.is_actionable is False


def test_same_direction_spacing_uses_existing_four_bar_minimum() -> None:
    first = _event(
        EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING,
        20,
        "2026-01-05",
    )
    second = _event(
        EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING,
        23,
        "2026-01-26",
    )
    third = _event(
        EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING,
        27,
        "2026-02-23",
    )
    candidates = (
        _candidate(
            bar_index=20,
            week="2026-01-05",
            event=first,
            qualification=PatternQualification.UNQUALIFIED,
            structural_scores=(0.8, 0.8, 0.8, 0.2, 0.2, 0.2),
        ),
        _candidate(
            bar_index=23,
            week="2026-01-26",
            event=second,
            qualification=PatternQualification.UNQUALIFIED,
            structural_scores=(0.8, 0.8, 0.8, 0.2, 0.2, 0.2),
        ),
        _candidate(
            bar_index=27,
            week="2026-02-23",
            event=third,
            qualification=PatternQualification.PERSISTENT_BEARISH,
            structural_scores=(0.8, 0.8, 0.8, 0.2, 0.2, 0.2),
        ),
    )

    audit = audit_weekly_structural_progression_candidates(
        symbol="LT.NS",
        candidates=candidates,
        source_fingerprint=_fingerprint(),
    )

    assert audit.rows[0].bars_since_previous_same_direction is None
    assert audit.rows[1].bars_since_previous_same_direction == 3
    assert audit.rows[1].meets_min_same_direction_spacing is False
    assert audit.rows[2].bars_since_previous_same_direction == 4
    assert audit.rows[2].meets_min_same_direction_spacing is True


def test_opposing_event_resets_same_direction_spacing_reference() -> None:
    candidates = (
        _candidate(
            bar_index=20,
            week="2026-01-05",
            event=_event(
                EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING,
                20,
                "2026-01-05",
            ),
            qualification=PatternQualification.UNQUALIFIED,
            structural_scores=(0.8, 0.8, 0.8, 0.2, 0.2, 0.2),
        ),
        _candidate(
            bar_index=24,
            week="2026-02-02",
            event=_event(
                EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING,
                24,
                "2026-02-02",
            ),
            qualification=PatternQualification.UNQUALIFIED,
            structural_scores=(0.2, 0.2, 0.2, 0.8, 0.8, 0.8),
        ),
        _candidate(
            bar_index=29,
            week="2026-03-09",
            event=_event(
                EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING,
                29,
                "2026-03-09",
            ),
            qualification=PatternQualification.UNQUALIFIED,
            structural_scores=(0.8, 0.8, 0.8, 0.2, 0.2, 0.2),
        ),
    )

    audit = audit_weekly_structural_progression_candidates(
        symbol="LT.NS",
        candidates=candidates,
        source_fingerprint=_fingerprint(),
    )

    assert audit.rows[2].previous_same_direction_bar_index is None
    assert audit.rows[2].bars_since_previous_same_direction is None
    assert audit.rows[2].meets_min_same_direction_spacing is None


def test_writer_outputs_summary_and_event_ledger(tmp_path) -> None:
    audit = audit_weekly_structural_progression_candidates(
        symbol="LT.NS",
        candidates=(
            _candidate(
                bar_index=20,
                week="2026-01-05",
                event=_event(
                    EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING,
                    20,
                    "2026-01-05",
                ),
                qualification=PatternQualification.PERSISTENT_BEARISH,
                structural_scores=(0.8, 0.8, 0.8, 0.2, 0.2, 0.2),
            ),
        ),
        source_fingerprint=_fingerprint(),
    )

    paths = write_weekly_structural_progression_audit(audit, tmp_path)
    summary = json.loads(paths.summary_json.read_text(encoding="utf-8"))
    ledger = pd.read_csv(paths.event_ledger_csv)

    assert summary["event_direction_counts"] == {
        "bearish": 1,
        "bullish": 0,
    }
    assert summary["is_actionable"] is False
    assert len(ledger) == 1
    assert ledger.loc[0, "event_direction"] == "bearish"
