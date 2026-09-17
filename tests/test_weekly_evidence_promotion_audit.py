from __future__ import annotations

import pytest

from background.qualification import PatternQualification
from models import (
    Evidence,
    EvidenceCategory,
    EvidenceCode,
    EvidenceDirection,
    StructuralPattern,
    TrendDirection,
    TrendState,
)
from weekly_decision_audit import LegacyGateBlocker, WeeklyDecisionGateAuditRecord
from weekly_evidence_promotion_audit import (
    WeeklyEvidenceAuditPartition,
    WeeklyEvidencePromotionAuditEngine,
    WeeklyEvidencePromotionCandidate,
    WeeklyEvidencePromotionInput,
    WeeklyLocationRelation,
    WeeklyStructuralOutcome,
)
from weekly_replay_comparison import WeeklyReplayPriceBar
from weekly_setup import WeeklyPriceZone


_PROGRESSION_CODES = {
    EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING,
    EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING,
}
_EFFORT_CODES = {
    EvidenceCode.EFFORT_GT_RESULT,
    EvidenceCode.RESULT_GT_EFFORT,
    EvidenceCode.EFFORT_RESULT,
}


def _evidence(
    code: EvidenceCode,
    bar_index: int,
    direction: EvidenceDirection,
    category: EvidenceCategory,
) -> Evidence:
    return Evidence(
        code=code,
        category=category,
        direction=direction,
        strength=0.8,
        weight=1.0,
        observation=str(code),
        description="WF6 fixture",
        bar_index=bar_index,
        week_beginning=f"W{bar_index:03d}",
    )


def _audit(
    symbol: str,
    bar_index: int,
    *,
    trend_direction: TrendDirection = TrendDirection.UP,
    trend_state: TrendState = TrendState.HEALTHY,
    structural_pattern: StructuralPattern = StructuralPattern.IMPROVING,
    current: tuple[Evidence, ...] = (),
    recent: tuple[Evidence, ...] | None = None,
    support_zone: WeeklyPriceZone | None = None,
    resistance_zone: WeeklyPriceZone | None = None,
    qualification: PatternQualification = PatternQualification.UNQUALIFIED,
    legacy_actionable: bool = False,
) -> WeeklyDecisionGateAuditRecord:
    recent_evidence = current if recent is None else recent
    progression = tuple(item for item in recent_evidence if item.code in _PROGRESSION_CODES)
    effort = tuple(item for item in recent_evidence if item.code in _EFFORT_CODES)
    absorption = tuple(item for item in recent_evidence if item.code is EvidenceCode.ABSORPTION)
    return WeeklyDecisionGateAuditRecord(
        symbol=symbol,
        week=f"W{bar_index:03d}",
        bar_index=bar_index,
        trend_direction=trend_direction,
        trend_state=trend_state,
        structural_pattern=structural_pattern,
        structural_swing_lineage=(),
        structural_progression_events=progression,
        legacy_qualification=qualification,
        legacy_qualification_reason="WF6 fixture qualification",
        legacy_candidate_reason="WF6 fixture candidate",
        legacy_qualification_actionable_evidence=(
            qualification is not PatternQualification.UNQUALIFIED
        ),
        legacy_actionable=legacy_actionable,
        structural_qualification_current=False,
        qualifying_evidence=(),
        scoring_evidence=(),
        scoring_evidence_age=None,
        current_evidence=current,
        recent_evidence=recent_evidence,
        campaign_evidence=recent_evidence,
        effort_result_evidence=effort,
        absorption_evidence=absorption,
        bullish_named_vsa_evidence=(),
        bearish_named_vsa_evidence=(),
        aligned_named_vsa_present=False,
        opposing_named_vsa_present=False,
        professional_pressure_conflict=False,
        professional_strength=0.7,
        professional_weakness=0.3,
        professional_net_strength=0.4,
        professional_net_pressure=(
            0.4 if trend_direction is TrendDirection.UP else -0.4
        ),
        professional_confidence=0.8,
        support_zone=support_zone,
        resistance_zone=resistance_zone,
        gate_blockers=(LegacyGateBlocker.QUALIFICATION_MISSING,),
    )


def _price(bar_index: int, close: float) -> WeeklyReplayPriceBar:
    return WeeklyReplayPriceBar(
        week=f"W{bar_index:03d}",
        bar_index=bar_index,
        high=close * 1.02,
        low=close * 0.98,
        close=close,
    )


def _dataset(
    symbol: str,
    audits: tuple[WeeklyDecisionGateAuditRecord, ...],
    closes: tuple[float, ...],
    *,
    out_of_sample_start_bar_index: int | None = None,
) -> WeeklyEvidencePromotionInput:
    return WeeklyEvidencePromotionInput(
        symbol=symbol,
        audits=audits,
        prices=tuple(
            _price(audit.bar_index, close)  # type: ignore[arg-type]
            for audit, close in zip(audits, closes)
        ),
        out_of_sample_start_bar_index=out_of_sample_start_bar_index,
    )


