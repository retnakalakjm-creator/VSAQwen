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
from weekly_replay_comparison import (
    WeeklyDirectionAgreement,
    WeeklyReplayBucket,
    WeeklyReplayComparisonEngine,
    WeeklyReplayPriceBar,
)
from weekly_thesis import ShadowWeeklyThesisState


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
        description="weekly replay comparison fixture",
        bar_index=bar_index,
        week_beginning=f"W{bar_index:03d}",
    )


def _audit(
    bar_index: int,
    *,
    trend_direction: TrendDirection = TrendDirection.UP,
    trend_state: TrendState = TrendState.HEALTHY,
    structural_pattern: StructuralPattern = StructuralPattern.IMPROVING,
    current_evidence: tuple[Evidence, ...] = (),
    recent_evidence: tuple[Evidence, ...] | None = None,
    progression_events: tuple[Evidence, ...] = (),
    effort_result_evidence: tuple[Evidence, ...] = (),
    absorption_evidence: tuple[Evidence, ...] = (),
    qualification: PatternQualification = PatternQualification.UNQUALIFIED,
    legacy_actionable: bool = False,
    net_pressure: float = 0.4,
    symbol: str = "TEST.NS",
) -> WeeklyDecisionGateAuditRecord:
    recent = current_evidence if recent_evidence is None else recent_evidence
    qualified = qualification is not PatternQualification.UNQUALIFIED
    blockers = () if legacy_actionable else (LegacyGateBlocker.QUALIFICATION_MISSING,)
    return WeeklyDecisionGateAuditRecord(
        symbol=symbol,
        week=f"W{bar_index:03d}",
        bar_index=bar_index,
        trend_direction=trend_direction,
        trend_state=trend_state,
        structural_pattern=structural_pattern,
        structural_swing_lineage=(),
        structural_progression_events=progression_events,
        legacy_qualification=qualification,
        legacy_qualification_reason="fixture qualification",
        legacy_candidate_reason="fixture candidate",
        legacy_qualification_actionable_evidence=qualified,
        legacy_actionable=legacy_actionable,
        structural_qualification_current=qualified,
        qualifying_evidence=progression_events if qualified else (),
        scoring_evidence=current_evidence if qualified else (),
        scoring_evidence_age=0 if qualified and current_evidence else None,
        current_evidence=current_evidence,
        recent_evidence=recent,
        campaign_evidence=recent,
        effort_result_evidence=effort_result_evidence,
        absorption_evidence=absorption_evidence,
        bullish_named_vsa_evidence=(),
        bearish_named_vsa_evidence=(),
        aligned_named_vsa_present=False,
        opposing_named_vsa_present=False,
        professional_pressure_conflict=False,
        professional_strength=0.7,
        professional_weakness=0.3,
        professional_net_strength=0.4,
        professional_net_pressure=net_pressure,
        professional_confidence=0.8,
        gate_blockers=blockers,
    )


def _price(
    bar_index: int,
    *,
    high: float = 101.0,
    low: float = 99.0,
    close: float = 100.0,
) -> WeeklyReplayPriceBar:
    return WeeklyReplayPriceBar(
        week=f"W{bar_index:03d}",
        bar_index=bar_index,
        high=high,
        low=low,
        close=close,
    )


