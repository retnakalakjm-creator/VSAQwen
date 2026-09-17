from __future__ import annotations

from types import SimpleNamespace

import pytest

from background.qualification import PatternQualification, PatternQualificationResult
from model.evidence_result_model import EvidenceResult
from model.score_model import ProfessionalScore, ProfessionalScoreResult
from models import (
    Evidence,
    EvidenceCategory,
    EvidenceCode,
    EvidenceDirection,
    StructuralPattern,
    TrendDirection,
    TrendState,
)
from scanner import ScannerCandidate
from weekly_decision_audit import LegacyGateBlocker, WeeklyDecisionGateAuditor
from weekly_setup import WeeklyPriceZone


def _evidence(
    code: EvidenceCode,
    bar_index: int,
    direction: EvidenceDirection,
    *,
    category: EvidenceCategory = EvidenceCategory.SIGNAL,
) -> Evidence:
    return Evidence(
        code=code,
        category=category,
        direction=direction,
        strength=0.8,
        weight=1.0,
        observation=str(code),
        description="audit fixture",
        bar_index=bar_index,
        week_beginning=f"W{bar_index:03d}",
    )


def _qualification(
    *,
    direction: PatternQualification = PatternQualification.PERSISTENT_BULLISH,
    actionable: bool = True,
    bars: tuple[int, ...] = (1, 5, 9),
    reason: str = "legacy qualification",
) -> PatternQualificationResult:
    if direction is PatternQualification.UNQUALIFIED:
        return PatternQualificationResult(
            qualification=direction,
            is_actionable_evidence=False,
            reason=reason,
        )
    code = (
        EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING
        if direction is PatternQualification.PERSISTENT_BULLISH
        else EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING
    )
    return PatternQualificationResult(
        qualification=direction,
        is_actionable_evidence=actionable,
        reason=reason,
        evidence_codes=tuple(code for _ in bars),
        evidence_bar_indices=bars,
    )


def _candidate(
    *,
    bar_index: int = 9,
    qualification_result: PatternQualificationResult | None = None,
    campaign_evidence: tuple[Evidence, ...] = (),
    target_bar_evidence: tuple[Evidence, ...] = (),
    qualifying_evidence: tuple[Evidence, ...] = (),
    scoring_evidence: tuple[Evidence, ...] = (),
    scoring_age: int | None = None,
    net_pressure: float = 0.4,
    confidence: float = 0.8,
    signal_bar_anomaly: bool = False,
) -> ScannerCandidate:
    qualification_result = qualification_result or _qualification()
    context = SimpleNamespace(
        trend=SimpleNamespace(
            direction=TrendDirection.UP,
            state=TrendState.HEALTHY,
        ),
        structural_pattern=StructuralPattern.IMPROVING,
        structural_swings=(),
    )
    evidence = EvidenceResult(context=context, evidence=campaign_evidence)  # type: ignore[arg-type]
    scores = ProfessionalScore(
        trend=0.7,
        supply=max(0.0, 0.5 - net_pressure / 2),
        demand=max(0.0, 0.5 + net_pressure / 2),
        effort=0.6,
        strength=0.8,
        weakness=0.2,
        confidence=confidence,
    )
    professional = ProfessionalScoreResult(scores=scores, evidence=scoring_evidence)
    scoring_bar_index = max((item.bar_index for item in scoring_evidence), default=None)
    if scoring_age is None and scoring_bar_index is not None:
        scoring_age = bar_index - scoring_bar_index

    return ScannerCandidate(
        evidence=evidence,
        professional=professional,
        qualification_result=qualification_result,
        target_bar_evidence=target_bar_evidence,
        campaign_evidence=campaign_evidence,
        qualifying_evidence=qualifying_evidence,
        scoring_evidence=scoring_evidence,
        scoring_bar_index=scoring_bar_index,
        scoring_evidence_age=scoring_age,
        bar_index=bar_index,
        week=f"W{bar_index:03d}",
        signal_bar_anomaly=signal_bar_anomaly,
        signal_bar_anomaly_reason="fixture anomaly" if signal_bar_anomaly else None,
    )


