from __future__ import annotations

import json

from models import EvidenceDirection
from weekly_actionability_counterfactual import (
    WeeklyActionabilityCounterfactualObservation,
    WeeklyActionabilityCounterfactualReport,
    WeeklyCounterfactualDisposition,
    WeeklyCounterfactualPartition,
    WeeklyCounterfactualPolicy,
    WeeklyCounterfactualReason,
)
from weekly_contradiction_reason_audit import (
    WeeklyContradictionReasonAuditEngine,
    WeeklyContradictionReasonClass,
    WeeklyContradictionSampleUnit,
)
from weekly_replay_comparison import DirectionalForwardOutcome
from weekly_thesis import ShadowWeeklyThesisState
from audit.weekly_contradiction_reason_runner import write_weekly_contradiction_reason_bundle


def _outcome(horizon: int, value: float) -> DirectionalForwardOutcome:
    return DirectionalForwardOutcome(
        horizon_weeks=horizon,
        available_weeks=horizon,
        complete=True,
        direction=EvidenceDirection.BULLISH,
        close_return_pct=value,
        maximum_favorable_excursion_pct=max(0.0, value + 2.0),
        maximum_adverse_excursion_pct=min(0.0, value - 2.0),
    )


def _rows_for_week(
    *,
    symbol: str,
    bar_index: int,
    state: ShadowWeeklyThesisState,
    shadow_direction: EvidenceDirection,
    reasons: tuple[WeeklyCounterfactualReason, ...],
    value: float,
    partition: WeeklyCounterfactualPartition = WeeklyCounterfactualPartition.IN_SAMPLE,
) -> tuple[WeeklyActionabilityCounterfactualObservation, ...]:
    rows = []
    for policy in WeeklyCounterfactualPolicy:
        rows.append(
            WeeklyActionabilityCounterfactualObservation(
                symbol=symbol,
                week=f"2025-W{bar_index:02d}",
                bar_index=bar_index,
                policy=policy,
                partition=partition,
                legacy_direction=EvidenceDirection.BULLISH,
                shadow_state=state,
                shadow_direction=shadow_direction,
                disposition=WeeklyCounterfactualDisposition.RETAIN,
                reasons=reasons,
                outcomes=(_outcome(5, value), _outcome(10, value * 2.0)),
            )
        )
    return tuple(rows)


def _report() -> WeeklyActionabilityCounterfactualReport:
    observations = (
        *_rows_for_week(
            symbol="AAA.NS",
            bar_index=10,
            state=ShadowWeeklyThesisState.BULLISH_SUPPORTED,
            shadow_direction=EvidenceDirection.BULLISH,
            reasons=(WeeklyCounterfactualReason.NONE,),
            value=1.0,
        ),
        *_rows_for_week(
            symbol="AAA.NS",
            bar_index=11,
            state=ShadowWeeklyThesisState.BULLISH_CHALLENGED,
            shadow_direction=EvidenceDirection.BULLISH,
            reasons=(
                WeeklyCounterfactualReason.CAMPAIGN_CHALLENGED,
                WeeklyCounterfactualReason.SHADOW_SUPPORT_MISSING,
            ),
            value=-2.0,
        ),
        *_rows_for_week(
            symbol="AAA.NS",
            bar_index=12,
            state=ShadowWeeklyThesisState.BULLISH_CHALLENGED,
            shadow_direction=EvidenceDirection.BULLISH,
            reasons=(
                WeeklyCounterfactualReason.CAMPAIGN_CHALLENGED,
                WeeklyCounterfactualReason.SHADOW_SUPPORT_MISSING,
            ),
            value=-3.0,
        ),
        *_rows_for_week(
            symbol="AAA.NS",
            bar_index=13,
            state=ShadowWeeklyThesisState.BEARISH_SUPPORTED,
            shadow_direction=EvidenceDirection.BEARISH,
            reasons=(
                WeeklyCounterfactualReason.OPPOSITE_SUPPORTED_THESIS,
                WeeklyCounterfactualReason.SHADOW_SUPPORT_MISSING,
            ),
            value=-4.0,
            partition=WeeklyCounterfactualPartition.OUT_OF_SAMPLE,
        ),
        *_rows_for_week(
            symbol="BBB.NS",
            bar_index=20,
            state=ShadowWeeklyThesisState.BULLISH_INVALIDATION_EVIDENCE,
            shadow_direction=EvidenceDirection.BULLISH,
            reasons=(
                WeeklyCounterfactualReason.STRUCTURAL_INVALIDATION,
                WeeklyCounterfactualReason.SHADOW_SUPPORT_MISSING,
            ),
            value=-5.0,
            partition=WeeklyCounterfactualPartition.OUT_OF_SAMPLE,
        ),
        *_rows_for_week(
            symbol="BBB.NS",
            bar_index=22,
            state=ShadowWeeklyThesisState.BULLISH_DEVELOPING,
            shadow_direction=EvidenceDirection.BULLISH,
            reasons=(WeeklyCounterfactualReason.SHADOW_SUPPORT_MISSING,),
            value=0.5,
            partition=WeeklyCounterfactualPartition.OUT_OF_SAMPLE,
        ),
    )
    return WeeklyActionabilityCounterfactualReport(
        symbols=("AAA.NS", "BBB.NS"),
        horizons_weeks=(5, 10),
        observations=observations,
        summaries=(),
        leave_one_symbol_out=(),
    )