def test_replay_exposes_all_four_legacy_vs_shadow_buckets() -> None:
    demand_10 = _evidence(
        EvidenceCode.DEMAND_COMING_IN,
        10,
        EvidenceDirection.BULLISH,
        EvidenceCategory.DEMAND,
    )
    demand_11 = _evidence(
        EvidenceCode.INCREASING_DEMAND,
        11,
        EvidenceDirection.BULLISH,
        EvidenceCategory.DEMAND,
    )

    audits = [
        _audit(10, current_evidence=(demand_10,)),
        _audit(
            11,
            current_evidence=(demand_11,),
            recent_evidence=(demand_10, demand_11),
            qualification=PatternQualification.PERSISTENT_BULLISH,
            legacy_actionable=True,
        ),
        _audit(
            12,
            structural_pattern=StructuralPattern.WEAKENING,
            current_evidence=(),
            recent_evidence=(demand_10, demand_11),
            qualification=PatternQualification.PERSISTENT_BULLISH,
            legacy_actionable=True,
        ),
        _audit(13, current_evidence=(), recent_evidence=()),
    ]

    report = WeeklyReplayComparisonEngine.compare(
        audits=audits,
        prices=[_price(index) for index in range(10, 14)],
        horizons_weeks=(1,),
    )

    assert [record.bucket for record in report.records] == [
        WeeklyReplayBucket.LEGACY_NO_SHADOW_YES,
        WeeklyReplayBucket.LEGACY_YES_SHADOW_YES,
        WeeklyReplayBucket.LEGACY_YES_SHADOW_NO,
        WeeklyReplayBucket.LEGACY_NO_SHADOW_NO,
    ]
    assert report.records[0].direction_agreement is WeeklyDirectionAgreement.SHADOW_ONLY
    assert report.records[1].direction_agreement is WeeklyDirectionAgreement.SAME
    assert report.records[2].shadow_state is ShadowWeeklyThesisState.BULLISH_CHALLENGED
    assert report.records[3].shadow_state is ShadowWeeklyThesisState.BULLISH_DEVELOPING
    assert {item.bucket: item.count for item in report.bucket_counts} == {
        WeeklyReplayBucket.LEGACY_YES_SHADOW_YES: 1,
        WeeklyReplayBucket.LEGACY_YES_SHADOW_NO: 1,
        WeeklyReplayBucket.LEGACY_NO_SHADOW_YES: 1,
        WeeklyReplayBucket.LEGACY_NO_SHADOW_NO: 1,
    }
    assert report.is_actionable is False


def test_decision_prefix_is_invariant_to_future_bars_and_future_prices() -> None:
    demand = _evidence(
        EvidenceCode.DEMAND_COMING_IN,
        10,
        EvidenceDirection.BULLISH,
        EvidenceCategory.DEMAND,
    )
    audits = [
        _audit(10, current_evidence=(demand,)),
        _audit(11, current_evidence=(), recent_evidence=(demand,)),
        _audit(12, current_evidence=(), recent_evidence=(demand,)),
    ]

    full = WeeklyReplayComparisonEngine.compare(
        audits=audits,
        prices=[
            _price(10, close=100.0),
            _price(11, high=160.0, low=80.0, close=150.0),
            _price(12, high=170.0, low=70.0, close=75.0),
        ],
        horizons_weeks=(1,),
    )
    prefix = WeeklyReplayComparisonEngine.compare(
        audits=audits[:2],
        prices=[_price(10, close=100.0), _price(11, close=100.0)],
        horizons_weeks=(1,),
    )

    for full_record, prefix_record in zip(full.records[:2], prefix.records):
        assert full_record.bucket is prefix_record.bucket
        assert full_record.shadow_state is prefix_record.shadow_state
        assert full_record.shadow_basis is prefix_record.shadow_basis
        assert full_record.shadow_direction is prefix_record.shadow_direction
        assert full_record.contradiction_state is prefix_record.contradiction_state

    assert (
        full.records[0].shadow_forward_outcomes[0].close_return_pct
        != prefix.records[0].shadow_forward_outcomes[0].close_return_pct
    )


