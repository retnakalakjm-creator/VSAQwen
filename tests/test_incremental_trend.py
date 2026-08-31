from __future__ import annotations

import numpy as np
import pandas as pd

from data import incremental_replay_window
from market_structure.incremental_trend import IncrementalTrendAnalyzer
from market_structure.swing_engine import SwingEngine
from metrics_engine import MetricsEngine
from scanner_state import ScannerState
from trend import TrendAnalyzer


def _bars(size: int = 120) -> pd.DataFrame:
    index = np.arange(size, dtype=float)
    close = 100.0 + np.sin(index / 3.0) * 4.0 + index * 0.12
    spread = 1.0 + (index % 5) * 0.15
    volume = 1000.0 + (index % 7) * 75.0 + index * 2.0
    return pd.DataFrame(
        {
            "week_beginning": [f"2025-W{i + 1:03d}" for i in range(size)],
            "open": close - 0.25,
            "high": close + spread / 2.0,
            "low": close - spread / 2.0,
            "close": close,
            "volume": volume,
        }
    )


def _structure_signature(structure) -> tuple[object, object, float, float, int]:
    return (
        structure.direction,
        structure.state,
        structure.strength,
        structure.confidence,
        structure.swing_count,
    )


def test_incremental_trend_matches_full_history() -> None:
    metrics = MetricsEngine().calculate(_bars())
    split = 80

    prefix_engine = SwingEngine()
    prefix_engine.calculate(metrics.iloc[: split + 1].copy())
    state = ScannerState.from_dict(
        prefix_engine.snapshot_state(symbol="TEST", timeframe="W").to_dict()
    )

    expected = TrendAnalyzer().analyze(metrics)
    actual = IncrementalTrendAnalyzer().analyze_from_state(metrics, state)

    assert _structure_signature(actual.structure) == _structure_signature(
        expected.structure
    )


def test_incremental_trend_matches_from_replay_window() -> None:
    metrics = MetricsEngine().calculate(_bars())
    split = 80

    prefix_engine = SwingEngine()
    prefix_engine.calculate(metrics.iloc[: split + 1].copy())
    state = ScannerState.from_dict(
        prefix_engine.snapshot_state(symbol="TEST", timeframe="W").to_dict()
    )

    replay_window = incremental_replay_window(metrics, state)
    expected = TrendAnalyzer().analyze(metrics)
    actual = IncrementalTrendAnalyzer().analyze_from_state(replay_window, state)

    assert _structure_signature(actual.structure) == _structure_signature(
        expected.structure
    )