def test_audit_mirrors_actionable_legacy_gate_without_changing_it() -> None:
    structural = tuple(
        _evidence(
            EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING,
            bar,
            EvidenceDirection.BULLISH,
            category=EvidenceCategory.TREND,
        )
        for bar in (1, 5, 9)
    )
    no_supply = _evidence(
        EvidenceCode.NO_SUPPLY,
        9,
        EvidenceDirection.BULLISH,
        category=EvidenceCategory.DEMAND,
    )
    campaign = structural + (no_supply,)
    candidate = _candidate(
        campaign_evidence=campaign,
        target_bar_evidence=(structural[-1], no_supply),
        qualifying_evidence=structural,
        scoring_evidence=(no_supply,),
    )

    support = WeeklyPriceZone(lower=95.0, upper=100.0)
    audit = WeeklyDecisionGateAuditor.audit(
        symbol="lt.ns",
        candidate=candidate,
        support_zone=support,
    )

    assert audit.symbol == "LT.NS"
    assert audit.legacy_qualification is PatternQualification.PERSISTENT_BULLISH
    assert audit.legacy_actionable is candidate.actionable is True
    assert audit.legacy_qualification_reason == candidate.qualification_result.reason
    assert audit.legacy_candidate_reason == candidate.reason
    assert audit.structural_qualification_current is True
    assert audit.aligned_named_vsa_present is True
    assert audit.opposing_named_vsa_present is False
    assert audit.gate_blockers == ()
    assert audit.trend_direction is TrendDirection.UP
    assert audit.trend_state is TrendState.HEALTHY
    assert audit.structural_pattern is StructuralPattern.IMPROVING
    assert audit.support_zone == support


def test_recent_evidence_is_bounded_and_future_evidence_is_excluded() -> None:
    old = _evidence(EvidenceCode.NO_SUPPLY, 9, EvidenceDirection.BULLISH)
    recent = _evidence(EvidenceCode.DEMAND_COMING_IN, 12, EvidenceDirection.BULLISH)
    current = _evidence(EvidenceCode.INCREASING_DEMAND, 20, EvidenceDirection.BULLISH)
    future = _evidence(EvidenceCode.TEST, 21, EvidenceDirection.BULLISH)
    structural = tuple(
        _evidence(
            EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING,
            bar,
            EvidenceDirection.BULLISH,
            category=EvidenceCategory.TREND,
        )
        for bar in (12, 16, 20)
    )
    campaign = (old, recent, current, future) + structural
    candidate = _candidate(
        bar_index=20,
        qualification_result=_qualification(bars=(12, 16, 20)),
        campaign_evidence=campaign,
        target_bar_evidence=(current, structural[-1]),
        qualifying_evidence=structural,
        scoring_evidence=(current,),
    )

    audit = WeeklyDecisionGateAuditor.audit(symbol="TEST.NS", candidate=candidate)

    recent_indices = tuple(item.bar_index for item in audit.recent_evidence)
    assert 9 not in recent_indices
    assert 12 in recent_indices
    assert 20 in recent_indices
    assert 21 not in recent_indices
    assert tuple(item.bar_index for item in audit.current_evidence) == (20, 20)


def test_read_only_effort_result_and_absorption_are_exposed_not_promoted() -> None:
    effort = _evidence(
        EvidenceCode.EFFORT_GT_RESULT,
        9,
        EvidenceDirection.BULLISH,
        category=EvidenceCategory.EFFORT,
    )
    absorption = _evidence(
        EvidenceCode.ABSORPTION,
        9,
        EvidenceDirection.BULLISH,
        category=EvidenceCategory.ABSORPTION,
    )
    structural = tuple(
        _evidence(
            EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING,
            bar,
            EvidenceDirection.BULLISH,
            category=EvidenceCategory.TREND,
        )
        for bar in (1, 5, 9)
    )
    invalidated = _qualification(
        actionable=False,
        reason="legacy missing VSA confirmation",
    )
    candidate = _candidate(
        qualification_result=invalidated,
        campaign_evidence=structural + (effort, absorption),
        target_bar_evidence=(structural[-1], effort, absorption),
        qualifying_evidence=structural,
        scoring_evidence=(),
    )

    audit = WeeklyDecisionGateAuditor.audit(symbol="TEST.NS", candidate=candidate)

    assert audit.effort_result_evidence == (effort,)
    assert audit.absorption_evidence == (absorption,)
    assert audit.aligned_named_vsa_present is False
    assert audit.legacy_actionable is False
    assert audit.gate_blockers == (
        LegacyGateBlocker.NAMED_VSA_CONFIRMATION_MISSING,
    )


