import pandas as pd

import config
from engine.columns import COL_DIRECTION, COL_SPREAD_CLASS, COL_VOLUME_CLASS
from evidence.absorption import collect_absorption
from evidence.campaign import ShakeoutRecoveryResult, _validate_shakeout_test, calculate_shakeout_quality, validate_shakeout, _recent_structural_weakness
from evidence.campaign_snapshot import CampaignSnapshot
from evidence.demand_coming_in import collect_demand_coming_in
from evidence.helpers import evaluate_detector, requirement, requirements_passed
from evidence.rules import has_strong_spread, has_weak_spread, is_above_average_spread, is_bearish_bar, is_confirmed_downtrend, is_high_volume, is_low_volume, is_narrow_spread, is_strong_close, is_very_high_volume, is_weak_close, makes_higher_low, makes_lower_low, volume_decreasing, volume_increasing, is_bullish_bar
from models import BackgroundContext, Evidence, EvidenceCode, Direction, SpreadClass, VolumeClass, TrendDirection, SwingLabel
from trend import TrendAnalyzer


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def collect_demand(ctx: BackgroundContext, metrics: pd.DataFrame) -> list[Evidence]:
    evidence: list[Evidence] = []
    campaign_snapshot = CampaignSnapshot.from_context(ctx)
    evidence.extend(_collect_stopping_volume(ctx, campaign_snapshot))
    evidence.extend(_collect_selling_climax(ctx, campaign_snapshot))
    evidence.extend(_collect_increasing_demand(ctx))
    evidence.extend(collect_demand_coming_in(ctx))
    evidence.extend(_collect_test(ctx, campaign_snapshot))
    evidence.extend(_collect_shakeout(ctx=ctx, validation_metrics=metrics))
    evidence.extend(_collect_no_supply(ctx))
    evidence.extend(collect_absorption(ctx))
    return evidence


def _collect_increasing_demand(ctx: BackgroundContext) -> list[Evidence]:
    """
    Detect the validated INCREASING_DEMAND production definition.

    Mandatory conditions match the historical point-in-time calibration:
    bullish bar, high volume, above-average spread, and increasing volume.
    """
    evidence: list[Evidence] = []
    bar = ctx.current
    previous = ctx.previous

    requirements = (
        requirement(name="Bullish Bar", passed=is_bullish_bar(bar)),
        requirement(name="High Volume", passed=is_high_volume(bar)),
        requirement(name="Above Average Spread", passed=is_above_average_spread(bar)),
        requirement(
            name="Volume Increasing",
            passed=previous is not None and volume_increasing(bar, previous),
        ),
    )

    evaluate_detector(
        evidence=evidence,
        ctx=ctx,
        code=EvidenceCode.INCREASING_DEMAND,
        requirements=requirements,
    )
    return evidence


def _collect_stopping_volume(ctx: BackgroundContext, campaign_snapshot: CampaignSnapshot | None = None) -> list[Evidence]:
    evidence: list[Evidence] = []
    bar = ctx.current
    previous = ctx.previous
    snapshot = campaign_snapshot or CampaignSnapshot.from_context(ctx)
    requirements = (
        requirement(name="Selling Campaign", passed=snapshot.has_selling_campaign()),
        requirement(name="Bearish Bar", passed=is_bearish_bar(bar)),
        requirement(name="High Volume", passed=is_high_volume(bar)),
        requirement(name="Above Average Spread", passed=is_above_average_spread(bar)),
        requirement(name="Close Off Low", passed=not is_weak_close(bar)),
    )
    if not requirements_passed(requirements):
        return evidence
    confirmations = (
        requirement(name="Very High Volume", passed=is_very_high_volume(bar)),
        requirement(name="Wide Spread", passed=has_strong_spread(bar)),
        requirement(name="Volume Increasing", passed=volume_increasing(bar, previous)),
        requirement(name="Higher Low", passed=makes_higher_low(bar, previous)),
    )
    evaluate_detector(evidence=evidence, ctx=ctx, code=EvidenceCode.STOPPING_VOLUME, requirements=requirements, confirmations=confirmations)
    return evidence


