from types import SimpleNamespace

from background.qualification import (
    PatternQualification,
    PatternQualificationEngine,
    PatternQualificationResult,
)
from models import EvidenceCode, EvidenceDirection
from scanner import ScannerCandidate, rank_candidates


def _result(bar_index: int, code: EvidenceCode, direction: EvidenceDirection):
    evidence = SimpleNamespace(
        bar_index=bar_index,
        code=code,
        direction=direction,
    )
    return SimpleNamespace(evidence=(evidence,))


def test_single_structural_event_is_unqualified():
    result = PatternQualificationEngine().evaluate([
        _result(
            99,
            EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING,
            EvidenceDirection.BEARISH,
        ),
    ])

    assert result.qualification == PatternQualification.UNQUALIFIED
    assert result.is_actionable_evidence is False


def test_three_close_events_are_not_persistent():
    result = PatternQualificationEngine().evaluate([
        _result(99, EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING, EvidenceDirection.BEARISH),
        _result(100, EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING, EvidenceDirection.BEARISH),
        _result(101, EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING, EvidenceDirection.BEARISH),
    ])

    assert result.qualification == PatternQualification.UNQUALIFIED
    assert result.is_actionable_evidence is False


def test_three_chronological_events_qualify_persistent_bearish():
    result = PatternQualificationEngine().evaluate([
        _result(99, EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING, EvidenceDirection.BEARISH),
        _result(107, EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING, EvidenceDirection.BEARISH),
        _result(115, EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING, EvidenceDirection.BEARISH),
    ])

    assert result.qualification == PatternQualification.PERSISTENT_BEARISH
    assert result.is_actionable_evidence is True
    assert result.evidence_bar_indices == (99, 107, 115)


def test_opposing_progression_invalidates_previous_bearish_sequence():
    result = PatternQualificationEngine().evaluate([
        _result(209, EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING, EvidenceDirection.BEARISH),
        _result(235, EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING, EvidenceDirection.BEARISH),
        _result(397, EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING, EvidenceDirection.BULLISH),
        _result(414, EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING, EvidenceDirection.BULLISH),
        _result(423, EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING, EvidenceDirection.BULLISH),
        _result(471, EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING, EvidenceDirection.BEARISH),
        _result(618, EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING, EvidenceDirection.BULLISH),
        _result(622, EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING, EvidenceDirection.BULLISH),
    ])

    assert result.qualification == PatternQualification.UNQUALIFIED
    assert result.is_actionable_evidence is False
    assert result.evidence_bar_indices == ()


def test_later_opposing_event_resets_persistence_before_target_bar():
    result = PatternQualificationEngine().evaluate([
        _result(209, EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING, EvidenceDirection.BEARISH),
        _result(235, EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING, EvidenceDirection.BEARISH),
        _result(471, EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING, EvidenceDirection.BEARISH),
        _result(618, EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING, EvidenceDirection.BULLISH),
        _result(622, EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING, EvidenceDirection.BULLISH),
    ])

    assert result.qualification == PatternQualification.UNQUALIFIED
    assert result.is_actionable_evidence is False


def _candidate(actionable: bool, base_score: float) -> ScannerCandidate:
    qualification = PatternQualificationResult(
        qualification=(
            PatternQualification.PERSISTENT_BEARISH
            if actionable
            else PatternQualification.UNQUALIFIED
        ),
        is_actionable_evidence=actionable,
        reason="test",
    )

    professional = SimpleNamespace(
        scores=SimpleNamespace(
            net_strength=base_score,
            net_pressure=0.0,
        ),
        confidence=0.5,
    )

    evidence = SimpleNamespace(evidence=())

    return ScannerCandidate(
        evidence=evidence,
        professional=professional,
        qualification_result=qualification,
    )


def test_actionable_candidate_ranks_above_higher_score_unqualified_candidate():
    qualified = _candidate(True, -0.40)
    unqualified = _candidate(False, 0.80)

    ranked = rank_candidates([unqualified, qualified])

    assert ranked == [qualified, unqualified]
