from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

import scanner_transition
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
from production_scanner import (
    CHECKPOINT_CORRUPT,
    CHECKPOINT_DATA_MISMATCH,
    scan_latest_candidate_production,
)
from scanner import ScannerEngine
from scanner_state import ScannerStateStore
from scanner_transition import ScannerTransitionEngine


def _metrics(size: int = 96) -> pd.DataFrame:
    anchors = [
        100.0,
        111.0,
        103.0,
        118.0,
        108.0,
        126.0,
        115.0,
        132.0,
        121.0,
        138.0,
    ]
    bars_per_segment = max(6, size // (len(anchors) - 1))
    points: list[float] = []
    for start, end in zip(anchors[:-1], anchors[1:]):
        points.extend(np.linspace(start, end, bars_per_segment, endpoint=False))
    if len(points) < size:
        points.extend(np.linspace(anchors[-1], anchors[-1] + 2.0, size - len(points)))

    close = np.asarray(points[:size], dtype=float)
    delta = np.diff(close, prepend=close[0])
    open_ = close - np.where(delta >= 0.0, 0.3, -0.3)
    spread = 1.0 + (np.arange(size, dtype=float) % 6.0) * 0.12
    high = np.maximum(open_, close) + spread / 2.0
    low = np.minimum(open_, close) - spread / 2.0
    volume = (
        1_000.0
        + (np.arange(size, dtype=float) % 9.0) * 60.0
        + np.where((np.arange(size) % 13) == 0, 325.0, 0.0)
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


def _count_transition_replays(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[int, int, bool]]:
    calls: list[tuple[int, int, bool]] = []
    original = ScannerTransitionEngine.run_to_index

    def recording_run_to_index(
        self: ScannerTransitionEngine,
        metrics: pd.DataFrame,
        target_index: int,
        *,
        state=None,
    ):
        calls.append((len(metrics), target_index, state is not None))
        return original(self, metrics, target_index, state=state)

    monkeypatch.setattr(
        scanner_transition.ScannerTransitionEngine,
        "run_to_index",
        recording_run_to_index,
    )
    return calls


def test_bootstrap_candidate_and_snapshot_share_one_transition_replay(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    metrics = _metrics()
    target_index = len(metrics) - 1
    store = ScannerStateStore(tmp_path)
    calls = _count_transition_replays(monkeypatch)

    candidate = scan_latest_candidate_production(
        metrics,
        symbol="MEASURE-BOOTSTRAP",
        timeframe="1wk",
        state_store=store,
    )

    assert candidate is not None
    assert candidate.bar_index == target_index
    assert calls == [(len(metrics), target_index, False)]
    assert store.load("MEASURE-BOOTSTRAP", "1wk").last_closed_bar == str(
        metrics.iloc[target_index][COL_WEEK]
    )


def test_corrupt_checkpoint_fallback_candidate_and_snapshot_share_one_replay(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    metrics = _metrics()
    target_index = len(metrics) - 1
    store = ScannerStateStore(tmp_path)
    path = store.path_for("MEASURE-CORRUPT", "1wk")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not valid json", encoding="utf-8")
    calls = _count_transition_replays(monkeypatch)
    diagnostics: list[str] = []

    candidate = scan_latest_candidate_production(
        metrics,
        symbol="MEASURE-CORRUPT",
        timeframe="1wk",
        state_store=store,
        fallback_diagnostics=diagnostics,
    )

    assert candidate is not None
    assert candidate.bar_index == target_index
    assert calls == [(len(metrics), target_index, False)]
    assert len(diagnostics) == 1
    assert CHECKPOINT_CORRUPT in diagnostics[0]
    assert "full replay fallback used" in diagnostics[0]
    assert store.load("MEASURE-CORRUPT", "1wk").last_closed_bar == str(
        metrics.iloc[target_index][COL_WEEK]
    )


def test_stale_checkpoint_fallback_candidate_and_snapshot_share_one_replay(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    metrics = _metrics()
    target_index = len(metrics) - 1
    store = ScannerStateStore(tmp_path)
    state = IncrementalScannerEngine().snapshot(
        metrics,
        target_index=target_index,
        symbol="MEASURE-STALE",
        timeframe="1wk",
    )
    store.save(replace(state, data_fingerprint="stale-data-fingerprint"))
    calls = _count_transition_replays(monkeypatch)
    diagnostics: list[str] = []

    candidate = scan_latest_candidate_production(
        metrics,
        symbol="MEASURE-STALE",
        timeframe="1wk",
        state_store=store,
        fallback_diagnostics=diagnostics,
    )

    assert candidate is not None
    assert candidate.bar_index == target_index
    assert calls == [(len(metrics), target_index, False)]
    assert len(diagnostics) == 1
    assert CHECKPOINT_DATA_MISMATCH in diagnostics[0]
    assert "full replay fallback used" in diagnostics[0]
    assert store.load("MEASURE-STALE", "1wk").last_closed_bar == str(
        metrics.iloc[target_index][COL_WEEK]
    )


def test_valid_latest_checkpoint_runs_one_candidate_replay_without_snapshot_refresh(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    metrics = _metrics()
    target_index = len(metrics) - 1
    store = ScannerStateStore(tmp_path)
    state = IncrementalScannerEngine().snapshot(
        metrics,
        target_index=target_index,
        symbol="MEASURE-LATEST",
        timeframe="1wk",
    )
    store.save(state)
    calls = _count_transition_replays(monkeypatch)

    candidate = scan_latest_candidate_production(
        metrics,
        symbol="MEASURE-LATEST",
        timeframe="1wk",
        state_store=store,
        allow_full_replay_fallback=False,
    )

    assert candidate is not None
    assert candidate.bar_index == target_index
    assert calls == [(len(metrics), target_index, False)]
    assert store.load("MEASURE-LATEST", "1wk").last_closed_bar == str(
        metrics.iloc[target_index][COL_WEEK]
    )
