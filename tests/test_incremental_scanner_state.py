from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

import scanner_state
from incremental_scanner import IncrementalScannerEngine
from market_structure.swing_engine import SwingEngine
from metrics_engine import MetricsEngine
from models import Evidence, EvidenceCategory, EvidenceCode, EvidenceDirection, SwingSearchState, SwingType
from scanner_state import (
    CandidateState,
    ConfirmedSwingState,
    ScannerState,
    ScannerStateStore,
    StructuralEventState,
    SCANNER_STATE_SCHEMA_VERSION,
)


def _state() -> ScannerState:
    event = StructuralEventState(
        bar_key="2026-08-21",
        code=EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING,
        category=EvidenceCategory.TREND,
        direction=EvidenceDirection.BEARISH,
        strength=0.8,
        weight=1.0,
        observation="weakening",
        description="structural quality weakened",
        quality=1.0,
    )
    return ScannerState(
        schema_version=SCANNER_STATE_SCHEMA_VERSION,
        symbol="TCS.NS",
        timeframe="weekly",
        last_closed_bar="2026-08-28",
        search_state=SwingSearchState.TRACKING_HIGH,
        candidate=CandidateState("2026-08-28", SwingType.HIGH, 100.0),
        confirmed_swings=(
            ConfirmedSwingState("2026-08-07", "2026-08-14", SwingType.LOW, 95.0),
        ),
        structural_events=(event,),
    )


def _metrics() -> pd.DataFrame:
    return MetricsEngine().calculate(
        pd.DataFrame(
            {
                "week_beginning": [f"2026-08-{i + 1:02d}" for i in range(25)],
                "open": [100.0 + i for i in range(25)],
                "high": [101.0 + i for i in range(25)],
                "low": [99.0 + i for i in range(25)],
                "close": [100.5 + i for i in range(25)],
                "volume": [1000.0] * 25,
            }
        )
    )


def test_scanner_state_event_round_trip() -> None:
    state = _state()
    restored = ScannerState.from_dict(state.to_dict())
    assert restored == state


def test_structural_event_rehydrates_evidence() -> None:
    event = StructuralEventState(
        bar_key="2026-08-21",
        code=EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING,
        category=EvidenceCategory.TREND,
        direction=EvidenceDirection.BULLISH,
        strength=0.5,
        weight=1.0,
        observation="improving",
        description="structural quality improved",
        quality=1.0,
    )
    evidence = event.to_evidence(42)
    assert isinstance(evidence, Evidence)
    assert evidence.bar_index == 42
    assert evidence.week_beginning == event.bar_key
    assert evidence.code == event.code
    assert evidence.direction == event.direction


def test_swing_engine_uses_canonical_schema_version() -> None:
    metrics = pd.DataFrame(
        {
            "week_beginning": ["2026-08-21", "2026-08-28"],
            "open": [99.0, 100.0],
            "high": [101.0, 102.0],
            "low": [98.0, 99.0],
            "close": [100.0, 101.0],
            "volume": [1000.0, 1100.0],
            "avg_spread": [1.0, 1.0],
        }
    )
    engine = SwingEngine()
    engine.calculate(metrics)
    state = engine.snapshot_state("TEST", "weekly")
    assert state.schema_version == SCANNER_STATE_SCHEMA_VERSION


def test_incremental_scanner_uses_canonical_schema_version() -> None:
    state = IncrementalScannerEngine().snapshot(
        _metrics(),
        target_index=20,
        symbol="TEST",
        timeframe="weekly",
    )
    assert state.schema_version == SCANNER_STATE_SCHEMA_VERSION


def test_incremental_scanner_rejects_missing_checkpoint_bar() -> None:
    metrics = _metrics()
    state = IncrementalScannerEngine().snapshot(
        metrics,
        target_index=20,
        symbol="TEST",
        timeframe="weekly",
    )
    stale = ScannerState.from_dict(
        {
            **state.to_dict(),
            "last_closed_bar": "2026-07-31",
        }
    )

    with pytest.raises(ValueError, match="checkpoint bar is not present"):
        IncrementalScannerEngine().resume_latest(metrics, stale)


def test_incremental_scanner_rejects_duplicate_checkpoint_bar_identities() -> None:
    metrics = _metrics()
    state = IncrementalScannerEngine().snapshot(
        metrics,
        target_index=20,
        symbol="TEST",
        timeframe="weekly",
    )
    duplicate = metrics.copy()
    duplicate.loc[21, "week_beginning"] = duplicate.loc[20, "week_beginning"]

    with pytest.raises(ValueError, match="duplicate checkpoint bar identities"):
        IncrementalScannerEngine().resume_latest(duplicate, state)


