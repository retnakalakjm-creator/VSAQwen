from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import production_scanner
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
from scanner import ScannerEngine
from scanner_state import ScannerStateStore


def _metrics(size: int = 132) -> pd.DataFrame:
    """Generic OHLCV fixture for first production transition-wiring slice."""

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


class _RecordingTransitionRunner:
    calls: list[tuple[int, int]] = []
    result: object = object()

    def scan_to_index(self, metrics: pd.DataFrame, target_index: int):
        self.__class__.calls.append((len(metrics), target_index))
        return self.__class__.result


class _ForbiddenTransitionRunner:
    def scan_to_index(self, metrics: pd.DataFrame, target_index: int):
        raise AssertionError("valid production resume must not use full replay")


def test_production_bootstrap_full_replay_uses_historical_transition_runner(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    metrics = _metrics()
    store = ScannerStateStore(tmp_path)
    _RecordingTransitionRunner.calls = []
    _RecordingTransitionRunner.result = object()
    monkeypatch.setattr(
        production_scanner,
        "HistoricalScannerRunner",
        _RecordingTransitionRunner,
    )

    candidate = production_scanner.scan_latest_candidate_production(
        metrics,
        symbol="PROD-WIRE",
        timeframe="1wk",
        state_store=store,
    )

    assert candidate is _RecordingTransitionRunner.result
    assert _RecordingTransitionRunner.calls == [(len(metrics), len(metrics) - 1)]
    assert store.path_for("PROD-WIRE", "1wk").exists()


def test_production_valid_checkpoint_resume_stays_on_incremental_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    metrics = _metrics()
    store = ScannerStateStore(tmp_path)
    state = IncrementalScannerEngine().snapshot(
        metrics,
        target_index=72,
        symbol="PROD-RESUME",
        timeframe="1wk",
    )
    store.save(state)
    monkeypatch.setattr(
        production_scanner,
        "HistoricalScannerRunner",
        _ForbiddenTransitionRunner,
    )

    candidate = production_scanner.scan_latest_candidate_production(
        metrics,
        symbol="PROD-RESUME",
        timeframe="1wk",
        state_store=store,
        allow_full_replay_fallback=False,
    )

    assert candidate is not None
    assert candidate.bar_index == len(metrics) - 1
    refreshed = store.load("PROD-RESUME", "1wk")
    assert refreshed.last_closed_bar == str(metrics.iloc[-1][COL_WEEK])


def test_production_stale_checkpoint_fallback_uses_historical_transition_runner(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    metrics = _metrics()
    store = ScannerStateStore(tmp_path)
    checkpoint_index = 72
    state = IncrementalScannerEngine().snapshot(
        metrics,
        target_index=checkpoint_index,
        symbol="PROD-STALE",
        timeframe="1wk",
    )
    store.save(state)

    revised_metrics = metrics.copy()
    revised_metrics.loc[checkpoint_index - 3, COL_VOLUME] = (
        revised_metrics.loc[checkpoint_index - 3, COL_VOLUME] * 1.05
    )
    diagnostics: list[str] = []
    _RecordingTransitionRunner.calls = []
    _RecordingTransitionRunner.result = object()
    monkeypatch.setattr(
        production_scanner,
        "HistoricalScannerRunner",
        _RecordingTransitionRunner,
    )

    candidate = production_scanner.scan_latest_candidate_production(
        revised_metrics,
        symbol="PROD-STALE",
        timeframe="1wk",
        state_store=store,
        fallback_diagnostics=diagnostics,
    )

    assert candidate is _RecordingTransitionRunner.result
    assert _RecordingTransitionRunner.calls == [
        (len(revised_metrics), len(revised_metrics) - 1)
    ]
    assert any(CHECKPOINT_DATA_MISMATCH in item for item in diagnostics)


def test_production_full_replay_transition_output_matches_legacy_scanner(
    tmp_path,
) -> None:
    metrics = _metrics()
    store = ScannerStateStore(tmp_path)

    production = production_scanner.scan_latest_candidate_production(
        metrics,
        symbol="PROD-PARITY",
        timeframe="1wk",
        state_store=store,
    )
    legacy = ScannerEngine().scan_to_index(metrics, len(metrics) - 1)

    assert production is not None
    assert production.bar_index == legacy.bar_index
    assert production.week == legacy.week
    assert production.qualification == legacy.qualification
    assert production.actionable == legacy.actionable
    assert production.scoring_evidence_age == legacy.scoring_evidence_age
    assert production.used_fallback_evidence == legacy.used_fallback_evidence
    assert production.effort_result_evidence_codes == legacy.effort_result_evidence_codes
    assert production.absorption_evidence_codes == legacy.absorption_evidence_codes
