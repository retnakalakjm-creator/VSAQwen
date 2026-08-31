from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

from background.qualification import PatternQualification, PatternQualificationResult
from models import EvidenceCode, EvidenceDirection, EvidenceCategory, TrendDirection
from scanner import ScannerEngine


CONFIRMATION_ONLY_CODES = frozenset(
    {
        EvidenceCode.DEMAND_COMING_IN,
        EvidenceCode.INCREASING_DEMAND,
        EvidenceCode.HIDDEN_DEMAND,
        EvidenceCode.DEMAND_DRYING_UP,
        EvidenceCode.NO_SUPPLY,
        EvidenceCode.SPRING,
        EvidenceCode.TEST,
        EvidenceCode.SELLING_CLIMAX,
        EvidenceCode.HIDDEN_SUPPLY,
        EvidenceCode.SUPPLY_HIGH_VOLUME,
        EvidenceCode.SUPPLY_WIDE_SPREAD,
        EvidenceCode.SUPPLY_ABSORPTION,
    }
)


def _event(code: EvidenceCode, bar_index: int = 30) -> SimpleNamespace:
    direction = (
        EvidenceDirection.BULLISH
        if code in ScannerEngine._BULLISH_VSA_CODES
        else EvidenceDirection.BEARISH
    )
    category = (
        EvidenceCategory.DEMAND
        if direction is EvidenceDirection.BULLISH
        else EvidenceCategory.SUPPLY
    )
    return SimpleNamespace(
        bar_index=bar_index,
        code=code,
        direction=direction,
        category=category,
    )


def _qualification() -> PatternQualificationResult:
    return PatternQualificationResult(
        qualification=PatternQualification.PERSISTENT_BULLISH,
        is_actionable_evidence=True,
        reason="qualified",
        evidence_codes=(EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING,) * 3,
        evidence_bar_indices=(10, 20, 30),
    )


def _professional(net_pressure: float = 0.25):
    return SimpleNamespace(
        scores=SimpleNamespace(net_pressure=net_pressure, net_strength=0.50),
        confidence=0.80,
    )


def _engine(professional=None) -> ScannerEngine:
    engine = ScannerEngine()
    engine._qualification = SimpleNamespace(
        evaluate=lambda history: _qualification(),
    )
    engine._professional = SimpleNamespace(
        calculate=lambda **_: professional or _professional(),
    )
    return engine


def _decision(events: tuple[SimpleNamespace, ...], net_pressure: float = 0.25):
    evidence = SimpleNamespace(context=object(), evidence=events)
    return _engine(_professional(net_pressure)).evaluate(
        trend=SimpleNamespace(
            structure=SimpleNamespace(direction=TrendDirection.UP),
        ),
        evidence=evidence,
        history=(),
        bar_index=30,
    )


def test_confirmation_only_removal_is_a_pure_counterfactual() -> None:
    baseline_events = (
        _event(EvidenceCode.STOPPING_VOLUME),
        _event(EvidenceCode.TEST),
    )
    baseline = _decision(baseline_events)
    counterfactual = _decision(
        tuple(
            item for item in baseline_events
            if item.code not in CONFIRMATION_ONLY_CODES
        )
    )

    assert baseline.actionable is True
    assert counterfactual.actionable is True
    assert baseline.scoring_evidence_age == counterfactual.scoring_evidence_age
    assert baseline.scoring_bar_index == counterfactual.scoring_bar_index


def test_confirmation_only_event_can_change_decision_contract_without_changing_pressure_score() -> None:
    baseline = _decision((_event(EvidenceCode.STOPPING_VOLUME),))
    with_confirmation = _decision(
        (
            _event(EvidenceCode.STOPPING_VOLUME),
            _event(EvidenceCode.SPRING),
        )
    )

    assert baseline.scoring_bar_index == with_confirmation.scoring_bar_index
    assert baseline.scoring_evidence_age == with_confirmation.scoring_evidence_age
    assert baseline.actionable is True
    assert with_confirmation.actionable is True


def test_confirmation_only_audit_does_not_assign_professional_weight() -> None:
    from config import DEMAND_EVIDENCE_WEIGHTS, SUPPLY_EVIDENCE_WEIGHTS

    for code in CONFIRMATION_ONLY_CODES:
        assert code not in DEMAND_EVIDENCE_WEIGHTS
        assert code not in SUPPLY_EVIDENCE_WEIGHTS
