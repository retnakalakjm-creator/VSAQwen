from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from engine.columns import (
    COL_CLOSE,
    COL_HIGH,
    COL_LOW,
    COL_OPEN,
    COL_VOLUME,
    COL_WEEK,
)
from incremental_scanner import IncrementalScannerEngine
from metrics_engine import MetricsEngine
from production_scanner import CHECKPOINT_DATA_MISMATCH
from production_transition_shadow import (
    compare_actionable_with_transition,
    compare_latest_candidate_with_transition,
)
from scanner import ScannerEngine
from scanner_state import ScannerStateStore


def _shadow_metrics(size: int = 132) -> pd.DataFrame:
    """Generic OHLCV fixture for production-vs-transition shadow checks."""

    anchors = [
        100.0,
        112.0,
        103.0,
        118.0,
        106.0,
        123.0,
        111.0,
        130.0,
        117.0,
        137.0,
        122.0,
        141.0,
        128.0,
    ]
    bars_per_segment = max(6, size // (len(anchors) - 1))
    points: list[float] = []
    for start, end in zip(anchors[:-1], anchors[1:]):
        points.extend(np.linspace(start, end, bars_per_segment, endpoint=False))
    if len(points) < size:
        points.extend(np.linspace(anchors[-1], anchors[-1] + 3.0, size - len(points)))

    close = np.asarray(points[:size], dtype=float)
    delta = np.diff(close, prepend=close[0])
    open_ = close - np.where(delta >= 0.0, 0.3, -0.3)
    spread = 1.1 + (np.arange(size, dtype=float) % 7.0) * 0.1
    high = np.maximum(open_, close) + spread / 2.0
    low = np.minimum(open_, close) - spread / 2.0
    volume = (
        1_000.0
        + (np.arange(size, dtype=float) % 13.0) * 45.0
        + np.where((np.arange(size) % 19) == 0, 275.0, 0.0)
    )

    raw = pd.DataFrame(
        {
            COL_WEEK: [
                value.strftime("%Y-%m-%d")
                for value in pd.date_range("2024-01-01", periods=size, freq="W-MON")
            ],
            COL_OPEN: open_,
            COL_HIGH: high,
            COL_LOW: low,
            COL_CLOSE: close,
            COL_VOLUME: volume,
        }
    )
    return MetricsEngine().calculate(raw)


def test_shadow_latest_bootstrap_matches_transition_runner(tmp_path) -> None:
    metrics = _shadow_metrics()
    store = ScannerStateStore(tmp_path)

    comparison = compare_latest_candidate_with_transition(
        metrics,
        symbol="SHADOW",
        timeframe="1wk",
        state_store=store,
    )

    assert comparison.matched is True
    assert comparison.fallback_diagnostics == ()
    assert comparison.production_candidate is not None
    assert comparison.transition_candidate is not None
    assert comparison.production_candidate.bar_index == len(metrics) - 1
    assert comparison.transition_candidate.bar_index == len(metrics) - 1
    assert store.path_for("SHADOW", "1wk").exists()


def test_shadow_resume_matches_transition_runner_without_fallback(tmp_path) -> None:
    metrics = _shadow_metrics()
    store = ScannerStateStore(tmp_path)
    checkpoint_index = 72

    state = IncrementalScannerEngine().snapshot(
        metrics,
        target_index=checkpoint_index,
        symbol="SHADOW",
        timeframe="1wk",
    )
    store.save(state)

    comparison = compare_latest_candidate_with_transition(
        metrics,
        symbol="SHADOW",
        timeframe="1wk",
        state_store=store,
        allow_full_replay_fallback=False,
    )

    assert comparison.matched is True
    assert comparison.fallback_diagnostics == ()
    assert comparison.production_candidate is not None
    assert comparison.transition_candidate is not None

    refreshed = store.load("SHADOW", "1wk")
    assert refreshed.last_closed_bar == str(metrics.iloc[-1][COL_WEEK])


def test_shadow_actionable_output_matches_transition_runner(tmp_path) -> None:
    metrics = _shadow_metrics()
    store = ScannerStateStore(tmp_path)

    comparison = compare_actionable_with_transition(
        metrics,
        symbol="SHADOW-ACTIONABLE",
        timeframe="1wk",
        state_store=store,
    )

    assert comparison.matched is True
    assert comparison.fallback_diagnostics == ()
    assert len(comparison.production_candidates) == len(comparison.transition_candidates)


def test_shadow_fallback_output_still_matches_transition_runner(tmp_path) -> None:
    metrics = _shadow_metrics()
    store = ScannerStateStore(tmp_path)
    checkpoint_index = 72

    state = IncrementalScannerEngine().snapshot(
        metrics,
        target_index=checkpoint_index,
        symbol="SHADOW-STALE",
        timeframe="1wk",
    )
    store.save(state)

    revised_metrics = metrics.copy()
    revised_metrics.loc[checkpoint_index - 3, COL_VOLUME] = (
        revised_metrics.loc[checkpoint_index - 3, COL_VOLUME] * 1.05
    )

    external_diagnostics: list[str] = []
    comparison = compare_latest_candidate_with_transition(
        revised_metrics,
        symbol="SHADOW-STALE",
        timeframe="1wk",
        state_store=store,
        fallback_diagnostics=external_diagnostics,
    )

    assert comparison.matched is True
    assert any(CHECKPOINT_DATA_MISMATCH in item for item in comparison.fallback_diagnostics)
    assert tuple(external_diagnostics) == comparison.fallback_diagnostics


def test_shadow_matches_empty_production_before_minimum_window(tmp_path) -> None:
    metrics = _shadow_metrics().iloc[: ScannerEngine.MIN_REPLAY_BARS].copy()
    store = ScannerStateStore(tmp_path)

    latest = compare_latest_candidate_with_transition(
        metrics,
        symbol="SHADOW-SHORT",
        timeframe="1wk",
        state_store=store,
    )
    actionable = compare_actionable_with_transition(
        metrics,
        symbol="SHADOW-SHORT-ACTIONABLE",
        timeframe="1wk",
        state_store=ScannerStateStore(tmp_path / "actionable"),
    )

    assert latest.matched is True
    assert latest.production_candidate is None
    assert latest.transition_candidate is None
    assert actionable.matched is True
    assert actionable.production_candidates == ()
    assert actionable.transition_candidates == ()


def test_shadow_helper_is_not_called_by_production_scanner() -> None:
    production_source = Path("production_scanner.py").read_text(encoding="utf-8")

    assert "production_transition_shadow" not in production_source
    assert "compare_latest_candidate_with_transition" not in production_source
    assert "compare_actionable_with_transition" not in production_source
