from types import SimpleNamespace

from background.qualification import PatternQualification, PatternQualificationResult
from models import EvidenceCode, EvidenceDirection, EvidenceCategory, TrendDirection
from scanner import ScannerEngine


def _evidence(bar_index: int, code: EvidenceCode, direction: EvidenceDirection):
    return SimpleNamespace(
        bar_index=bar_index,
        code=code,
        direction=direction,
        category=(
            EvidenceCategory.DEMAND
            if direction is EvidenceDirection.BULLISH
            else EvidenceCategory.SUPPLY
        ),
    )


def _professional(net_pressure: float = 0.25, confidence: float = 0.80):
    return SimpleNamespace(
        scores=SimpleNamespace(
            net_pressure=net_pressure,
            net_strength=0.50,
        ),
        confidence=confidence,
    )


def _engine(qualification: PatternQualificationResult, professional=None) -> ScannerEngine:
    engine = ScannerEngine()
    engine._qualification = SimpleNamespace(evaluate=lambda history: qualification)
    engine._professional = SimpleNamespace(
        calculate=lambda **_: professional or _professional()
    )
    return engine


def _evaluate(
    qualification: PatternQualificationResult,
    current_bar: int,
    *events,
    net_pressure: float = 0.25,
):
    event_tuple = tuple(events)
    evidence = SimpleNamespace(context=object(), evidence=event_tuple)
    return _engine(
        qualification,
        _professional(net_pressure=net_pressure),
    ).evaluate(
        trend=SimpleNamespace(structure=SimpleNamespace(direction=TrendDirection.UP)),
        evidence=evidence,
        history=(),
        bar_index=current_bar,
    )


def test_current_directional_vsa_keeps_current_persistent_bullish_actionable():
    qualification = PatternQualificationResult(
        qualification=PatternQualification.PERSISTENT_BULLISH,
        is_actionable_evidence=True,
        reason="qualified",
        evidence_codes=(EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING,) * 3,
        evidence_bar_indices=(10, 20, 30),
    )
    candidate = _evaluate(
        qualification,
        30,
        _evidence(30, EvidenceCode.STOPPING_VOLUME, EvidenceDirection.BULLISH),
    )

    assert candidate.actionable is True
    assert candidate.scoring_bar_index == 30
    assert candidate.scoring_evidence_age == 0
    assert candidate.used_fallback_evidence is False


def test_three_bar_old_directional_vsa_can_confirm_structural_continuation():
    qualification = PatternQualificationResult(
        qualification=PatternQualification.PERSISTENT_BULLISH,
        is_actionable_evidence=True,
        reason="qualified",
        evidence_codes=(EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING,) * 3,
        evidence_bar_indices=(10, 20, 25),
    )
    candidate = _evaluate(
        qualification,
        28,
        _evidence(25, EvidenceCode.STOPPING_VOLUME, EvidenceDirection.BULLISH),
    )

    assert candidate.actionable is True
    assert candidate.scoring_evidence_age == 3
    assert candidate.used_fallback_evidence is True


def test_four_bar_old_directional_vsa_is_not_actionable():
    qualification = PatternQualificationResult(
        qualification=PatternQualification.PERSISTENT_BULLISH,
        is_actionable_evidence=True,
        reason="qualified",
        evidence_codes=(EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING,) * 3,
        evidence_bar_indices=(10, 20, 24),
    )
    candidate = _evaluate(
        qualification,
        28,
        _evidence(24, EvidenceCode.STOPPING_VOLUME, EvidenceDirection.BULLISH),
    )

    assert candidate.actionable is False
    assert candidate.scoring_evidence_age == 4


def test_opposing_current_vsa_invalidates_persistent_bullish_structure():
    qualification = PatternQualificationResult(
        qualification=PatternQualification.PERSISTENT_BULLISH,
        is_actionable_evidence=True,
        reason="qualified",
        evidence_codes=(EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING,) * 3,
        evidence_bar_indices=(10, 20, 30),
    )
    candidate = _evaluate(
        qualification,
        30,
        _evidence(30, EvidenceCode.BUYING_CLIMAX, EvidenceDirection.BEARISH),
        net_pressure=-0.20,
    )

    assert candidate.actionable is False
    assert "contradicted" in candidate.reason


def test_mixed_directional_vsa_does_not_count_as_clean_confirmation():
    qualification = PatternQualificationResult(
        qualification=PatternQualification.PERSISTENT_BULLISH,
        is_actionable_evidence=True,
        reason="qualified",
        evidence_codes=(EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING,) * 3,
        evidence_bar_indices=(10, 20, 30),
    )
    candidate = _evaluate(
        qualification,
        30,
        _evidence(30, EvidenceCode.STOPPING_VOLUME, EvidenceDirection.BULLISH),
        _evidence(30, EvidenceCode.BUYING_CLIMAX, EvidenceDirection.BEARISH),
    )

    assert candidate.actionable is False
    assert candidate.scoring_bar_index == 30
