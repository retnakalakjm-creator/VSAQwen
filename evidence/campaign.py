"""
Campaign Context Engine

Determines whether professional buying or
selling campaigns are active.
"""
from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
import inspect

import pandas as pd

from engine.columns import COL_CLOSE, COL_CLOSE_POSITION, COL_DIRECTION, COL_LOW, COL_SPREAD, COL_VOLUME
import config
from collections.abc import Sequence
from .rules import (
    
    closes_higher_than_previous,
    closes_lower_than_previous,
    is_confirmed_uptrend,
    is_confirmed_downtrend,
    is_down_bar,
    is_strong_close,
    is_up_bar,
    is_weak_close,
)
from models import (
    BackgroundContext,
    BarContext,
    StructuralSwing,
    SwingType,
)

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



def _count(
    bars: tuple[
        BarContext,
        ...
    ],
    predicate: Callable[
        [BarContext],
        bool,
    ],
) -> int:
    """
    Count bars satisfying a predicate.
    """

    return sum(
        predicate(bar)
        for bar in bars
    )

def _count_higher_closing_bars(
    bars: tuple[
        BarContext,
        ...
    ],
) -> int:

    return sum(

        closes_higher_than_previous(current, previous)

        for previous, current in zip(
            bars,
            bars[1:],
        )

    )

def _count_lower_closing_bars(
    bars: tuple[
        BarContext,
        ...
    ],
) -> int:

    return sum(

        closes_lower_than_previous(current, previous)

        for previous, current in zip(
            bars,
            bars[1:],
        )

    )

def _recent_structural_strength(
    ctx: BackgroundContext,
) -> bool:

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

    return (
         _spread_adjusted_amplitude_improving(recent)
    )

def _recent_structural_weakness(
    ctx: BackgroundContext,
) -> bool:

    lows = [
        item
        for item in ctx.structural_swings
        if item.swing.type is SwingType.LOW
    ]

    if len(lows) < 2:
        return False

    previous = lows[-2]
    latest = lows[-1]

    previous_score = (
        previous.evaluation.smart_money.overall
    )

    latest_score = (
        latest.evaluation.smart_money.overall
    )

    amplitude_weakening = (
        _spread_adjusted_amplitude_weakening(ctx)
    )

    professional_weakening = (
        latest_score < previous_score
    )

    return (
        amplitude_weakening
        and professional_weakening
    )

def _validate_shakeout_test(
    metrics: pd.DataFrame,    
    shakeout_index: int,
) -> ShakeoutTestValidation:

    reference = metrics.iloc[shakeout_index]

    shakeout_low = float(
        reference[COL_LOW]
    )

    shakeout_spread = float(
        reference[COL_SPREAD]
    )

    start = shakeout_index + 1

    end = min(
        len(metrics),
        start + config.SHAKEOUT_TEST_LOOKAHEAD,
    )

    for index in range(start, end):

        bar = metrics.iloc[index]

        low = float(
            bar[COL_LOW]
        )

        distance = low - shakeout_low

        distance_ratio = (
            distance / shakeout_spread
        )

        spread_ratio = float(
            bar[COL_SPREAD]
            / shakeout_spread
        )

        volume_ratio = float(
            bar[COL_VOLUME]
            / reference[COL_VOLUME]
        )

        close_position = int(
            bar[COL_CLOSE_POSITION]
        )
        # print(
        #     "TEST CANDIDATE",
        #     {
        #         "shakeout_index": shakeout_index,
        #         "test_index": index,
        #         "distance_ratio": distance_ratio,
        #         "spread_ratio": spread_ratio,
        #         "volume_ratio": volume_ratio,
        #         "close_position": close_position,
        #     },
        # )
        # ----------------------------------------
        # Test must revisit the shakeout low
        # ----------------------------------------

        if (
            distance_ratio
            > config.SHAKEOUT_TEST_MAX_DISTANCE_RATIO
        ):
            print("  REJECT: too far from low")
            continue

        # ----------------------------------------
        # Reject material penetration
        # ----------------------------------------

        if (
            distance_ratio
            < -config.SHAKEOUT_TEST_MAX_PENETRATION_RATIO
        ):
            print("  REJECT: excessive penetration")
            continue

        # ----------------------------------------
        # Test must show reduced effort
        # ----------------------------------------
        if volume_ratio > config.SHAKEOUT_TEST_MAX_VOLUME_RATIO:
            print("  REJECT: volume too high")
            continue

        if spread_ratio > config.SHAKEOUT_TEST_MAX_SPREAD_RATIO:
            print("  REJECT: spread too high")
            continue


        # reduced_volume = (
        #     volume_ratio
        #     <= config.SHAKEOUT_TEST_MAX_VOLUME_RATIO
        # )

        # reduced_spread = (
        #     spread_ratio
        #     <= config.SHAKEOUT_TEST_MAX_SPREAD_RATIO
        # )

        # if not reduced_volume or not reduced_spread:
        #     continue

        # ----------------------------------------
        # Test must close acceptably
        # ----------------------------------------

        if (
            close_position
            < config.SHAKEOUT_TEST_MIN_CLOSE_POSITION
        ):
            print("  REJECT: close too low")
            continue

        # ----------------------------------------
        # Valid test found
        # ----------------------------------------
        # print(
        #     "  >>> VALID TEST",
        #     {
        #         "shakeout_index": shakeout_index,
        #         "test_index": index,
        #     },
        # )

        return ShakeoutTestValidation(
            result=ShakeoutTestResult.VALID,
            test_index=index,
            distance_ratio=distance_ratio,
            spread_ratio=spread_ratio,
            volume_ratio=volume_ratio,
            close_position=close_position,
        )

    # ----------------------------------------
    # No valid test found
    # ----------------------------------------
    
    return ShakeoutTestValidation(
        result=ShakeoutTestResult.NO_TEST,
        test_index=None,
        distance_ratio=None,
        spread_ratio=None,
        volume_ratio=None,
        close_position=None,
    )

