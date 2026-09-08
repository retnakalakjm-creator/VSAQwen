"""Forward-outcome helpers for historical scanner validation.

This module is analysis-only. It deliberately models execution from the bar
*after* a signal so audits do not accidentally score same-bar entries that would
not have been known at signal time.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Iterable

import pandas as pd

from engine.columns import COL_CLOSE, COL_HIGH, COL_LOW
from models import EvidenceDirection


class OutcomeSide(IntEnum):
    """Directional side used to convert raw returns into favorable returns."""

    SHORT = -1
    NEUTRAL = 0
    LONG = 1


@dataclass(frozen=True, slots=True)
class ForwardOutcome:
    """Point-in-time outcome for one signal and one holding horizon.

    Attributes
    ----------
    signal_bar_index
        Bar where the evidence or scanner candidate was observed.
    execution_bar_index
        First bar after the signal. Entry is modeled at this bar's close.
    exit_bar_index
        Bar used for the horizon exit. If insufficient future bars exist, this
        is the last available bar and ``complete`` is false.
    horizon_bars
        Requested number of bars to hold after the execution bar.
    bars_available
        Number of forward bars actually available after the execution bar.
    raw_return
        Exit close divided by entry close minus one.
    favorable_return
        Raw return multiplied by direction. Long setups favor positive returns;
        short setups favor negative returns; neutral setups report zero.
    mfe
        Maximum favorable excursion after the execution close.
    mae
        Maximum adverse excursion after the execution close, represented as a
        negative value or zero.
    complete
        Whether the full requested horizon was available.
    """

    signal_bar_index: int
    execution_bar_index: int
    exit_bar_index: int
    horizon_bars: int
    bars_available: int
    entry_price: float
    exit_price: float
    raw_return: float
    favorable_return: float
    mfe: float
    mae: float
    complete: bool


def normalize_outcome_side(value: OutcomeSide | EvidenceDirection | int | str) -> OutcomeSide:
    """Normalize common scanner/audit direction values to an outcome side."""
    if isinstance(value, OutcomeSide):
        return value
    if isinstance(value, EvidenceDirection):
        if value is EvidenceDirection.BULLISH:
            return OutcomeSide.LONG
        if value is EvidenceDirection.BEARISH:
            return OutcomeSide.SHORT
        return OutcomeSide.NEUTRAL
    if isinstance(value, int):
        if value > 0:
            return OutcomeSide.LONG
        if value < 0:
            return OutcomeSide.SHORT
        return OutcomeSide.NEUTRAL

    normalized = str(value).strip().lower()
    if normalized in {"long", "bull", "bullish", "buy", "up", "1"}:
        return OutcomeSide.LONG
    if normalized in {"short", "bear", "bearish", "sell", "down", "-1"}:
        return OutcomeSide.SHORT
    if normalized in {"neutral", "flat", "none", "0"}:
        return OutcomeSide.NEUTRAL
    raise ValueError(f"Unsupported outcome side: {value!r}")


def compute_forward_outcome(
    bars: pd.DataFrame,
    *,
    signal_bar_index: int,
    horizon_bars: int,
    side: OutcomeSide | EvidenceDirection | int | str,
    close_column: str = COL_CLOSE,
    high_column: str = COL_HIGH,
    low_column: str = COL_LOW,
) -> ForwardOutcome | None:
    """Compute one next-bar-execution forward outcome.

    Returns ``None`` when there is no execution bar after the signal. This keeps
    latest-bar audits honest: a fresh setup can be recorded, but it cannot be
    scored until at least one later bar exists.
    """
    if horizon_bars <= 0:
        raise ValueError("horizon_bars must be greater than zero")
    if signal_bar_index < 0 or signal_bar_index >= len(bars):
        raise IndexError("signal_bar_index is outside bars")

    missing = [
        column
        for column in (close_column, high_column, low_column)
        if column not in bars.columns
    ]
    if missing:
        raise ValueError(f"Missing required price columns: {missing}")

    execution_bar_index = signal_bar_index + 1
    if execution_bar_index >= len(bars):
        return None

    requested_exit_index = execution_bar_index + horizon_bars
    exit_bar_index = min(requested_exit_index, len(bars) - 1)
    bars_available = max(0, exit_bar_index - execution_bar_index)
    complete = exit_bar_index == requested_exit_index

    entry_price = float(bars.iloc[execution_bar_index][close_column])
    exit_price = float(bars.iloc[exit_bar_index][close_column])
    if entry_price <= 0:
        raise ValueError("entry price must be greater than zero")

    raw_return = exit_price / entry_price - 1.0
    outcome_side = normalize_outcome_side(side)
    favorable_return = raw_return * int(outcome_side)

    future_window = bars.iloc[execution_bar_index + 1 : exit_bar_index + 1]
    if future_window.empty:
        mfe = 0.0
        mae = 0.0
    elif outcome_side is OutcomeSide.LONG:
        mfe = float(future_window[high_column].max()) / entry_price - 1.0
        mae = float(future_window[low_column].min()) / entry_price - 1.0
        mae = min(mae, 0.0)
    elif outcome_side is OutcomeSide.SHORT:
        mfe = entry_price / float(future_window[low_column].min()) - 1.0
        adverse = entry_price / float(future_window[high_column].max()) - 1.0
        mae = min(adverse, 0.0)
    else:
        mfe = 0.0
        mae = 0.0

    return ForwardOutcome(
        signal_bar_index=signal_bar_index,
        execution_bar_index=execution_bar_index,
        exit_bar_index=exit_bar_index,
        horizon_bars=horizon_bars,
        bars_available=bars_available,
        entry_price=entry_price,
        exit_price=exit_price,
        raw_return=raw_return,
        favorable_return=favorable_return,
        mfe=mfe,
        mae=mae,
        complete=complete,
    )


def compute_forward_outcomes(
    bars: pd.DataFrame,
    *,
    signal_bar_indices: Iterable[int],
    horizons: Iterable[int],
    side: OutcomeSide | EvidenceDirection | int | str,
) -> list[ForwardOutcome]:
    """Compute outcomes for many signal indexes and horizons.

    Incomplete latest signals are skipped only when no execution bar exists.
    Partially available horizons are retained with ``complete=False`` so audits
    can decide whether to exclude them later.
    """
    outcomes: list[ForwardOutcome] = []
    normalized_side = normalize_outcome_side(side)
    for signal_bar_index in signal_bar_indices:
        for horizon_bars in horizons:
            outcome = compute_forward_outcome(
                bars,
                signal_bar_index=signal_bar_index,
                horizon_bars=horizon_bars,
                side=normalized_side,
            )
            if outcome is not None:
                outcomes.append(outcome)
    return outcomes


__all__ = [
    "ForwardOutcome",
    "OutcomeSide",
    "compute_forward_outcome",
    "compute_forward_outcomes",
    "normalize_outcome_side",
]
