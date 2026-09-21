"""Parallel/checkpoint runner for L8 matched NO_SUPPLY controls."""

from __future__ import annotations

import hashlib
import json
import multiprocessing
import os
from collections.abc import Callable, Iterable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

from audit.daily_event_no_supply_matched_environment import (
    NoSupplyMatchedControl,
    NoSupplyMatchedSourceLineage,
    NoSupplySymbolMatchSummary,
    NoSupplyUnmatchedTarget,
    match_symbol_controls,
)
from audit.daily_input_reproducibility import (
    DailyAuditInputBundle,
    load_daily_audit_input,
)
from audit.offline_daily_evidence import (
    DEFAULT_DAILY_EVIDENCE_MIN_TARGET_INDEX,
)


MATCHED_CONTROL_CHECKPOINT_VERSION = 1
ProgressWriter = Callable[[str], None]


@dataclass(frozen=True, slots=True)
class FrozenMatchedControlResult:
    controls: tuple[NoSupplyMatchedControl, ...]
    unmatched_targets: tuple[NoSupplyUnmatchedTarget, ...]
    symbol_rows: tuple[NoSupplySymbolMatchSummary, ...]
    failures: tuple[str, ...]
    worker_count: int
    checkpoint_reused_count: int
    checkpoint_written_count: int


@dataclass(frozen=True, slots=True)
class _WorkerCompletion:
    symbol: str
    controls: tuple[NoSupplyMatchedControl, ...] | None
    unmatched_targets: tuple[NoSupplyUnmatchedTarget, ...] | None
    symbol_summary: NoSupplySymbolMatchSummary | None
    exception_type: str | None = None
    reason: str | None = None


