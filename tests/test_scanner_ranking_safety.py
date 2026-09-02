from types import SimpleNamespace

import pytest

from background.qualification import PatternQualification, PatternQualificationResult
from model.score_model import ProfessionalScore, ProfessionalScoreResult
from scanner import ScannerCandidate, rank_actionable_candidates, rank_candidates


def _candidate(name: str, *, actionable: bool, base_score: float, ranking_score: float | None = None):
    return SimpleNamespace(
        name=name,
        actionable=actionable,
        base_score=base_score,
        ranking_score=base_score if ranking_score is None else ranking_score,
    )


def test_rank_candidates_prioritizes_actionability_over_score() -> None:
    candidates = [
        _candidate("non_actionable_high_score", actionable=False, base_score=0.99),
        _candidate("actionable_lower_score", actionable=True, base_score=0.25),
    ]

    ranked = rank_candidates(candidates)

    assert [candidate.name for candidate in ranked] == [
        "actionable_lower_score",
        "non_actionable_high_score",
    ]


def test_rank_candidates_orders_equal_actionability_by_ranking_score() -> None:
    candidates = [
        _candidate("medium", actionable=True, base_score=0.50, ranking_score=0.50),
        _candidate("high", actionable=True, base_score=0.80, ranking_score=0.80),
        _candidate("low", actionable=True, base_score=0.20, ranking_score=0.20),
    ]

    ranked = rank_candidates(candidates)

    assert [candidate.name for candidate in ranked] == [
        "high",
        "medium",
        "low",
    ]


def test_rank_actionable_candidates_excludes_non_actionable_candidates() -> None:
    candidates = [
        _candidate("actionable", actionable=True, base_score=0.30),
        _candidate("non_actionable", actionable=False, base_score=1.00),
    ]

    ranked = rank_actionable_candidates(candidates)

    assert [candidate.name for candidate in ranked] == ["actionable"]


def test_ranking_is_deterministic_for_frozen_scores() -> None:
    candidates = [
        _candidate("first", actionable=True, base_score=0.70),
        _candidate("second", actionable=True, base_score=0.40),
        _candidate("third", actionable=False, base_score=0.95),
    ]

    first = [candidate.name for candidate in rank_candidates(candidates)]
    second = [candidate.name for candidate in rank_candidates(tuple(candidates))]

    assert first == second


def _scanner_candidate(qualification: PatternQualification, *, strength: float, weakness: float) -> ScannerCandidate:
    return ScannerCandidate(
        evidence=None,
        professional=ProfessionalScoreResult(
            scores=ProfessionalScore(
                trend=0.5,
                supply=0.5,
                demand=0.5,
                effort=0.5,
                strength=strength,
                weakness=weakness,
                confidence=1.0,
            ),
            evidence=(),
        ),
        qualification_result=PatternQualificationResult(
            qualification=qualification,
            is_actionable_evidence=True,
            reason="test",
        ),
    )


def test_directional_ranking_uses_conviction_magnitude() -> None:
    bullish = _scanner_candidate(
        PatternQualification.PERSISTENT_BULLISH,
        strength=0.60,
        weakness=0.0,
    )
    bearish = _scanner_candidate(
        PatternQualification.PERSISTENT_BEARISH,
        strength=0.0,
        weakness=0.80,
    )

    assert bullish.base_score == 0.60
    assert bearish.base_score == -0.80
    assert bullish.ranking_score == 0.60
    assert bearish.ranking_score == 0.80
    assert rank_candidates([bullish, bearish]) == [bearish, bullish]


def test_bearish_ranking_handles_positive_raw_net_strength() -> None:
    candidate = _scanner_candidate(
        PatternQualification.PERSISTENT_BEARISH,
        strength=0.70,
        weakness=0.20,
    )

    assert candidate.base_score == pytest.approx(0.50)
    assert candidate.ranking_score == pytest.approx(0.50)


def test_bullish_ranking_handles_negative_raw_net_strength() -> None:
    candidate = _scanner_candidate(
        PatternQualification.PERSISTENT_BULLISH,
        strength=0.10,
        weakness=0.60,
    )

    assert candidate.base_score == pytest.approx(-0.50)
    assert candidate.ranking_score == pytest.approx(0.50)
