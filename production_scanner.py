from __future__ import annotations

from collections.abc import MutableSequence
from pathlib import Path

import pandas as pd

from incremental_scanner import IncrementalScannerEngine
from logger import Log
from scanner import ScannerCandidate, ScannerEngine
from scanner_state import (
    ScannerStateFingerprintMismatch,
    ScannerStateStore,
    validate_scanner_state_fingerprints,
)

DEFAULT_TIMEFRAME = "1wk"

CHECKPOINT_MISSING = "CHECKPOINT_MISSING"
CHECKPOINT_STALE = "CHECKPOINT_STALE"
CHECKPOINT_CONFIG_MISMATCH = "CHECKPOINT_CONFIG_MISMATCH"
CHECKPOINT_DATA_MISMATCH = "CHECKPOINT_DATA_MISMATCH"
CHECKPOINT_CORRUPT = "CHECKPOINT_CORRUPT"
ENGINE_DIVERGENCE = "ENGINE_DIVERGENCE"


def _target_index(metrics: pd.DataFrame) -> int | None:
    if len(metrics) <= ScannerEngine.MIN_REPLAY_BARS:
        return None
    return len(metrics) - 1


def _snapshot_latest(
    *,
    metrics: pd.DataFrame,
    symbol: str,
    timeframe: str,
    store: ScannerStateStore,
    engine: IncrementalScannerEngine,
) -> None:
    target_index = _target_index(metrics)
    if target_index is None:
        return

    state = engine.snapshot(
        metrics,
        target_index=target_index,
        symbol=symbol,
        timeframe=timeframe,
    )
    store.save(state)


def _record_fallback(
    diagnostics: MutableSequence[str] | None,
    *,
    symbol: str,
    timeframe: str,
    code: str,
    reason: str,
) -> None:
    message = (
        f"{code}: {reason}; symbol={symbol}; timeframe={timeframe}; "
        "full replay fallback used"
    )
    Log.warn("Scanner fallback: %s", message)
    if diagnostics is not None:
        diagnostics.append(message)


def _fingerprint_fallback_code(exc: ScannerStateFingerprintMismatch) -> str:
    message = str(exc).lower()
    has_engine = "engine" in message
    has_config = "config" in message
    has_data = "data" in message

    if has_config and not has_engine and not has_data:
        return CHECKPOINT_CONFIG_MISMATCH
    if has_data and not has_engine and not has_config:
        return CHECKPOINT_DATA_MISMATCH
    return CHECKPOINT_STALE


def _fingerprint_reason(code: str) -> str:
    if code == CHECKPOINT_CONFIG_MISMATCH:
        return "persisted scanner state config fingerprint is stale"
    if code == CHECKPOINT_DATA_MISMATCH:
        return "persisted scanner state data prefix fingerprint is stale"
    return "persisted scanner state engine/config/data fingerprint is stale"


def scan_latest_candidate_production(
    metrics: pd.DataFrame,
    *,
    symbol: str,
    timeframe: str = DEFAULT_TIMEFRAME,
    state_store: ScannerStateStore | None = None,
    state_root: str | Path = "state",
    allow_full_replay_fallback: bool = True,
    fallback_diagnostics: MutableSequence[str] | None = None,
) -> ScannerCandidate | None:
    """Scan the latest bar using the incremental production path.

    The first run for a symbol/timeframe bootstraps a durable scanner state with
    one full point-in-time scan. Later runs resume from the saved causal state and
    refresh that state at the latest completed bar. Persisted state is only used
    when its engine/config/data fingerprints match the current runtime and data
    prefix; stale state falls back to a full replay when fallback is allowed.

    ``fallback_diagnostics`` receives explicit diagnostic messages when a saved
    checkpoint is corrupt, stale, or unable to resume. Normal first-run bootstrap
    remains quiet because no persisted checkpoint was rejected.
    """
    target_index = _target_index(metrics)
    if target_index is None:
        return None

    store = state_store if state_store is not None else ScannerStateStore(state_root)
    incremental = IncrementalScannerEngine()
    full_scanner = ScannerEngine()

    try:
        state = store.load(symbol, timeframe)
        validate_scanner_state_fingerprints(state, metrics)
    except FileNotFoundError:
        state = None
    except ScannerStateFingerprintMismatch as exc:
        if not allow_full_replay_fallback:
            raise
        code = _fingerprint_fallback_code(exc)
        _record_fallback(
            fallback_diagnostics,
            symbol=symbol,
            timeframe=timeframe,
            code=code,
            reason=_fingerprint_reason(code),
        )
        state = None
    except ValueError:
        if not allow_full_replay_fallback:
            raise
        _record_fallback(
            fallback_diagnostics,
            symbol=symbol,
            timeframe=timeframe,
            code=CHECKPOINT_CORRUPT,
            reason="persisted scanner state could not be loaded or validated",
        )
        state = None

    if state is not None:
        try:
            candidate = incremental.resume_latest(metrics, state)
        except (ValueError, IndexError, RuntimeError):
            if not allow_full_replay_fallback:
                raise
            _record_fallback(
                fallback_diagnostics,
                symbol=symbol,
                timeframe=timeframe,
                code=ENGINE_DIVERGENCE,
                reason="persisted scanner state could not resume current metrics",
            )
            candidate = full_scanner.scan_to_index(metrics, target_index)
    else:
        candidate = full_scanner.scan_to_index(metrics, target_index)

    _snapshot_latest(
        metrics=metrics,
        symbol=symbol,
        timeframe=timeframe,
        store=store,
        engine=incremental,
    )
    return candidate


def scan_actionable_production(
    metrics: pd.DataFrame,
    *,
    symbol: str,
    timeframe: str = DEFAULT_TIMEFRAME,
    state_store: ScannerStateStore | None = None,
    state_root: str | Path = "state",
    allow_full_replay_fallback: bool = True,
    fallback_diagnostics: MutableSequence[str] | None = None,
) -> list[ScannerCandidate]:
    """Return the latest actionable candidate via the incremental production path."""
    candidate = scan_latest_candidate_production(
        metrics,
        symbol=symbol,
        timeframe=timeframe,
        state_store=state_store,
        state_root=state_root,
        allow_full_replay_fallback=allow_full_replay_fallback,
        fallback_diagnostics=fallback_diagnostics,
    )
    if candidate is None or not candidate.actionable:
        return []
    return [candidate]


__all__ = [
    "CHECKPOINT_CONFIG_MISMATCH",
    "CHECKPOINT_CORRUPT",
    "CHECKPOINT_DATA_MISMATCH",
    "CHECKPOINT_MISSING",
    "CHECKPOINT_STALE",
    "DEFAULT_TIMEFRAME",
    "ENGINE_DIVERGENCE",
    "scan_actionable_production",
    "scan_latest_candidate_production",
]
