from dataclasses import replace
from types import SimpleNamespace

from model.score_model import ProfessionalScore, ProfessionalScoreResult
from scanner import ScannerCandidate
from professional.scoring_engine import ProfessionalScoringEngine


def test_legacy_candidate_restores_pre_gate_confidence_only() -> None:
    scores = ProfessionalScore(
        trend=0.50,
        supply=0.10,
        demand=0.40,
        effort=0.60,
        strength=0.70,
        weakness=0.20,
        confidence=0.0,
    )
    candidate = ScannerCandidate(
        evidence=SimpleNamespace(evidence=()),
        professional=ProfessionalScoreResult(scores=scores, evidence=()),
    )

    from run_increasing_demand_gate_impact_audit import _legacy_candidate

    legacy = _legacy_candidate(candidate)

    assert legacy.base_score == candidate.base_score
    assert legacy.net_pressure == candidate.net_pressure
    assert legacy.professional.scores.confidence == ProfessionalScoringEngine._measure_confidence(scores)


def test_legacy_candidate_does_not_mutate_source() -> None:
    scores = ProfessionalScore(
        trend=0.50,
        supply=0.10,
        demand=0.40,
        effort=0.60,
        strength=0.70,
        weakness=0.20,
        confidence=0.0,
    )
    professional = ProfessionalScoreResult(scores=scores, evidence=())
    candidate = ScannerCandidate(
        evidence=SimpleNamespace(evidence=()),
        professional=professional,
    )

    from run_increasing_demand_gate_impact_audit import _legacy_candidate

    legacy = _legacy_candidate(candidate)

    assert legacy.professional is not professional
    assert candidate.professional.scores.confidence == 0.0