def test_reason_decomposition_is_exclusive_and_policy_deduplicated() -> None:
    report = WeeklyContradictionReasonAuditEngine.audit(counterfactual_report=_report())

    assert len(report.observations) == 6
    assert [item.reason_class for item in report.observations] == [
        WeeklyContradictionReasonClass.SAME_DIRECTION_SUPPORTED,
        WeeklyContradictionReasonClass.CAMPAIGN_CHALLENGED,
        WeeklyContradictionReasonClass.CAMPAIGN_CHALLENGED,
        WeeklyContradictionReasonClass.OPPOSITE_SUPPORTED_THESIS,
        WeeklyContradictionReasonClass.STRUCTURAL_INVALIDATION,
        WeeklyContradictionReasonClass.SHADOW_SUPPORT_MISSING,
    ]
    assert report.is_actionable is False


def test_episode_starts_collapse_consecutive_same_reason_weeks() -> None:
    report = WeeklyContradictionReasonAuditEngine.audit(counterfactual_report=_report())
    challenged = tuple(
        item
        for item in report.observations
        if item.reason_class is WeeklyContradictionReasonClass.CAMPAIGN_CHALLENGED
    )

    assert len(challenged) == 2
    assert challenged[0].episode_start is True
    assert challenged[0].episode_length_so_far == 1
    assert challenged[1].episode_start is False
    assert challenged[1].episode_length_so_far == 2
    assert challenged[0].episode_id == challenged[1].episode_id


def test_episode_summary_uses_only_first_bar_and_preserves_oos() -> None:
    report = WeeklyContradictionReasonAuditEngine.audit(counterfactual_report=_report())
    all_episode = next(
        item
        for item in report.summaries
        if item.reason_class is WeeklyContradictionReasonClass.CAMPAIGN_CHALLENGED
        and item.sample_unit is WeeklyContradictionSampleUnit.EPISODE_START
        and item.horizon_weeks == 5
        and item.partition is WeeklyCounterfactualPartition.ALL
    )
    oos_opposite = next(
        item
        for item in report.summaries
        if item.reason_class is WeeklyContradictionReasonClass.OPPOSITE_SUPPORTED_THESIS
        and item.sample_unit is WeeklyContradictionSampleUnit.BAR
        and item.horizon_weeks == 5
        and item.partition is WeeklyCounterfactualPartition.OUT_OF_SAMPLE
    )

    assert all_episode.metrics.observation_count == 1
    assert all_episode.metrics.mean_close_return_pct == -2.0
    assert oos_opposite.metrics.observation_count == 1
    assert oos_opposite.metrics.mean_close_return_pct == -4.0


def test_leave_one_symbol_out_is_reason_specific() -> None:
    report = WeeklyContradictionReasonAuditEngine.audit(counterfactual_report=_report())
    row = next(
        item
        for item in report.leave_one_symbol_out
        if item.reason_class is WeeklyContradictionReasonClass.STRUCTURAL_INVALIDATION
        and item.sample_unit is WeeklyContradictionSampleUnit.BAR
        and item.horizon_weeks == 5
        and item.held_out_symbol == "BBB.NS"
    )

    assert row.held_out.observation_count == 1
    assert row.held_out.mean_close_return_pct == -5.0
    assert row.other_symbols.observation_count == 0
    assert row.held_out_minus_other_mean_close_pct is None


def test_bundle_export_is_read_only_and_contains_reason_counts(tmp_path) -> None:
    report = WeeklyContradictionReasonAuditEngine.audit(counterfactual_report=_report())
    paths = write_weekly_contradiction_reason_bundle(report, tmp_path)

    payload = json.loads(paths.summary_json.read_text(encoding="utf-8"))
    assert payload["is_actionable"] is False
    assert payload["unique_legacy_actionable_observations"] == 6
    assert payload["reason_counts"]["campaign_challenged"] == {
        "bar_observations": 2,
        "episodes": 1,
    }
    assert paths.observations_csv.exists()
    assert paths.summaries_csv.exists()
    assert paths.leave_one_symbol_out_csv.exists()
