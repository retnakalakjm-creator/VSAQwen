import pandas as pd

from evidence.campaign import ShakeoutRecoveryResult, _validate_shakeout_test, calculate_shakeout_quality, has_recent_weakness, has_selling_campaign, validate_shakeout
from evidence.helpers import evaluate_detector, requirement, requirements_passed
from evidence.rules import has_strong_spread, has_weak_spread, is_above_average_spread, is_bearish_bar, is_confirmed_downtrend, is_low_volume, is_narrow_spread, is_strong_close, is_very_high_volume, is_weak_close, makes_higher_low, makes_lower_low, volume_decreasing, volume_increasing
from models import BackgroundContext, Evidence, EvidenceCode


# -------------------------------------------------------------------------
# Public API
# -------------------------------------------------------------------------
def collect_demand(
    ctx: BackgroundContext,
    metrics: pd.DataFrame,
) -> list[Evidence]:

    evidence: list[Evidence] = []

    # Test and Selling Climax remain disabled until their
    # production-history validation is completed.
    # evidence.extend(_collect_test(ctx))
    # evidence.extend(_collect_selling_climax(ctx))

    evidence.extend(
        _collect_shakeout(
            ctx=ctx,
            validation_metrics=metrics,
        )
    )

    evidence.extend(
        _collect_no_supply(ctx)
    )

    return evidence


# -------------------------------------------------------------------------
# Selling Climax
# -------------------------------------------------------------------------
def _collect_selling_climax(
    ctx: BackgroundContext,
) -> list[Evidence]:

    evidence: list[Evidence] = []

    bar = ctx.current
    previous = ctx.previous

    requirements = (
        requirement(
            name="Selling Campaign",
            passed=has_selling_campaign(ctx),
        ),
        requirement(
            name="Bearish Bar",
            passed=is_bearish_bar(bar),
        ),
        requirement(
            name="Very High Volume",
            passed=is_very_high_volume(bar),
        ),
        requirement(
            name="Above Average Spread",
            passed=is_above_average_spread(bar),
        ),
    )

    if not requirements_passed(requirements):
        return evidence

    confirmations = (
        requirement(
            name="Wide Spread",
            passed=has_strong_spread(bar),
        ),
        requirement(
            name="Strong Close",
            passed=is_strong_close(bar),
        ),
        requirement(
            name="Increasing Volume",
            passed=volume_increasing(bar, previous),
        ),
    )

    evaluate_detector(
        evidence=evidence,
        ctx=ctx,
        code=EvidenceCode.SELLING_CLIMAX,
        requirements=requirements,
        confirmations=confirmations,
    )

    return evidence


# -------------------------------------------------------------------------
# Test
# -------------------------------------------------------------------------
def _collect_test(
    ctx: BackgroundContext,
) -> list[Evidence]:

    evidence: list[Evidence] = []

    bar = ctx.current
    previous = ctx.previous

    requirements = (
        requirement(
            name="Selling Campaign",
            passed=has_selling_campaign(ctx),
        ),
        requirement(
            name="Down Bar",
            passed=is_bearish_bar(bar),
        ),
        requirement(
            name="Low Volume",
            passed=is_low_volume(bar),
        ),
        requirement(
            name="Narrow Spread",
            passed=is_narrow_spread(bar),
        ),
    )

    if not requirements_passed(requirements):
        return evidence

    confirmations = (
        requirement(
            name="Volume Decreasing",
            passed=volume_decreasing(bar, previous),
        ),
        requirement(
            name="Strong Close",
            passed=is_strong_close(bar),
        ),
        requirement(
            name="Higher Low",
            passed=makes_higher_low(bar, previous),
        ),
    )

    evaluate_detector(
        evidence=evidence,
        ctx=ctx,
        code=EvidenceCode.TEST,
        requirements=requirements,
        confirmations=confirmations,
    )

    return evidence


# -------------------------------------------------------------------------
# ShakeOut
# -------------------------------------------------------------------------
def _collect_shakeout(
    ctx: BackgroundContext,
    validation_metrics: pd.DataFrame,
) -> list[Evidence]:

    evidence: list[Evidence] = []

    bar = ctx.current
    previous = ctx.previous
    row = validation_metrics.iloc[bar.bar_index]
    requirements = (
        requirement(
            name="Bearish Bar",
            passed=is_bearish_bar(bar),
        ),
        requirement(
            name="Selling Pressure Present",
            passed=has_selling_campaign(ctx),
        ),
        requirement(
            name="Wide Spread",
            passed=has_strong_spread(bar),
        ),
        requirement(
            name="Very High Volume",
            passed=is_very_high_volume(bar),
        ),
        requirement(
            name="Strong Close",
            passed=is_strong_close(bar),
        ),
        requirement(
            name="Lower Low",
            passed=makes_lower_low(bar, previous),
        ),
    )

    if not requirements_passed(requirements):
        return evidence

    shakeout_index = bar.bar_index

    validation = validate_shakeout(
        metrics=validation_metrics,
        shakeout_index=shakeout_index,
    )

    if validation.recovery.result != ShakeoutRecoveryResult.VALID:
        return evidence

    assert validation.test.test_index is not None
    assert validation.recovery.recovery_index is not None

    quality = calculate_shakeout_quality(
        validation=validation,
    )

    evaluate_detector(
        evidence=evidence,
        ctx=ctx,
        code=EvidenceCode.SHAKEOUT,
        requirements=requirements,
        confirmations=(),
        test_index=validation.test.test_index,
        recovery_index=validation.recovery.recovery_index,
        quality=quality,
    )

    return evidence


# -------------------------------------------------------------------------
# No Supply
# -------------------------------------------------------------------------
def _collect_no_supply(
    ctx: BackgroundContext,
) -> list[Evidence]:

    evidence: list[Evidence] = []

    bar = ctx.current
    previous = ctx.previous

    requirements = (
        requirement(
            name="Bullish Environment",
            passed=ctx.is_bearish_environment(),
        ),
        requirement(
            name="Bearish Bar",
            passed=is_bearish_bar(bar),
        ),
        requirement(
            name="Low Volume",
            passed=is_low_volume(bar),
        ),
        requirement(
            name="Narrow Spread",
            passed=is_narrow_spread(bar),
        ),
    )

    if not requirements_passed(requirements):
        return evidence

    confirmations = (
        requirement(
            name="Weak Spread",
            passed=has_weak_spread(bar),
        ),
        requirement(
            name="Volume Decreasing",
            passed=volume_decreasing(bar, previous),
        ),
        requirement(
            name="Weak Selling Result",
            passed=is_weak_close(bar),
        ),
    )

    evaluate_detector(
        evidence=evidence,
        ctx=ctx,
        code=EvidenceCode.NO_SUPPLY,
        requirements=requirements,
        confirmations=confirmations,
    )

    return evidence


# ==========================================================
# Public API
# ==========================================================
__all__ = [
    "collect_demand",
]
