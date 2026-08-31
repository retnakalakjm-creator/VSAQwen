from __future__ import annotations

import numpy as np
import pandas as pd

from engine.columns import COL_CLOSE, COL_HIGH, COL_LOW, COL_OPEN, COL_VOLUME, COL_WEEK
from market_structure.swing_engine import SwingEngine
from metrics_engine import MetricsEngine
from models import SwingSearchState
from scanner_state import ScannerState
from trend import TrendAnalyzer


def _bars(size: int = 120) -> pd.DataFrame:
    index = np.arange(size, dtype=float)
    close = 100.0 + np.sin(index / 3.0) * 4.0 + index * 0.12
    spread = 1.0 + (index % 5) * 0.15
    volume = 1000.0 + (index % 7) * 75.0 + index * 2.0
    return pd.DataFrame(
        {
            COL_WEEK: [f"2025-W{i + 1:03d}" for i in range(size)],
            COL_OPEN: close - 0.25,
            COL_HIGH: close + spread / 2.0,
            COL_LOW: close - spread / 2.0,
            COL_CLOSE: close,
            COL_VOLUME: volume,
        }
    )


def _swing_signature(swings) -> tuple[tuple[object, int, int, float, str], ...]:
    return tuple(
        (
            swing.type,
            swing.bar_index,
            swing.confirmation_index,
            swing.price,
            swing.week_beginning,
        )
        for swing in swings
    )


def _structure_signature(structure) -> tuple[object, object, float, float]:
    return (
        structure.direction,
        structure.state,
        structure.strength,
        structure.confidence,
    )


def test_serialized_swing_state_reconstruction_matches_full_history() -> None:
    bars = _bars()
    full_metrics = MetricsEngine().calculate(bars)
    full_engine = SwingEngine()
    full_swings = full_engine.calculate(full_metrics)
    full_structure = TrendAnalyzer().analyze(full_metrics).structure

    split = 80
    prefix_metrics = full_metrics.iloc[: split + 1].copy()
    prefix_engine = SwingEngine()
    prefix_engine.calculate(prefix_metrics)
    state = prefix_engine.snapshot_state(symbol="TEST", timeframe="W")
    restored = ScannerState.from_dict(state.to_dict())

    resumed_engine = SwingEngine()
    resumed_swings = resumed_engine.calculate_from_state(full_metrics, restored)
    resumed_structure = TrendAnalyzer().analyze(full_metrics).structure

    assert _swing_signature(resumed_swings) == _swing_signature(full_swings)
    assert _structure_signature(resumed_structure) == _structure_signature(full_structure)
    assert restored.search_state in (
        SwingSearchState.TRACKING_HIGH,
        SwingSearchState.TRACKING_LOW,
        SwingSearchState.WAITING_HIGH_CONFIRMATION,
        SwingSearchState.WAITING_LOW_CONFIRMATION,
    )
