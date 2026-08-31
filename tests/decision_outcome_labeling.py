from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True, slots=True)
class DecisionOutcome:
    signal_index: int
    horizon: int
    direction: int
    entry_close: float
    exit_close: float | None
    forward_return: float | None
    maximum_favorable_excursion: float | None
    maximum_adverse_excursion: float | None
    complete: bool


def _column(frame: pd.DataFrame, name: str) -> str:
    if name in frame.columns:
        return name
    lowered = {str(column).lower(): column for column in frame.columns}
    try:
        return lowered[name.lower()]
    except KeyError as exc:
        raise ValueError(f"Missing required outcome column: {name}") from exc


def label_outcome(
    frame: pd.DataFrame,
    signal_index: int,
    direction: int,
    horizon: int,
) -> DecisionOutcome:
    if direction not in (-1, 1):
        raise ValueError("direction must be -1 or 1")
    if horizon <= 0:
        raise ValueError("horizon must be greater than zero")
    if signal_index < 0 or signal_index >= len(frame):
        raise IndexError("signal_index is outside the frame")

    close_col = _column(frame, "Close")
    high_col = _column(frame, "High")
    low_col = _column(frame, "Low")

    entry = float(frame.iloc[signal_index][close_col])
    end = signal_index + horizon
    if end >= len(frame):
        return DecisionOutcome(
            signal_index=signal_index,
            horizon=horizon,
            direction=direction,
            entry_close=entry,
            exit_close=None,
            forward_return=None,
            maximum_favorable_excursion=None,
            maximum_adverse_excursion=None,
            complete=False,
        )

    future = frame.iloc[signal_index + 1 : end + 1]
    exit_close = float(future.iloc[-1][close_col])
    forward_return = direction * (exit_close / entry - 1.0)

    highs = future[high_col].astype(float)
    lows = future[low_col].astype(float)
    if direction == 1:
        mfe = float(max(0.0, highs.max() / entry - 1.0))
        mae = float(max(0.0, 1.0 - lows.min() / entry))
    else:
        mfe = float(max(0.0, 1.0 - lows.min() / entry))
        mae = float(max(0.0, highs.max() / entry - 1.0))

    return DecisionOutcome(
        signal_index=signal_index,
        horizon=horizon,
        direction=direction,
        entry_close=entry,
        exit_close=exit_close,
        forward_return=float(forward_return),
        maximum_favorable_excursion=mfe,
        maximum_adverse_excursion=mae,
        complete=True,
    )
