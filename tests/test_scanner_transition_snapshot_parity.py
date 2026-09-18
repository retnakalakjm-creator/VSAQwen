from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

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
from scanner import ScannerEngine
from scanner_state import (
    ScannerState,
    scanner_state_fingerprints,
    validate_scanner_state_fingerprints,
)
from scanner_transition_snapshot import ScannerTransitionSnapshotAdapter


def _metrics(size: int = 132) -> pd.DataFrame:
    """Generic synthetic OHLCV fixture with enough swings for snapshot parity."""

    anchors = [
        100.0,
        113.0,
        104.0,
        119.0,
        108.0,
        125.0,
        112.0,
        130.0,
        116.0,
        136.0,
        121.0,
        141.0,
        124.0,
        134.0,
    ]
    bars_per_segment = max(6, size // (len(anchors) - 1))
    points: list[float] = []
    for start, end in zip(anchors[:-1], anchors[1:]):
        points.extend(np.linspace(start, end, bars_per_segment, endpoint=False))
    if len(points) < size:
        points.extend(np.linspace(anchors[-1], anchors[-1] + 4.0, size - len(points)))

    close = np.asarray(points[:size], dtype=float)
    delta = np.diff(close, prepend=close[0])
    open_ = close - np.where(delta >= 0.0, 0.35, -0.35)
    spread = 1.2 + (np.arange(size, dtype=float) % 6.0) * 0.12
    high = np.maximum(open_, close) + spread / 2.0
    low = np.minimum(open_, close) - spread / 2.0
    volume = (
        1_000.0
        + (np.arange(size, dtype=float) % 11.0) * 55.0
        + np.where((np.arange(size) % 17) == 0, 350.0, 0.0)
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


def _state_signature(state: ScannerState) -> tuple[object, ...]:
    return (
        state.schema_version,
        state.symbol,
        state.timeframe,
        state.last_closed_bar,
        state.search_state,
        None if state.candidate is None else state.candidate.to_dict(),
        tuple(item.to_dict() for item in state.confirmed_swings),
        tuple(item.to_dict() for item in state.structural_events),
        state.engine_fingerprint,
        state.config_fingerprint,
        state.data_fingerprint,
    )


@pytest.mark.parametrize("target_index", (36, 72, 108, 131))
def test_transition_snapshot_matches_incremental_snapshot_contract(
    target_index: int,
) -> None:
    metrics = _metrics()

    transition = ScannerTransitionSnapshotAdapter().snapshot(
        metrics,
        target_index=target_index,
        symbol="SNAPSHOT-PARITY",
        timeframe="1wk",
    )
    incremental = IncrementalScannerEngine().snapshot(
        metrics,
        target_index=target_index,
        symbol="SNAPSHOT-PARITY",
        timeframe="1wk",
    )

    assert _state_signature(transition) == _state_signature(incremental)


@pytest.mark.parametrize("target_index", (36, 72, 108))
def test_transition_snapshot_fingerprints_validate_current_prefix(
    target_index: int,
) -> None:
    metrics = _metrics()
    snapshot = ScannerTransitionSnapshotAdapter().snapshot(
        metrics,
        target_index=target_index,
        symbol="SNAPSHOT-FINGERPRINT",
        timeframe="1wk",
    )
    prefix = metrics.iloc[: target_index + 1].copy()

    validate_scanner_state_fingerprints(snapshot, prefix)
    assert {
        "engine_fingerprint": snapshot.engine_fingerprint,
        "config_fingerprint": snapshot.config_fingerprint,
        "data_fingerprint": snapshot.data_fingerprint,
    } == scanner_state_fingerprints(prefix, snapshot.last_closed_bar)


def test_transition_snapshot_reuses_transition_swing_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    metrics = _metrics()
    adapter = ScannerTransitionSnapshotAdapter()

    def forbidden_replay(*args, **kwargs):
        raise AssertionError("snapshot must reuse transition swing state")

    monkeypatch.setattr(
        ScannerTransitionSnapshotAdapter,
        "_snapshot_swing_state",
        staticmethod(forbidden_replay),
    )

    snapshot = adapter.snapshot(
        metrics,
        target_index=72,
        symbol="SNAPSHOT-REUSE",
        timeframe="1wk",
    )

    assert snapshot.last_closed_bar == str(metrics.iloc[72][COL_WEEK])
    assert snapshot.symbol == "SNAPSHOT-REUSE"
    assert snapshot.timeframe == "1wk"


def test_transition_snapshot_matches_expected_checkpoint_identity() -> None:
    metrics = _metrics()
    target_index = 72

    snapshot = ScannerTransitionSnapshotAdapter().snapshot(
        metrics,
        target_index=target_index,
        symbol="SNAPSHOT-IDENTITY",
        timeframe="1wk",
    )

    assert snapshot.last_closed_bar == str(metrics.iloc[target_index][COL_WEEK])
    assert snapshot.symbol == "SNAPSHOT-IDENTITY"
    assert snapshot.timeframe == "1wk"


def test_transition_snapshot_rejects_invalid_target_index() -> None:
    metrics = _metrics()
    adapter = ScannerTransitionSnapshotAdapter()

    with pytest.raises(ValueError, match="target_index must be"):
        adapter.snapshot(
            metrics,
            target_index=ScannerEngine.MIN_REPLAY_BARS - 1,
            symbol="SNAPSHOT-INVALID",
            timeframe="1wk",
        )

    with pytest.raises(IndexError, match="outside metrics"):
        adapter.snapshot(
            metrics,
            target_index=len(metrics),
            symbol="SNAPSHOT-INVALID",
            timeframe="1wk",
        )


def test_transition_snapshot_adapter_is_wired_into_production_scanner() -> None:
    production_source = Path("production_scanner.py").read_text(encoding="utf-8")

    assert "scanner_transition_snapshot" in production_source
    assert "ScannerTransitionSnapshotAdapter" in production_source
    assert "IncrementalScannerEngine" not in production_source
