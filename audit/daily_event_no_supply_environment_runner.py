"""Parallel frozen-snapshot runner for L6 NO_SUPPLY environment replay."""

from __future__ import annotations

import hashlib
import json
import multiprocessing
import os
from collections.abc import Callable, Iterable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

from audit.daily_event_no_supply_environment_replay import (
    NoSupplyEnvironmentObservation,
    NoSupplyEnvironmentSourceLineage,
    NoSupplyReplayFailure,
    NoSupplySymbolReplaySummary,
    replay_symbol_no_supply_environment,
)
from audit.daily_input_reproducibility import (
    DailyAuditInputBundle,
    load_daily_audit_input,
)
from audit.offline_daily_evidence import (
    DEFAULT_DAILY_EVIDENCE_MIN_TARGET_INDEX,
)


ProgressWriter = Callable[[str], None]
NO_SUPPLY_REPLAY_CHECKPOINT_VERSION = 1


@dataclass(frozen=True, slots=True)
class FrozenNoSupplyEnvironmentReplayResult:
    observations: tuple[NoSupplyEnvironmentObservation, ...]
    symbol_rows: tuple[NoSupplySymbolReplaySummary, ...]
    failures: tuple[NoSupplyReplayFailure, ...]
    worker_count: int
    checkpoint_reused_count: int = 0
    checkpoint_written_count: int = 0
    progress_manifest: str | None = None


@dataclass(frozen=True, slots=True)
class _WorkerCompletion:
    symbol: str
    observations: tuple[NoSupplyEnvironmentObservation, ...] | None
    symbol_summary: NoSupplySymbolReplaySummary | None
    exception_type: str | None = None
    reason: str | None = None





def build_no_supply_checkpoint_signature(
    *,
    source_lineage: NoSupplyEnvironmentSourceLineage,
    now: str,
    min_target_index: int,
) -> str:
    if min_target_index < 0:
        raise ValueError("min_target_index cannot be negative")
    payload = {
        "checkpoint_version": NO_SUPPLY_REPLAY_CHECKPOINT_VERSION,
        "replay_contract": "no-supply-current-vs-bullish-environment-v1",
        "source_lineage": asdict(source_lineage),
        "now": str(now),
        "min_target_index": int(min_target_index),
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def default_no_supply_worker_count(symbol_count: int) -> int:
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


def select_symbol_shard(
    symbols: Sequence[str] | Iterable[str],
    *,
    shard_index: int,
    shard_count: int,
) -> tuple[str, ...]:
    requested = _normalize_symbols(symbols)
    if shard_count < 1:
        raise ValueError("shard_count must be positive")
    if not 0 <= shard_index < shard_count:
        raise ValueError(
            "shard_index must satisfy 0 <= shard_index < shard_count"
        )
    selected = tuple(
        symbol
        for index, symbol in enumerate(requested)
        if index % shard_count == shard_index
    )
    if not selected:
        raise ValueError(
            "selected shard is empty; reduce shard_count or choose "
            "another shard_index"
        )
    return selected


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
) -> _WorkerCompletion:
    symbol, input_snapshot_dir, now, min_target_index = task
    try:
        daily = load_daily_audit_input(input_snapshot_dir, symbol)
        observations, symbol_summary = (
            replay_symbol_no_supply_environment(
                symbol=symbol,
                daily=daily,
                now=now,
                min_target_index=min_target_index,
            )
        )
    except Exception as exc:
        return _WorkerCompletion(
            symbol=symbol,
            observations=None,
            symbol_summary=None,
            exception_type=type(exc).__name__,
            reason=str(exc),
        )
    return _WorkerCompletion(
        symbol=symbol,
        observations=observations,
        symbol_summary=symbol_summary,
    )


def _progress_message(
    *,
    completed: int,
    total: int,
    completion: _WorkerCompletion,
) -> str:
    if (
        completion.observations is not None
        and completion.symbol_summary is not None
    ):
        row = completion.symbol_summary
        return (
            f"[daily-no-supply] {completed}/{total} completed "
            f"{completion.symbol}: "
            f"{row.replayed_bearish_target_count} bearish prefixes, "
            f"{row.current_candidate_count} current, "
            f"{row.alternate_candidate_count} alternate"
        )
    return (
        f"[daily-no-supply] {completed}/{total} failed "
        f"{completion.symbol}: {completion.exception_type}: "
        f"{completion.reason}"
    )


