"""
Professional VSA Swing Scanner

Evidence Rules

Reusable semantic predicates used by all
Evidence collectors.
"""

from __future__ import annotations

from models import (
    BackgroundContext,
    BarContext,
    ClosePosition,
    Direction,
    SpreadClass,
    TrendDirection,
    TrendResult,
    TrendState,
    TrendStructure,
    VolumeClass,
)


# =============================================================================
# Direction
# =============================================================================
def is_up_bar(bar: BarContext) -> bool:
    return bar.direction == Direction.UP


def is_down_bar(bar: BarContext) -> bool:
    return bar.direction == Direction.DOWN


def is_neutral_bar(bar: BarContext) -> bool:
    return bar.direction == Direction.NEUTRAL


def is_bullish_bar(
    bar: BarContext,
) -> bool:
    """
    Alias for an up bar.
    """

    return is_up_bar(bar)


def is_bearish_bar(
    bar: BarContext,
) -> bool:
    """
    Alias for a down bar.
    """

    return is_down_bar(bar)


# =============================================================================
# Volume
# =============================================================================
def is_ultra_high_volume(bar: BarContext) -> bool:
    return bar.volume == VolumeClass.ULTRA_HIGH


def is_very_high_volume(bar: BarContext) -> bool:

    return bar.volume in (

        VolumeClass.VERY_HIGH,

        VolumeClass.ULTRA_HIGH,
    )


def is_high_volume(bar: BarContext) -> bool:

    return bar.volume in (

        VolumeClass.HIGH,

        VolumeClass.VERY_HIGH,

        VolumeClass.ULTRA_HIGH,
    )


def is_average_volume(bar: BarContext) -> bool:
    return bar.volume == VolumeClass.AVERAGE


def is_low_volume(bar: BarContext) -> bool:

    return bar.volume in (

        VolumeClass.ULTRA_LOW,

        VolumeClass.VERY_LOW,

        VolumeClass.LOW,
    )


def is_very_low_volume(bar: BarContext) -> bool:
    return bar.volume <= VolumeClass.VERY_LOW


def is_ultra_low_volume(bar: BarContext) -> bool:
    return bar.volume == VolumeClass.ULTRA_LOW

# =============================================================================
# Spread
# =============================================================================
def is_very_wide_spread(bar: BarContext) -> bool:
    return bar.spread == SpreadClass.VERY_WIDE

def is_wide_spread(bar: BarContext) -> bool:
    return bar.spread in (
        SpreadClass.WIDE,
        SpreadClass.VERY_WIDE,
    )

def is_above_average_spread(bar: BarContext) -> bool:
    return bar.spread >= SpreadClass.ABOVE_AVERAGE

def is_average_spread(bar: BarContext) -> bool:
    return bar.spread == SpreadClass.AVERAGE

def is_below_average_spread(bar: BarContext) -> bool:
    return bar.spread == SpreadClass.BELOW_AVERAGE

def is_narrow_spread(bar: BarContext) -> bool:
    return bar.spread <= SpreadClass.NARROW

def has_strong_spread(
    bar: BarContext,
) -> bool:

    return is_wide_spread(bar)

def has_weak_spread(
    bar: BarContext,
) -> bool:

    return is_narrow_spread(bar)

# =============================================================================
# Close Position
# =============================================================================
def closes_on_high(bar: BarContext) -> bool:
    return bar.close_position == ClosePosition.ON_HIGH

def closes_upper(bar: BarContext) -> bool:
    return bar.close_position in (
        ClosePosition.UPPER,
        ClosePosition.ON_HIGH,
    )

def closes_middle(bar: BarContext) -> bool:
    return bar.close_position == ClosePosition.MIDDLE

def closes_lower(bar: BarContext) -> bool:
    return bar.close_position in (
        ClosePosition.LOWER,
        ClosePosition.ON_LOW,
    )
    
def closes_on_low(bar: BarContext) -> bool:
    return bar.close_position == ClosePosition.ON_LOW

#These are aliases only FOR readability perspective
def is_weak_close(bar: BarContext) -> bool:
    return closes_lower(bar)


def is_strong_close(bar: BarContext) -> bool:
    return closes_upper(bar)


def is_neutral_close(bar: BarContext) -> bool:
    return closes_middle(bar)


# =============================================================================
# Relationships
# =============================================================================
def volume_increasing(
    current: BarContext,
    previous: BarContext,
) -> bool:
    return current.volume > previous.volume


def volume_decreasing(
    current: BarContext,
    previous: BarContext,
) -> bool:
    return current.volume < previous.volume


def spread_increasing(
    current: BarContext,
    previous: BarContext,
) -> bool:
    return current.spread > previous.spread


def spread_decreasing(
    current: BarContext,
    previous: BarContext,
) -> bool:
    return current.spread < previous.spread

