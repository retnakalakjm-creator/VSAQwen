from __future__ import annotations

import numpy as np
import pandas as pd

from engine.columns import (
    COL_AVG_SPREAD,
    COL_AVG_VOLUME,
    COL_CLOSE,
    COL_HIGH,
    COL_LOW,
    COL_OPEN,
    COL_SPREAD,
    COL_VOLUME,
    COL_WEEK,
)
from metrics_engine import MetricsEngine
from scanner import ScannerEngine


def _metrics(size: int = 48) -> pd.DataFrame:
    close = np.linspace(100.0, 125.0, size)
    spread = np.full(size, 1.0)
    high = close + 0.5
    low = close - 0.5
    open_ = close - 0.2
    volume = np.full(size, 1_000.0)

    weekly = pd.DataFrame(
        {
            COL_WEEK: [f"2025-W{i + 1:02d}" for i in range(size)],
            COL_OPEN: open_,
            COL_HIGH: high,
            COL_LOW: low,
            COL_CLOSE: close,
            COL_VOLUME: volume,
            COL_SPREAD: spread,
            COL_AVG_VOLUME: volume,
            COL_AVG_SPREAD: spread,
        }
    )
    return MetricsEngine().calculate(weekly)


def test_historical_candidate_exposes_next_execution_bar() -> None:
    metrics = _metrics()
    target_index = ScannerEngine.MIN_REPLAY_BARS + 5

    candidate = ScannerEngine().scan_to_index(metrics, target_index)

    assert candidate.bar_index == target_index
    assert candidate.week == str(metrics.iloc[target_index][COL_WEEK])
    assert candidate.signal_bar_index == candidate.bar_index
    assert candidate.signal_week == candidate.week
    assert candidate.execution_bar_index == target_index + 1
    assert candidate.execution_week == str(metrics.iloc[target_index + 1][COL_WEEK])
    assert candidate.execution_available is True
    assert candidate.execution_pending is False


def test_latest_candidate_marks_execution_as_pending_until_next_bar() -> None:
    metrics = _metrics()
    target_index = len(metrics) - 1

    candidate = ScannerEngine().scan_to_index(metrics, target_index)

    assert candidate.signal_bar_index == target_index
    assert candidate.signal_week == str(metrics.iloc[target_index][COL_WEEK])
    assert candidate.execution_bar_index is None
    assert candidate.execution_week is None
    assert candidate.execution_available is False
    assert "not a same-bar entry" in candidate.execution_note
