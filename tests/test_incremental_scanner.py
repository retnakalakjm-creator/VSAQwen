from __future__ import annotations

import numpy as np
import pandas as pd

from data import METRIC_REPLAY_SEED_BARS
from market_structure.incremental_scanner import IncrementalStructurePipeline
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


def _state(metrics: pd.DataFrame) -> ScannerState:
    split = 80
    engine = SwingEngine()
    engine.calculate(metrics.iloc[: split + 1].copy())
    return ScannerState.from_dict(
        engine.snapshot_state(symbol="TEST", timeframe="W").to_dict()
    )


def _signature(structure) -> tuple[object, object, float, float, int]:
    return (
        structure.direction,
        structure.state,
        structure.strength,
        structure.confidence,
        structure.swing_count,
    )


def test_incremental_structure_pipeline_matches_full_history() -> None:
    metrics = MetricsEngine().calculate(_bars())
    state = _state(metrics)

    pipeline = IncrementalStructurePipeline()
    actual = pipeline.analyze(metrics, state)
    expected = TrendAnalyzer().analyze(metrics)

    assert _signature(actual.structure) == _signature(expected.structure)


def test_incremental_structure_pipeline_uses_safe_replay_window() -> None:
    metrics = MetricsEngine().calculate(_bars())
    state = _state(metrics)

    replay = IncrementalStructurePipeline.replay_window(metrics, state)

    assert len(replay) <= len(metrics)
    assert len(replay) >= METRIC_REPLAY_SEED_BARS + 1
    assert str(replay.iloc[-1]["week_beginning"]) == str(
        metrics.iloc[-1]["week_beginning"]
    )