def _validate_shakeout_recovery(
    metrics: pd.DataFrame,
    test_index: int,
) -> ShakeoutRecoveryValidation:

    test_reference = metrics.iloc[test_index]

    test_low = float(
        test_reference[COL_LOW]
    )

    test_close = float(
        test_reference[COL_CLOSE]
    )
    test_spread = float(test_reference[COL_SPREAD])
    test_volume = float(test_reference[COL_VOLUME])
    start = test_index + 1

    end = min(
        len(metrics),
        start + config.SHAKEOUT_RECOVERY_LOOKAHEAD,
    )

    for index in range(start, end):

        bar = metrics.iloc[index]

        direction = int(
            bar[COL_DIRECTION]
        )

        close_position = int(
            bar[COL_CLOSE_POSITION]
        )

        bar_low = float(
            bar[COL_LOW]
        )

        bar_close = float(
            bar[COL_CLOSE]
        )
        bar_spread = float(bar[COL_SPREAD])
        bar_volume = float(bar[COL_VOLUME])
        
        if test_spread > 0.0:
            spread_ratio = bar_spread / test_spread
        else:
            spread_ratio = 1.0

        if test_volume > 0.0:
            volume_ratio = bar_volume / test_volume
        else:
            volume_ratio = 1.0

        close_change = bar_close - test_close

        if test_spread > 0.0:
            close_change_spread_ratio = (
                close_change / test_spread
            )
        else:
            close_change_spread_ratio = 0.0

        if test_spread > 0.0:
            low_clearance_ratio = (
                bar_low - test_low
            ) / test_spread
        else:
            low_clearance_ratio = 0.0
        
        recovery_candidate = (
            direction == 1
            and close_position
                >= config.SHAKEOUT_RECOVERY_MIN_CLOSE_POSITION
            and bar_close > test_close
            and bar_low >= test_low
        )       

        if recovery_candidate:
        #    print(
        #         ">>> RECOVERY CONFIRMED",
        #         {
        #             "test_index": test_index,
        #             "recovery_index": index,
        #             "spread_ratio": spread_ratio,
        #             "volume_ratio": volume_ratio,
        #             "close_change": close_change,
        #             "close_change_ratio": close_change_ratio,
        #             "low_clearance_ratio": low_clearance_ratio,
        #             "close_position": close_position,
        #         },
        #     )

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

