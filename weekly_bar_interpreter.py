"""Weekly bar-by-bar professional VSA interpretation.

This module turns completed weekly OHLCV/metric rows into a compact
trader-readable report. It intentionally emits narrative text only and does
not produce entry, stop, target, position-size, broker, or order instructions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from engine.columns import (
    COL_CLOSE,
    COL_CLOSE_RATIO,
    COL_OPEN,
    COL_PRICE_CHANGE_PCT,
    COL_SPREAD_RATIO,
    COL_VOLUME_RATIO,
    COL_WEEK,
)

DEFAULT_WEEKLY_BAR_READING_LOOKBACK = 15
MAX_WEEKLY_BAR_READING_LOOKBACK = 52


@dataclass(frozen=True)
class WeeklyBarReading:
    """One completed weekly bar interpreted in plain English."""

    week: str
    professional_reading: str

    def to_dict(self) -> dict[str, str]:
        return {
            "week": self.week,
            "professional_reading": self.professional_reading,
        }


def build_weekly_bar_readings(
    metrics: pd.DataFrame,
    *,
    lookback: int = DEFAULT_WEEKLY_BAR_READING_LOOKBACK,
) -> list[WeeklyBarReading]:
    """Build one professional reading per completed weekly bar.

    The caller owns data loading and completed-week filtering. This function is
    intentionally single-pass over the requested tail window and does not run a
    scanner replay, mutate state, or persist artifacts.
    """
    if lookback <= 0:
        raise ValueError("lookback must be greater than zero")
    if lookback > MAX_WEEKLY_BAR_READING_LOOKBACK:
        raise ValueError(
            f"lookback must be less than or equal to {MAX_WEEKLY_BAR_READING_LOOKBACK}"
        )
    if metrics.empty:
        return []

    start_index = max(0, len(metrics) - lookback)
    readings: list[WeeklyBarReading] = []
    for index in range(start_index, len(metrics)):
        row = metrics.iloc[index]
        readings.append(
            WeeklyBarReading(
                week=_week(row),
                professional_reading=_professional_reading(row),
            )
        )
    return readings


def _professional_reading(row: pd.Series) -> str:
    direction = _direction(row)
    spread = _spread_label(row)
    close_position = _close_position_label(row)
    volume = _volume_label(row)
    analysis = _bar_analysis(
        direction=direction,
        spread=spread,
        close_position=close_position,
        volume=volume,
    )
    smart_money = _smart_money_interpretation(row, direction)
    bias = _bias(row, direction)
    return f"{analysis} {smart_money} Bias: {bias}."


def _bar_analysis(
    *,
    direction: str,
    spread: str,
    close_position: str,
    volume: str,
) -> str:
    if direction == "bullish":
        return (
            f"The weekly bar was {spread} and bullish, closing {close_position} "
            f"with {volume} volume."
        )
    if direction == "bearish":
        return (
            f"The weekly bar was {spread} and bearish, closing {close_position} "
            f"with {volume} volume."
        )
    return (
        f"The weekly bar was {spread} with little net price progress, closing "
        f"{close_position} on {volume} volume."
    )


def _smart_money_interpretation(row: pd.Series, direction: str) -> str:
    close_ratio = _safe_float(row.get(COL_CLOSE_RATIO), 0.5)
    volume_ratio = _safe_float(row.get(COL_VOLUME_RATIO), 1.0)
    spread_ratio = _safe_float(row.get(COL_SPREAD_RATIO), 1.0)
    price_change_pct = _safe_float(row.get(COL_PRICE_CHANGE_PCT), 0.0)
    recovered_from_low = close_ratio >= 0.62
    closed_weak = close_ratio <= 0.35
    high_effort = volume_ratio >= 1.15 or spread_ratio >= 1.25
    low_effort = volume_ratio <= 0.75 and spread_ratio <= 0.95

    if direction == "bullish" and recovered_from_low and high_effort:
        return (
            "Demand produced a meaningful upward result, so Smart Money appears "
            "to be supporting the advance. In VSA terms, this resembles a Sign "
            "of Strength when it appears after prior weakness or testing."
        )
    if direction == "bullish" and volume_ratio <= 0.75:
        return (
            "Price advanced on lighter effort. Buyers were present, but the move "
            "still needs stronger follow-through before treating it as decisive demand."
        )
    if direction == "bullish" and close_ratio < 0.45:
        return (
            "The rally could not hold the upper part of the range. This suggests "
            "supply appeared into higher prices, so the bullish result is not clean."
        )
    if direction == "bearish" and closed_weak and high_effort:
        return (
            "Heavy effort produced a weak close. This shows supply entering the "
            "market and can act as a distribution or weakness warning if it occurs "
            "near resistance."
        )
    if direction == "bearish" and low_effort:
        return (
            "Price moved lower without strong selling effort. That often means "
            "supply is drying up rather than aggressive distribution continuing."
        )
    if direction == "bearish" and recovered_from_low:
        return (
            "The downside was tested and price recovered from the lower area. "
            "Smart Money may be checking whether meaningful supply remains."
        )
    if abs(price_change_pct) < 0.01 or (spread_ratio <= 0.75 and volume_ratio <= 0.80):
        return (
            "There was limited result and limited effort. This is more consistent "
            "with a pause, test, or No Supply style bar than a decisive campaign."
        )
    return (
        "The bar gives a mixed message. Supply and demand should be read in the "
        "context of the surrounding weekly sequence rather than as a standalone signal."
    )


def _bias(row: pd.Series, direction: str) -> str:
    close_ratio = _safe_float(row.get(COL_CLOSE_RATIO), 0.5)
    volume_ratio = _safe_float(row.get(COL_VOLUME_RATIO), 1.0)
    spread_ratio = _safe_float(row.get(COL_SPREAD_RATIO), 1.0)

    if direction == "bullish" and close_ratio >= 0.65 and (volume_ratio >= 1.0 or spread_ratio >= 1.2):
        return "Bullish"
    if direction == "bullish" and close_ratio >= 0.50:
        return "Mild Bullish"
    if direction == "bearish" and close_ratio <= 0.35 and (volume_ratio >= 1.1 or spread_ratio >= 1.2):
        return "Bearish / Supply Warning"
    if direction == "bearish" and volume_ratio <= 0.75:
        return "Neutral to Mildly Bullish"
    if direction == "bearish":
        return "Neutral to Bearish"
    return "Neutral"


def _direction(row: pd.Series) -> str:
    open_ = _safe_float(row.get(COL_OPEN), 0.0)
    close = _safe_float(row.get(COL_CLOSE), open_)
    if close > open_:
        return "bullish"
    if close < open_:
        return "bearish"
    return "neutral"


def _spread_label(row: pd.Series) -> str:
    ratio = _safe_float(row.get(COL_SPREAD_RATIO), 1.0)
    if ratio >= 1.60:
        return "very wide"
    if ratio >= 1.20:
        return "wide"
    if ratio <= 0.65:
        return "narrow"
    if ratio <= 0.85:
        return "slightly narrow"
    return "normal"


def _volume_label(row: pd.Series) -> str:
    ratio = _safe_float(row.get(COL_VOLUME_RATIO), 1.0)
    if ratio >= 1.60:
        return "very high"
    if ratio >= 1.20:
        return "high"
    if ratio <= 0.65:
        return "low"
    if ratio <= 0.85:
        return "below-average"
    return "normal"


def _close_position_label(row: pd.Series) -> str:
    ratio = _safe_float(row.get(COL_CLOSE_RATIO), 0.5)
    if ratio >= 0.82:
        return "near the high"
    if ratio >= 0.62:
        return "in the upper part of the range"
    if ratio <= 0.18:
        return "near the low"
    if ratio <= 0.38:
        return "in the lower part of the range"
    return "near the middle of the range"


def _week(row: pd.Series) -> str:
    value = row.get(COL_WEEK)
    if isinstance(value, pd.Timestamp):
        return str(value)
    return str(value)


def _safe_float(value: Any, default: float) -> float:
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


__all__ = [
    "DEFAULT_WEEKLY_BAR_READING_LOOKBACK",
    "MAX_WEEKLY_BAR_READING_LOOKBACK",
    "WeeklyBarReading",
    "build_weekly_bar_readings",
]
