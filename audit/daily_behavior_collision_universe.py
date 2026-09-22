"""Frozen-snapshot universe audit for DailyBehavior evidence-identity collisions.

This module prepares point-in-time daily sequence study inputs from the existing
frozen daily OHLCV snapshot, production weekly authority, and the cached causal
K5 evidence producer. It remains analysis-only and does not change production
DailyBehavior, scanner, scoring, qualification, or actionability semantics.
"""

from __future__ import annotations

import json
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from audit.daily_behavior_sequence_runner import (
    DailyBehaviorSequenceHistoricalStudy,
    DailyBehaviorSequenceStudyBundlePaths,
    DailyBehaviorSequenceStudyInput,
    run_daily_behavior_sequence_historical_study,
    write_daily_behavior_sequence_study_bundle,
)
from audit.daily_input_reproducibility import (
    daily_audit_input_manifest_sha256,
    load_daily_audit_input,
    load_daily_audit_input_bundle,
)
from audit.genuine_daily_sequence_case import (
    derive_historical_production_weekly_setups,
)
from audit.offline_daily_evidence import (
    DEFAULT_DAILY_EVIDENCE_MIN_TARGET_INDEX,
    produce_offline_daily_evidence_cached,
)
from audit.weekly_direction_assignments import (
    produce_causal_weekly_direction_assignments,
)
from engine.columns import COL_CLOSE, COL_HIGH, COL_LOW


DAILY_BEHAVIOR_COLLISION_UNIVERSE_AUDIT_ID = (
    "daily-behavior-evidence-collision-universe-v1"
)


@dataclass(frozen=True, slots=True)
class DailyBehaviorCollisionSymbolSummary:
    symbol: str
    daily_bar_count: int
    daily_evidence_count: int
    weekly_candidate_count: int
    weekly_setup_count: int
    weekly_direction_assignment_count: int
    bullish_assignment_count: int
    bearish_assignment_count: int
    k3_input_fingerprint: str


@dataclass(frozen=True, slots=True)
class DailyBehaviorCollisionSymbolFailure:
    symbol: str
    error_type: str
    message: str


@dataclass(frozen=True, slots=True)
class PreparedDailyBehaviorCollisionUniverse:
    input_snapshot_dir: Path
    input_snapshot_manifest_sha256: str
    input_snapshot_basket: str
    input_snapshot_cutoff: str
    requested_symbols: tuple[str, ...]
    study_inputs: tuple[DailyBehaviorSequenceStudyInput, ...]
    symbol_summaries: tuple[DailyBehaviorCollisionSymbolSummary, ...]
    failures: tuple[DailyBehaviorCollisionSymbolFailure, ...]
    worker_count: int


@dataclass(frozen=True, slots=True)
class DailyBehaviorCollisionUniverseRun:
    prepared: PreparedDailyBehaviorCollisionUniverse
    study: DailyBehaviorSequenceHistoricalStudy | None
    study_paths: DailyBehaviorSequenceStudyBundlePaths | None
    summary_json: Path
    symbol_summary_csv: Path
    failures_csv: Path

    @property
    def succeeded_symbol_count(self) -> int:
        return len(self.prepared.symbol_summaries)

    @property
    def failed_symbol_count(self) -> int:
        return len(self.prepared.failures)

    @property
    def is_actionable(self) -> bool:
        return False


def _cutoff_now(cutoff: str) -> pd.Timestamp:
    timestamp = pd.Timestamp(cutoff)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("Asia/Kolkata")
    else:
        timestamp = timestamp.tz_convert("Asia/Kolkata")
    return timestamp.normalize() + pd.Timedelta(hours=16)


def _normalize_symbols(
    available: Iterable[str],
    requested: Iterable[str] | None,
) -> tuple[str, ...]:
    available_symbols = tuple(str(item).strip().upper() for item in available)
    if requested is None:
        return available_symbols

    selected = tuple(str(item).strip().upper() for item in requested)
    if not selected:
        raise ValueError("requested symbols cannot be empty")
    if len(set(selected)) != len(selected):
        raise ValueError("requested symbols must be unique")

    missing = sorted(set(selected) - set(available_symbols))
    if missing:
        raise ValueError(f"requested symbols are absent from snapshot: {missing}")
    return selected


