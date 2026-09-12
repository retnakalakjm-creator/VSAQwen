"""Effort-vs-Result professional scoring neutrality guards.

PR #138 enabled production collection of contextual Effort/Result evidence.
These tests ensure that invocation does not leak into professional scoring,
ranking pressure, or directional VSA confirmation before a separate scoring
validation explicitly changes that behavior.
"""

from __future__ import annotations

from types import SimpleNamespace

import config
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
from professional.scoring_engine import ProfessionalScoringEngine
from scanner import ScannerEngine


NEUTRAL_EFFORT_RESULT_CODES = (
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
    return EvidenceResult(
        context=SimpleNamespace(),
        evidence=tuple(items),
    )


def _effort_item(code: EvidenceCode, *, bar_index: int = 42) -> Evidence:
    return Evidence(
        code=code,
        category=EvidenceCategory.EFFORT,
        direction=EvidenceDirection.NEUTRAL,
        strength=1.0,
        weight=0.0,
        observation=f"contextual {code}",
        description=f"contextual {code}",
        bar_index=bar_index,
        week_beginning="2026-03-02",
    )


def _score_signature(result) -> tuple[float, float, float, float, float, float, float]:
    return (
        result.trend,
        result.supply,
        result.demand,
        result.effort,
        result.strength,
        result.weakness,
        result.confidence,
    )


def test_effort_result_config_weights_remain_disabled_after_engine_invocation():
    assert config.EFFORT_EVIDENCE_WEIGHTS[EvidenceCode.EFFORT_GT_RESULT] == 0.0
    assert config.EFFORT_EVIDENCE_WEIGHTS[EvidenceCode.RESULT_GT_EFFORT] == 0.0
    assert config.EFFORT_EVIDENCE_WEIGHTS[EvidenceCode.ABSORPTION] == 0.0
    assert config.EFFORT_EVIDENCE_WEIGHTS.get(EvidenceCode.EFFORT_RESULT, 0.0) == 0.0


def test_effort_result_context_does_not_change_professional_score_signature():
    trend = _trend_result()
    baseline = ProfessionalScoringEngine().calculate(
        trend=trend,
        evidence=_evidence_result(),
    )
    contextual = ProfessionalScoringEngine().calculate(
        trend=trend,
        evidence=_evidence_result(
            _effort_item(EvidenceCode.EFFORT_GT_RESULT),
            _effort_item(EvidenceCode.RESULT_GT_EFFORT),
        ),
    )

    assert _score_signature(contextual) == _score_signature(baseline)
    assert contextual.effort == 0.0
    assert contextual.scores.net_pressure == baseline.scores.net_pressure
    assert contextual.scores.net_strength == baseline.scores.net_strength


def test_each_effort_result_code_is_zero_contribution_to_effort_score():
    engine = ProfessionalScoringEngine()

    for code in NEUTRAL_EFFORT_RESULT_CODES:
        result = _evidence_result(_effort_item(code))
        assert engine._score_effort(result) == 0.0


def test_effort_result_codes_do_not_become_directional_vsa_confirmation():
    scoring_evidence = tuple(
        _effort_item(code, bar_index=index)
        for index, code in enumerate(NEUTRAL_EFFORT_RESULT_CODES, start=30)
    )

    bullish, bearish = ScannerEngine._vsa_directional_evidence(scoring_evidence)

    assert bullish == ()
    assert bearish == ()