def _safe_symbol_filename(symbol: str) -> str:
    return (
        symbol.replace("^", "_")
        .replace("/", "_")
        .replace("\\", "_")
        .replace(":", "_")
    )


def _checkpoint_path(
    checkpoint_dir: Path,
    symbol: str,
) -> Path:
    return checkpoint_dir / (
        f"{_safe_symbol_filename(symbol)}.json"
    )


def write_no_supply_symbol_checkpoint(
    *,
    checkpoint_dir: str | Path,
    checkpoint_signature: str,
    symbol: str,
    observations: tuple[NoSupplyEnvironmentObservation, ...],
    symbol_summary: NoSupplySymbolReplaySummary,
) -> Path:
    root = Path(checkpoint_dir)
    root.mkdir(parents=True, exist_ok=True)
    clean_symbol = str(symbol).strip().upper()
    if not clean_symbol:
        raise ValueError("checkpoint symbol cannot be blank")
    if symbol_summary.symbol != clean_symbol:
        raise ValueError("checkpoint symbol summary does not match symbol")
    if any(item.symbol != clean_symbol for item in observations):
        raise ValueError("checkpoint contains observation for wrong symbol")

    path = _checkpoint_path(root, clean_symbol)
    payload = {
        "checkpoint_version": NO_SUPPLY_REPLAY_CHECKPOINT_VERSION,
        "checkpoint_signature": checkpoint_signature,
        "symbol": clean_symbol,
        "symbol_summary": asdict(symbol_summary),
        "observations": [
            {
                **asdict(item),
                "passed_confirmations": list(item.passed_confirmations),
                "failed_confirmations": list(item.failed_confirmations),
            }
            for item in observations
        ],
    }
    temp = path.with_name(
        f".{path.name}.{os.getpid()}.tmp"
    )
    temp.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temp.replace(path)
    return path


def load_no_supply_symbol_checkpoint(
    *,
    checkpoint_dir: str | Path,
    checkpoint_signature: str,
    symbol: str,
) -> tuple[
    tuple[NoSupplyEnvironmentObservation, ...],
    NoSupplySymbolReplaySummary,
] | None:
    clean_symbol = str(symbol).strip().upper()
    path = _checkpoint_path(Path(checkpoint_dir), clean_symbol)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if (
        int(payload.get("checkpoint_version", -1))
        != NO_SUPPLY_REPLAY_CHECKPOINT_VERSION
    ):
        return None
    if payload.get("checkpoint_signature") != checkpoint_signature:
        return None
    if payload.get("symbol") != clean_symbol:
        return None

    try:
        summary_payload = payload["symbol_summary"]
        observation_payloads = payload["observations"]
        symbol_summary = NoSupplySymbolReplaySummary(
            **summary_payload
        )
        observations = tuple(
            NoSupplyEnvironmentObservation(
                **{
                    **item,
                    "passed_confirmations": tuple(
                        item["passed_confirmations"]
                    ),
                    "failed_confirmations": tuple(
                        item["failed_confirmations"]
                    ),
                }
            )
            for item in observation_payloads
        )
    except (KeyError, TypeError, ValueError):
        return None

    if symbol_summary.symbol != clean_symbol:
        return None
    if any(item.symbol != clean_symbol for item in observations):
        return None
    if symbol_summary.common_signature_count != len(observations):
        return None
    return observations, symbol_summary


def _selection_digest(
    symbols: tuple[str, ...],
) -> str:
    payload = "\n".join(symbols).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:12]


def replay_progress_manifest_path(
    checkpoint_dir: str | Path,
    symbols: Sequence[str] | Iterable[str],
) -> Path:
    requested = _normalize_symbols(symbols)
    root = Path(checkpoint_dir) / "progress"
    return root / f"selection-{_selection_digest(requested)}.json"


