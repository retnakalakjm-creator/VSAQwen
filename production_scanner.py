from __future__ import annotations

from collections.abc import MutableSequence
from pathlib import Path

import pandas as pd

from engine.columns import COL_WEEK
from historical_scanner import HistoricalScannerRunner
from logger import Log
from scanner import ScannerCandidate, ScannerEngine
from scanner_state import (
    ScannerState,
    ScannerStateFingerprintMismatch,
    ScannerStateStore,
    validate_scanner_state_fingerprints,
)
from scanner_transition_resume import ScannerTransitionResumeAdapter
from scanner_transition_snapshot import ScannerTransitionSnapshotAdapter

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


def _target_bar_key(metrics: pd.DataFrame, target_index: int) -> str | None:
    if COL_WEEK not in metrics.columns:
        return None
    value = metrics.iloc[target_index].get(COL_WEEK)
    if value is None or pd.isna(value):
        return None
    return str(value)


def _state_matches_target(
    state: ScannerState,
    metrics: pd.DataFrame,
    target_index: int,
) -> bool:
    target_key = _target_bar_key(metrics, target_index)
    return target_key is not None and state.last_closed_bar == target_key


def _full_replay_candidate(metrics: pd.DataFrame, target_index: int) -> ScannerCandidate:
    """Return a full point-in-time candidate through the historical runner."""

    return HistoricalScannerRunner().scan_to_index(metrics, target_index)


def _full_replay_candidate_and_snapshot(
    metrics: pd.DataFrame,
    *,
    target_index: int,
    symbol: str,
    timeframe: str,
    snapshot: ScannerTransitionSnapshotAdapter,
) -> tuple[ScannerCandidate, ScannerState]:
    """Return latest candidate and snapshot from one full-replay boundary."""

    runner = HistoricalScannerRunner()
    scan_to_index_with_state = getattr(runner, "scan_to_index_with_state", None)
    if callable(scan_to_index_with_state):
        candidate, transition_state = scan_to_index_with_state(metrics, target_index)
        snapshot_from_transition_state = getattr(
            snapshot,
            "snapshot_from_transition_state",
            None,
        )
        if callable(snapshot_from_transition_state):
            return candidate, snapshot_from_transition_state(
                metrics,
                target_index=target_index,
                symbol=symbol,
                timeframe=timeframe,
                transition_state=transition_state,
            )

    candidate = _full_replay_candidate(metrics, target_index)
    return candidate, snapshot.snapshot(
        metrics,
        target_index=target_index,
        symbol=symbol,
        timeframe=timeframe,
    )


def _snapshot_latest(
    *,
    metrics: pd.DataFrame,
    symbol: str,
    timeframe: str,
    store: ScannerStateStore,
    snapshot: ScannerTransitionSnapshotAdapter,
) -> None:
    target_index = _target_index(metrics)
    if target_index is None:
        return

    state = snapshot.snapshot(
        metrics,
        target_index=target_index,
        symbol=symbol,
        timeframe=timeframe,
    )
    store.save(state)


def _snapshot_from_resume_result(
    *,
    metrics: pd.DataFrame,
    symbol: str,
    timeframe: str,
    target_index: int,
    snapshot: ScannerTransitionSnapshotAdapter,
    resume_result: object,
) -> ScannerState | None:
    snapshot_from_transition_state = getattr(
        snapshot,
        "snapshot_from_transition_state",
        None,
    )
    transition_state = getattr(resume_result, "transition_state", None)
    if not callable(snapshot_from_transition_state) or transition_state is None:
        return None

    return snapshot_from_transition_state(
        metrics,
        target_index=target_index,
        symbol=symbol,
        timeframe=timeframe,
        transition_state=transition_state,
    )


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
    """Scan the latest bar using the production scanner path.

    The first run for a symbol/timeframe bootstraps a durable scanner state with
    one full point-in-time scan through the transition runner. Later runs resume
    from the saved causal state through the transition resume adapter and refresh
    that state at the latest completed bar through the transition snapshot
    adapter. Persisted state is only used when its engine/config/data fingerprints
    match the current runtime and data prefix; stale state falls back to a full
    transition-runner replay when fallback is allowed.

    ``fallback_diagnostics`` receives explicit diagnostic messages when a saved
    checkpoint is corrupt, stale, or unable to resume. Normal first-run bootstrap
    remains quiet because no persisted checkpoint was rejected.
    """
    target_index = _target_index(metrics)
    if target_index is None:
        return None

    store = state_store if state_store is not None else ScannerStateStore(state_root)
    transition_resume = ScannerTransitionResumeAdapter()
    transition_snapshot = ScannerTransitionSnapshotAdapter()
    needs_snapshot_refresh = True
    replay_snapshot: ScannerState | None = None

    try:
        state = store.load(symbol, timeframe)
        validate_scanner_state_fingerprints(state, metrics)
        needs_snapshot_refresh = not _state_matches_target(
            state,
            metrics,
            target_index,
        )
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
            resume_latest_with_state = getattr(
                transition_resume,
                "resume_latest_with_state",
                None,
            )
            if callable(resume_latest_with_state):
                resume_result = resume_latest_with_state(metrics, state)
                candidate = resume_result.candidate
                if needs_snapshot_refresh:
                    replay_snapshot = _snapshot_from_resume_result(
                        metrics=metrics,
                        symbol=symbol,
                        timeframe=timeframe,
                        target_index=target_index,
                        snapshot=transition_snapshot,
                        resume_result=resume_result,
                    )
            else:
                candidate = transition_resume.resume_latest(metrics, state)
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
            candidate, replay_snapshot = _full_replay_candidate_and_snapshot(
                metrics,
                target_index=target_index,
                symbol=symbol,
                timeframe=timeframe,
                snapshot=transition_snapshot,
            )
            needs_snapshot_refresh = True
    else:
        candidate, replay_snapshot = _full_replay_candidate_and_snapshot(
            metrics,
            target_index=target_index,
            symbol=symbol,
            timeframe=timeframe,
            snapshot=transition_snapshot,
        )

    if needs_snapshot_refresh:
        if replay_snapshot is not None:
            store.save(replay_snapshot)
        else:
            _snapshot_latest(
                metrics=metrics,
                symbol=symbol,
                timeframe=timeframe,
                store=store,
                snapshot=transition_snapshot,
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
    """Return the latest actionable candidate via the production scanner path."""
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