def _collect_selling_climax(ctx: BackgroundContext, campaign_snapshot: CampaignSnapshot | None = None) -> list[Evidence]:
    evidence: list[Evidence] = []
    bar = ctx.current
    previous = ctx.previous
    snapshot = campaign_snapshot or CampaignSnapshot.from_context(ctx)
    requirements = (
        requirement(name="Selling Campaign", passed=snapshot.has_selling_campaign()),
        requirement(name="Bearish Bar", passed=is_bearish_bar(bar)),
        requirement(name="Very High Volume", passed=is_very_high_volume(bar)),
        requirement(name="Above Average Spread", passed=is_above_average_spread(bar)),
    )
    if not requirements_passed(requirements):
        return evidence
    confirmations = (
        requirement(name="Wide Spread", passed=has_strong_spread(bar)),
        requirement(name="Strong Close", passed=is_strong_close(bar)),
        requirement(name="Increasing Volume", passed=volume_increasing(bar, previous)),
    )
    evaluate_detector(evidence=evidence, ctx=ctx, code=EvidenceCode.SELLING_CLIMAX, requirements=requirements, confirmations=confirmations)
    return evidence


def _collect_test(ctx: BackgroundContext, campaign_snapshot: CampaignSnapshot | None = None) -> list[Evidence]:
    evidence: list[Evidence] = []
    bar = ctx.current
    previous = ctx.previous
    snapshot = campaign_snapshot or CampaignSnapshot.from_context(ctx)
    trend = getattr(ctx, "trend", None)
    no_strong_downtrend_contradiction = True if trend is None else not (is_confirmed_downtrend(trend) and not _recent_structural_weakness(ctx))
    requirements = (
        requirement(name="Selling Campaign", passed=snapshot.has_selling_campaign()),
        requirement(name="Down Bar", passed=is_bearish_bar(bar)),
        requirement(name="Low Volume", passed=is_low_volume(bar)),
        requirement(name="Narrow Spread", passed=is_narrow_spread(bar)),
        requirement(name="No Strong Downtrend Contradiction", passed=no_strong_downtrend_contradiction),
    )
    if not requirements_passed(requirements):
        return evidence
    confirmations = (
        requirement(name="Volume Decreasing", passed=volume_decreasing(bar, previous)),
        requirement(name="Strong Close", passed=is_strong_close(bar)),
        requirement(name="Higher Low", passed=makes_higher_low(bar, previous)),
    )
    evaluate_detector(evidence=evidence, ctx=ctx, code=EvidenceCode.TEST, requirements=requirements, confirmations=confirmations)
    return evidence


def _candidate_trend_direction(
    classified_structural: list,
    candidate_index: int,
) -> TrendDirection:
    """Derive candidate-time trend direction from causal structural swings."""
    structural = [
        item
        for item in classified_structural
        if item.swing.confirmation_index <= candidate_index
    ]
    if not structural:
        return TrendDirection.UNKNOWN

    return TrendAnalyzer._determine_direction(
        TrendAnalyzer._weighted_label_counts(structural)
    )


def _candidate_campaign_snapshot(
    ctx: BackgroundContext,
    validation_metrics: pd.DataFrame,
    candidate_index: int,
    classified_structural: list,
) -> CampaignSnapshot:
    start = max(
        0,
        candidate_index + 1 - config.BACKGROUND_LOOKBACK,
    )
    recent_metrics = validation_metrics.iloc[start : candidate_index + 1]
    structural = tuple(
        item
        for item in ctx.structural_swings
        if item.swing.confirmation_index <= candidate_index
    )
    return CampaignSnapshot.from_metrics(
        recent_metrics,
        trend_direction=_candidate_trend_direction(
            classified_structural,
            candidate_index,
        ),
        structural_swings=structural,
    )