def _prepare_symbol(
    input_snapshot_dir: str,
    symbol: str,
    cutoff: str,
    min_target_index: int,
) -> tuple[DailyBehaviorSequenceStudyInput, DailyBehaviorCollisionSymbolSummary]:
    daily = load_daily_audit_input(input_snapshot_dir, symbol)
    now = _cutoff_now(cutoff)

    weekly_archive = derive_historical_production_weekly_setups(
        symbol=symbol,
        daily=daily,
        now=now,
    )
    evidence_archive = produce_offline_daily_evidence_cached(
        symbol=symbol,
        daily=daily,
        now=now,
        min_target_index=min_target_index,
    )
    direction_archive = produce_causal_weekly_direction_assignments(
        symbol=symbol,
        daily=daily,
        setups=weekly_archive.setups,
        now=now,
    )

    if not pd.DatetimeIndex(evidence_archive.completed_daily.index).equals(
        pd.DatetimeIndex(direction_archive.completed_daily.index)
    ):
        raise ValueError("cached K5 / K6 completed-session mismatch")

    bars = evidence_archive.completed_daily.loc[
        :, [COL_CLOSE, COL_HIGH, COL_LOW]
    ].copy()
    study_input = DailyBehaviorSequenceStudyInput(
        symbol=symbol,
        bars=bars,
        weekly_directions=direction_archive.assignments,
        evidence=evidence_archive.evidence,
    )

    # Use the canonical runner fingerprint rather than inventing another identity.
    from audit.daily_behavior_sequence_runner import (
        fingerprint_daily_behavior_sequence_input,
    )

    fingerprint = fingerprint_daily_behavior_sequence_input(study_input)
    bullish = sum(
        item.direction.value == "bullish"
        for item in direction_archive.assignments
    )
    bearish = sum(
        item.direction.value == "bearish"
        for item in direction_archive.assignments
    )

    summary = DailyBehaviorCollisionSymbolSummary(
        symbol=symbol,
        daily_bar_count=len(bars),
        daily_evidence_count=len(evidence_archive.evidence),
        weekly_candidate_count=weekly_archive.candidate_count,
        weekly_setup_count=weekly_archive.setup_count,
        weekly_direction_assignment_count=len(direction_archive.assignments),
        bullish_assignment_count=bullish,
        bearish_assignment_count=bearish,
        k3_input_fingerprint=fingerprint.sha256,
    )
    return study_input, summary


def prepare_daily_behavior_collision_universe(
    *,
    input_snapshot_dir: str | Path,
    workers: int = 1,
    symbols: Iterable[str] | None = None,
    min_target_index: int = DEFAULT_DAILY_EVIDENCE_MIN_TARGET_INDEX,
) -> PreparedDailyBehaviorCollisionUniverse:
    if workers <= 0:
        raise ValueError("workers must be positive")
    if min_target_index < 0:
        raise ValueError("min_target_index cannot be negative")

    root = Path(input_snapshot_dir)
    bundle = load_daily_audit_input_bundle(root)
    requested_symbols = _normalize_symbols(
        (item.symbol for item in bundle.fingerprints),
        symbols,
    )

    prepared: dict[
        str,
        tuple[DailyBehaviorSequenceStudyInput, DailyBehaviorCollisionSymbolSummary],
    ] = {}
    failures: list[DailyBehaviorCollisionSymbolFailure] = []

    if workers == 1:
        for index, symbol in enumerate(requested_symbols, start=1):
            try:
                prepared[symbol] = _prepare_symbol(
                    str(root),
                    symbol,
                    bundle.cutoff,
                    min_target_index,
                )
                print(
                    f"[{index}/{len(requested_symbols)}] {symbol} OK",
                    file=sys.stderr,
                )
            except Exception as exc:  # pragma: no cover - exercised by real audit
                failures.append(
                    DailyBehaviorCollisionSymbolFailure(
                        symbol=symbol,
                        error_type=type(exc).__name__,
                        message=str(exc),
                    )
                )
                print(
                    f"[{index}/{len(requested_symbols)}] {symbol} FAILED: {exc}",
                    file=sys.stderr,
                )
    else:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(
                    _prepare_symbol,
                    str(root),
                    symbol,
                    bundle.cutoff,
                    min_target_index,
                ): symbol
                for symbol in requested_symbols
            }
            completed_count = 0
            for future in as_completed(futures):
                symbol = futures[future]
                completed_count += 1
                try:
                    prepared[symbol] = future.result()
                    print(
                        f"[{completed_count}/{len(requested_symbols)}] {symbol} OK",
                        file=sys.stderr,
                    )
                except Exception as exc:
                    failures.append(
                        DailyBehaviorCollisionSymbolFailure(
                            symbol=symbol,
                            error_type=type(exc).__name__,
                            message=str(exc),
                        )
                    )
                    print(
                        f"[{completed_count}/{len(requested_symbols)}] "
                        f"{symbol} FAILED: {exc}",
                        file=sys.stderr,
                    )

    ordered_symbols = tuple(
        symbol for symbol in requested_symbols if symbol in prepared
    )
    return PreparedDailyBehaviorCollisionUniverse(
        input_snapshot_dir=root,
        input_snapshot_manifest_sha256=daily_audit_input_manifest_sha256(root),
        input_snapshot_basket=bundle.basket_name,
        input_snapshot_cutoff=bundle.cutoff,
        requested_symbols=requested_symbols,
        study_inputs=tuple(prepared[symbol][0] for symbol in ordered_symbols),
        symbol_summaries=tuple(prepared[symbol][1] for symbol in ordered_symbols),
        failures=tuple(sorted(failures, key=lambda item: item.symbol)),
        worker_count=workers,
    )


