from __future__ import annotations

import json

import pandas as pd

from audit.weekly_actionability_counterfactual_runner import (
    write_weekly_actionability_counterfactual_bundle,
)
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
from weekly_actionability_counterfactual import (
    WeeklyActionabilityCounterfactualEngine,
    WeeklyActionabilityCounterfactualInput,
    WeeklyCounterfactualDisposition,
    WeeklyCounterfactualPartition,
    WeeklyCounterfactualPolicy,
    WeeklyCounterfactualReason,
)
from weekly_decision_audit import WeeklyDecisionGateAuditRecord
from weekly_replay_comparison import WeeklyReplayPriceBar
from weekly_thesis import ShadowWeeklyThesisState


def _evidence(
    bar_index: int,
    *,
    bullish: bool,
) -> Evidence:
    return Evidence(
        code=(EvidenceCode.DEMAND_COMING_IN if bullish else EvidenceCode.SUPPLY_COMING_IN),
        category=(EvidenceCategory.DEMAND if bullish else EvidenceCategory.SUPPLY),
        direction=(EvidenceDirection.BULLISH if bullish else EvidenceDirection.BEARISH),
        strength=0.8,
        weight=1.0,
        observation="fixture",
        description="WF7A fixture",
        bar_index=bar_index,
        week_beginning=f"W{bar_index}",
    )


def _audit(
    bar_index: int,
    *,
    trend_direction: TrendDirection,
    trend_state: TrendState,
    structural_pattern: StructuralPattern,
    current: Evidence,
    recent: tuple[Evidence, ...],
    pressure: float,
) -> WeeklyDecisionGateAuditRecord:
    return WeeklyDecisionGateAuditRecord(
        symbol="TEST.NS",
        week=f"W{bar_index}",
        bar_index=bar_index,
        trend_direction=trend_direction,
        trend_state=trend_state,
        structural_pattern=structural_pattern,
        structural_swing_lineage=(),
        structural_progression_events=(),
        legacy_qualification=PatternQualification.PERSISTENT_BULLISH,
        legacy_qualification_reason="fixture bullish qualification",
        legacy_candidate_reason="fixture actionable",
        legacy_qualification_actionable_evidence=True,
        legacy_actionable=True,
        structural_qualification_current=True,
        qualifying_evidence=(),
        scoring_evidence=(current,),
        scoring_evidence_age=0,
        current_evidence=(current,),
        recent_evidence=recent,
        campaign_evidence=recent,
        effort_result_evidence=(),
        absorption_evidence=(),
        bullish_named_vsa_evidence=(),
        bearish_named_vsa_evidence=(),
        aligned_named_vsa_present=True,
        opposing_named_vsa_present=False,
        professional_pressure_conflict=False,
        professional_strength=0.8,
        professional_weakness=0.2,
        professional_net_strength=0.6,
        professional_net_pressure=pressure,
        professional_confidence=0.8,
    )


def _dataset(symbol: str = "TEST.NS") -> WeeklyActionabilityCounterfactualInput:
    evidence = {
        20: _evidence(20, bullish=True),
        21: _evidence(21, bullish=False),
        22: _evidence(22, bullish=False),
        23: _evidence(23, bullish=False),
        24: _evidence(24, bullish=False),
        25: _evidence(25, bullish=False),
    }
    audits = (
        _audit(
            20,
            trend_direction=TrendDirection.UP,
            trend_state=TrendState.HEALTHY,
            structural_pattern=StructuralPattern.IMPROVING,
            current=evidence[20],
            recent=(evidence[20],),
            pressure=0.4,
        ),
        _audit(
            21,
            trend_direction=TrendDirection.UP,
            trend_state=TrendState.HEALTHY,
            structural_pattern=StructuralPattern.IMPROVING,
            current=evidence[21],
            recent=(evidence[20], evidence[21]),
            pressure=0.4,
        ),
        _audit(
            22,
            trend_direction=TrendDirection.UP,
            trend_state=TrendState.HEALTHY,
            structural_pattern=StructuralPattern.IMPROVING,
            current=evidence[22],
            recent=(evidence[20], evidence[21], evidence[22]),
            pressure=0.4,
        ),
        _audit(
            23,
            trend_direction=TrendDirection.UP,
            trend_state=TrendState.REVERSING,
            structural_pattern=StructuralPattern.IMPROVING,
            current=evidence[23],
            recent=(evidence[20], evidence[21], evidence[22], evidence[23]),
            pressure=-0.4,
        ),
        _audit(
            24,
            trend_direction=TrendDirection.DOWN,
            trend_state=TrendState.REVERSING,
            structural_pattern=StructuralPattern.WEAKENING,
            current=evidence[24],
            recent=(evidence[20], evidence[21], evidence[22], evidence[23], evidence[24]),
            pressure=-0.4,
        ),
        _audit(
            25,
            trend_direction=TrendDirection.DOWN,
            trend_state=TrendState.HEALTHY,
            structural_pattern=StructuralPattern.WEAKENING,
            current=evidence[25],
            recent=(evidence[21], evidence[22], evidence[23], evidence[24], evidence[25]),
            pressure=-0.4,
        ),
    )
    if symbol != "TEST.NS":
        audits = tuple(
            WeeklyDecisionGateAuditRecord(
                **{
                    field: (symbol if field == "symbol" else getattr(item, field))
                    for field in item.__dataclass_fields__
                }
            )
            for item in audits
        )

    closes = (100.0, 101.0, 99.0, 97.0, 94.0, 92.0)
    prices = tuple(
        WeeklyReplayPriceBar(
            week=f"W{20 + position}",
            bar_index=20 + position,
            high=close + 2.0,
            low=close - 2.0,
            close=close,
        )
        for position, close in enumerate(closes)
    )
    return WeeklyActionabilityCounterfactualInput(
        symbol=symbol,
        audits=audits,
        prices=prices,
        out_of_sample_start_bar_index=24,
    )


