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
from production_scanner import (
    CHECKPOINT_CONFIG_MISMATCH,
    CHECKPOINT_CORRUPT,
    CHECKPOINT_DATA_MISMATCH,
    CHECKPOINT_STALE,
    CHECKPOINT_WRITE_FAILED,
    ENGINE_DIVERGENCE,
    scan_actionable_production,
    scan_latest_candidate_production,
)
from scanner import ScannerEngine
from scanner_exceptions import ScannerStateWriteError
from scanner_recovery import ScannerRecoveryPhase
from scanner_state import ScannerStateStore


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


def test_resume_failure_records_engine_divergence_diagnostic(
    tmp_path,
    monkeypatch,
) -> None:
    metrics = _metrics()
    store = ScannerStateStore(tmp_path)
    store.save(_snapshot_at(metrics))
    diagnostics: list[str] = []

    class FailingTransitionResumeAdapter:
        def resume_latest(self, _metrics, _state):
            raise RuntimeError("forced transition resume divergence")

    monkeypatch.setattr(
        "production_scanner.ScannerTransitionResumeAdapter",
        FailingTransitionResumeAdapter,
    )

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


def test_structured_config_fallback_event_matches_legacy_diagnostic(tmp_path) -> None:
    metrics = _metrics()
    store = ScannerStateStore(tmp_path)
    store.save(replace(_snapshot_at(metrics), config_fingerprint="stale-config"))
    diagnostics: list[str] = []
    recovery_events = []

    candidate = scan_latest_candidate_production(
        metrics,
        symbol="TEST",
        timeframe="1wk",
        state_store=store,
        fallback_diagnostics=diagnostics,
        recovery_events=recovery_events,
    )

    assert len(diagnostics) == 1
    assert len(recovery_events) == 1
    event = recovery_events[0]
    assert event.code == CHECKPOINT_CONFIG_MISMATCH
    assert event.phase is ScannerRecoveryPhase.LOAD_VALIDATE
    assert event.symbol == "TEST"
    assert event.timeframe == "1wk"
    assert event.fallback_used is True
    assert event.exception_type == "ScannerStateFingerprintMismatch"
    assert event.message == diagnostics[0]
    _assert_matches_full_replay(candidate, metrics)


def test_structured_corrupt_checkpoint_event_exposes_exception_type(tmp_path) -> None:
    metrics = _metrics()
    store = ScannerStateStore(tmp_path)
    store.path_for("TEST", "1wk").write_text("not-json", encoding="utf-8")
    recovery_events = []

    candidate = scan_latest_candidate_production(
        metrics,
        symbol="TEST",
        timeframe="1wk",
        state_store=store,
        recovery_events=recovery_events,
    )

    assert len(recovery_events) == 1
    event = recovery_events[0]
    assert event.code == CHECKPOINT_CORRUPT
    assert event.phase is ScannerRecoveryPhase.LOAD_VALIDATE
    assert event.exception_type == "ScannerStateCorruptError"
    _assert_matches_full_replay(candidate, metrics)


def test_structured_resume_failure_event_identifies_resume_phase(
    tmp_path,
    monkeypatch,
) -> None:
    metrics = _metrics()
    store = ScannerStateStore(tmp_path)
    store.save(_snapshot_at(metrics))
    diagnostics: list[str] = []
    recovery_events = []

    class FailingTransitionResumeAdapter:
        def resume_latest(self, _metrics, _state):
            raise RuntimeError("forced transition resume divergence")

    monkeypatch.setattr(
        "production_scanner.ScannerTransitionResumeAdapter",
        FailingTransitionResumeAdapter,
    )

    candidate = scan_latest_candidate_production(
        metrics,
        symbol="TEST",
        timeframe="1wk",
        state_store=store,
        fallback_diagnostics=diagnostics,
        recovery_events=recovery_events,
    )

    assert len(recovery_events) == 1
    event = recovery_events[0]
    assert event.code == ENGINE_DIVERGENCE
    assert event.phase is ScannerRecoveryPhase.RESUME
    assert event.exception_type == "RuntimeError"
    assert event.message == diagnostics[0]
    _assert_matches_full_replay(candidate, metrics)


def test_normal_bootstrap_emits_no_structured_recovery_event(tmp_path) -> None:
    metrics = _metrics()
    recovery_events = []

    candidate = scan_latest_candidate_production(
        metrics,
        symbol="TEST",
        timeframe="1wk",
        state_store=ScannerStateStore(tmp_path),
        recovery_events=recovery_events,
    )

    assert recovery_events == []
    _assert_matches_full_replay(candidate, metrics)


def test_actionable_scan_forwards_structured_recovery_events(tmp_path) -> None:
    metrics = _metrics()
    store = ScannerStateStore(tmp_path)
    store.save(replace(_snapshot_at(metrics), data_fingerprint="stale-data"))
    recovery_events = []

    scan_actionable_production(
        metrics,
        symbol="TEST",
        timeframe="1wk",
        state_store=store,
        recovery_events=recovery_events,
    )

    assert len(recovery_events) == 1
    assert recovery_events[0].code == CHECKPOINT_DATA_MISMATCH


def test_persistence_write_failure_emits_structured_event_and_propagates(
    tmp_path,
    monkeypatch,
) -> None:
    metrics = _metrics()
    store = ScannerStateStore(tmp_path)
    diagnostics: list[str] = []
    recovery_events = []

    def fail_replace(_source, _destination):
        raise OSError("simulated persistence write failure")

    monkeypatch.setattr("scanner_state.os.replace", fail_replace)

    with pytest.raises(
        ScannerStateWriteError,
        match="simulated persistence write failure",
    ):
        scan_latest_candidate_production(
            metrics,
            symbol="TEST",
            timeframe="1wk",
            state_store=store,
            fallback_diagnostics=diagnostics,
            recovery_events=recovery_events,
        )

    assert diagnostics == []
    assert len(recovery_events) == 1
    event = recovery_events[0]
    assert event.code == CHECKPOINT_WRITE_FAILED
    assert event.phase is ScannerRecoveryPhase.PERSIST
    assert event.symbol == "TEST"
    assert event.timeframe == "1wk"
    assert event.fallback_used is False
    assert event.exception_type == "ScannerStateWriteError"
    assert "full replay fallback not used" in event.message
    assert not store.path_for("TEST", "1wk").exists()
    assert not list(tmp_path.glob(".*.tmp"))
