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
from incremental_scanner import IncrementalScannerEngine
from metrics_engine import MetricsEngine
from production_scanner import (
    scan_actionable_production,
    scan_latest_candidate_production,
)
from scanner import ScannerEngine
from scanner_state import ScannerStateStore


def _metrics(size: int = 120) -> pd.DataFrame:
    points: list[float] = []
    anchors = [100.0, 108.0, 101.0, 111.0, 103.0, 115.0, 106.0]
    for start, end in zip(anchors[:-1], anchors[1:]):
        points.extend(np.linspace(start, end, 18, endpoint=False))
    points.extend(np.linspace(anchors[-1], 118.0, size - len(points)))
    close = np.asarray(points[:size], dtype=float)
    spread = np.full(size, 1.0)
    high = close + 0.5
    low = close - 0.5
    open_ = close - 0.2
    volume = np.full(size, 1_000.0)

    return pd.DataFrame(
        {
            COL_WEEK: [f"2025-01-{i + 1:02d}" for i in range(size)],
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


def _production_metrics() -> pd.DataFrame:
    return MetricsEngine().calculate(_metrics())


def _candidate_signature(candidate) -> tuple[object, bool, float, float, float, tuple[object, ...], tuple[object, ...]]:
    return (
        candidate.qualification,
        candidate.actionable,
        candidate.professional.confidence,
        candidate.professional.scores.net_strength,
        candidate.professional.scores.net_pressure,
        tuple(item.code for item in candidate.qualifying_evidence),
        tuple(item.code for item in candidate.scoring_evidence),
    )


def test_production_scanner_bootstraps_state_and_matches_full_replay(tmp_path) -> None:
    metrics = _production_metrics()
    store = ScannerStateStore(tmp_path)

    candidate = scan_latest_candidate_production(
        metrics,
        symbol="TEST",
        timeframe="1wk",
        state_store=store,
    )
    full = ScannerEngine().scan_to_index(metrics, len(metrics) - 1)

    assert candidate is not None
    assert _candidate_signature(candidate) == _candidate_signature(full)
    assert candidate.bar_index == full.bar_index
    assert candidate.week == full.week
    assert store.path_for("TEST", "1wk").exists()


def test_production_scanner_resumes_persisted_state_and_matches_full_replay(tmp_path) -> None:
    metrics = _production_metrics()
    store = ScannerStateStore(tmp_path)
    split = 72

    state = IncrementalScannerEngine().snapshot(
        metrics,
        target_index=split,
        symbol="TEST",
        timeframe="1wk",
    )
    store.save(state)

    candidate = scan_latest_candidate_production(
        metrics,
        symbol="TEST",
        timeframe="1wk",
        state_store=store,
    )
    full = ScannerEngine().scan_to_index(metrics, len(metrics) - 1)

    assert candidate is not None
    assert _candidate_signature(candidate) == _candidate_signature(full)
    assert candidate.bar_index == full.bar_index
    assert candidate.week == full.week

    refreshed = store.load("TEST", "1wk")
    assert refreshed.last_closed_bar == str(metrics.iloc[-1][COL_WEEK])


def test_production_actionable_list_matches_full_replay(tmp_path) -> None:
    metrics = _production_metrics()
    store = ScannerStateStore(tmp_path)

    candidates = scan_actionable_production(
        metrics,
        symbol="TEST",
        timeframe="1wk",
        state_store=store,
    )
    full = ScannerEngine().scan_actionable(metrics)

    assert len(candidates) == len(full)
    if full:
        assert _candidate_signature(candidates[0]) == _candidate_signature(full[0])


def test_production_scanner_returns_none_before_minimum_replay_bars(tmp_path) -> None:
    metrics = _production_metrics().iloc[: ScannerEngine.MIN_REPLAY_BARS].copy()

    assert scan_latest_candidate_production(
        metrics,
        symbol="TEST",
        timeframe="1wk",
        state_store=ScannerStateStore(tmp_path),
    ) is None