def test_bullish_forward_outcome_reports_5_week_return_mfe_and_mae() -> None:
    demand = _evidence(
        EvidenceCode.DEMAND_COMING_IN,
        10,
        EvidenceDirection.BULLISH,
        EvidenceCategory.DEMAND,
    )
    audits = [_audit(10, current_evidence=(demand,))]
    audits.extend(_audit(index) for index in range(11, 16))
    prices = [
        _price(10, high=101.0, low=99.0, close=100.0),
        _price(11, high=105.0, low=98.0, close=104.0),
        _price(12, high=110.0, low=102.0, close=108.0),
        _price(13, high=107.0, low=95.0, close=96.0),
        _price(14, high=115.0, low=94.0, close=112.0),
        _price(15, high=120.0, low=90.0, close=110.0),
    ]

    report = WeeklyReplayComparisonEngine.compare(
        audits=audits,
        prices=prices,
        horizons_weeks=(5,),
    )
    outcome = report.records[0].shadow_forward_outcomes[0]

    assert outcome.complete is True
    assert outcome.available_weeks == 5
    assert outcome.close_return_pct == pytest.approx(10.0)
    assert outcome.maximum_favorable_excursion_pct == pytest.approx(20.0)
    assert outcome.maximum_adverse_excursion_pct == pytest.approx(-10.0)


def test_bearish_forward_outcome_is_direction_adjusted_symmetrically() -> None:
    supply = _evidence(
        EvidenceCode.SUPPLY_COMING_IN,
        10,
        EvidenceDirection.BEARISH,
        EvidenceCategory.SUPPLY,
    )
    audits = [
        _audit(
            10,
            trend_direction=TrendDirection.DOWN,
            structural_pattern=StructuralPattern.WEAKENING,
            current_evidence=(supply,),
            net_pressure=-0.4,
        )
    ]
    audits.extend(
        _audit(
            index,
            trend_direction=TrendDirection.DOWN,
            structural_pattern=StructuralPattern.WEAKENING,
            net_pressure=-0.4,
        )
        for index in range(11, 16)
    )
    prices = [
        _price(10, high=101.0, low=99.0, close=100.0),
        _price(11, high=103.0, low=95.0, close=97.0),
        _price(12, high=106.0, low=90.0, close=93.0),
        _price(13, high=110.0, low=85.0, close=88.0),
        _price(14, high=108.0, low=80.0, close=82.0),
        _price(15, high=107.0, low=81.0, close=90.0),
    ]

    report = WeeklyReplayComparisonEngine.compare(
        audits=audits,
        prices=prices,
        horizons_weeks=(5,),
    )
    outcome = report.records[0].shadow_forward_outcomes[0]

    assert outcome.close_return_pct == pytest.approx(10.0)
    assert outcome.maximum_favorable_excursion_pct == pytest.approx(20.0)
    assert outcome.maximum_adverse_excursion_pct == pytest.approx(-10.0)


def test_timing_summary_records_behavior_and_legacy_milestones() -> None:
    no_supply = _evidence(
        EvidenceCode.NO_SUPPLY,
        10,
        EvidenceDirection.BULLISH,
        EvidenceCategory.DEMAND,
    )
    progression_1 = _evidence(
        EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING,
        10,
        EvidenceDirection.BULLISH,
        EvidenceCategory.TREND,
    )
    demand = _evidence(
        EvidenceCode.DEMAND_COMING_IN,
        11,
        EvidenceDirection.BULLISH,
        EvidenceCategory.DEMAND,
    )
    effort = _evidence(
        EvidenceCode.EFFORT_RESULT,
        11,
        EvidenceDirection.BULLISH,
        EvidenceCategory.EFFORT,
    )
    absorption = _evidence(
        EvidenceCode.ABSORPTION,
        11,
        EvidenceDirection.BULLISH,
        EvidenceCategory.ABSORPTION,
    )
    progression_2 = _evidence(
        EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING,
        11,
        EvidenceDirection.BULLISH,
        EvidenceCategory.TREND,
    )
    progression_3 = _evidence(
        EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING,
        12,
        EvidenceDirection.BULLISH,
        EvidenceCategory.TREND,
    )

    audits = [
        _audit(
            10,
            current_evidence=(no_supply, progression_1),
            progression_events=(progression_1,),
        ),
        _audit(
            11,
            current_evidence=(demand, effort, absorption, progression_2),
            recent_evidence=(
                no_supply,
                progression_1,
                demand,
                effort,
                absorption,
                progression_2,
            ),
            progression_events=(progression_2,),
            effort_result_evidence=(effort,),
            absorption_evidence=(absorption,),
        ),
        _audit(
            12,
            current_evidence=(progression_3,),
            progression_events=(progression_3,),
            qualification=PatternQualification.PERSISTENT_BULLISH,
            legacy_actionable=False,
        ),
        _audit(
            13,
            qualification=PatternQualification.PERSISTENT_BULLISH,
            legacy_actionable=True,
        ),
    ]

    report = WeeklyReplayComparisonEngine.compare(
        audits=audits,
        prices=[_price(index) for index in range(10, 14)],
        horizons_weeks=(1,),
    )
    bullish = next(
        item for item in report.timing if item.direction is EvidenceDirection.BULLISH
    )

    assert bullish.first_opposing_pressure_reduction_bar_index == 10
    assert bullish.first_aligned_pressure_emergence_bar_index == 11
    assert bullish.first_supportive_effort_result_bar_index == 11
    assert bullish.first_absorption_or_rejection_bar_index == 11
    assert bullish.first_structural_progression_bar_index == 10
    assert bullish.second_structural_progression_bar_index == 11
    assert bullish.third_structural_progression_bar_index == 12
    assert bullish.first_legacy_qualification_bar_index == 12
    assert bullish.first_legacy_actionable_bar_index == 13
    assert bullish.first_shadow_supported_bar_index == 10
    assert bullish.shadow_supported_minus_legacy_actionable_weeks == -3