def test_incremental_scanner_allows_latest_checkpoint_resume() -> None:
    metrics = _metrics()
    state = IncrementalScannerEngine().snapshot(
        metrics,
        target_index=20,
        symbol="TEST",
        timeframe="weekly",
    )

    resumed = IncrementalScannerEngine().resume_latest(metrics, state)

    assert resumed.bar_index == len(metrics) - 1
    assert resumed.week == str(metrics.iloc[-1]["week_beginning"])


def test_incremental_scanner_resumes_from_checkpoint_with_appended_bars() -> None:
    metrics = _metrics()
    checkpoint_index = 20
    checkpoint = metrics.iloc[: checkpoint_index + 1].copy()
    state = IncrementalScannerEngine().snapshot(
        checkpoint,
        target_index=checkpoint_index,
        symbol="TEST",
        timeframe="weekly",
    )

    current = metrics.iloc[:].copy()
    resumed = IncrementalScannerEngine().resume_latest(current, state)
    full = IncrementalScannerEngine()._scanner.scan_to_index(current, len(current) - 1)

    assert state.last_closed_bar == str(checkpoint.iloc[-1]["week_beginning"])
    assert state.last_closed_bar != str(current.iloc[-1]["week_beginning"])
    assert resumed.bar_index == len(current) - 1
    assert resumed.week == str(current.iloc[-1]["week_beginning"])
    assert resumed.actionable == full.actionable
    assert resumed.qualification == full.qualification
    assert resumed.professional.confidence == full.professional.confidence
    assert resumed.professional.scores.net_strength == full.professional.scores.net_strength
    assert resumed.professional.scores.net_pressure == full.professional.scores.net_pressure


def test_state_store_round_trip(tmp_path: Path) -> None:
    state = _state()
    store = ScannerStateStore(tmp_path)

    path = store.save(state)

    assert path.exists()
    assert store.load(state.symbol, state.timeframe) == state


def test_state_store_rejects_wrong_schema(tmp_path: Path) -> None:
    state = _state()
    store = ScannerStateStore(tmp_path)
    payload = state.to_dict()
    payload["schema_version"] = SCANNER_STATE_SCHEMA_VERSION - 1
    path = store.path_for(state.symbol, state.timeframe)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported ScannerState schema version"):
        store.load(state.symbol, state.timeframe)


def test_state_store_rejects_identity_mismatch(tmp_path: Path) -> None:
    state = _state()
    store = ScannerStateStore(tmp_path)
    store.save(state)

    path = store.path_for(state.symbol, state.timeframe)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["symbol"] = "RELIANCE.NS"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="identity"):
        store.load(state.symbol, state.timeframe)


def test_state_store_delete(tmp_path: Path) -> None:
    state = _state()
    store = ScannerStateStore(tmp_path)
    store.save(state)

    store.delete(state.symbol, state.timeframe)

    with pytest.raises(FileNotFoundError):
        store.load(state.symbol, state.timeframe)


def test_state_store_failed_replace_preserves_last_good_checkpoint(tmp_path: Path, monkeypatch) -> None:
    original = _state()
    replacement = ScannerState.from_dict(
        {
            **original.to_dict(),
            "last_closed_bar": "2026-09-04",
        }
    )
    store = ScannerStateStore(tmp_path)
    destination = store.save(original)

    def fail_replace(_source, _destination):
        raise OSError("simulated interrupted replace")

    monkeypatch.setattr(scanner_state.os, "replace", fail_replace)

    with pytest.raises(OSError, match="simulated interrupted replace"):
        store.save(replacement)

    assert store.load(original.symbol, original.timeframe) == original
    assert destination.read_text(encoding="utf-8") == json.dumps(
        original.to_dict(),
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    )
    assert not list(tmp_path.glob(".*.tmp"))


def test_state_store_rejects_truncated_checkpoint_without_fallback(tmp_path: Path) -> None:
    state = _state()
    store = ScannerStateStore(tmp_path)
    path = store.path_for(state.symbol, state.timeframe)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{\"schema_version\": 3,", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid ScannerState file"):
        store.load(state.symbol, state.timeframe)


def test_state_store_rejects_corrupt_checkpoint_without_fallback(tmp_path: Path) -> None:
    state = _state()
    store = ScannerStateStore(tmp_path)
    path = store.path_for(state.symbol, state.timeframe)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = state.to_dict()
    payload["candidate"] = {"bar_key": "2026-08-28"}
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid ScannerState file"):
        store.load(state.symbol, state.timeframe)