# =============================================================================
# Price Relationships
# =============================================================================
def closes_higher_than_previous(
    current: BarContext,
    previous: BarContext,
) -> bool:
    """
    True when the current bar closes above
    the previous bar.
    """
    return current.close_price > previous.close_price


def closes_lower_than_previous(
    current: BarContext,
    previous: BarContext,
) -> bool:
    """
    True when the current bar closes below
    the previous bar.
    """
    return current.close_price < previous.close_price

def makes_lower_high(
    current: BarContext,
    previous: BarContext,
) -> bool:
    return current.high < previous.high


def makes_higher_low(
    current: BarContext,
    previous: BarContext,
) -> bool:
    return current.low > previous.low


def makes_higher_high(
    current: BarContext,
    previous: BarContext,
) -> bool:
    return current.high > previous.high


def makes_lower_low(
    current: BarContext,
    previous: BarContext,
) -> bool:
    return current.low < previous.low


def inside_bar(
    current: BarContext,
    previous: BarContext,
) -> bool:
    return (
        current.high <= previous.high
        and current.low >= previous.low
    )

def outside_bar(
    current: BarContext,
    previous: BarContext,
) -> bool:
    return (
        current.high >= previous.high
        and current.low <= previous.low
    )

# =============================================================================
#                              Market Context
# =============================================================================


# =============================================================================
# Trend Context
# =============================================================================
def is_confirmed_uptrend(
    trend: TrendStructure,
) -> bool:
    """
    Return True when the market is in a confirmed
    bullish trend.
    """

    return (
        trend.direction == TrendDirection.UP
        and trend.state in (
            TrendState.DEVELOPING,
            TrendState.HEALTHY,
            TrendState.EXHAUSTED,
        )
    )

def is_confirmed_downtrend(
    trend: TrendStructure,
) -> bool:
    """
    Return True when the market is in a confirmed
    bearish trend.
    """

    return (
        trend.direction == TrendDirection.DOWN
        and trend.state in (
            TrendState.DEVELOPING,
            TrendState.HEALTHY,
            TrendState.EXHAUSTED,
        )
    )

def is_ranging_market(
    trend: TrendStructure,
) -> bool:
    """
    Return True when no directional trend exists.
    """

    return trend.direction == TrendDirection.RANGE

def is_trend_reversing(
    trend: TrendStructure,
) -> bool:
    """
    Return True when Trend Engine detects reversal.
    """

    return (
        trend.state
        == TrendState.REVERSING
    )

def is_trend_exhausted(
    trend: TrendStructure,
) -> bool:
    """
    Return True when trend shows exhaustion.
    """

    return (
        trend.state
        == TrendState.EXHAUSTED
    )

def is_healthy_trend(
    trend: TrendStructure,
) -> bool:
    """
    Return True when trend is healthy.
    """

    return (
        trend.state
        == TrendState.HEALTHY
    )

def is_developing_trend(
    trend: TrendStructure,
) -> bool:
    """
    Return True when trend is developing.
    """

    return (
        trend.state
        == TrendState.DEVELOPING
    )

def is_correcting_trend(
    trend: TrendStructure,
) -> bool:
    """
    Return True when trend is correcting.
    """

    return (
        trend.state
        == TrendState.CORRECTING
    )    
   
   
    
# ==========================================================
# Public API
# ==========================================================

__all__ = [
    "is_up_bar",
    "is_down_bar",
    "is_neutral_bar",
    "is_bullish_bar",
    "is_bearish_bar",

    "is_ultra_high_volume",
    "is_very_high_volume",
    "is_high_volume",
    "is_average_volume",
    "is_low_volume",
    "is_very_low_volume",
    "is_ultra_low_volume",

    "is_very_wide_spread",
    "is_wide_spread",
    "is_above_average_spread",
    "is_average_spread",
    "is_below_average_spread",
    "is_narrow_spread",
    "has_strong_spread",
    "has_weak_spread",

    "closes_on_high",
    "closes_upper",
    "closes_middle",
    "closes_lower",
    "closes_on_low",

    "volume_increasing",
    "volume_decreasing",
    "spread_increasing",
    "spread_decreasing",
    "is_strong_close",
    "is_weak_close",
    "is_neutral_close",

    "closes_higher_than_previous",
    "closes_lower_than_previous",
    "makes_lower_high",
    "makes_higher_low",    
    "makes_higher_high",
    "makes_lower_low",
    "inside_bar",
    "outside_bar",
    
    "is_confirmed_uptrend",
    "is_confirmed_downtrend",
    "is_ranging_market",
    "is_trend_reversing",
    "is_trend_exhausted",
    "is_healthy_trend",
    "is_developing_trend",
    "is_correcting_trend",

    "closes_higher",
    "closes_lower",

]    