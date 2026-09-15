from __future__ import annotations

from dataclasses import replace

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
    CHECKPOINT_CONFIG_MISMATCH,
    CHECKPOINT_CORRUPT,
    CHECKPOINT_DATA_MISMATCH,
    CHECKPOINT_STALE,
    ENGINE_DIVERGENCE,
    scan_actionable_production,
    scan_latest_candidate_production,
)
from scanner import ScannerEngine
from scanner_state import CandidateState, ScannerStateStore


def _raw_bars(size: int = 120) -> pd.DataFrame:
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


def _metrics() -> pd.DataFrame:
    return MetricsEngine().calculate(_raw_bars())


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


def _snapshot_at(metrics: pd.DataFrame, split: int = 72):
    return IncrementalScannerEngine().snapshot(
        metrics,
        target_index=split,
        symbol="TEST",
        timeframe="1wk",
    )


def _assert_matches_full_replay(candidate, metrics: pd.DataFrame) -> None:
    full = ScannerEngine().scan_to_index(metrics, len(metrics) - 1)
    assert candidate is not None
    assert _candidate_signature(candidate) == _candidate_signature(full)
    assert candidate.bar_index == full.bar_index
    assert candidate.week == full.week


def test_normal_first_run_bootstrap_stays_quiet(tmp_path) -> None:
    metrics = _metrics()
    diagnostics: list[str] = []

    candidate = scan_latest_candidate_production(
        metrics,
        symbol="TEST",
        timeframe="1wk",
        state_store=ScannerStateStore(tmp_path),
        fallback_diagnostics=diagnostics,
    )

    assert diagnostics == []
    _assert_matches_full_replay(candidate, metrics)


def test_config_fingerprint_mismatch_records_fallback_diagnostic(tmp_path) -> None:
    metrics = _metrics()
    store = ScannerStateStore(tmp_path)
    store.save(replace(_snapshot_at(metrics), config_fingerprint="stale-config"))
    diagnostics: list[str] = []

    candidate = scan_latest_candidate_production(
        metrics,
        symbol="TEST",
        timeframe="1wk",
        state_store=store,
        fallback_diagnostics=diagnostics,
    )

    assert len(diagnostics) == 1
    assert diagnostics[0].startswith(CHECKPOINT_CONFIG_MISMATCH)
    assert "full replay fallback used" in diagnostics[0]
    _assert_matches_full_replay(candidate, metrics)


def test_data_fingerprint_mismatch_records_fallback_diagnostic(tmp_path) -> None:
    metrics = _metrics()
    store = ScannerStateStore(tmp_path)
    store.save(replace(_snapshot_at(metrics), data_fingerprint="stale-data"))
    diagnostics: list[str] = []

    candidate = scan_latest_candidate_production(
        metrics,
        symbol="TEST",
        timeframe="1wk",
        state_store=store,
        fallback_diagnostics=diagnostics,
    )

    assert len(diagnostics) == 1
    assert diagnostics[0].startswith(CHECKPOINT_DATA_MISMATCH)
    assert "full replay fallback used" in diagnostics[0]
    _assert_matches_full_replay(candidate, metrics)


def test_mixed_fingerprint_mismatch_records_stale_checkpoint_diagnostic(tmp_path) -> None:
    metrics = _metrics()
    store = ScannerStateStore(tmp_path)
    store.save(
        replace(
            _snapshot_at(metrics),
            engine_fingerprint="old-engine",
            config_fingerprint="old-config",
        )
    )
    diagnostics: list[str] = []

    candidate = scan_latest_candidate_production(
        metrics,
        symbol="TEST",
        timeframe="1wk",
        state_store=store,
        fallback_diagnostics=diagnostics,
    )

    assert len(diagnostics) == 1
    assert diagnostics[0].startswith(CHECKPOINT_STALE)
    assert "full replay fallback used" in diagnostics[0]
    _assert_matches_full_replay(candidate, metrics)


def test_corrupt_checkpoint_records_fallback_diagnostic(tmp_path) -> None:
    metrics = _metrics()
    store = ScannerStateStore(tmp_path)
    store.path_for("TEST", "1wk").write_text("not-json", encoding="utf-8")
    diagnostics: list[str] = []

    candidate = scan_latest_candidate_production(
        metrics,
        symbol="TEST",
        timeframe="1wk",
        state_store=store,
        fallback_diagnostics=diagnostics,
    )

    assert len(diagnostics) == 1
    assert diagnostics[0].startswith(CHECKPOINT_CORRUPT)
    assert "full replay fallback used" in diagnostics[0]
    _assert_matches_full_replay(candidate, metrics)


def test_resume_failure_records_engine_divergence_diagnostic(tmp_path) -> None:
    metrics = _metrics()
    store = ScannerStateStore(tmp_path)
    state = _snapshot_at(metrics)
    assert state.candidate is not None
    store.save(
        replace(
            state,
            candidate=CandidateState(
                bar_key="missing-candidate-bar",
                type=state.candidate.type,
                price=state.candidate.price,
            ),
        )
    )
    diagnostics: list[str] = []

    candidate = scan_latest_candidate_production(
        metrics,
        symbol="TEST",
        timeframe="1wk",
        state_store=store,
        fallback_diagnostics=diagnostics,
    )

    assert len(diagnostics) == 1
    assert diagnostics[0].startswith(ENGINE_DIVERGENCE)
    assert "full replay fallback used" in diagnostics[0]
    _assert_matches_full_replay(candidate, metrics)


def test_actionable_scan_forwards_fallback_diagnostics(tmp_path) -> None:
    metrics = _metrics()
    store = ScannerStateStore(tmp_path)
    store.save(replace(_snapshot_at(metrics), config_fingerprint="stale-config"))
    diagnostics: list[str] = []

    scan_actionable_production(
        metrics,
        symbol="TEST",
        timeframe="1wk",
        state_store=store,
        fallback_diagnostics=diagnostics,
    )

    assert len(diagnostics) == 1
    assert diagnostics[0].startswith(CHECKPOINT_CONFIG_MISMATCH)
