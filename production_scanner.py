from __future__ import annotations

from pathlib import Path

import pandas as pd

from incremental_scanner import IncrementalScannerEngine
from scanner import ScannerCandidate, ScannerEngine
from scanner_state import ScannerStateStore

DEFAULT_TIMEFRAME = "1wk"


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


def scan_latest_candidate_production(
    metrics: pd.DataFrame,
    *,
    symbol: str,
    timeframe: str = DEFAULT_TIMEFRAME,
    state_store: ScannerStateStore | None = None,
    state_root: str | Path = "state",
    allow_full_replay_fallback: bool = True,
) -> ScannerCandidate | None:
    """Scan the latest bar using the incremental production path.

    The first run for a symbol/timeframe bootstraps a durable scanner state with
    one full point-in-time scan. Later runs resume from the saved causal state and
    refresh that state at the latest completed bar.
    """
    target_index = _target_index(metrics)
    if target_index is None:
        return None

    store = state_store if state_store is not None else ScannerStateStore(state_root)
    incremental = IncrementalScannerEngine()
    full_scanner = ScannerEngine()

    try:
        state = store.load(symbol, timeframe)
    except FileNotFoundError:
        state = None
    except ValueError:
        if not allow_full_replay_fallback:
            raise
        state = None

    if state is not None:
        try:
            candidate = incremental.resume_latest(metrics, state)
        except (ValueError, IndexError, RuntimeError):
            if not allow_full_replay_fallback:
                raise
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
) -> list[ScannerCandidate]:
    """Return the latest actionable candidate via the incremental production path."""
    candidate = scan_latest_candidate_production(
        metrics,
        symbol=symbol,
        timeframe=timeframe,
        state_store=state_store,
        state_root=state_root,
        allow_full_replay_fallback=allow_full_replay_fallback,
    )
    if candidate is None or not candidate.actionable:
        return []
    return [candidate]
