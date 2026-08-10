"""
Professional VSA Swing Scanner
Presentation Formatters

Contains only presentation logic.
No analysis or calculations.
"""

from __future__ import annotations

import pandas as pd

from models import (
    ClosePosition,
    Direction,
    SpreadClass,
    VolumeClass,
)


# =============================================================================
# Enum Formatting
# =============================================================================

def direction_name(value: int) -> str:
    return Direction(value).name.replace("_", " ").title()


def volume_name(value: int) -> str:
    return VolumeClass(value).name.replace("_", " ").title()


def spread_name(value: int) -> str:
    return SpreadClass(value).name.replace("_", " ").title()


def close_position_name(value: int) -> str:
    return ClosePosition(value).name.replace("_", " ").title()


# =============================================================================
# Number Formatting
# =============================================================================

def volume(value: float) -> str:

    if value >= 1_000_000_000:
        return f"{value/1_000_000_000:.2f}B"

    if value >= 1_000_000:
        return f"{value/1_000_000:.2f}M"

    if value >= 1_000:
        return f"{value/1_000:.2f}K"

    return f"{value:.0f}"


def percent(value: float) -> str:
    return f"{value:.2f}%"


def ratio(value: float) -> str:
    return f"{value:.2f}×"


def score(value: float) -> str:
    return f"{value:.0f}/100"


def price(value: float) -> str:
    return f"{value:.2f}"


# =============================================================================
# DataFrame Formatter
# =============================================================================

def dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return a human-readable dataframe.
    """

    d = df.copy()

    if "direction_class" in d.columns:
        d["direction_class"] = d["direction_class"].map(direction_name)

    if "volume_class" in d.columns:
        d["volume_class"] = d["volume_class"].map(volume_name)

    if "spread_class" in d.columns:
        d["spread_class"] = d["spread_class"].map(spread_name)

    if "close_position" in d.columns:
        d["close_position"] = d["close_position"].map(close_position_name)

    if "volume" in d.columns:
        d["volume"] = d["volume"].map(volume)

    if "volume_ratio" in d.columns:
        d["volume_ratio"] = d["volume_ratio"].map(ratio)

    if "spread_ratio" in d.columns:
        d["spread_ratio"] = d["spread_ratio"].map(ratio)

    if "price_change_pct" in d.columns:
        d["price_change_pct"] = d["price_change_pct"].map(percent)

    return d