def _observation(report, bar_index, candidate, evidence_code=None):
    return next(
        item
        for item in report.observations
        if item.bar_index == bar_index
        and item.candidate is candidate
        and item.evidence_code is evidence_code
    )


def test_candidate_presence_uses_current_bar_and_campaign_context_uses_prior_bounded_evidence() -> None:
    demand = _evidence(
        EvidenceCode.DEMAND_COMING_IN,
        10,
        EvidenceDirection.BULLISH,
        EvidenceCategory.DEMAND,
    )
    old_absorption = _evidence(
        EvidenceCode.ABSORPTION,
        10,
        EvidenceDirection.BULLISH,
        EvidenceCategory.ABSORPTION,
    )
    effort = _evidence(
        EvidenceCode.EFFORT_RESULT,
        11,
        EvidenceDirection.BULLISH,
        EvidenceCategory.EFFORT,
    )
    audits = (
        _audit("TEST.NS", 10, current=(demand, old_absorption)),
        _audit(
            "TEST.NS",
            11,
            current=(effort,),
            recent=(demand, old_absorption, effort),
        ),
        _audit("TEST.NS", 12, current=(), recent=(demand, old_absorption, effort)),
    )

    report = WeeklyEvidencePromotionAuditEngine.audit(
        datasets=(_dataset("TEST.NS", audits, (100.0, 105.0, 110.0)),),
        horizons_weeks=(1,),
    )

    effort_obs = _observation(
        report,
        11,
        WeeklyEvidencePromotionCandidate.EFFORT_RESULT,
    )
    absorption_obs = _observation(
        report,
        11,
        WeeklyEvidencePromotionCandidate.ABSORPTION,
    )
    campaign_obs = _observation(
        report,
        11,
        WeeklyEvidencePromotionCandidate.CAMPAIGN_CONTEXT,
    )

    assert effort_obs.present is True
    assert effort_obs.evidence_codes == (EvidenceCode.EFFORT_RESULT,)
    assert absorption_obs.present is False
    assert campaign_obs.present is True
    assert campaign_obs.prior_aligned_evidence_count == 2
    assert EvidenceCode.ABSORPTION in campaign_obs.evidence_codes
    assert report.is_actionable is False


def test_named_vsa_is_audited_per_code_and_per_regime() -> None:
    no_supply = _evidence(
        EvidenceCode.NO_SUPPLY,
        10,
        EvidenceDirection.BULLISH,
        EvidenceCategory.DEMAND,
    )
    audits = (
        _audit("TEST.NS", 10, current=(no_supply,)),
        _audit(
            "TEST.NS",
            11,
            trend_state=TrendState.CORRECTING,
            structural_pattern=StructuralPattern.STABLE,
        ),
        _audit("TEST.NS", 12),
    )

    report = WeeklyEvidencePromotionAuditEngine.audit(
        datasets=(_dataset("TEST.NS", audits, (100.0, 101.0, 102.0)),),
        horizons_weeks=(1,),
    )

    observation = _observation(
        report,
        10,
        WeeklyEvidencePromotionCandidate.NAMED_VSA,
        EvidenceCode.NO_SUPPLY,
    )
    assert observation.present is True

    summaries = tuple(
        item
        for item in report.summaries
        if item.candidate is WeeklyEvidencePromotionCandidate.NAMED_VSA
        and item.evidence_code is EvidenceCode.NO_SUPPLY
        and item.direction is EvidenceDirection.BULLISH
        and item.horizon_weeks == 1
        and item.partition is WeeklyEvidenceAuditPartition.ALL
    )
    assert any(item.regime is None for item in summaries)
    assert any(
        item.regime is not None
        and item.regime.trend_state is TrendState.HEALTHY
        and item.regime.structural_pattern is StructuralPattern.IMPROVING
        for item in summaries
    )


