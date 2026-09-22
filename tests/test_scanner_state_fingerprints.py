from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

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
from production_scanner import scan_latest_candidate_production
from scanner import ScannerEngine
from scanner_state import (
    SCANNER_STATE_ENGINE_FINGERPRINT,
    SCANNER_STATE_SCHEMA_VERSION,
    ScannerStateFingerprintMismatch,
    ScannerStateStore,
    scanner_state_data_fingerprint,
    validate_scanner_state_fingerprints,
)


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


def _snapshot(metrics: pd.DataFrame, split: int = 72):
    return IncrementalScannerEngine().snapshot(
        metrics,
        target_index=split,
        symbol="TEST",
        timeframe="1wk",
    )


def test_incremental_snapshot_includes_runtime_config_and_data_fingerprints() -> None:
    metrics = _production_metrics()
    state = _snapshot(metrics)

    assert state.engine_fingerprint == SCANNER_STATE_ENGINE_FINGERPRINT
    assert state.config_fingerprint
    assert state.data_fingerprint == scanner_state_data_fingerprint(
        metrics,
        state.last_closed_bar,
    )
    validate_scanner_state_fingerprints(state, metrics)


def test_data_fingerprint_detects_checkpoint_prefix_change() -> None:
    metrics = _production_metrics()
    state = _snapshot(metrics)
    changed = metrics.copy()
    changed.loc[10, COL_CLOSE] = float(changed.loc[10, COL_CLOSE]) + 2.0

    with pytest.raises(ScannerStateFingerprintMismatch, match="data"):
        validate_scanner_state_fingerprints(state, changed)


def test_data_fingerprint_allows_new_bars_after_checkpoint() -> None:
    metrics = _production_metrics()
    split = 72
    state = _snapshot(metrics, split=split)
    changed = metrics.copy()
    changed.loc[split + 5, COL_CLOSE] = float(changed.loc[split + 5, COL_CLOSE]) + 2.0

    validate_scanner_state_fingerprints(state, changed)


def test_production_scanner_rejects_stale_engine_fingerprint_without_fallback(tmp_path) -> None:
    metrics = _production_metrics()
    store = ScannerStateStore(tmp_path)
    state = replace(_snapshot(metrics), engine_fingerprint="old-engine")
    store.save(state)

    with pytest.raises(ScannerStateFingerprintMismatch, match="engine"):
        scan_latest_candidate_production(
            metrics,
            symbol="TEST",
            timeframe="1wk",
            state_store=store,
            allow_full_replay_fallback=False,
        )


def test_production_scanner_rejects_stale_config_fingerprint_without_fallback(tmp_path) -> None:
    metrics = _production_metrics()
    store = ScannerStateStore(tmp_path)
    state = replace(_snapshot(metrics), config_fingerprint="old-config")
    store.save(state)

    with pytest.raises(ScannerStateFingerprintMismatch, match="config"):
        scan_latest_candidate_production(
            metrics,
            symbol="TEST",
            timeframe="1wk",
            state_store=store,
            allow_full_replay_fallback=False,
        )


def test_production_scanner_rebuilds_from_full_replay_when_state_is_stale(tmp_path) -> None:
    metrics = _production_metrics()
    store = ScannerStateStore(tmp_path)
    stale_state = replace(_snapshot(metrics), data_fingerprint="old-data")
    store.save(stale_state)

    candidate = scan_latest_candidate_production(
        metrics,
        symbol="TEST",
        timeframe="1wk",
        state_store=store,
    )
    full = ScannerEngine().scan_to_index(metrics, len(metrics) - 1)

    assert candidate is not None
    assert _candidate_signature(candidate) == _candidate_signature(full)

    refreshed = store.load("TEST", "1wk")
    assert refreshed.last_closed_bar == str(metrics.iloc[-1][COL_WEEK])
    assert refreshed.data_fingerprint != stale_state.data_fingerprint
    validate_scanner_state_fingerprints(refreshed, metrics)



def test_previous_schema_checkpoint_rebuilds_through_full_replay(tmp_path) -> None:
    metrics = _production_metrics()
    store = ScannerStateStore(tmp_path)
    state = _snapshot(metrics, split=72)
    payload = state.to_dict()
    payload["schema_version"] = SCANNER_STATE_SCHEMA_VERSION - 1

    path = store.path_for("TEST", "1wk")
    path.parent.mkdir(parents=True, exist_ok=True)
    import json

    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2),
        encoding="utf-8",
    )

    candidate = scan_latest_candidate_production(
        metrics,
        symbol="TEST",
        timeframe="1wk",
        state_store=store,
    )
    full = ScannerEngine().scan_to_index(metrics, len(metrics) - 1)

    assert candidate is not None
    assert _candidate_signature(candidate) == _candidate_signature(full)
    assert store.load("TEST", "1wk").schema_version == SCANNER_STATE_SCHEMA_VERSION