def _observation(report, bar_index, policy):
    return next(
        item
        for item in report.observations
        if item.bar_index == bar_index and item.policy is policy
    )


def test_counterfactual_policies_distinguish_challenge_invalidation_and_opposite_support() -> None:
    report = WeeklyActionabilityCounterfactualEngine.audit(
        datasets=(_dataset(),),
        horizons_weeks=(1,),
    )

    supported = _observation(
        report,
        20,
        WeeklyCounterfactualPolicy.REQUIRE_SAME_DIRECTION_SHADOW_SUPPORT,
    )
    assert supported.shadow_state is ShadowWeeklyThesisState.BULLISH_SUPPORTED
    assert supported.disposition is WeeklyCounterfactualDisposition.RETAIN

    challenged = _observation(
        report,
        22,
        WeeklyCounterfactualPolicy.MATERIAL_CONTRADICTION,
    )
    assert challenged.shadow_state is ShadowWeeklyThesisState.BULLISH_CHALLENGED
    assert WeeklyCounterfactualReason.CAMPAIGN_CHALLENGED in challenged.reasons
    assert challenged.disposition is WeeklyCounterfactualDisposition.SUPPRESS

    invalidated = _observation(
        report,
        24,
        WeeklyCounterfactualPolicy.STRUCTURAL_INVALIDATION_ONLY,
    )
    assert invalidated.shadow_state is ShadowWeeklyThesisState.BULLISH_INVALIDATION_EVIDENCE
    assert WeeklyCounterfactualReason.STRUCTURAL_INVALIDATION in invalidated.reasons
    assert invalidated.disposition is WeeklyCounterfactualDisposition.SUPPRESS
    assert invalidated.partition is WeeklyCounterfactualPartition.OUT_OF_SAMPLE

    opposite = _observation(
        report,
        25,
        WeeklyCounterfactualPolicy.MATERIAL_CONTRADICTION_OR_OPPOSITE_SUPPORT,
    )
    assert opposite.shadow_state is ShadowWeeklyThesisState.BEARISH_SUPPORTED
    assert opposite.shadow_direction is EvidenceDirection.BEARISH
    assert WeeklyCounterfactualReason.OPPOSITE_SUPPORTED_THESIS in opposite.reasons
    assert opposite.disposition is WeeklyCounterfactualDisposition.SUPPRESS


def test_strict_policy_is_audit_only_and_suppresses_missing_same_direction_support() -> None:
    report = WeeklyActionabilityCounterfactualEngine.audit(
        datasets=(_dataset(),),
        horizons_weeks=(1, 2),
    )

    assert report.is_actionable is False
    strict = tuple(
        item
        for item in report.observations
        if item.policy is WeeklyCounterfactualPolicy.REQUIRE_SAME_DIRECTION_SHADOW_SUPPORT
    )
    assert len(strict) == 6
    assert sum(item.suppressed for item in strict) >= 4
    assert all(
        WeeklyCounterfactualReason.SHADOW_SUPPORT_MISSING in item.reasons
        for item in strict
        if item.suppressed
    )


def test_summaries_keep_baseline_retained_and_suppressed_outcomes_separate() -> None:
    report = WeeklyActionabilityCounterfactualEngine.audit(
        datasets=(_dataset(),),
        horizons_weeks=(1,),
    )
    summary = next(
        item
        for item in report.summaries
        if item.policy is WeeklyCounterfactualPolicy.MATERIAL_CONTRADICTION
        and item.horizon_weeks == 1
        and item.partition is WeeklyCounterfactualPartition.ALL
    )

    assert summary.baseline.observation_count == 6
    assert summary.retained.observation_count + summary.suppressed.observation_count == 6
    assert summary.baseline.complete_outcome_count == 5
    assert summary.retained_minus_suppressed_mean_close_pct is not None


def test_out_of_sample_and_leave_one_symbol_out_are_reported_without_verdict() -> None:
    report = WeeklyActionabilityCounterfactualEngine.audit(
        datasets=(_dataset("AAA.NS"), _dataset("BBB.NS")),
        horizons_weeks=(1,),
    )

    partitions = {item.partition for item in report.observations}
    assert WeeklyCounterfactualPartition.IN_SAMPLE in partitions
    assert WeeklyCounterfactualPartition.OUT_OF_SAMPLE in partitions
    assert report.leave_one_symbol_out
    assert {item.held_out_symbol for item in report.leave_one_symbol_out} == {
        "AAA.NS",
        "BBB.NS",
    }
    assert report.is_actionable is False


def test_bundle_writer_exports_reviewable_counterfactual_artifacts(tmp_path) -> None:
    report = WeeklyActionabilityCounterfactualEngine.audit(
        datasets=(_dataset("AAA.NS"), _dataset("BBB.NS")),
        horizons_weeks=(1,),
    )
    paths = write_weekly_actionability_counterfactual_bundle(report, tmp_path)

    assert all(path.exists() for path in (
        paths.summary_json,
        paths.observations_csv,
        paths.summaries_csv,
        paths.leave_one_symbol_out_csv,
    ))
    payload = json.loads(paths.summary_json.read_text(encoding="utf-8"))
    assert payload["is_actionable"] is False
    assert payload["symbol_count"] == 2
    assert pd.read_csv(paths.observations_csv).shape[0] == len(report.observations)
    assert not pd.read_csv(paths.summaries_csv).empty
    assert not pd.read_csv(paths.leave_one_symbol_out_csv).empty
