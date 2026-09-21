"""Parallel orchestration for frozen daily-event inventory replay.

The worker boundary is intentionally audit-only. Each process independently
loads and verifies one frozen snapshot, then runs either the cached causal
replay or the legacy prefix replay oracle. Parent aggregation restores
requested symbol order.
"""

from __future__ import annotations

import multiprocessing
import os
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from audit.daily_event_inventory import DailyEventAuditFailure
from audit.daily_input_reproducibility import (
    DailyAuditInputBundle,
    load_daily_audit_input,
)
from audit.offline_daily_evidence import (
    OfflineDailyEvidenceArchive,
    produce_offline_daily_evidence,
    produce_offline_daily_evidence_cached,
)


ProgressWriter = Callable[[str], None]

REPLAY_MODE_CACHED = "cached"
REPLAY_MODE_PREFIX = "prefix"
REPLAY_MODES = (REPLAY_MODE_CACHED, REPLAY_MODE_PREFIX)


@dataclass(frozen=True, slots=True)
class FrozenSnapshotReplayResult:
    archives: tuple[OfflineDailyEvidenceArchive, ...]
    failures: tuple[DailyEventAuditFailure, ...]
    worker_count: int


@dataclass(frozen=True, slots=True)
class _SnapshotWorkerCompletion:
    symbol: str
    archive: OfflineDailyEvidenceArchive | None
    exception_type: str | None = None
    reason: str | None = None


def default_snapshot_worker_count(symbol_count: int) -> int:
    if symbol_count < 1:
        raise ValueError("symbol_count must be positive")
    cpu_count = os.cpu_count() or 1
    usable_cpu_count = max(1, cpu_count - 1)
    return min(symbol_count, 4, usable_cpu_count)


def _normalize_symbols(
    symbols: Sequence[str] | Iterable[str],
) -> tuple[str, ...]:
    normalized = tuple(
        str(symbol).strip().upper()
        for symbol in symbols
        if str(symbol).strip()
    )
    if not normalized:
        raise ValueError("at least one symbol is required")
    if len(set(normalized)) != len(normalized):
        raise ValueError("symbols must be unique")
    return normalized


def _scheduled_symbols(
    symbols: tuple[str, ...],
    bundle: DailyAuditInputBundle,
) -> tuple[str, ...]:
    row_counts = {
        item.symbol: item.row_count
        for item in bundle.fingerprints
    }
    missing = sorted(set(symbols) - set(row_counts))
    if missing:
        raise ValueError(
            "daily audit input bundle missing requested symbols: "
            f"{missing}"
        )
    position = {symbol: index for index, symbol in enumerate(symbols)}
    return tuple(
        sorted(
            symbols,
            key=lambda symbol: (
                -row_counts[symbol],
                position[symbol],
            ),
        )
    )


def _snapshot_worker_task(
    task: tuple[str, str, str, int, str],
) -> _SnapshotWorkerCompletion:
    symbol, input_snapshot_dir, now, min_target_index, replay_mode = task
    try:
        daily = load_daily_audit_input(input_snapshot_dir, symbol)
        producer = (
            produce_offline_daily_evidence_cached
            if replay_mode == REPLAY_MODE_CACHED
            else produce_offline_daily_evidence
        )
        archive = producer(
            symbol=symbol,
            daily=daily,
            now=now,
            min_target_index=min_target_index,
        )
    except Exception as exc:
        return _SnapshotWorkerCompletion(
            symbol=symbol,
            archive=None,
            exception_type=type(exc).__name__,
            reason=str(exc),
        )
    return _SnapshotWorkerCompletion(
        symbol=symbol,
        archive=archive,
    )


def _progress_message(
    *,
    completed: int,
    total: int,
    completion: _SnapshotWorkerCompletion,
) -> str:
    if completion.archive is not None:
        return (
            f"[daily-event-inventory] {completed}/{total} completed "
            f"{completion.symbol}: "
            f"{completion.archive.evaluated_bar_count} evaluated bars"
        )
    return (
        f"[daily-event-inventory] {completed}/{total} failed "
        f"{completion.symbol}: {completion.exception_type}: "
        f"{completion.reason}"
    )