def test_subsequent_structural_confirmation_and_invalidation_are_attached_after_decision() -> None:
    demand = _evidence(
        EvidenceCode.DEMAND_COMING_IN,
        10,
        EvidenceDirection.BULLISH,
        EvidenceCategory.DEMAND,
    )
    progression = _evidence(
        EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING,
        11,
        EvidenceDirection.BULLISH,
        EvidenceCategory.TREND,
    )
    supply = _evidence(
        EvidenceCode.INCREASING_SUPPLY,
        12,
        EvidenceDirection.BEARISH,
        EvidenceCategory.SUPPLY,
    )

    audits = [
        _audit(
            10,
            current_evidence=(demand,),
            qualification=PatternQualification.PERSISTENT_BULLISH,
            legacy_actionable=True,
        ),
        _audit(
            11,
            current_evidence=(progression,),
            recent_evidence=(demand, progression),
            progression_events=(progression,),
        ),
        _audit(
            12,
            trend_direction=TrendDirection.DOWN,
            trend_state=TrendState.DEVELOPING,
            structural_pattern=StructuralPattern.WEAKENING,
            current_evidence=(supply,),
            recent_evidence=(demand, progression, supply),
            net_pressure=-0.5,
        ),
    ]

    report = WeeklyReplayComparisonEngine.compare(
        audits=audits,
        prices=[_price(index) for index in range(10, 13)],
        horizons_weeks=(1,),
    )
    record = report.records[0]

    assert record.bucket is WeeklyReplayBucket.LEGACY_YES_SHADOW_YES
    assert record.legacy_first_structural_confirmation_bar_index == 11
    assert record.shadow_first_structural_confirmation_bar_index == 11
    assert record.legacy_first_structural_invalidation_bar_index == 12
    assert record.shadow_first_structural_invalidation_bar_index == 12


def test_replay_validation_rejects_identity_and_horizon_errors() -> None:
    audit = _audit(10)

    with pytest.raises(ValueError, match="equal length"):
        WeeklyReplayComparisonEngine.compare(audits=[audit], prices=[])

    with pytest.raises(ValueError, match="price identity"):
        WeeklyReplayComparisonEngine.compare(
            audits=[audit],
            prices=[_price(11)],
        )

    with pytest.raises(ValueError, match="positive week counts"):
        WeeklyReplayComparisonEngine.compare(
            audits=[audit],
            prices=[_price(10)],
            horizons_weeks=(0,),
        )