def validate_shakeout(
    metrics: pd.DataFrame,   
    shakeout_index: int,
) -> ShakeoutValidation:

    # 1. First validate the TEST
    test_validation = _validate_shakeout_test(
        metrics=metrics,        
        shakeout_index=shakeout_index,
    )
    
    # 2. No valid test → recovery cannot be evaluated
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
    
    # 3. We now know the test index exists
    assert test_validation.test_index is not None

    # 4. Validate recovery after the accepted test
    recovery_validation = _validate_shakeout_recovery(
        metrics=metrics,
        test_index=test_validation.test_index,
    )
    
    # 5. Return complete validation
    return ShakeoutValidation(
        test=test_validation,
        recovery=recovery_validation,
    )

def calculate_shakeout_quality(
    *,
    validation: ShakeoutValidation,
) -> float:

    assert (
        validation.test.result
        == ShakeoutTestResult.VALID
    )

    assert (
        validation.recovery.result
        == ShakeoutRecoveryResult.VALID
    )

    test_quality = calculate_test_quality(
        validation.test,
    )

    recovery_quality = calculate_recovery_quality(
        validation.recovery,
    )

    quality = (
        test_quality
        + recovery_quality
    ) / 2.0
    print(
        "SHAKEOUT QUALITY",
        {
            "test_quality": test_quality,
            "recovery_quality": recovery_quality,
            "quality": quality,
        },
    )
    return max(
        0.0,
        min(quality, 1.0),
    )


def calculate_recovery_quality(
    validation: ShakeoutRecoveryValidation,
) -> float:

    assert validation.spread_ratio is not None
    assert validation.volume_ratio is not None
    assert validation.close_position is not None
    assert validation.close_change_spread_ratio is not None
    assert validation.low_clearance_ratio is not None

    # --------------------------------------------------
    # Core recovery quality
    # --------------------------------------------------

    # Strong close is one of the most important signs
    # that demand has overcome the selling pressure.
    close_quality = (
        validation.close_position / 4.0
    )

    # The closer the recovery low remains to the
    # shakeout/test low, the better the low is being held.
    low_clearance_quality = max(
        0.0,
        min(
            1.0
            - (
                validation.low_clearance_ratio
                / config.SHAKEOUT_RECOVERY_LOW_CLEARANCE_TARGET
            ),
            1.0,
        ),
    )

    # --------------------------------------------------
    # Secondary recovery quality
    # --------------------------------------------------

    # A stronger recovery close is better, but the raw
    # percentage change should not dominate the quality.
    close_change_quality = min(
        max(
            validation.close_change_spread_ratio
            / config.SHAKEOUT_RECOVERY_CLOSE_CHANGE_TARGET,
            0.0,
        ),
        1.0,
    )

    # Recovery spread below the shakeout/test spread is
    # supportive, not automatically "bad".
    spread_quality = min(
        1.0,
        config.SHAKEOUT_RECOVERY_SPREAD_TARGET
        / validation.spread_ratio,
    )

    # Lower recovery volume than the test is also
    # supportive because it indicates reduced selling
    # pressure during the recovery.
    volume_quality = min(
        1.0,
        config.SHAKEOUT_RECOVERY_VOLUME_TARGET
        / validation.volume_ratio,
    )

    # --------------------------------------------------
    # Weighted quality
    # --------------------------------------------------

    quality = (
        0.30 * close_quality
        + 0.30 * low_clearance_quality
        + 0.15 * close_change_quality
        + 0.125 * spread_quality
        + 0.125 * volume_quality
    )
    quality = max(
        0.0,
        min(quality, 1.0),
    )
    print(
        "SHAKEOUT RECOVERY QUALITY",
        {
            "close_quality": close_quality,
            "close_change_quality": close_change_quality,
            "low_hold_quality": low_clearance_quality,
            "spread_quality": spread_quality,
            "volume_quality": volume_quality,
            "quality": quality,
        },
    )
    return quality



def calculate_test_quality(
    validation: ShakeoutTestValidation,
) -> float:

    assert validation.distance_ratio is not None
    assert validation.spread_ratio is not None
    assert validation.volume_ratio is not None
    assert validation.close_position is not None

    distance_quality = max(
        0.0,
        1.0 - validation.distance_ratio,
    )

    spread_quality = max(
        0.0,
        1.0 - validation.spread_ratio,
    )

    volume_quality = max(
        0.0,
        1.0 - validation.volume_ratio,
    )

    close_quality = (
        validation.close_position / 4.0
    )

    quality = (
        distance_quality
        + spread_quality
        + volume_quality
        + close_quality
    ) / 4.0

    # print(
    #     "SHAKEOUT TEST QUALITY",
    #     {
    #         "distance_quality": distance_quality,
    #         "spread_quality": spread_quality,
    #         "volume_quality": volume_quality,
    #         "close_quality": close_quality,
    #         "quality": quality,
    #     },
    # )

    return quality