def build_matched_checkpoint_signature(
    *,
    source_lineage: NoSupplyMatchedSourceLineage,
    max_match_distance_sessions: int,
    min_target_index: int,
) -> str:
    payload = {
        "version": MATCHED_CONTROL_CHECKPOINT_VERSION,
        "contract": "no-supply-matched-environment-controls-v1",
        "source_lineage": asdict(source_lineage),
        "max_match_distance_sessions": int(max_match_distance_sessions),
        "min_target_index": int(min_target_index),
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def default_matched_worker_count(symbol_count: int) -> int:
    if symbol_count < 1:
        raise ValueError("symbol_count must be positive")
    usable = max(1, (os.cpu_count() or 1) - 1)
    return min(symbol_count, 4, usable)


def _normalize_symbols(
    symbols: Sequence[str] | Iterable[str],
) -> tuple[str, ...]:
    result = tuple(
        str(symbol).strip().upper()
        for symbol in symbols
        if str(symbol).strip()
    )
    if not result or len(result) != len(set(result)):
        raise ValueError("symbols must be non-empty and unique")
    return result


def _checkpoint_path(root: Path, symbol: str) -> Path:
    safe = (
        symbol.replace("^", "_")
        .replace("/", "_")
        .replace("\\", "_")
        .replace(":", "_")
    )
    return root / f"{safe}.json"


def write_symbol_match_checkpoint(
    *,
    checkpoint_dir: str | Path,
    signature: str,
    symbol: str,
    controls: tuple[NoSupplyMatchedControl, ...],
    unmatched_targets: tuple[NoSupplyUnmatchedTarget, ...],
    symbol_summary: NoSupplySymbolMatchSummary,
) -> Path:
    root = Path(checkpoint_dir)
    root.mkdir(parents=True, exist_ok=True)
    path = _checkpoint_path(root, symbol)
    payload = {
        "version": MATCHED_CONTROL_CHECKPOINT_VERSION,
        "signature": signature,
        "symbol": symbol,
        "controls": [asdict(item) for item in controls],
        "unmatched_targets": [
            asdict(item) for item in unmatched_targets
        ],
        "symbol_summary": asdict(symbol_summary),
    }
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temp.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temp.replace(path)
    return path


def load_symbol_match_checkpoint(
    *,
    checkpoint_dir: str | Path,
    signature: str,
    symbol: str,
) -> tuple[
    tuple[NoSupplyMatchedControl, ...],
    tuple[NoSupplyUnmatchedTarget, ...],
    NoSupplySymbolMatchSummary,
] | None:
    path = _checkpoint_path(Path(checkpoint_dir), symbol)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if int(payload.get("version", -1)) != MATCHED_CONTROL_CHECKPOINT_VERSION:
            return None
        if payload.get("signature") != signature:
            return None
        if payload.get("symbol") != symbol:
            return None
        controls = tuple(
            NoSupplyMatchedControl(**item)
            for item in payload["controls"]
        )
        unmatched = tuple(
            NoSupplyUnmatchedTarget(**item)
            for item in payload["unmatched_targets"]
        )
        summary = NoSupplySymbolMatchSummary(
            **payload["symbol_summary"]
        )
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None
    if summary.symbol != symbol:
        return None
    if len(controls) + len(unmatched) != summary.source_target_count:
        return None
    return controls, unmatched, summary


def _worker_task(
    task: tuple[
        str,
        str,
        tuple[dict[str, object], ...],
        tuple[dict[str, object], ...],
        int,
        int,
    ],
) -> _WorkerCompletion:
    (
        symbol,
        snapshot_dir,
        target_records,
        common_records,
        max_distance,
        min_target_index,
    ) = task
    try:
        daily = load_daily_audit_input(snapshot_dir, symbol)
        controls, unmatched, summary = match_symbol_controls(
            symbol=symbol,
            daily=daily,
            targets=pd.DataFrame(target_records),
            common_signature_sessions=pd.DataFrame(common_records),
            max_match_distance_sessions=max_distance,
            min_target_index=min_target_index,
        )
    except Exception as exc:
        return _WorkerCompletion(
            symbol=symbol,
            controls=None,
            unmatched_targets=None,
            symbol_summary=None,
            exception_type=type(exc).__name__,
            reason=str(exc),
        )
    return _WorkerCompletion(
        symbol=symbol,
        controls=controls,
        unmatched_targets=unmatched,
        symbol_summary=summary,
    )


def run_frozen_matched_control_discovery(
    symbols: Sequence[str] | Iterable[str],
    *,
    bundle: DailyAuditInputBundle,
    input_snapshot_dir: str | Path,
    targets: pd.DataFrame,
    common_signature_sessions: pd.DataFrame,
    max_match_distance_sessions: int,
    min_target_index: int = DEFAULT_DAILY_EVIDENCE_MIN_TARGET_INDEX,
    workers: int | None = None,
    checkpoint_dir: str | Path | None = None,
    checkpoint_signature: str | None = None,
    resume: bool = True,
    progress_writer: ProgressWriter | None = None,
) -> FrozenMatchedControlResult:
    requested = _normalize_symbols(symbols)
    snapshot_symbols = {
        item.symbol for item in bundle.fingerprints
    }
    missing = sorted(set(requested) - snapshot_symbols)
    if missing:
        raise ValueError(f"snapshot missing symbols: {missing}")
    if checkpoint_dir is not None and not checkpoint_signature:
        raise ValueError(
            "checkpoint_signature is required with checkpoint_dir"
        )

    worker_count = (
        default_matched_worker_count(len(requested))
        if workers is None
        else min(int(workers), len(requested))
    )
    if worker_count < 1:
        raise ValueError("workers must be positive")

    controls_by_symbol: dict[str, tuple[NoSupplyMatchedControl, ...]] = {}
    unmatched_by_symbol: dict[
        str, tuple[NoSupplyUnmatchedTarget, ...]
    ] = {}
    summaries: dict[str, NoSupplySymbolMatchSummary] = {}
    failures: dict[str, str] = {}
    reused: set[str] = set()
    written: set[str] = set()

    if checkpoint_dir is not None and resume:
        assert checkpoint_signature is not None
        for symbol in requested:
            loaded = load_symbol_match_checkpoint(
                checkpoint_dir=checkpoint_dir,
                signature=checkpoint_signature,
                symbol=symbol,
            )
            if loaded is None:
                continue
            controls, unmatched, summary = loaded
            controls_by_symbol[symbol] = controls
            unmatched_by_symbol[symbol] = unmatched
            summaries[symbol] = summary
            reused.add(symbol)

    pending = tuple(
        symbol for symbol in requested if symbol not in reused
    )
    if progress_writer is not None:
        progress_writer(
            "[daily-no-supply-l8] "
            f"{len(requested)} requested, {len(reused)} resumed, "
            f"{len(pending)} pending, {worker_count} workers"
        )

    tasks = []
    for symbol in pending:
        symbol_targets = targets.loc[
            targets["symbol"] == symbol
        ]
        symbol_common = common_signature_sessions.loc[
            common_signature_sessions["symbol"] == symbol
        ]
        tasks.append(
            (
                symbol,
                str(Path(input_snapshot_dir)),
                tuple(symbol_targets.to_dict("records")),
                tuple(symbol_common.to_dict("records")),
                int(max_match_distance_sessions),
                int(min_target_index),
            )
        )

    def capture(completion: _WorkerCompletion) -> None:
        if (
            completion.controls is None
            or completion.unmatched_targets is None
            or completion.symbol_summary is None
        ):
            failures[completion.symbol] = (
                f"{completion.exception_type}: {completion.reason}"
            )
            return
        controls_by_symbol[completion.symbol] = completion.controls
        unmatched_by_symbol[completion.symbol] = (
            completion.unmatched_targets
        )
        summaries[completion.symbol] = completion.symbol_summary
        if checkpoint_dir is not None:
            assert checkpoint_signature is not None
            write_symbol_match_checkpoint(
                checkpoint_dir=checkpoint_dir,
                signature=checkpoint_signature,
                symbol=completion.symbol,
                controls=completion.controls,
                unmatched_targets=completion.unmatched_targets,
                symbol_summary=completion.symbol_summary,
            )
        written.add(completion.symbol)

    def report(index: int, completion: _WorkerCompletion) -> None:
        if progress_writer is None:
            return
        if completion.symbol_summary is None:
            progress_writer(
                "[daily-no-supply-l8] "
                f"{len(reused) + index}/{len(requested)} failed "
                f"{completion.symbol}: {completion.reason}"
            )
            return
        row = completion.symbol_summary
        progress_writer(
            "[daily-no-supply-l8] "
            f"{len(reused) + index}/{len(requested)} completed "
            f"{completion.symbol}: {row.matched_target_count}/"
            f"{row.source_target_count} matched, "
            f"{row.candidate_environment_replay_count} trend replays"
        )

    if tasks and worker_count == 1:
        for index, task in enumerate(tasks, start=1):
            completion = _worker_task(task)
            capture(completion)
            report(index, completion)
    elif tasks:
        context = multiprocessing.get_context("spawn")
        actual_workers = min(worker_count, len(tasks))
        pool = context.Pool(processes=actual_workers)
        try:
            for index, completion in enumerate(
                pool.imap_unordered(_worker_task, tasks, chunksize=1),
                start=1,
            ):
                capture(completion)
                report(index, completion)
        except BaseException:
            pool.terminate()
            pool.join()
            raise
        else:
            pool.close()
            pool.join()

    controls = tuple(
        item
        for symbol in requested
        for item in controls_by_symbol.get(symbol, ())
    )
    unmatched = tuple(
        item
        for symbol in requested
        for item in unmatched_by_symbol.get(symbol, ())
    )
    symbol_rows = tuple(
        summaries[symbol]
        for symbol in requested
        if symbol in summaries
    )
    failure_rows = tuple(
        f"{symbol}: {failures[symbol]}"
        for symbol in requested
        if symbol in failures
    )
    return FrozenMatchedControlResult(
        controls=controls,
        unmatched_targets=unmatched,
        symbol_rows=symbol_rows,
        failures=failure_rows,
        worker_count=worker_count,
        checkpoint_reused_count=len(reused),
        checkpoint_written_count=len(written),
    )


__all__ = [
    "MATCHED_CONTROL_CHECKPOINT_VERSION",
    "FrozenMatchedControlResult",
    "build_matched_checkpoint_signature",
    "default_matched_worker_count",
    "load_symbol_match_checkpoint",
    "run_frozen_matched_control_discovery",
    "write_symbol_match_checkpoint",
]