def _write_progress_manifest(
    *,
    path: Path,
    checkpoint_signature: str,
    requested: tuple[str, ...],
    reused: set[str],
    completed: set[str],
    failures: dict[str, NoSupplyReplayFailure],
    worker_count: int,
    status: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    successful = reused | completed
    pending = [
        symbol
        for symbol in requested
        if symbol not in successful and symbol not in failures
    ]
    payload = {
        "checkpoint_version": NO_SUPPLY_REPLAY_CHECKPOINT_VERSION,
        "checkpoint_signature": checkpoint_signature,
        "status": status,
        "requested_symbols": list(requested),
        "checkpoint_reused_symbols": [
            symbol for symbol in requested if symbol in reused
        ],
        "newly_completed_symbols": [
            symbol for symbol in requested if symbol in completed
        ],
        "failed_symbols": [
            symbol for symbol in requested if symbol in failures
        ],
        "pending_symbols": pending,
        "requested_symbol_count": len(requested),
        "checkpoint_reused_count": len(reused),
        "newly_completed_count": len(completed),
        "failed_symbol_count": len(failures),
        "pending_symbol_count": len(pending),
        "worker_count": worker_count,
    }
    temp = path.with_name(
        f".{path.name}.{os.getpid()}.tmp"
    )
    temp.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temp.replace(path)


def run_frozen_no_supply_environment_replay(
    symbols: Sequence[str] | Iterable[str],
    *,
    bundle: DailyAuditInputBundle,
    input_snapshot_dir: str | Path,
    now: str,
    min_target_index: int = DEFAULT_DAILY_EVIDENCE_MIN_TARGET_INDEX,
    workers: int | None = None,
    progress_writer: ProgressWriter | None = None,
    checkpoint_dir: str | Path | None = None,
    checkpoint_signature: str | None = None,
    resume: bool = True,
) -> FrozenNoSupplyEnvironmentReplayResult:
    requested = _normalize_symbols(symbols)
    scheduled = _scheduled_symbols(requested, bundle)

    if checkpoint_dir is not None and not checkpoint_signature:
        raise ValueError(
            "checkpoint_signature is required when checkpoint_dir is set"
        )

    worker_count = (
        default_no_supply_worker_count(len(requested))
        if workers is None
        else int(workers)
    )
    if worker_count < 1:
        raise ValueError("workers must be positive")
    worker_count = min(worker_count, len(requested))

    observations_by_symbol: dict[
        str,
        tuple[NoSupplyEnvironmentObservation, ...],
    ] = {}
    summaries_by_symbol: dict[str, NoSupplySymbolReplaySummary] = {}
    failures_by_symbol: dict[str, NoSupplyReplayFailure] = {}
    reused_symbols: set[str] = set()
    completed_symbols: set[str] = set()
    manifest_path: Path | None = None

    if checkpoint_dir is not None:
        assert checkpoint_signature is not None
        manifest_path = replay_progress_manifest_path(
            checkpoint_dir,
            requested,
        )
        if resume:
            for symbol in requested:
                loaded = load_no_supply_symbol_checkpoint(
                    checkpoint_dir=checkpoint_dir,
                    checkpoint_signature=checkpoint_signature,
                    symbol=symbol,
                )
                if loaded is None:
                    continue
                observations, summary = loaded
                observations_by_symbol[symbol] = observations
                summaries_by_symbol[symbol] = summary
                reused_symbols.add(symbol)

    pending_scheduled = tuple(
        symbol for symbol in scheduled if symbol not in reused_symbols
    )

    if progress_writer is not None:
        progress_writer(
            "[daily-no-supply] frozen replay: "
            f"{len(requested)} requested, "
            f"{len(reused_symbols)} resumed, "
            f"{len(pending_scheduled)} pending, "
            f"{worker_count} workers; "
            "non-bearish targets are skipped before prefix replay"
        )

    if manifest_path is not None:
        _write_progress_manifest(
            path=manifest_path,
            checkpoint_signature=checkpoint_signature or "",
            requested=requested,
            reused=reused_symbols,
            completed=completed_symbols,
            failures=failures_by_symbol,
            worker_count=worker_count,
            status="RUNNING",
        )

    tasks = tuple(
        (
            symbol,
            str(Path(input_snapshot_dir)),
            now,
            int(min_target_index),
        )
        for symbol in pending_scheduled
    )

    def capture(completion: _WorkerCompletion) -> None:
        if (
            completion.observations is not None
            and completion.symbol_summary is not None
        ):
            if completion.symbol_summary.symbol != completion.symbol:
                raise RuntimeError(
                    "NO_SUPPLY worker returned wrong symbol summary"
                )
            if any(
                item.symbol != completion.symbol
                for item in completion.observations
            ):
                raise RuntimeError(
                    "NO_SUPPLY worker returned observation for wrong symbol"
                )
            observations_by_symbol[completion.symbol] = (
                completion.observations
            )
            summaries_by_symbol[completion.symbol] = (
                completion.symbol_summary
            )
            completed_symbols.add(completion.symbol)
            if checkpoint_dir is not None:
                assert checkpoint_signature is not None
                write_no_supply_symbol_checkpoint(
                    checkpoint_dir=checkpoint_dir,
                    checkpoint_signature=checkpoint_signature,
                    symbol=completion.symbol,
                    observations=completion.observations,
                    symbol_summary=completion.symbol_summary,
                )
            return

        failures_by_symbol[completion.symbol] = NoSupplyReplayFailure(
            symbol=completion.symbol,
            exception_type=completion.exception_type or "UnknownError",
            reason=completion.reason or "unknown worker failure",
        )

    def after_completion(
        *,
        completed_index: int,
        completion: _WorkerCompletion,
    ) -> None:
        if progress_writer is not None:
            progress_writer(
                _progress_message(
                    completed=(
                        len(reused_symbols) + completed_index
                    ),
                    total=len(requested),
                    completion=completion,
                )
            )
        if manifest_path is not None:
            _write_progress_manifest(
                path=manifest_path,
                checkpoint_signature=checkpoint_signature or "",
                requested=requested,
                reused=reused_symbols,
                completed=completed_symbols,
                failures=failures_by_symbol,
                worker_count=worker_count,
                status="RUNNING",
            )

    if tasks and worker_count == 1:
        completions = map(_worker_task, tasks)
        for completed_index, completion in enumerate(
            completions,
            start=1,
        ):
            capture(completion)
            after_completion(
                completed_index=completed_index,
                completion=completion,
            )
    elif tasks:
        actual_worker_count = min(worker_count, len(tasks))
        context = multiprocessing.get_context("spawn")
        pool = context.Pool(processes=actual_worker_count)
        try:
            completions = pool.imap_unordered(
                _worker_task,
                tasks,
                chunksize=1,
            )
            for completed_index, completion in enumerate(
                completions,
                start=1,
            ):
                capture(completion)
                after_completion(
                    completed_index=completed_index,
                    completion=completion,
                )
        except BaseException:
            pool.terminate()
            pool.join()
            if manifest_path is not None:
                _write_progress_manifest(
                    path=manifest_path,
                    checkpoint_signature=checkpoint_signature or "",
                    requested=requested,
                    reused=reused_symbols,
                    completed=completed_symbols,
                    failures=failures_by_symbol,
                    worker_count=worker_count,
                    status="INTERRUPTED",
                )
            raise
        else:
            pool.close()
            pool.join()

    final_status = (
        "COMPLETE"
        if not failures_by_symbol
        and len(reused_symbols | completed_symbols) == len(requested)
        else "PARTIAL"
    )
    if manifest_path is not None:
        _write_progress_manifest(
            path=manifest_path,
            checkpoint_signature=checkpoint_signature or "",
            requested=requested,
            reused=reused_symbols,
            completed=completed_symbols,
            failures=failures_by_symbol,
            worker_count=worker_count,
            status=final_status,
        )

    observations = tuple(
        item
        for symbol in requested
        for item in observations_by_symbol.get(symbol, ())
    )
    symbol_rows = tuple(
        summaries_by_symbol[symbol]
        for symbol in requested
        if symbol in summaries_by_symbol
    )
    failures = tuple(
        failures_by_symbol[symbol]
        for symbol in requested
        if symbol in failures_by_symbol
    )
    return FrozenNoSupplyEnvironmentReplayResult(
        observations=observations,
        symbol_rows=symbol_rows,
        failures=failures,
        worker_count=worker_count,
        checkpoint_reused_count=len(reused_symbols),
        checkpoint_written_count=len(completed_symbols),
        progress_manifest=(
            str(manifest_path) if manifest_path is not None else None
        ),
    )


__all__ = [
    "NO_SUPPLY_REPLAY_CHECKPOINT_VERSION",
    "FrozenNoSupplyEnvironmentReplayResult",
    "build_no_supply_checkpoint_signature",
    "default_no_supply_worker_count",
    "load_no_supply_symbol_checkpoint",
    "replay_progress_manifest_path",
    "run_frozen_no_supply_environment_replay",
    "select_symbol_shard",
    "write_no_supply_symbol_checkpoint",
]