# =============================================================================
# Campaign Context
# =============================================================================    
def has_recent_strength(
    ctx: BackgroundContext,
) -> bool:
    """
    Recent market behaviour
    demonstrates strength.
    """

    score = 0

    if is_confirmed_uptrend(
        ctx.trend,
    ):
        score += 1

    if _count(
        ctx.bars,
        is_up_bar,
    ) >= config.CAMPAIGN_MIN_UP_BARS:
        score += 1

    if _count_higher_closing_bars(
        ctx.bars,
    ) >= config.CAMPAIGN_MIN_HIGHER_CLOSES:
        score += 1

    if _count(
       ctx.bars,
        is_strong_close,
    ) >= config.CAMPAIGN_MIN_STRONG_CLOSES:
        score += 1

    if _recent_structural_strength(ctx):
        score += 1
        
    return score >= config.CAMPAIGN_REQUIRED_SCORE

def has_recent_weakness(
    ctx: BackgroundContext,
) -> bool:

    confirmed_downtrend = is_confirmed_downtrend(
        ctx.trend,
    )

    down_bars = _count(
        ctx.bars,
        is_down_bar,
    )

    lower_closes = _count_lower_closing_bars(
        ctx.bars,
    )

    weak_closes = _count(
        ctx.bars,
        is_weak_close,
    )

    structural_weakness = _recent_structural_weakness(
        ctx,
    )

    score = 0

    # Broader trend context contributes,
    # but is NOT mandatory.
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

def has_buying_campaign(
    ctx: BackgroundContext,
) -> bool:
    """
    Smart Money is actively
    supporting higher prices.
    """

    return (
        is_confirmed_uptrend(ctx.trend)
        and has_recent_strength(ctx)
    )

def has_selling_campaign(
    ctx: BackgroundContext,    
) -> bool:
    recent_weakness = has_recent_weakness(
        ctx,       
    )    
    return recent_weakness

def _spread_adjusted_amplitude_improving(
    recent: Sequence[StructuralSwing],
) -> bool:

    if len(recent) < 2:
        return False

    previous = recent[-2]
    current = recent[-1]

    previous_value = (
        previous.evaluation.structure.snapshot
        .current_spread_adjusted_amplitude
    )

    current_value = (
        current.evaluation.structure.snapshot
        .current_spread_adjusted_amplitude
    )

    if previous_value is None:
        return False

    if current_value is None:
        return False

    return current_value >= previous_value

def _spread_adjusted_amplitude_weakening(
    ctx: BackgroundContext,
) -> bool:
    """
    Successive structural swings are becoming
    less powerful relative to the current market
    volatility.
    """

    swings = ctx.structural_swings

    if len(swings) < 2:
        return False

    latest = swings[-1]
    previous = swings[-2]

    latest_amplitude = (
        latest.evaluation.structure.snapshot
        .current_spread_adjusted_amplitude
    )

    previous_amplitude = (
        previous.evaluation.structure.snapshot
        .current_spread_adjusted_amplitude
    )

    if (
        latest_amplitude is None
        or previous_amplitude is None
    ):
        return False

    return latest_amplitude < previous_amplitude

# def _spread_adjusted_amplitude_weakening(
#     ctx: BackgroundContext,
# ) -> bool:
#     """
#     Successive structural swings are becoming
#     less powerful relative to the current market
#     volatility.
#     """

#     swings = ctx.structural_swings

#     if len(swings) < 2:
#         return False

#     latest = swings[-1]
#     previous = swings[-2]
    
#     return (
#         latest.score.structure.current_spread_adjusted_amplitude
#         < previous.score.structure.current_spread_adjusted_amplitude
#     )
# ==========================================================
# Public API
# ==========================================================
__all__ = [

    "has_recent_strength",

    "has_recent_weakness",

    "has_buying_campaign",

    "has_selling_campaign",

]    