def _capture_completion(
    completion: _SnapshotWorkerCompletion,
    *,
    archives_by_symbol: dict[str, OfflineDailyEvidenceArchive],
    failures_by_symbol: dict[str, DailyEventAuditFailure],
) -> None:
    if completion.archive is not None:
        if completion.archive.symbol != completion.symbol:
            raise RuntimeError(
                "frozen replay worker returned wrong symbol: "
                f"expected {completion.symbol}, "
                f"got {completion.archive.symbol}"
            )
        archives_by_symbol[completion.symbol] = completion.archive
        return

    failures_by_symbol[completion.symbol] = DailyEventAuditFailure(
        symbol=completion.symbol,
        exception_type=completion.exception_type or "UnknownError",
        reason=completion.reason or "",
    )


def run_frozen_snapshot_replay(
    symbols: Sequence[str] | Iterable[str],
    *,
    bundle: DailyAuditInputBundle,
    input_snapshot_dir: str | Path,
    now: str,
    min_target_index: int,
    workers: int | None = None,
    replay_mode: str = REPLAY_MODE_CACHED,
    progress_writer: ProgressWriter | None = None,
) -> FrozenSnapshotReplayResult:
    requested = _normalize_symbols(symbols)
    scheduled = _scheduled_symbols(requested, bundle)
    if replay_mode not in REPLAY_MODES:
        raise ValueError(
            f"replay_mode must be one of {REPLAY_MODES}, got {replay_mode!r}"
        )
    worker_count = (
        default_snapshot_worker_count(len(requested))
        if workers is None
        else int(workers)
    )
    if worker_count < 1:
        raise ValueError("workers must be positive")
    worker_count = min(worker_count, len(requested))

    if progress_writer is not None:
        progress_writer(
            "[daily-event-inventory] frozen replay: "
            f"{len(requested)} symbols, {worker_count} workers, "
            f"mode={replay_mode}"
        )

    root = str(Path(input_snapshot_dir))
    tasks = tuple(
        (symbol, root, now, min_target_index, replay_mode)
        for symbol in scheduled
    )
    archives_by_symbol: dict[str, OfflineDailyEvidenceArchive] = {}
    failures_by_symbol: dict[str, DailyEventAuditFailure] = {}

    if worker_count == 1:
        completions = (
            _snapshot_worker_task(task)
            for task in tasks
        )
        for completed, completion in enumerate(completions, start=1):
            _capture_completion(
                completion,
                archives_by_symbol=archives_by_symbol,
                failures_by_symbol=failures_by_symbol,
            )
            if progress_writer is not None:
                progress_writer(
                    _progress_message(
                        completed=completed,
                        total=len(requested),
                        completion=completion,
                    )
                )
    else:
        context = multiprocessing.get_context("spawn")
        pool = context.Pool(processes=worker_count)
        try:
            completions = pool.imap_unordered(
                _snapshot_worker_task,
                tasks,
                chunksize=1,
            )
            for completed, completion in enumerate(completions, start=1):
                _capture_completion(
                    completion,
                    archives_by_symbol=archives_by_symbol,
                    failures_by_symbol=failures_by_symbol,
                )
                if progress_writer is not None:
                    progress_writer(
                        _progress_message(
                            completed=completed,
                            total=len(requested),
                            completion=completion,
                        )
                    )
        except KeyboardInterrupt:
            pool.terminate()
            pool.join()
            raise
        except BaseException:
            pool.terminate()
            pool.join()
            raise
        else:
            pool.close()
            pool.join()

    archives = tuple(
        archives_by_symbol[symbol]
        for symbol in requested
        if symbol in archives_by_symbol
    )
    failures = tuple(
        failures_by_symbol[symbol]
        for symbol in requested
        if symbol in failures_by_symbol
    )
    return FrozenSnapshotReplayResult(
        archives=archives,
        failures=failures,
        worker_count=worker_count,
    )


__all__ = [
    "FrozenSnapshotReplayResult",
    "REPLAY_MODE_CACHED",
    "REPLAY_MODE_PREFIX",
    "REPLAY_MODES",
    "default_snapshot_worker_count",
    "run_frozen_snapshot_replay",
]
