from __future__ import annotations

from model.evidence_result_model import EvidenceResult
from model.score_model import ProfessionalScore, ProfessionalScoreResult
from models import Evidence, EvidenceCategory, EvidenceCode, EvidenceDirection
from scanner import ScannerCandidate, ScannerEngine


def _evidence(
    code: EvidenceCode,
    *,
    bar_index: int = 20,
    direction: EvidenceDirection = EvidenceDirection.NEUTRAL,
    category: EvidenceCategory = EvidenceCategory.EFFORT,
    weight: float = 0.0,
) -> Evidence:
    return Evidence(
        code=code,
        category=category,
        direction=direction,
        strength=0.5,
        weight=weight,
        observation=code.value,
        description="test evidence",
        bar_index=bar_index,
        week_beginning="2026-09-14",
    )


def _candidate(*items: Evidence) -> ScannerCandidate:
    score = ProfessionalScore(
        trend=0.0,
        supply=0.0,
        demand=0.0,
        effort=0.0,
        strength=0.0,
        weakness=0.0,
        confidence=0.0,
    )
    return ScannerCandidate(
        evidence=EvidenceResult(context=object(), evidence=tuple(items)),
        professional=ProfessionalScoreResult(scores=score, evidence=()),
        target_bar_evidence=tuple(items),
        campaign_evidence=tuple(items),
        bar_index=20,
        week="2026-09-14",
    )


def test_effort_result_events_are_exposed_as_read_only_candidate_evidence() -> None:
    effort_without_result = _evidence(EvidenceCode.EFFORT_GT_RESULT)
    result_without_effort = _evidence(EvidenceCode.RESULT_GT_EFFORT)
    scoring_event = _evidence(
        EvidenceCode.NO_SUPPLY,
        direction=EvidenceDirection.BULLISH,
        category=EvidenceCategory.DEMAND,
        weight=1.0,
    )

    candidate = _candidate(
        effort_without_result,
        result_without_effort,
        scoring_event,
    )

    assert candidate.effort_result_evidence == (
        effort_without_result,
        result_without_effort,
    )
    assert candidate.effort_result_evidence_codes == (
        EvidenceCode.EFFORT_GT_RESULT.value,
        EvidenceCode.RESULT_GT_EFFORT.value,
    )


def test_effort_result_events_do_not_become_scoring_vsa_evidence() -> None:
    result_without_effort = _evidence(EvidenceCode.RESULT_GT_EFFORT, bar_index=21)
    no_supply = _evidence(
        EvidenceCode.NO_SUPPLY,
        bar_index=20,
        direction=EvidenceDirection.BULLISH,
        category=EvidenceCategory.DEMAND,
        weight=1.0,
    )
    evidence = EvidenceResult(
        context=object(),
        evidence=(no_supply, result_without_effort),
    )

    scoring = ScannerEngine._scoring_evidence(evidence, 21)

    assert scoring == (no_supply,)
    assert result_without_effort not in scoring


def test_effort_result_only_bar_does_not_create_scoring_evidence() -> None:
    evidence = EvidenceResult(
        context=object(),
        evidence=(
            _evidence(EvidenceCode.EFFORT_GT_RESULT, bar_index=21),
            _evidence(EvidenceCode.RESULT_GT_EFFORT, bar_index=21),
        ),
    )

    assert ScannerEngine._scoring_evidence(evidence, 21) == ()