def _find_recovery_anchored_shakeout(ctx: BackgroundContext, validation_metrics: pd.DataFrame):
    current_index = int(ctx.current.bar_index)
    if current_index <= 0:
        return None
    lookback = config.SHAKEOUT_TEST_LOOKAHEAD + config.SHAKEOUT_RECOVERY_LOOKAHEAD + 1
    start = max(0, current_index - lookback)
    point_in_time_metrics = validation_metrics.iloc[: current_index + 1]

    from evidence.engine import EvidenceEngine

    context_factory = EvidenceEngine()
    classified_structural = TrendAnalyzer()._classify_swings(
        list(ctx.structural_swings)
    )

    for candidate_index in range(current_index - 1, start - 1, -1):
        candidate_row = validation_metrics.iloc[candidate_index]
        if Direction(int(candidate_row[COL_DIRECTION])) != Direction.DOWN:
            continue
        if VolumeClass(int(candidate_row[COL_VOLUME_CLASS])) < VolumeClass.VERY_HIGH:
            continue
        if SpreadClass(int(candidate_row[COL_SPREAD_CLASS])) < SpreadClass.WIDE:
            continue

        candidate_snapshot = _candidate_campaign_snapshot(
            ctx,
            validation_metrics,
            candidate_index,
            classified_structural,
        )
        candidate_bar = context_factory._create_bar_context(
            candidate_row,
            candidate_index,
        )
        previous_index = candidate_index - 1
        if previous_index < 0:
            continue
        candidate_previous = context_factory._create_bar_context(
            validation_metrics.iloc[previous_index],
            previous_index,
        )
        candidate_requirements = (
            requirement(name="Bearish Bar", passed=is_bearish_bar(candidate_bar)),
            requirement(name="Selling Pressure Present", passed=candidate_snapshot.has_selling_campaign()),
            requirement(name="Wide Spread", passed=has_strong_spread(candidate_bar)),
            requirement(name="Very High Volume", passed=is_very_high_volume(candidate_bar)),
            requirement(name="Lower Low", passed=makes_lower_low(candidate_bar, candidate_previous)),
        )
        if not requirements_passed(candidate_requirements):
            continue

        validation = validate_shakeout(metrics=point_in_time_metrics, shakeout_index=candidate_index)
        if validation.recovery.result != ShakeoutRecoveryResult.VALID:
            continue
        if validation.recovery.recovery_index != current_index:
            continue
        return candidate_requirements, validation
    return None


def _collect_shakeout(ctx: BackgroundContext, validation_metrics: pd.DataFrame) -> list[Evidence]:
    evidence: list[Evidence] = []
    found = _find_recovery_anchored_shakeout(ctx=ctx, validation_metrics=validation_metrics)
    if found is None:
        return evidence
    requirements, validation = found
    assert validation.test.test_index is not None
    assert validation.recovery.recovery_index is not None
    quality = calculate_shakeout_quality(validation=validation)
    evaluate_detector(evidence=evidence, ctx=ctx, code=EvidenceCode.SHAKEOUT, requirements=requirements, confirmations=(), test_index=validation.test.test_index, recovery_index=validation.recovery.recovery_index, quality=quality)
    return evidence


def _collect_no_supply(ctx: BackgroundContext) -> list[Evidence]:
    evidence: list[Evidence] = []
    bar = ctx.current
    previous = ctx.previous
    requirements = (
        requirement(name="Bullish Environment", passed=ctx.is_bearish_environment()),
        requirement(name="Bearish Bar", passed=is_bearish_bar(bar)),
        requirement(name="Low Volume", passed=is_low_volume(bar)),
        requirement(name="Narrow Spread", passed=is_narrow_spread(bar)),
    )
    if not requirements_passed(requirements):
        return evidence
    confirmations = (
        requirement(name="Weak Spread", passed=has_weak_spread(bar)),
        requirement(name="Volume Decreasing", passed=volume_decreasing(bar, previous)),
        requirement(name="Weak Selling Result", passed=is_weak_close(bar)),
    )
    evaluate_detector(evidence=evidence, ctx=ctx, code=EvidenceCode.NO_SUPPLY, requirements=requirements, confirmations=confirmations)
    return evidence


__all__ = ["collect_demand"]
