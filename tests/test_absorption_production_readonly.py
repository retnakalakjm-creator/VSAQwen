from __future__ import annotations

from model.evidence_result_model import EvidenceResult
from model.score_model import ProfessionalScore, ProfessionalScoreResult
from models import Evidence, EvidenceCategory, EvidenceCode, EvidenceDirection
from scanner import ScannerCandidate, ScannerEngine


def _evidence(
    code: EvidenceCode,
    *,
    bar_index: int = 20,
    direction: EvidenceDirection = EvidenceDirection.BULLISH,
    category: EvidenceCategory = EvidenceCategory.ABSORPTION,
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


def test_absorption_is_exposed_as_read_only_candidate_evidence() -> None:
    absorption = _evidence(EvidenceCode.ABSORPTION)
    no_supply = _evidence(
        EvidenceCode.NO_SUPPLY,
        direction=EvidenceDirection.BULLISH,
        category=EvidenceCategory.DEMAND,
        weight=1.0,
    )

    candidate = _candidate(absorption, no_supply)

    assert candidate.absorption_evidence == (absorption,)
    assert candidate.absorption_evidence_codes == (EvidenceCode.ABSORPTION.value,)


def test_absorption_does_not_become_scoring_vsa_evidence() -> None:
    absorption = _evidence(EvidenceCode.ABSORPTION, bar_index=21)
    no_supply = _evidence(
        EvidenceCode.NO_SUPPLY,
        bar_index=20,
        direction=EvidenceDirection.BULLISH,
        category=EvidenceCategory.DEMAND,
        weight=1.0,
    )
    evidence = EvidenceResult(
        context=object(),
        evidence=(no_supply, absorption),
    )

    scoring = ScannerEngine._scoring_evidence(evidence, 21)

    assert scoring == (no_supply,)
    assert absorption not in scoring


def test_absorption_only_bar_does_not_create_scoring_evidence() -> None:
    evidence = EvidenceResult(
        context=object(),
        evidence=(
            _evidence(EvidenceCode.ABSORPTION, bar_index=21),
        ),
    )

    assert ScannerEngine._scoring_evidence(evidence, 21) == ()


def test_absorption_is_not_directional_scanner_confirmation() -> None:
    absorption = _evidence(EvidenceCode.ABSORPTION)

    bullish, bearish = ScannerEngine._vsa_directional_evidence((absorption,))

    assert bullish == ()
    assert bearish == ()
