from __future__ import annotations

import pandas as pd

import production_scanner
from production_scanner import CHECKPOINT_CORRUPT, scan_latest_candidate_production
from scanner import ScannerEngine


def _minimal_metrics(size: int | None = None) -> pd.DataFrame:
    bar_count = size or ScannerEngine.MIN_REPLAY_BARS + 4
    return pd.DataFrame(
        {
            "week_beginning": [
                value.strftime("%Y-%m-%d")
                for value in pd.date_range("2024-01-01", periods=bar_count, freq="W-MON")
            ]
        }
    )


class EmptyStore:
    def __init__(self) -> None:
        self.saved: list[object] = []

    def load(self, symbol: str, timeframe: str) -> object:
        raise FileNotFoundError(symbol, timeframe)

    def save(self, state: object) -> None:
        self.saved.append(state)


class CorruptStore(EmptyStore):
    def load(self, symbol: str, timeframe: str) -> object:
        raise ValueError("corrupt scanner state")


def test_bootstrap_reuses_historical_transition_state_for_snapshot(monkeypatch) -> None:
    metrics = _minimal_metrics()
    candidate = object()
    snapshot_state = object()

    class RecordingHistoricalRunner:
        instances: list["RecordingHistoricalRunner"] = []

        def __init__(self) -> None:
            self.scan_to_index_calls: list[tuple[int, int]] = []
            self.scan_to_index_with_state_calls: list[tuple[int, int]] = []
            RecordingHistoricalRunner.instances.append(self)

        def scan_to_index(self, metrics_arg: pd.DataFrame, target_index: int):
            self.scan_to_index_calls.append((len(metrics_arg), target_index))
            raise AssertionError("bootstrap should use the state-returning runner")

        def scan_to_index_with_state(
            self,
            metrics_arg: pd.DataFrame,
            target_index: int,
        ):
            self.scan_to_index_with_state_calls.append((len(metrics_arg), target_index))
            return candidate, "transition-state"

    class RecordingSnapshotAdapter:
        instances: list["RecordingSnapshotAdapter"] = []

        def __init__(self) -> None:
            self.snapshot_calls: list[object] = []
            self.snapshot_from_transition_state_calls: list[tuple[int, int, object]] = []
            RecordingSnapshotAdapter.instances.append(self)

        def snapshot(self, *args: object, **kwargs: object) -> object:
            self.snapshot_calls.append((args, kwargs))
            raise AssertionError("bootstrap should not replay snapshot")

        def snapshot_from_transition_state(
            self,
            metrics_arg: pd.DataFrame,
            *,
            target_index: int,
            symbol: str,
            timeframe: str,
            transition_state: object,
        ) -> object:
            self.snapshot_from_transition_state_calls.append(
                (len(metrics_arg), target_index, transition_state)
            )
            assert symbol == "TEST"
            assert timeframe == "1wk"
            return snapshot_state

    monkeypatch.setattr(
        production_scanner,
        "HistoricalScannerRunner",
        RecordingHistoricalRunner,
    )
    monkeypatch.setattr(
        production_scanner,
        "ScannerTransitionSnapshotAdapter",
        RecordingSnapshotAdapter,
    )

    store = EmptyStore()
    returned = scan_latest_candidate_production(
        metrics,
        symbol="TEST",
        timeframe="1wk",
        state_store=store,
    )

    assert returned is candidate
    assert store.saved == [snapshot_state]
    assert len(RecordingHistoricalRunner.instances) == 1
    runner = RecordingHistoricalRunner.instances[0]
    assert runner.scan_to_index_calls == []
    assert runner.scan_to_index_with_state_calls == [(len(metrics), len(metrics) - 1)]
    assert len(RecordingSnapshotAdapter.instances) == 1
    snapshot_adapter = RecordingSnapshotAdapter.instances[0]
    assert snapshot_adapter.snapshot_calls == []
    assert snapshot_adapter.snapshot_from_transition_state_calls == [
        (len(metrics), len(metrics) - 1, "transition-state")
    ]


def test_corrupt_checkpoint_fallback_reuses_historical_transition_state_for_snapshot(
    monkeypatch,
) -> None:
    metrics = _minimal_metrics()
    candidate = object()
    snapshot_state = object()

    class RecordingHistoricalRunner:
        calls: list[tuple[int, int]] = []

        def scan_to_index(self, metrics_arg: pd.DataFrame, target_index: int):
            raise AssertionError("fallback should use the state-returning runner")

        def scan_to_index_with_state(
            self,
            metrics_arg: pd.DataFrame,
            target_index: int,
        ):
            self.calls.append((len(metrics_arg), target_index))
            return candidate, "fallback-transition-state"

    class RecordingSnapshotAdapter:
        snapshot_calls: list[object] = []
        snapshot_from_transition_state_calls: list[tuple[int, int, object]] = []

        def snapshot(self, *args: object, **kwargs: object) -> object:
            self.snapshot_calls.append((args, kwargs))
            raise AssertionError("fallback should not replay snapshot")

        def snapshot_from_transition_state(
            self,
            metrics_arg: pd.DataFrame,
            *,
            target_index: int,
            symbol: str,
            timeframe: str,
            transition_state: object,
        ) -> object:
            self.snapshot_from_transition_state_calls.append(
                (len(metrics_arg), target_index, transition_state)
            )
            return snapshot_state

    monkeypatch.setattr(
        production_scanner,
        "HistoricalScannerRunner",
        RecordingHistoricalRunner,
    )
    monkeypatch.setattr(
        production_scanner,
        "ScannerTransitionSnapshotAdapter",
        RecordingSnapshotAdapter,
    )

    store = CorruptStore()
    diagnostics: list[str] = []
    returned = scan_latest_candidate_production(
        metrics,
        symbol="TEST",
        timeframe="1wk",
        state_store=store,
        fallback_diagnostics=diagnostics,
    )

    assert returned is candidate
    assert store.saved == [snapshot_state]
    assert RecordingHistoricalRunner.calls == [(len(metrics), len(metrics) - 1)]
    assert RecordingSnapshotAdapter.snapshot_calls == []
    assert RecordingSnapshotAdapter.snapshot_from_transition_state_calls == [
        (len(metrics), len(metrics) - 1, "fallback-transition-state")
    ]
    assert len(diagnostics) == 1
    assert CHECKPOINT_CORRUPT in diagnostics[0]
    assert "full replay fallback used" in diagnostics[0]
