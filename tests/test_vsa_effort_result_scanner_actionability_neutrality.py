"""Effort-vs-Result scanner actionability neutrality guards.

PR #138 enabled contextual Effort/Result collection, PR #139 neutralized
professional scoring weights, and PR #140 protected aggregation neutrality.
These tests protect the scanner actionability path so Effort/Result observations
can appear in the current scoring window without becoming directional VSA
confirmation or actionable scanner evidence before a separate scoring/ranking PR.
"""

from __future__ import annotations

from model.evidence_result_model import EvidenceResult
from models import (
    Evidence,
    EvidenceCategory,
    EvidenceCode,
    EvidenceDirection,
    TrendDirection,
    TrendResult,
    TrendState,
    TrendStructure,
)
from scanner import ScannerEngine


EFFORT_RESULT_CODES = (
    EvidenceCode.EFFORT_GT_RESULT,
    EvidenceCode.RESULT_GT_EFFORT,
    EvidenceCode.ABSORPTION,
    EvidenceCode.EFFORT_RESULT,
)


def _trend_result() -> TrendResult:
    return TrendResult(
        structure=TrendStructure(
            direction=TrendDirection.UP,
            state=TrendState.HEALTHY,
            strength=0.80,
            confidence=0.80,
            swing_count=0,
            swings=(),
            structural_swings=(),
            hh_count=0,
            hl_count=0,
            lh_count=0,
            ll_count=0,
        )
    )


def _evidence_result(*items: Evidence) -> EvidenceResult:
    return EvidenceResult(context=None, evidence=tuple(items))


def _evidence(
    *,
    code: EvidenceCode,
    category: EvidenceCategory,
    direction: EvidenceDirection,
    bar_index: int,
    weight: float = 0.0,
    strength: float = 1.0,
) -> Evidence:
    return Evidence(
        code=code,
        category=category,
        direction=direction,
        strength=strength,
        weight=weight,
        observation=f"{code} observation",
        description=f"{code} description",
        bar_index=bar_index,
        week_beginning=f"2026-03-{bar_index:02d}",
    )


def _effort_result(code: EvidenceCode, *, bar_index: int = 42) -> Evidence:
    return _evidence(
        code=code,
        category=EvidenceCategory.EFFORT,
        direction=EvidenceDirection.NEUTRAL,
        weight=0.0,
        bar_index=bar_index,
    )


def _bearish_vsa(*, bar_index: int = 42) -> Evidence:
    return _evidence(
        code=EvidenceCode.UPTHRUST,
        category=EvidenceCategory.SUPPLY,
        direction=EvidenceDirection.BEARISH,
        weight=1.0,
        bar_index=bar_index,
    )


def _structural_weakening(bar_index: int) -> Evidence:
    return _evidence(
        code=EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING,
        category=EvidenceCategory.TREND,
        direction=EvidenceDirection.BEARISH,
        weight=1.0,
        bar_index=bar_index,
    )


def _persistent_bearish_history(*, target_bar: int = 42) -> tuple[EvidenceResult, ...]:
    return tuple(
        _evidence_result(_structural_weakening(index))
        for index in (30, 36, target_bar)
    )


def _candidate_with_current(*items: Evidence, target_bar: int = 42):
    return ScannerEngine().evaluate(
        trend=_trend_result(),
        evidence=_evidence_result(*items),
        history=_persistent_bearish_history(target_bar=target_bar),
        bar_index=target_bar,
        week="2026-03-02",
    )


def test_effort_result_only_current_scoring_window_is_not_actionable_confirmation():
    candidate = _candidate_with_current(
        _effort_result(EvidenceCode.EFFORT_GT_RESULT),
        _effort_result(EvidenceCode.RESULT_GT_EFFORT),
    )

    assert candidate.scoring_evidence_codes == (
        str(EvidenceCode.EFFORT_GT_RESULT),
        str(EvidenceCode.RESULT_GT_EFFORT),
    )
    assert candidate.scoring_bar_index == 42
    assert candidate.scoring_evidence_age == 0
    assert not candidate.actionable
    assert not candidate.qualification_result.is_actionable_evidence
    assert "no directional VSA confirmation" in candidate.reason


def test_each_effort_result_code_alone_fails_scanner_actionability_gate():
    for code in EFFORT_RESULT_CODES:
        candidate = _candidate_with_current(_effort_result(code))

        assert candidate.scoring_evidence_codes == (str(code),)
        assert candidate.professional.effort == 0.0
        assert candidate.professional.scores.net_pressure == 0.0
        assert not candidate.actionable
        assert not candidate.qualification_result.is_actionable_evidence


def test_effort_result_context_does_not_change_directional_vsa_actionability():
    baseline = _candidate_with_current(_bearish_vsa())
    with_context = _candidate_with_current(
        _bearish_vsa(),
        _effort_result(EvidenceCode.EFFORT_GT_RESULT),
        _effort_result(EvidenceCode.RESULT_GT_EFFORT),
    )

    assert baseline.actionable
    assert with_context.actionable
    assert with_context.qualification == baseline.qualification
    assert with_context.professional.effort == baseline.professional.effort
    assert with_context.professional.scores.net_pressure == baseline.professional.scores.net_pressure
    assert with_context.professional.scores.net_strength == baseline.professional.scores.net_strength
    assert with_context.ranking_score == baseline.ranking_score


def test_effort_result_codes_are_not_directional_scanner_vsa_evidence():
    scoring_evidence = tuple(
        _effort_result(code, bar_index=index)
        for index, code in enumerate(EFFORT_RESULT_CODES, start=42)
    )

    bullish, bearish = ScannerEngine._vsa_directional_evidence(scoring_evidence)

    assert bullish == ()
    assert bearish == ()