def test_opposing_named_vsa_is_reported_as_legacy_blocker() -> None:
    structural = tuple(
        _evidence(
            EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING,
            bar,
            EvidenceDirection.BULLISH,
            category=EvidenceCategory.TREND,
        )
        for bar in (1, 5, 9)
    )
    no_demand = _evidence(
        EvidenceCode.NO_DEMAND,
        9,
        EvidenceDirection.BEARISH,
        category=EvidenceCategory.SUPPLY,
    )
    invalidated = _qualification(
        actionable=False,
        reason="legacy VSA conflict",
    )
    candidate = _candidate(
        qualification_result=invalidated,
        campaign_evidence=structural + (no_demand,),
        target_bar_evidence=(structural[-1], no_demand),
        qualifying_evidence=structural,
        scoring_evidence=(no_demand,),
    )

    audit = WeeklyDecisionGateAuditor.audit(symbol="TEST.NS", candidate=candidate)

    assert audit.opposing_named_vsa_present is True
    assert audit.aligned_named_vsa_present is False
    assert audit.gate_blockers == (
        LegacyGateBlocker.OPPOSING_NAMED_VSA_PRESENT,
    )
    assert audit.legacy_actionable is False


def test_fresh_named_vsa_can_support_legacy_continuation_after_structural_event() -> None:
    structural = tuple(
        _evidence(
            EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING,
            bar,
            EvidenceDirection.BULLISH,
            category=EvidenceCategory.TREND,
        )
        for bar in (1, 5, 9)
    )
    demand = _evidence(
        EvidenceCode.DEMAND_COMING_IN,
        10,
        EvidenceDirection.BULLISH,
        category=EvidenceCategory.DEMAND,
    )
    candidate = _candidate(
        bar_index=10,
        qualification_result=_qualification(bars=(1, 5, 9)),
        campaign_evidence=structural + (demand,),
        target_bar_evidence=(demand,),
        qualifying_evidence=structural,
        scoring_evidence=(demand,),
    )

    audit = WeeklyDecisionGateAuditor.audit(symbol="TEST.NS", candidate=candidate)

    assert audit.structural_qualification_current is False
    assert audit.aligned_named_vsa_present is True
    assert audit.gate_blockers == ()
    assert audit.legacy_actionable is True


def test_stale_named_vsa_is_identified_before_directional_support() -> None:
    structural = tuple(
        _evidence(
            EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING,
            bar,
            EvidenceDirection.BULLISH,
            category=EvidenceCategory.TREND,
        )
        for bar in (12, 16, 20)
    )
    stale = _evidence(EvidenceCode.NO_SUPPLY, 15, EvidenceDirection.BULLISH)
    invalidated = _qualification(
        actionable=False,
        bars=(12, 16, 20),
        reason="legacy VSA stale",
    )
    candidate = _candidate(
        bar_index=20,
        qualification_result=invalidated,
        campaign_evidence=structural + (stale,),
        target_bar_evidence=(structural[-1],),
        qualifying_evidence=structural,
        scoring_evidence=(stale,),
        scoring_age=5,
    )

    audit = WeeklyDecisionGateAuditor.audit(symbol="TEST.NS", candidate=candidate)

    assert audit.scoring_evidence_age == 5
    assert audit.gate_blockers == (
        LegacyGateBlocker.NAMED_VSA_CONFIRMATION_STALE,
    )


def test_unqualified_zero_confidence_and_anomaly_remain_observable() -> None:
    qualification = _qualification(
        direction=PatternQualification.UNQUALIFIED,
        reason="no persistence",
    )
    candidate = _candidate(
        qualification_result=qualification,
        confidence=0.0,
        signal_bar_anomaly=True,
    )

    audit = WeeklyDecisionGateAuditor.audit(symbol="TEST.NS", candidate=candidate)

    assert audit.gate_blockers == (
        LegacyGateBlocker.QUALIFICATION_MISSING,
        LegacyGateBlocker.SIGNAL_BAR_ANOMALY,
    )
    assert audit.professional_confidence == 0.0
    assert audit.legacy_candidate_reason == "fixture anomaly"


def test_empty_symbol_is_rejected() -> None:
    candidate = _candidate()

    with pytest.raises(ValueError, match="symbol cannot be empty"):
        WeeklyDecisionGateAuditor.audit(symbol="   ", candidate=candidate)
