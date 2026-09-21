"""Parallel frozen-snapshot orchestration for the L3 confirmation audit."""

from __future__ import annotations

import multiprocessing
import os
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from audit.daily_event_confirmation_counterfactual import (
    DailyConfirmationAuditFailure,
    DailyConfirmationObservation,
    capture_symbol_confirmation_observations,
)
from audit.daily_input_reproducibility import (
    DailyAuditInputBundle,
    load_daily_audit_input,
)
from audit.offline_daily_evidence import (
    DEFAULT_DAILY_EVIDENCE_MIN_TARGET_INDEX,
)


ProgressWriter = Callable[[str], None]


@dataclass(frozen=True, slots=True)
class FrozenConfirmationReplayResult:
    observations: tuple[DailyConfirmationObservation, ...]
    failures: tuple[DailyConfirmationAuditFailure, ...]
    worker_count: int


@dataclass(frozen=True, slots=True)
class _ConfirmationWorkerCompletion:
    symbol: str
    observations: tuple[DailyConfirmationObservation, ...] | None
    exception_type: str | None = None
    reason: str | None = None


def default_confirmation_worker_count(symbol_count: int) -> int:
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


def _worker_task(
    task: tuple[str, str, str, int],
) -> _ConfirmationWorkerCompletion:
    symbol, input_snapshot_dir, now, min_target_index = task
    try:
        daily = load_daily_audit_input(input_snapshot_dir, symbol)
        observations = capture_symbol_confirmation_observations(
            symbol=symbol,
            daily=daily,
            now=now,
            min_target_index=min_target_index,
        )
    except Exception as exc:
        return _ConfirmationWorkerCompletion(
            symbol=symbol,
            observations=None,
            exception_type=type(exc).__name__,
            reason=str(exc),
        )
    return _ConfirmationWorkerCompletion(
        symbol=symbol,
        observations=observations,
    )


def _capture_completion(
    completion: _ConfirmationWorkerCompletion,
    *,
    observations_by_symbol: dict[
        str,
        tuple[DailyConfirmationObservation, ...],
    ],
    failures_by_symbol: dict[str, DailyConfirmationAuditFailure],
) -> None:
    if completion.observations is not None:
        if any(
            item.symbol != completion.symbol
            for item in completion.observations
        ):
            raise RuntimeError(
                "confirmation worker returned observation for wrong symbol"
            )
        observations_by_symbol[completion.symbol] = completion.observations
        return

    failures_by_symbol[completion.symbol] = DailyConfirmationAuditFailure(
        symbol=completion.symbol,
        exception_type=completion.exception_type or "UnknownError",
        reason=completion.reason or "unknown worker failure",
    )


def _progress_message(
    *,
    completed: int,
    total: int,
    completion: _ConfirmationWorkerCompletion,
) -> str:
    if completion.observations is not None:
        return (
            f"[daily-confirmation] {completed}/{total} completed "
            f"{completion.symbol}: "
            f"{len(completion.observations)} physical observations"
        )
    return (
        f"[daily-confirmation] {completed}/{total} failed "
        f"{completion.symbol}: {completion.exception_type}: "
        f"{completion.reason}"
    )


def run_frozen_confirmation_replay(
    symbols: Sequence[str] | Iterable[str],
    *,
    bundle: DailyAuditInputBundle,
    input_snapshot_dir: str | Path,
    now: str,
    min_target_index: int = DEFAULT_DAILY_EVIDENCE_MIN_TARGET_INDEX,
    workers: int | None = None,
    progress_writer: ProgressWriter | None = None,
) -> FrozenConfirmationReplayResult:
    requested = _normalize_symbols(symbols)
    scheduled = _scheduled_symbols(requested, bundle)

    worker_count = (
        default_confirmation_worker_count(len(requested))
        if workers is None
        else int(workers)
    )
    if worker_count < 1:
        raise ValueError("workers must be positive")
    worker_count = min(worker_count, len(requested))

    if progress_writer is not None:
        progress_writer(
            "[daily-confirmation] frozen replay: "
            f"{len(requested)} symbols, {worker_count} workers"
        )

    tasks = tuple(
        (
            symbol,
            str(Path(input_snapshot_dir)),
            now,
            int(min_target_index),
        )
        for symbol in scheduled
    )
    observations_by_symbol: dict[
        str,
        tuple[DailyConfirmationObservation, ...],
    ] = {}
    failures_by_symbol: dict[str, DailyConfirmationAuditFailure] = {}

    if worker_count == 1:
        completions = map(_worker_task, tasks)
        for completed, completion in enumerate(completions, start=1):
            _capture_completion(
                completion,
                observations_by_symbol=observations_by_symbol,
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
                _worker_task,
                tasks,
                chunksize=1,
            )
            for completed, completion in enumerate(completions, start=1):
                _capture_completion(
                    completion,
                    observations_by_symbol=observations_by_symbol,
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
        except BaseException:
            pool.terminate()
            pool.join()
            raise
        else:
            pool.close()
            pool.join()

    observations = tuple(
        item
        for symbol in requested
        for item in observations_by_symbol.get(symbol, ())
    )
    failures = tuple(
        failures_by_symbol[symbol]
        for symbol in requested
        if symbol in failures_by_symbol
    )
    return FrozenConfirmationReplayResult(
        observations=observations,
        failures=failures,
        worker_count=worker_count,
    )


__all__ = [
    "FrozenConfirmationReplayResult",
    "default_confirmation_worker_count",
    "run_frozen_confirmation_replay",
]
