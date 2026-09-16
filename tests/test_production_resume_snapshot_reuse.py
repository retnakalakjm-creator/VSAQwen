from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

import production_scanner
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
from production_scanner import scan_latest_candidate_production
from scanner import ScannerEngine
from scanner_state import ScannerStateStore
from scanner_transition import ScannerTransitionEngine


def _metrics(size: int = 104) -> pd.DataFrame:
    anchors = [
        100.0,
        112.0,
        103.0,
        119.0,
        108.0,
        127.0,
        115.0,
        134.0,
        122.0,
        140.0,
    ]
    bars_per_segment = max(6, size // (len(anchors) - 1))
    points: list[float] = []
    for start, end in zip(anchors[:-1], anchors[1:]):
        points.extend(np.linspace(start, end, bars_per_segment, endpoint=False))
    if len(points) < size:
        points.extend(np.linspace(anchors[-1], anchors[-1] + 2.0, size - len(points)))

    close = np.asarray(points[:size], dtype=float)
    delta = np.diff(close, prepend=close[0])
    open_ = close - np.where(delta >= 0.0, 0.35, -0.35)
    spread = 1.1 + (np.arange(size, dtype=float) % 7.0) * 0.1
    high = np.maximum(open_, close) + spread / 2.0
    low = np.minimum(open_, close) - spread / 2.0
    volume = (
        1_000.0
        + (np.arange(size, dtype=float) % 11.0) * 55.0
        + np.where((np.arange(size) % 17) == 0, 325.0, 0.0)
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


def test_valid_behind_checkpoint_resume_and_snapshot_share_one_transition_replay(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    metrics = _metrics()
    symbol = "MEASURE-RESUME-REUSE"
    timeframe = "1wk"
    checkpoint_index = 72
    target_index = len(metrics) - 1
    store = ScannerStateStore(tmp_path)
    store.save(
        IncrementalScannerEngine().snapshot(
            metrics,
            target_index=checkpoint_index,
            symbol=symbol,
            timeframe=timeframe,
        )
    )
    calls = _count_transition_replays(monkeypatch)

    candidate = scan_latest_candidate_production(
        metrics,
        symbol=symbol,
        timeframe=timeframe,
        state_store=store,
        allow_full_replay_fallback=False,
    )

    assert candidate is not None
    assert candidate.bar_index == target_index
    assert calls == [(len(metrics), target_index, True)]
    refreshed = store.load(symbol, timeframe)
    assert refreshed.last_closed_bar == str(metrics.iloc[target_index][COL_WEEK])


def test_resume_snapshot_reuse_uses_state_returning_resume_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    metrics = _metrics()
    symbol = "RESUME-BOUNDARY"
    timeframe = "1wk"
    checkpoint_index = 72
    target_index = len(metrics) - 1
    checkpoint_state = IncrementalScannerEngine().snapshot(
        metrics,
        target_index=checkpoint_index,
        symbol=symbol,
        timeframe=timeframe,
    )
    candidate = object()
    snapshot_state = object()

    class Store:
        saved: list[object] = []

        def load(self, received_symbol: str, received_timeframe: str):
            assert received_symbol == symbol
            assert received_timeframe == timeframe
            return checkpoint_state

        def save(self, state: object) -> None:
            self.saved.append(state)

    class RecordingResumeAdapter:
        instances: list["RecordingResumeAdapter"] = []

        def __init__(self) -> None:
            self.resume_latest_calls: list[object] = []
            self.resume_latest_with_state_calls: list[tuple[int, object]] = []
            RecordingResumeAdapter.instances.append(self)

        def resume_latest(self, *_args: object, **_kwargs: object) -> object:
            self.resume_latest_calls.append((_args, _kwargs))
            raise AssertionError("behind resume should use state-returning boundary")

        def resume_latest_with_state(self, received_metrics, state):
            self.resume_latest_with_state_calls.append((len(received_metrics), state))
            return SimpleNamespace(
                candidate=candidate,
                transition_state="resumed-transition-state",
            )

    class RecordingSnapshotAdapter:
        instances: list["RecordingSnapshotAdapter"] = []

        def __init__(self) -> None:
            self.snapshot_calls: list[object] = []
            self.snapshot_from_transition_state_calls: list[tuple[int, int, object]] = []
            RecordingSnapshotAdapter.instances.append(self)

        def snapshot(self, *args: object, **kwargs: object) -> object:
            self.snapshot_calls.append((args, kwargs))
            raise AssertionError("resume snapshot refresh should not replay snapshot")

        def snapshot_from_transition_state(
            self,
            received_metrics,
            *,
            target_index: int,
            symbol: str,
            timeframe: str,
            transition_state: object,
        ) -> object:
            self.snapshot_from_transition_state_calls.append(
                (len(received_metrics), target_index, transition_state)
            )
            assert symbol == "RESUME-BOUNDARY"
            assert timeframe == "1wk"
            return snapshot_state

    monkeypatch.setattr(
        production_scanner,
        "ScannerTransitionResumeAdapter",
        RecordingResumeAdapter,
    )
    monkeypatch.setattr(
        production_scanner,
        "ScannerTransitionSnapshotAdapter",
        RecordingSnapshotAdapter,
    )

    store = Store()
    returned = scan_latest_candidate_production(
        metrics,
        symbol=symbol,
        timeframe=timeframe,
        state_store=store,  # type: ignore[arg-type]
        allow_full_replay_fallback=False,
    )

    assert returned is candidate
    assert store.saved == [snapshot_state]
    assert len(RecordingResumeAdapter.instances) == 1
    resume = RecordingResumeAdapter.instances[0]
    assert resume.resume_latest_calls == []
    assert resume.resume_latest_with_state_calls == [(len(metrics), checkpoint_state)]
    assert len(RecordingSnapshotAdapter.instances) == 1
    snapshot = RecordingSnapshotAdapter.instances[0]
    assert snapshot.snapshot_calls == []
    assert snapshot.snapshot_from_transition_state_calls == [
        (len(metrics), target_index, "resumed-transition-state")
    ]


def test_resume_snapshot_reuse_keeps_old_resume_adapter_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    metrics = _metrics()
    symbol = "RESUME-COMPAT"
    timeframe = "1wk"
    checkpoint_index = 72
    checkpoint_state = IncrementalScannerEngine().snapshot(
        metrics,
        target_index=checkpoint_index,
        symbol=symbol,
        timeframe=timeframe,
    )
    candidate = object()
    snapshot_state = object()

    class Store:
        saved: list[object] = []

        def load(self, _symbol: str, _timeframe: str):
            return checkpoint_state

        def save(self, state: object) -> None:
            self.saved.append(state)

    class OldResumeAdapter:
        calls: list[tuple[int, object]] = []

        def resume_latest(self, received_metrics, state):
            self.calls.append((len(received_metrics), state))
            return candidate

    class OldSnapshotAdapter:
        calls: list[tuple[int, int, str, str]] = []

        def snapshot(self, received_metrics, *, target_index, symbol, timeframe):
            self.calls.append((len(received_metrics), target_index, symbol, timeframe))
            return snapshot_state

    monkeypatch.setattr(
        production_scanner,
        "ScannerTransitionResumeAdapter",
        OldResumeAdapter,
    )
    monkeypatch.setattr(
        production_scanner,
        "ScannerTransitionSnapshotAdapter",
        OldSnapshotAdapter,
    )

    store = Store()
    returned = scan_latest_candidate_production(
        metrics,
        symbol=symbol,
        timeframe=timeframe,
        state_store=store,  # type: ignore[arg-type]
        allow_full_replay_fallback=False,
    )

    assert returned is candidate
    assert OldResumeAdapter.calls == [(len(metrics), checkpoint_state)]
    assert OldSnapshotAdapter.calls == [(len(metrics), len(metrics) - 1, symbol, timeframe)]
    assert store.saved == [snapshot_state]
