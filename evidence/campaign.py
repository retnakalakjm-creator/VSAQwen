"""
Campaign Context Engine

Determines whether professional buying or
selling campaigns are active.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
import logging

import pandas as pd

import config
from engine.columns import COL_CLOSE, COL_CLOSE_POSITION, COL_DIRECTION, COL_LOW, COL_SPREAD, COL_VOLUME
from models import BackgroundContext, BarContext, StructuralSwing, SwingType
from .rules import (
    closes_higher_than_previous,
    closes_lower_than_previous,
    is_confirmed_downtrend,
    is_confirmed_uptrend,
    is_down_bar,
    is_strong_close,
    is_up_bar,
    is_weak_close,
)

logger = logging.getLogger(__name__)


class ShakeoutTestResult(StrEnum):
    VALID = "valid"
    BAD_TEST = "bad_test"
    NO_TEST = "no_test"


class ShakeoutRecoveryResult(StrEnum):
    VALID = "valid"
    FAILED = "failed"
    NO_RECOVERY = "no_recovery"


@dataclass(frozen=True, slots=True)
class ShakeoutTestValidation:
    result: ShakeoutTestResult
    test_index: int | None
    distance_ratio: float | None
    spread_ratio: float | None
    volume_ratio: float | None
    close_position: int | None


@dataclass(frozen=True, slots=True)
class ShakeoutRecoveryValidation:
    result: ShakeoutRecoveryResult
    recovery_index: int | None
    spread_ratio: float | None
    volume_ratio: float | None
    close_position: int | None
    close_change_spread_ratio: float | None
    low_clearance_ratio: float | None


@dataclass(frozen=True, slots=True)
class ShakeoutValidation:
    test: ShakeoutTestValidation
    recovery: ShakeoutRecoveryValidation


def _count(bars: tuple[BarContext, ...], predicate: Callable[[BarContext], bool]) -> int:
    """Count bars satisfying a predicate."""
    return sum(predicate(bar) for bar in bars)


def _count_higher_closing_bars(bars: tuple[BarContext, ...]) -> int:
    return sum(closes_higher_than_previous(current, previous) for previous, current in zip(bars, bars[1:]))


def _count_lower_closing_bars(bars: tuple[BarContext, ...]) -> int:
    return sum(closes_lower_than_previous(current, previous) for previous, current in zip(bars, bars[1:]))


def _recent_structural_strength(ctx: BackgroundContext) -> bool:
    swings = ctx.structural_swings
    if len(swings) < 2:
        return False

    recent = swings[-2:]
    if recent[0].swing.type is not SwingType.HIGH:
        return False
    if recent[1].swing.type is not SwingType.HIGH:
        return False
    if recent[0].evaluation.smart_money.overall < config.MIN_PROFESSIONAL_SWING_SCORE:
        return False
    if recent[1].evaluation.smart_money.overall < config.MIN_PROFESSIONAL_SWING_SCORE:
        return False

    return _spread_adjusted_amplitude_improving(recent)


def _recent_structural_weakness(ctx: BackgroundContext) -> bool:
    lows = [item for item in ctx.structural_swings if item.swing.type is SwingType.LOW]
    if len(lows) < 2:
        return False

    previous = lows[-2]
    latest = lows[-1]
    previous_score = previous.evaluation.smart_money.overall
    latest_score = latest.evaluation.smart_money.overall
    amplitude_weakening = _spread_adjusted_amplitude_weakening(ctx)
    professional_weakening = latest_score < previous_score

    return amplitude_weakening and professional_weakening


def _validate_shakeout_test(metrics: pd.DataFrame, shakeout_index: int) -> ShakeoutTestValidation:
    reference = metrics.iloc[shakeout_index]
    shakeout_low = float(reference[COL_LOW])
    shakeout_spread = float(reference[COL_SPREAD])

    start = shakeout_index + 1
    end = min(len(metrics), start + config.SHAKEOUT_TEST_FORWARD_WINDOW)

    for index in range(start, end):
        bar = metrics.iloc[index]
        low = float(bar[COL_LOW])
        distance = low - shakeout_low
        distance_ratio = distance / shakeout_spread
        spread_ratio = float(bar[COL_SPREAD] / shakeout_spread)
        volume_ratio = float(bar[COL_VOLUME] / reference[COL_VOLUME])
        close_position = int(bar[COL_CLOSE_POSITION])

        if distance_ratio > config.SHAKEOUT_TEST_MAX_DISTANCE_RATIO:
            logger.debug(
                "Rejecting shakeout test: too far from low",
                extra={
                    "shakeout_index": shakeout_index,
                    "test_index": index,
                    "distance_ratio": distance_ratio,
                },
            )
            continue

        if distance_ratio < -config.SHAKEOUT_TEST_MAX_PENETRATION_RATIO:
            logger.debug(
                "Rejecting shakeout test: excessive penetration",
                extra={
                    "shakeout_index": shakeout_index,
                    "test_index": index,
                    "distance_ratio": distance_ratio,
                },
            )
            continue

        if volume_ratio > config.SHAKEOUT_TEST_MAX_VOLUME_RATIO:
            logger.debug(
                "Rejecting shakeout test: volume too high",
                extra={
                    "shakeout_index": shakeout_index,
                    "test_index": index,
                    "volume_ratio": volume_ratio,
                },
            )
            continue

        if spread_ratio > config.SHAKEOUT_TEST_MAX_SPREAD_RATIO:
            logger.debug(
                "Rejecting shakeout test: spread too high",
                extra={
                    "shakeout_index": shakeout_index,
                    "test_index": index,
                    "spread_ratio": spread_ratio,
                },
            )
            continue

        if close_position < config.SHAKEOUT_TEST_MIN_CLOSE_POSITION:
            logger.debug(
                "Rejecting shakeout test: close too low",
                extra={
                    "shakeout_index": shakeout_index,
                    "test_index": index,
                    "close_position": close_position,
                },
            )
            continue

        return ShakeoutTestValidation(
            result=ShakeoutTestResult.VALID,
            test_index=index,
            distance_ratio=distance_ratio,
            spread_ratio=spread_ratio,
            volume_ratio=volume_ratio,
            close_position=close_position,
        )

    return ShakeoutTestValidation(
        result=ShakeoutTestResult.NO_TEST,
        test_index=None,
        distance_ratio=None,
        spread_ratio=None,
        volume_ratio=None,
        close_position=None,
    )


def _validate_shakeout_recovery(metrics: pd.DataFrame, test_index: int) -> ShakeoutRecoveryValidation:
    test_reference = metrics.iloc[test_index]
    test_low = float(test_reference[COL_LOW])
    test_close = float(test_reference[COL_CLOSE])
    test_spread = float(test_reference[COL_SPREAD])
    test_volume = float(test_reference[COL_VOLUME])

    start = test_index + 1
    end = min(len(metrics), start + config.SHAKEOUT_RECOVERY_FORWARD_WINDOW)

    for index in range(start, end):
        bar = metrics.iloc[index]
        direction = int(bar[COL_DIRECTION])
        close_position = int(bar[COL_CLOSE_POSITION])
        bar_low = float(bar[COL_LOW])
        bar_close = float(bar[COL_CLOSE])
        bar_spread = float(bar[COL_SPREAD])
        bar_volume = float(bar[COL_VOLUME])

        spread_ratio = bar_spread / test_spread if test_spread > 0.0 else 1.0
        volume_ratio = bar_volume / test_volume if test_volume > 0.0 else 1.0
        close_change = bar_close - test_close
        close_change_spread_ratio = close_change / test_spread if test_spread > 0.0 else 0.0
        low_clearance_ratio = (bar_low - test_low) / test_spread if test_spread > 0.0 else 0.0

        recovery_candidate = (
            direction == 1
            and close_position >= config.SHAKEOUT_RECOVERY_MIN_CLOSE_POSITION
            and bar_close > test_close
            and bar_low >= test_low
        )

        if recovery_candidate:
            logger.debug(
                "Shakeout recovery confirmed",
                extra={
                    "test_index": test_index,
                    "recovery_index": index,
                    "spread_ratio": spread_ratio,
                    "volume_ratio": volume_ratio,
                    "close_change_spread_ratio": close_change_spread_ratio,
                    "low_clearance_ratio": low_clearance_ratio,
                    "close_position": close_position,
                },
            )
            return ShakeoutRecoveryValidation(
                result=ShakeoutRecoveryResult.VALID,
                recovery_index=index,
                spread_ratio=spread_ratio,
                volume_ratio=volume_ratio,
                close_position=close_position,
                close_change_spread_ratio=close_change_spread_ratio,
                low_clearance_ratio=low_clearance_ratio,
            )

    return ShakeoutRecoveryValidation(
        result=ShakeoutRecoveryResult.NO_RECOVERY,
        recovery_index=None,
        spread_ratio=None,
        volume_ratio=None,
        close_position=None,
        close_change_spread_ratio=None,
        low_clearance_ratio=None,
    )


def validate_shakeout(metrics: pd.DataFrame, shakeout_index: int) -> ShakeoutValidation:
    test_validation = _validate_shakeout_test(metrics=metrics, shakeout_index=shakeout_index)
    if test_validation.result != ShakeoutTestResult.VALID:
        return ShakeoutValidation(
            test=test_validation,
            recovery=ShakeoutRecoveryValidation(
                result=ShakeoutRecoveryResult.NO_RECOVERY,
                recovery_index=None,
                spread_ratio=None,
                volume_ratio=None,
                close_position=None,
                close_change_spread_ratio=None,
                low_clearance_ratio=None,
            ),
        )

    assert test_validation.test_index is not None
    recovery_validation = _validate_shakeout_recovery(metrics=metrics, test_index=test_validation.test_index)
    return ShakeoutValidation(test=test_validation, recovery=recovery_validation)


def calculate_shakeout_quality(*, validation: ShakeoutValidation) -> float:
    assert validation.test.result == ShakeoutTestResult.VALID
    assert validation.recovery.result == ShakeoutRecoveryResult.VALID

    test_quality = calculate_test_quality(validation.test)
    recovery_quality = calculate_recovery_quality(validation.recovery)
    quality = (test_quality + recovery_quality) / 2.0
    logger.debug(
        "Calculated shakeout quality",
        extra={
            "test_quality": test_quality,
            "recovery_quality": recovery_quality,
            "quality": quality,
        },
    )
    return max(0.0, min(quality, 1.0))


def calculate_recovery_quality(validation: ShakeoutRecoveryValidation) -> float:
    assert validation.spread_ratio is not None
    assert validation.volume_ratio is not None
    assert validation.close_position is not None
    assert validation.close_change_spread_ratio is not None
    assert validation.low_clearance_ratio is not None

    close_quality = validation.close_position / 4.0
    low_clearance_quality = max(
        0.0,
        min(1.0 - (validation.low_clearance_ratio / config.SHAKEOUT_RECOVERY_LOW_CLEARANCE_TARGET), 1.0),
    )
    close_change_quality = min(
        max(validation.close_change_spread_ratio / config.SHAKEOUT_RECOVERY_CLOSE_CHANGE_TARGET, 0.0),
        1.0,
    )
    spread_quality = min(1.0, config.SHAKEOUT_RECOVERY_SPREAD_TARGET / validation.spread_ratio)
    volume_quality = min(1.0, config.SHAKEOUT_RECOVERY_VOLUME_TARGET / validation.volume_ratio)

    quality = (
        0.30 * close_quality
        + 0.30 * low_clearance_quality
        + 0.15 * close_change_quality
        + 0.125 * spread_quality
        + 0.125 * volume_quality
    )
    quality = max(0.0, min(quality, 1.0))
    logger.debug(
        "Calculated shakeout recovery quality",
        extra={
            "close_quality": close_quality,
            "close_change_quality": close_change_quality,
            "low_hold_quality": low_clearance_quality,
            "spread_quality": spread_quality,
            "volume_quality": volume_quality,
            "quality": quality,
        },
    )
    return quality


def calculate_test_quality(validation: ShakeoutTestValidation) -> float:
    assert validation.distance_ratio is not None
    assert validation.spread_ratio is not None
    assert validation.volume_ratio is not None
    assert validation.close_position is not None

    distance_quality = max(0.0, 1.0 - validation.distance_ratio)
    spread_quality = max(0.0, 1.0 - validation.spread_ratio)
    volume_quality = max(0.0, 1.0 - validation.volume_ratio)
    close_quality = validation.close_position / 4.0
    return (distance_quality + spread_quality + volume_quality + close_quality) / 4.0


# =============================================================================
# Campaign Context
# =============================================================================

def has_recent_strength(ctx: BackgroundContext) -> bool:
    """Recent market behaviour demonstrates strength."""
    score = 0
    if is_confirmed_uptrend(ctx.trend):
        score += 1
    if _count(ctx.bars, is_up_bar) >= config.CAMPAIGN_MIN_UP_BARS:
        score += 1
    if _count_higher_closing_bars(ctx.bars) >= config.CAMPAIGN_MIN_HIGHER_CLOSES:
        score += 1
    if _count(ctx.bars, is_strong_close) >= config.CAMPAIGN_MIN_STRONG_CLOSES:
        score += 1
    if _recent_structural_strength(ctx):
        score += 1
    return score >= config.CAMPAIGN_REQUIRED_SCORE


def has_recent_weakness(ctx: BackgroundContext) -> bool:
    confirmed_downtrend = is_confirmed_downtrend(ctx.trend)
    down_bars = _count(ctx.bars, is_down_bar)
    lower_closes = _count_lower_closing_bars(ctx.bars)
    weak_closes = _count(ctx.bars, is_weak_close)
    structural_weakness = _recent_structural_weakness(ctx)

    score = 0
    if confirmed_downtrend:
        score += 1
    if down_bars >= config.CAMPAIGN_MIN_DOWN_BARS:
        score += 1
    if lower_closes >= config.CAMPAIGN_MIN_LOWER_CLOSES:
        score += 1
    if weak_closes >= config.CAMPAIGN_MIN_WEAK_CLOSES:
        score += 1
    if structural_weakness:
        score += 1
    return score >= config.CAMPAIGN_REQUIRED_SCORE


def has_buying_campaign(ctx: BackgroundContext) -> bool:
    """Smart Money is actively supporting higher prices."""
    return is_confirmed_uptrend(ctx.trend) and has_recent_strength(ctx)


def has_selling_campaign(ctx: BackgroundContext) -> bool:
    recent_weakness = has_recent_weakness(ctx)
    return recent_weakness


def _spread_adjusted_amplitude_improving(recent: Sequence[StructuralSwing]) -> bool:
    if len(recent) < 2:
        return False

    previous = recent[-2]
    current = recent[-1]
    previous_value = previous.evaluation.structure.snapshot.current_spread_adjusted_amplitude
    current_value = current.evaluation.structure.snapshot.current_spread_adjusted_amplitude

    if previous_value is None:
        return False
    if current_value is None:
        return False
    return current_value >= previous_value


def _spread_adjusted_amplitude_weakening(ctx: BackgroundContext) -> bool:
    """Successive structural swings are becoming less powerful relative to current volatility."""
    swings = ctx.structural_swings
    if len(swings) < 2:
        return False

    latest = swings[-1]
    previous = swings[-2]
    latest_amplitude = latest.evaluation.structure.snapshot.current_spread_adjusted_amplitude
    previous_amplitude = previous.evaluation.structure.snapshot.current_spread_adjusted_amplitude

    if latest_amplitude is None or previous_amplitude is None:
        return False
    return latest_amplitude < previous_amplitude


__all__ = [
    "has_recent_strength",
    "has_recent_weakness",
    "has_buying_campaign",
    "has_selling_campaign",
]