def test_location_is_continuous_and_threshold_sensitivity_is_caller_selected() -> None:
    demand = _evidence(
        EvidenceCode.DEMAND_COMING_IN,
        10,
        EvidenceDirection.BULLISH,
        EvidenceCategory.DEMAND,
    )
    audits = (
        _audit(
            "TEST.NS",
            10,
            current=(demand,),
            support_zone=WeeklyPriceZone(lower=95.0, upper=100.0),
        ),
        _audit("TEST.NS", 11),
        _audit("TEST.NS", 12),
    )

    report = WeeklyEvidencePromotionAuditEngine.audit(
        datasets=(_dataset("TEST.NS", audits, (101.0, 103.0, 104.0)),),
        horizons_weeks=(1,),
        location_distance_thresholds_pct=(0.5, 1.0),
    )

    location = _observation(
        report,
        10,
        WeeklyEvidencePromotionCandidate.LOCATION,
    )
    assert location.eligible is True
    assert location.present is False
    assert location.location_relation is WeeklyLocationRelation.ABOVE
    assert location.location_distance_pct == pytest.approx((1.0 / 101.0) * 100.0)

    half = next(
        item
        for item in report.location_sensitivity
        if item.direction is EvidenceDirection.BULLISH
        and item.horizon_weeks == 1
        and item.threshold_pct == 0.5
    )
    one = next(
        item
        for item in report.location_sensitivity
        if item.direction is EvidenceDirection.BULLISH
        and item.horizon_weeks == 1
        and item.threshold_pct == 1.0
    )
    assert half.supportive_near_zone.observation_count == 0
    assert one.supportive_near_zone.observation_count == 1


def test_present_vs_absent_summary_uses_only_complete_direction_adjusted_outcomes() -> None:
    effort = _evidence(
        EvidenceCode.EFFORT_RESULT,
        10,
        EvidenceDirection.BULLISH,
        EvidenceCategory.EFFORT,
    )
    audits = (
        _audit("TEST.NS", 10, current=(effort,)),
        _audit("TEST.NS", 11),
        _audit("TEST.NS", 12),
    )

    report = WeeklyEvidencePromotionAuditEngine.audit(
        datasets=(_dataset("TEST.NS", audits, (100.0, 110.0, 110.0)),),
        horizons_weeks=(1,),
    )

    summary = next(
        item
        for item in report.summaries
        if item.candidate is WeeklyEvidencePromotionCandidate.EFFORT_RESULT
        and item.evidence_code is None
        and item.direction is EvidenceDirection.BULLISH
        and item.horizon_weeks == 1
        and item.partition is WeeklyEvidenceAuditPartition.ALL
        and item.regime is None
    )

    assert summary.present.observation_count == 1
    assert summary.present.complete_outcome_count == 1
    assert summary.present.mean_close_return_pct == pytest.approx(10.0)
    assert summary.absent.observation_count == 2
    assert summary.absent.complete_outcome_count == 1
    assert summary.absent.mean_close_return_pct == pytest.approx(0.0)
    assert summary.mean_close_return_delta_pct == pytest.approx(10.0)


def test_time_split_is_explicit_and_does_not_change_candidate_presence() -> None:
    demand = _evidence(
        EvidenceCode.DEMAND_COMING_IN,
        10,
        EvidenceDirection.BULLISH,
        EvidenceCategory.DEMAND,
    )
    audits = (
        _audit("TEST.NS", 10, current=(demand,)),
        _audit("TEST.NS", 11),
        _audit("TEST.NS", 12),
    )
    dataset = _dataset(
        "TEST.NS",
        audits,
        (100.0, 101.0, 102.0),
        out_of_sample_start_bar_index=12,
    )

    report = WeeklyEvidencePromotionAuditEngine.audit(
        datasets=(dataset,),
        horizons_weeks=(1,),
    )

    bar10 = _observation(
        report,
        10,
        WeeklyEvidencePromotionCandidate.CAMPAIGN_CONTEXT,
    )
    bar12 = _observation(
        report,
        12,
        WeeklyEvidencePromotionCandidate.CAMPAIGN_CONTEXT,
    )
    assert bar10.partition is WeeklyEvidenceAuditPartition.IN_SAMPLE
    assert bar12.partition is WeeklyEvidenceAuditPartition.OUT_OF_SAMPLE
    assert any(
        item.partition is WeeklyEvidenceAuditPartition.IN_SAMPLE
        for item in report.summaries
    )
    assert any(
        item.partition is WeeklyEvidenceAuditPartition.OUT_OF_SAMPLE
        for item in report.summaries
    )


def test_later_aligned_progression_is_attached_as_outcome_not_used_to_create_current_candidate() -> None:
    effort = _evidence(
        EvidenceCode.EFFORT_RESULT,
        10,
        EvidenceDirection.BULLISH,
        EvidenceCategory.EFFORT,
    )
    progression = _evidence(
        EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING,
        11,
        EvidenceDirection.BULLISH,
        EvidenceCategory.TREND,
    )
    audits = (
        _audit("TEST.NS", 10, current=(effort,)),
        _audit("TEST.NS", 11, current=(progression,), recent=(effort, progression)),
        _audit("TEST.NS", 12, recent=(effort, progression)),
    )

    report = WeeklyEvidencePromotionAuditEngine.audit(
        datasets=(_dataset("TEST.NS", audits, (100.0, 102.0, 104.0)),),
        horizons_weeks=(1,),
    )

    effort_observation = _observation(
        report,
        10,
        WeeklyEvidencePromotionCandidate.EFFORT_RESULT,
    )
    progression_observation = _observation(
        report,
        10,
        WeeklyEvidencePromotionCandidate.PROFESSIONAL_SWING_PROGRESSION,
        EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING,
    )
    assert effort_observation.present is True
    assert effort_observation.structural_outcome is WeeklyStructuralOutcome.CONFIRMED_FIRST
    assert progression_observation.present is False


