"""Effort-vs-Result scanner ranking neutrality guards.

PR #138 enabled contextual Effort/Result collection, PR #139 neutralized
professional scoring weights, PR #140 protected aggregation neutrality, and
PR #141 protected scanner actionability neutrality. These tests protect scanner
ranking and promotion behavior before any separate Effort/Result scoring or
ranking PR.
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
from scanner import ScannerCandidate, ScannerEngine, rank_actionable_candidates, rank_candidates


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


def _bearish_vsa(
    *,
    code: EvidenceCode = EvidenceCode.UPTHRUST,
    bar_index: int = 42,
) -> Evidence:
    return _evidence(
        code=code,
        category=EvidenceCategory.SUPPLY,
        direction=EvidenceDirection.BEARISH,
        weight=1.0,
        bar_index=bar_index,
    )


def _bullish_vsa(
    *,
    code: EvidenceCode = EvidenceCode.STOPPING_VOLUME,
    bar_index: int = 42,
) -> Evidence:
    return _evidence(
        code=code,
        category=EvidenceCategory.DEMAND,
        direction=EvidenceDirection.BULLISH,
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


def _structural_improving(bar_index: int) -> Evidence:
    return _evidence(
        code=EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING,
        category=EvidenceCategory.TREND,
        direction=EvidenceDirection.BULLISH,
        weight=1.0,
        bar_index=bar_index,
    )


def _persistent_bearish_history(*, target_bar: int = 42) -> tuple[EvidenceResult, ...]:
    return tuple(
        _evidence_result(_structural_weakening(index))
        for index in (30, 36, target_bar)
    )


def _persistent_bullish_history(*, target_bar: int = 42) -> tuple[EvidenceResult, ...]:
    return tuple(
        _evidence_result(_structural_improving(index))
        for index in (30, 36, target_bar)
    )


def _candidate_with_current(
    *items: Evidence,
    history: tuple[EvidenceResult, ...] | None = None,
    target_bar: int = 42,
) -> ScannerCandidate:
    return ScannerEngine().evaluate(
        trend=_trend_result(),
        evidence=_evidence_result(*items),
        history=history or _persistent_bearish_history(target_bar=target_bar),
        bar_index=target_bar,
        week="2026-03-02",
    )


def _rank_key(candidate: ScannerCandidate) -> tuple[bool, float]:
    return (candidate.actionable, candidate.ranking_score)


def test_effort_result_only_candidates_are_not_promoted_into_actionable_ranking():
    actionable = _candidate_with_current(_bearish_vsa())
    contextual_only = tuple(
        _candidate_with_current(_effort_result(code))
        for code in EFFORT_RESULT_CODES
    )

    ranked = rank_candidates((*contextual_only, actionable))

    assert ranked[0] == actionable
    assert rank_actionable_candidates((*contextual_only, actionable)) == [actionable]
    for candidate, code in zip(contextual_only, EFFORT_RESULT_CODES):
        assert candidate.scoring_evidence_codes == (str(code),)
        assert not candidate.actionable
        assert not candidate.qualification_result.is_actionable_evidence


def test_effort_result_context_does_not_add_bearish_ranking_tiebreaker():
    baseline = _candidate_with_current(_bearish_vsa())
    with_context = _candidate_with_current(
        _bearish_vsa(),
        _effort_result(EvidenceCode.EFFORT_GT_RESULT),
        _effort_result(EvidenceCode.RESULT_GT_EFFORT),
        _effort_result(EvidenceCode.ABSORPTION),
    )

    assert baseline.actionable
    assert with_context.actionable
    assert len(with_context.scoring_evidence) > len(baseline.scoring_evidence)
    assert _rank_key(with_context) == _rank_key(baseline)
    assert rank_actionable_candidates((baseline, with_context)) == [baseline, with_context]
    assert rank_actionable_candidates((with_context, baseline)) == [with_context, baseline]


def test_effort_result_context_does_not_add_bullish_ranking_tiebreaker():
    history = _persistent_bullish_history()
    baseline = _candidate_with_current(_bullish_vsa(), history=history)
    with_context = _candidate_with_current(
        _bullish_vsa(),
        _effort_result(EvidenceCode.EFFORT_GT_RESULT),
        _effort_result(EvidenceCode.RESULT_GT_EFFORT),
        _effort_result(EvidenceCode.EFFORT_RESULT),
        history=history,
    )

    assert baseline.actionable
    assert with_context.actionable
    assert len(with_context.scoring_evidence) > len(baseline.scoring_evidence)
    assert _rank_key(with_context) == _rank_key(baseline)
    assert rank_actionable_candidates((baseline, with_context)) == [baseline, with_context]
    assert rank_actionable_candidates((with_context, baseline)) == [with_context, baseline]


def test_effort_result_context_does_not_change_relative_scanner_ordering():
    stronger = _candidate_with_current(
        _bearish_vsa(code=EvidenceCode.BUYING_CLIMAX)
    )
    weaker = _candidate_with_current(
        _bearish_vsa(code=EvidenceCode.NO_DEMAND)
    )
    weaker_with_context = _candidate_with_current(
        _bearish_vsa(code=EvidenceCode.NO_DEMAND),
        _effort_result(EvidenceCode.EFFORT_GT_RESULT),
        _effort_result(EvidenceCode.RESULT_GT_EFFORT),
        _effort_result(EvidenceCode.ABSORPTION),
    )

    assert stronger.actionable
    assert weaker.actionable
    assert weaker_with_context.actionable
    assert stronger.ranking_score > weaker.ranking_score
    assert weaker_with_context.ranking_score == weaker.ranking_score
    assert rank_actionable_candidates((weaker_with_context, stronger)) == [
        stronger,
        weaker_with_context,
    ]
