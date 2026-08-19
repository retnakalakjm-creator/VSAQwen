import pandas as pd

import config
from engine.columns import COL_DIRECTION, COL_SPREAD_CLASS, COL_VOLUME_CLASS
from evidence.campaign import ShakeoutRecoveryResult, _validate_shakeout_test, calculate_shakeout_quality, has_recent_weakness, has_selling_campaign, validate_shakeout, _recent_structural_weakness
from evidence.helpers import evaluate_detector, requirement, requirements_passed
from evidence.rules import has_strong_spread, has_weak_spread, is_above_average_spread, is_bearish_bar, is_confirmed_downtrend, is_high_volume, is_low_volume, is_narrow_spread, is_strong_close, is_very_high_volume, is_weak_close, makes_higher_low, makes_lower_low, volume_decreasing, volume_increasing
from models import BackgroundContext, Evidence, EvidenceCode, Direction, SpreadClass, VolumeClass


# -------------------------------------------------------------------------
# Public API
# -------------------------------------------------------------------------
def collect_demand(ctx: BackgroundContext, metrics: pd.DataFrame) -> list[Evidence]:
    evidence: list[Evidence] = []
    evidence.extend(_collect_stopping_volume(ctx))
    evidence.extend(_collect_demand_coming_in(ctx))
    evidence.extend(_collect_test(ctx))
    evidence.extend(_collect_shakeout(ctx=ctx, validation_metrics=metrics))
    evidence.extend(_collect_no_supply(ctx))
    return evidence


def _collect_demand_coming_in(ctx: BackgroundContext) -> list[Evidence]:
    """
    Detect audited Demand Coming In candidates.

    Mandatory conditions match the validated point-in-time definition:
    bearish direction, high-or-higher volume, above-average-or-higher
    spread, and close at least in the middle of the bar.
    """
    evidence: list[Evidence] = []
    bar = ctx.current
    previous = ctx.previous

    requirements = (
        requirement(name="Down Bar", passed=bar.direction == Direction.DOWN),
        requirement(name="High Volume", passed=bar.volume >= VolumeClass.HIGH),
        requirement(name="Above Average Spread", passed=bar.spread >= SpreadClass.ABOVE_AVERAGE),
        requirement(name="Close Not Off Low", passed=int(bar.close_position) >= 2),
    )

    if not requirements_passed(requirements):
        return evidence

    confirmations = (
        requirement(
            name="Volume Increasing",
            passed=previous is not None and volume_increasing(bar, previous),
            mandatory=False,
        ),
        requirement(
            name="Higher Low",
            passed=previous is not None and makes_higher_low(bar, previous),
            mandatory=False,
        ),
    )

    evaluate_detector(
        evidence=evidence,
        ctx=ctx,
        code=EvidenceCode.DEMAND_COMING_IN,
        requirements=requirements,
        confirmations=confirmations,
    )
    return evidence


def _collect_stopping_volume(ctx: BackgroundContext) -> list[Evidence]:
    evidence: list[Evidence] = []
    bar = ctx.current
    previous = ctx.previous
    requirements = (
        requirement(name="Selling Campaign", passed=has_selling_campaign(ctx)),
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


def _collect_selling_climax(ctx: BackgroundContext) -> list[Evidence]:
    evidence: list[Evidence] = []
    bar = ctx.current
    previous = ctx.previous
    requirements = (
        requirement(name="Selling Campaign", passed=has_selling_campaign(ctx)),
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


def _collect_test(ctx: BackgroundContext) -> list[Evidence]:
    evidence: list[Evidence] = []
    bar = ctx.current
    previous = ctx.previous
    trend = getattr(ctx, "trend", None)
    no_strong_downtrend_contradiction = True if trend is None else not (is_confirmed_downtrend(trend) and not _recent_structural_weakness(ctx))
    requirements = (
        requirement(name="Selling Campaign", passed=has_selling_campaign(ctx)),
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


def _find_recovery_anchored_shakeout(ctx: BackgroundContext, validation_metrics: pd.DataFrame):
    current_index = int(ctx.current.bar_index)
    if current_index <= 0:
        return None
    lookback = config.SHAKEOUT_TEST_LOOKAHEAD + config.SHAKEOUT_RECOVERY_LOOKAHEAD + 1
    start = max(0, current_index - lookback)
    point_in_time_metrics = validation_metrics.iloc[: current_index + 1]

    for candidate_index in range(current_index - 1, start - 1, -1):
        candidate_row = validation_metrics.iloc[candidate_index]
        if Direction(int(candidate_row[COL_DIRECTION])) != Direction.DOWN:
            continue
        if VolumeClass(int(candidate_row[COL_VOLUME_CLASS])) < VolumeClass.VERY_HIGH:
            continue
        if SpreadClass(int(candidate_row[COL_SPREAD_CLASS])) < SpreadClass.WIDE:
            continue

        from evidence.engine import EvidenceEngine
        from trend import TrendAnalyzer
        candidate_replay = validation_metrics.iloc[: candidate_index + 1].copy()
        candidate_trend = TrendAnalyzer().analyze(candidate_replay)
        candidate_engine = EvidenceEngine()
        candidate_engine._reset(metrics=candidate_replay, trend=candidate_trend, structural_swings=tuple(candidate_trend.structure.structural_swings), validation_metrics=candidate_replay)
        candidate_ctx = candidate_engine._ctx
        if candidate_ctx is None or candidate_ctx.previous is None:
            continue

        candidate_bar = candidate_ctx.current
        candidate_previous = candidate_ctx.previous
        candidate_requirements = (
            requirement(name="Bearish Bar", passed=is_bearish_bar(candidate_bar)),
            requirement(name="Selling Pressure Present", passed=has_selling_campaign(candidate_ctx)),
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