def test_future_price_changes_outcomes_but_not_frozen_candidate_presence() -> None:
    effort = _evidence(
        EvidenceCode.EFFORT_RESULT,
        10,
        EvidenceDirection.BULLISH,
        EvidenceCategory.EFFORT,
    )
    audits = (
        _audit("TEST.NS", 10, current=(effort,)),
        _audit("TEST.NS", 11),
        _audit("TEST.NS", 12),
    )

    rising = WeeklyEvidencePromotionAuditEngine.audit(
        datasets=(_dataset("TEST.NS", audits, (100.0, 110.0, 120.0)),),
        horizons_weeks=(1,),
    )
    falling = WeeklyEvidencePromotionAuditEngine.audit(
        datasets=(_dataset("TEST.NS", audits, (100.0, 90.0, 80.0)),),
        horizons_weeks=(1,),
    )

    rising_obs = _observation(
        rising,
        10,
        WeeklyEvidencePromotionCandidate.EFFORT_RESULT,
    )
    falling_obs = _observation(
        falling,
        10,
        WeeklyEvidencePromotionCandidate.EFFORT_RESULT,
    )
    assert rising_obs.present == falling_obs.present is True
    assert rising_obs.evidence_codes == falling_obs.evidence_codes
    assert rising_obs.partition == falling_obs.partition
    assert rising_obs.regime == falling_obs.regime
    assert rising_obs.outcomes[0].close_return_pct == pytest.approx(10.0)
    assert falling_obs.outcomes[0].close_return_pct == pytest.approx(-10.0)


def test_multiple_symbols_produce_leave_one_symbol_out_descriptive_checks() -> None:
    effort_a = _evidence(
        EvidenceCode.EFFORT_RESULT,
        10,
        EvidenceDirection.BULLISH,
        EvidenceCategory.EFFORT,
    )
    effort_b = _evidence(
        EvidenceCode.EFFORT_RESULT,
        10,
        EvidenceDirection.BULLISH,
        EvidenceCategory.EFFORT,
    )
    audits_a = (
        _audit("AAA.NS", 10, current=(effort_a,)),
        _audit("AAA.NS", 11),
        _audit("AAA.NS", 12),
    )
    audits_b = (
        _audit("BBB.NS", 10, current=(effort_b,)),
        _audit("BBB.NS", 11),
        _audit("BBB.NS", 12),
    )

    report = WeeklyEvidencePromotionAuditEngine.audit(
        datasets=(
            _dataset("AAA.NS", audits_a, (100.0, 105.0, 105.0)),
            _dataset("BBB.NS", audits_b, (100.0, 95.0, 95.0)),
        ),
        horizons_weeks=(1,),
    )

    summaries = tuple(
        item
        for item in report.leave_one_symbol_out
        if item.candidate is WeeklyEvidencePromotionCandidate.EFFORT_RESULT
        and item.evidence_code is None
        and item.direction is EvidenceDirection.BULLISH
        and item.horizon_weeks == 1
    )
    assert {item.held_out_symbol for item in summaries} == {"AAA.NS", "BBB.NS"}
    aaa = next(item for item in summaries if item.held_out_symbol == "AAA.NS")
    bbb = next(item for item in summaries if item.held_out_symbol == "BBB.NS")
    assert aaa.held_out_mean_close_delta_pct == pytest.approx(5.0)
    assert bbb.held_out_mean_close_delta_pct == pytest.approx(-5.0)


def test_validation_rejects_duplicate_symbols_invalid_horizons_and_negative_location_thresholds() -> None:
    audits = (
        _audit("TEST.NS", 10),
        _audit("TEST.NS", 11),
    )
    dataset = _dataset("TEST.NS", audits, (100.0, 101.0))

    with pytest.raises(ValueError, match="unique symbols"):
        WeeklyEvidencePromotionAuditEngine.audit(
            datasets=(dataset, dataset),
            horizons_weeks=(1,),
        )

    with pytest.raises(ValueError, match="positive week counts"):
        WeeklyEvidencePromotionAuditEngine.audit(
            datasets=(dataset,),
            horizons_weeks=(0,),
        )

    with pytest.raises(ValueError, match="non-negative"):
        WeeklyEvidencePromotionAuditEngine.audit(
            datasets=(dataset,),
            horizons_weeks=(1,),
            location_distance_thresholds_pct=(-1.0,),
        )
