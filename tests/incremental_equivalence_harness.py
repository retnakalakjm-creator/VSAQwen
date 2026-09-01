from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from engine.columns import COL_WEEK
import config
from market_structure.swing_engine import SwingEngine
from scanner_state import ScannerState


@dataclass(frozen=True, slots=True)
class EquivalenceResult:
    split_index: int
    equal_swings: bool
    equal_state: bool
    full_swing_count: int
    incremental_swing_count: int

    @property
    def equivalent(self) -> bool:
        return self.equal_swings and self.equal_state


def snapshot_after_prefix(
    metrics: pd.DataFrame,
    *,
    symbol: str,
    timeframe: str,
    split_index: int,
) -> ScannerState:
    if split_index <= 0 or split_index >= len(metrics):
        raise ValueError("split_index must leave at least one bar after the checkpoint")

    engine = SwingEngine()
    engine.calculate(metrics.iloc[:split_index])
    return engine.snapshot_state(symbol=symbol, timeframe=timeframe)


def _stable_swing_identity(swing, metrics: pd.DataFrame) -> tuple:
    weeks = metrics[COL_WEEK].tolist()
    return (
        str(swing.week_beginning),
        swing.type,
        float(swing.price),
        str(weeks[swing.confirmation_index]),
    )


def _retained_swing_identities(swings, metrics: pd.DataFrame) -> tuple:
    retained = tuple(swings)[-config.STRUCTURE_LOOKBACK :]
    return tuple(_stable_swing_identity(swing, metrics) for swing in retained)


def compare_swing_sequences(
    full_swings,
    incremental_swings,
    *,
    full_metrics: pd.DataFrame,
    incremental_metrics: pd.DataFrame,
) -> bool:
    return _retained_swing_identities(full_swings, full_metrics) == _retained_swing_identities(
        incremental_swings,
        incremental_metrics,
    )


def compare_state(
    full_state: ScannerState,
    incremental_state: ScannerState,
) -> bool:
    return full_state.to_dict() == incremental_state.to_dict()


def _state_anchor_index(metrics: pd.DataFrame, state: ScannerState) -> int:
    weeks = [str(week) for week in metrics[COL_WEEK].tolist()]
    positions = {week: index for index, week in enumerate(weeks)}
    if state.last_closed_bar not in positions:
        raise ValueError(
            f"State last_closed_bar is not present in metrics: {state.last_closed_bar!r}"
        )
    keys = [
        state.candidate.bar_key if state.candidate is not None else None,
        *(item.pivot_bar_key for item in state.confirmed_swings),
        *(item.confirmation_bar_key for item in state.confirmed_swings),
    ]
    missing = [key for key in keys if key is not None and key not in positions]
    if missing:
        raise ValueError(f"State bar identity is not present in metrics: {missing[0]!r}")
    return positions[state.last_closed_bar]


def run_equivalence_case(
    metrics: pd.DataFrame,
    *,
    symbol: str,
    timeframe: str,
    split_index: int,
) -> EquivalenceResult:
    state = snapshot_after_prefix(
        metrics,
        symbol=symbol,
        timeframe=timeframe,
        split_index=split_index,
    )

    full_engine = SwingEngine()
    full_swings = full_engine.calculate(metrics)
    full_state = full_engine.snapshot_state(symbol=symbol, timeframe=timeframe)

    anchor_index = _state_anchor_index(metrics, state)
    reopened = metrics.iloc[anchor_index:].copy()

    incremental_engine = SwingEngine()
    incremental_swings = incremental_engine.calculate_from_state(reopened, state)
    incremental_state = incremental_engine.snapshot_state(
        symbol=symbol,
        timeframe=timeframe,
    )

    return EquivalenceResult(
        split_index=split_index,
        equal_swings=compare_swing_sequences(
            full_swings,
            incremental_swings,
            full_metrics=metrics,
            incremental_metrics=reopened,
        ),
        equal_state=compare_state(full_state, incremental_state),
        full_swing_count=len(full_swings),
        incremental_swing_count=len(incremental_swings),
    )