def _read_collision_counts(
    paths: DailyBehaviorSequenceStudyBundlePaths,
) -> tuple[int, int]:
    payload = json.loads(paths.summary_json.read_text(encoding="utf-8"))
    return (
        int(payload.get("coarse_signature_collision_count", 0)),
        int(payload.get("collision_observation_count", 0)),
    )


def run_daily_behavior_collision_universe(
    *,
    input_snapshot_dir: str | Path,
    output_dir: str | Path,
    workers: int = 1,
    symbols: Iterable[str] | None = None,
    min_target_index: int = DEFAULT_DAILY_EVIDENCE_MIN_TARGET_INDEX,
    horizons_bars: Iterable[int] = (1, 3, 5, 10, 15),
    lookback_bars: int = 5,
) -> DailyBehaviorCollisionUniverseRun:
    prepared = prepare_daily_behavior_collision_universe(
        input_snapshot_dir=input_snapshot_dir,
        workers=workers,
        symbols=symbols,
        min_target_index=min_target_index,
    )

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    symbol_summary_csv = root / "daily_behavior_collision_symbol_summary.csv"
    failures_csv = root / "daily_behavior_collision_failures.csv"
    summary_json = root / "daily_behavior_collision_universe_summary.json"

    pd.DataFrame(
        [asdict(item) for item in prepared.symbol_summaries],
        columns=(
            "symbol",
            "daily_bar_count",
            "daily_evidence_count",
            "weekly_candidate_count",
            "weekly_setup_count",
            "weekly_direction_assignment_count",
            "bullish_assignment_count",
            "bearish_assignment_count",
            "k3_input_fingerprint",
        ),
    ).to_csv(symbol_summary_csv, index=False)

    pd.DataFrame(
        [asdict(item) for item in prepared.failures],
        columns=("symbol", "error_type", "message"),
    ).to_csv(failures_csv, index=False)

    study: DailyBehaviorSequenceHistoricalStudy | None = None
    study_paths: DailyBehaviorSequenceStudyBundlePaths | None = None
    collision_count = 0
    collision_observation_count = 0

    if not prepared.failures:
        study = run_daily_behavior_sequence_historical_study(
            prepared.study_inputs,
            horizons_bars=horizons_bars,
            lookback_bars=lookback_bars,
        )
        study_paths = write_daily_behavior_sequence_study_bundle(
            study,
            output_dir=root,
        )
        collision_count, collision_observation_count = _read_collision_counts(
            study_paths
        )

    payload = {
        "audit_id": DAILY_BEHAVIOR_COLLISION_UNIVERSE_AUDIT_ID,
        "input_snapshot_basket": prepared.input_snapshot_basket,
        "input_snapshot_cutoff": prepared.input_snapshot_cutoff,
        "input_snapshot_manifest_sha256": (
            prepared.input_snapshot_manifest_sha256
        ),
        "requested_symbol_count": len(prepared.requested_symbols),
        "succeeded_symbol_count": len(prepared.symbol_summaries),
        "failed_symbol_count": len(prepared.failures),
        "worker_count": prepared.worker_count,
        "min_target_index": min_target_index,
        "daily_bar_count": sum(
            item.daily_bar_count for item in prepared.symbol_summaries
        ),
        "daily_evidence_count": sum(
            item.daily_evidence_count for item in prepared.symbol_summaries
        ),
        "weekly_candidate_count": sum(
            item.weekly_candidate_count for item in prepared.symbol_summaries
        ),
        "weekly_setup_count": sum(
            item.weekly_setup_count for item in prepared.symbol_summaries
        ),
        "weekly_direction_assignment_count": sum(
            item.weekly_direction_assignment_count
            for item in prepared.symbol_summaries
        ),
        "bullish_assignment_count": sum(
            item.bullish_assignment_count for item in prepared.symbol_summaries
        ),
        "bearish_assignment_count": sum(
            item.bearish_assignment_count for item in prepared.symbol_summaries
        ),
        "record_count": None if study is None else study.record_count,
        "fresh_sequence_count": (
            None if study is None else study.fresh_sequence_count
        ),
        "outcome_observation_count": (
            None if study is None else study.outcome_observation_count
        ),
        "signature_summary_count": (
            None if study is None else len(study.summaries)
        ),
        "coarse_signature_collision_count": collision_count,
        "collision_observation_count": collision_observation_count,
        "failures": [asdict(item) for item in prepared.failures],
        "is_actionable": False,
    }
    summary_json.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    return DailyBehaviorCollisionUniverseRun(
        prepared=prepared,
        study=study,
        study_paths=study_paths,
        summary_json=summary_json,
        symbol_summary_csv=symbol_summary_csv,
        failures_csv=failures_csv,
    )


__all__ = [
    "DAILY_BEHAVIOR_COLLISION_UNIVERSE_AUDIT_ID",
    "DailyBehaviorCollisionSymbolFailure",
    "DailyBehaviorCollisionSymbolSummary",
    "DailyBehaviorCollisionUniverseRun",
    "PreparedDailyBehaviorCollisionUniverse",
    "prepare_daily_behavior_collision_universe",
    "run_daily_behavior_collision_universe",
]
