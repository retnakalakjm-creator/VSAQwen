"""Reproducible multi-symbol historical runner for daily behavior sequences.

The runner is analysis-only. It consumes prepared point-in-time inputs rather
than inferring weekly direction or daily evidence from prices.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import pandas as pd

from audit.daily_behavior_sequence_outcomes import (
    DailyBehaviorSequenceOutcomeObservation,
    DailyBehaviorSequenceOutcomeSummary,
    build_daily_behavior_sequence_outcomes,
    daily_behavior_sequence_signature,
    sequence_has_fresh_behavior,
    summarize_daily_behavior_sequence_outcomes,
)
from daily_behavior_sequence import DailyBehaviorSequence, evaluate_daily_behavior_sequence
from engine.columns import COL_CLOSE, COL_HIGH, COL_LOW
from models import Evidence
from weekly_setup import WeeklySetupDirection


DEFAULT_DAILY_SEQUENCE_STUDY_OUTPUT_DIR = Path(
    "reports/daily-behavior-sequences/latest"
)


@dataclass(frozen=True, slots=True)
class DailyBehaviorSequenceDirectionAssignment:
    """Weekly direction visible to one exact completed daily bar."""

    bar_index: int
    direction: WeeklySetupDirection


@dataclass(frozen=True, slots=True)
class DailyBehaviorSequenceStudyInput:
    """Frozen prepared input boundary for one symbol-level sequence study."""

    symbol: str
    bars: pd.DataFrame
    weekly_directions: tuple[DailyBehaviorSequenceDirectionAssignment, ...]
    evidence: tuple[Evidence, ...]


@dataclass(frozen=True, slots=True)
class DailyBehaviorSequenceInputFingerprint:
    symbol: str
    bar_count: int
    direction_assignment_count: int
    evidence_count: int
    first_index: str | None
    last_index: str | None
    sha256: str


@dataclass(frozen=True, slots=True)
class DailyBehaviorSequenceStudyRecord:
    symbol: str
    bar_index: int
    weekly_direction: WeeklySetupDirection
    sequence: DailyBehaviorSequence
    outcomes: tuple[DailyBehaviorSequenceOutcomeObservation, ...]

    @property
    def fresh_behavior(self) -> bool:
        return sequence_has_fresh_behavior(self.sequence)

    @property
    def is_actionable(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class DailyBehaviorSequenceSymbolStudy:
    symbol: str
    input_fingerprint: DailyBehaviorSequenceInputFingerprint
    records: tuple[DailyBehaviorSequenceStudyRecord, ...]

    @property
    def fresh_sequence_count(self) -> int:
        return sum(1 for item in self.records if item.fresh_behavior)

    @property
    def outcome_observation_count(self) -> int:
        return sum(len(item.outcomes) for item in self.records)

    @property
    def is_actionable(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class DailyBehaviorSequenceSymbolFailure:
    symbol: str
    stage: str
    error_type: str
    message: str


@dataclass(frozen=True, slots=True)
class DailyBehaviorSequenceHistoricalStudy:
    requested_symbols: tuple[str, ...]
    successful_symbols: tuple[str, ...]
    horizons_bars: tuple[int, ...]
    lookback_bars: int
    symbol_results: tuple[DailyBehaviorSequenceSymbolStudy, ...]
    failures: tuple[DailyBehaviorSequenceSymbolFailure, ...]
    summaries: tuple[DailyBehaviorSequenceOutcomeSummary, ...]
    external_baseline_used: bool
    continue_on_symbol_error: bool

    @property
    def failed_symbols(self) -> tuple[str, ...]:
        return tuple(item.symbol for item in self.failures)

    @property
    def input_fingerprints(self) -> tuple[DailyBehaviorSequenceInputFingerprint, ...]:
        return tuple(item.input_fingerprint for item in self.symbol_results)

    @property
    def record_count(self) -> int:
        return sum(len(item.records) for item in self.symbol_results)

    @property
    def fresh_sequence_count(self) -> int:
        return sum(item.fresh_sequence_count for item in self.symbol_results)

    @property
    def outcome_observation_count(self) -> int:
        return sum(item.outcome_observation_count for item in self.symbol_results)

    @property
    def is_actionable(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class DailyBehaviorSequenceStudyBundlePaths:
    summary_json: Path
    input_fingerprints_json: Path
    input_fingerprints_csv: Path
    failures_csv: Path
    sequence_records_csv: Path
    outcomes_csv: Path
    summaries_csv: Path

    def as_dict(self) -> dict[str, str]:
        return {key: str(value) for key, value in asdict(self).items()}


def _normalize_symbol(symbol: str) -> str:
    normalized = str(symbol).strip().upper()
    if not normalized:
        raise ValueError("symbol cannot be blank")
    return normalized


def _normalize_horizons(horizons: Iterable[int]) -> tuple[int, ...]:
    normalized = tuple(sorted(set(int(item) for item in horizons)))
    if not normalized or any(item <= 0 for item in normalized):
        raise ValueError("horizons must contain positive bar counts")
    return normalized


def _canonical_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return _canonical_value(asdict(value))
    if isinstance(value, dict):
        return {
            str(key): _canonical_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    if hasattr(value, "item") and callable(value.item):
        try:
            return _canonical_value(value.item())
        except (TypeError, ValueError):
            pass
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("study inputs cannot contain non-finite numeric values")
        return value
    return value


def _validate_bars(bars: pd.DataFrame) -> None:
    if bars.empty:
        raise ValueError("bars cannot be empty")
    missing = [
        column
        for column in (COL_CLOSE, COL_HIGH, COL_LOW)
        if column not in bars.columns
    ]
    if missing:
        raise ValueError(f"bars missing required price columns: {missing}")

    for column in (COL_CLOSE, COL_HIGH, COL_LOW):
        for value in bars[column]:
            numeric = float(value)
            if not math.isfinite(numeric):
                raise ValueError(f"{column} contains non-finite values")


def _normalized_assignments(
    assignments: Sequence[DailyBehaviorSequenceDirectionAssignment],
    *,
    bar_count: int,
) -> tuple[DailyBehaviorSequenceDirectionAssignment, ...]:
    ordered = tuple(sorted(assignments, key=lambda item: item.bar_index))
    seen: set[int] = set()
    for item in ordered:
        if item.bar_index < 0 or item.bar_index >= bar_count:
            raise IndexError("weekly direction bar_index is outside bars")
        if item.bar_index in seen:
            raise ValueError(
                f"duplicate weekly direction assignment for bar {item.bar_index}"
            )
        seen.add(item.bar_index)
    return ordered


def _normalized_evidence(
    evidence: Sequence[Evidence],
    *,
    bar_count: int,
) -> tuple[Evidence, ...]:
    for item in evidence:
        if item.bar_index < 0 or item.bar_index >= bar_count:
            raise IndexError("evidence bar_index is outside bars")

    return tuple(
        sorted(
            evidence,
            key=lambda item: (
                item.bar_index,
                str(item.code),
                int(item.direction),
                json.dumps(
                    _canonical_value(item),
                    sort_keys=True,
                    separators=(",", ":"),
                    default=str,
                ),
            ),
        )
    )


def fingerprint_daily_behavior_sequence_input(
    study_input: DailyBehaviorSequenceStudyInput,
) -> DailyBehaviorSequenceInputFingerprint:
    """Fingerprint only the exact prepared inputs that K3 consumes."""

    symbol = _normalize_symbol(study_input.symbol)
    _validate_bars(study_input.bars)
    assignments = _normalized_assignments(
        study_input.weekly_directions,
        bar_count=len(study_input.bars),
    )
    evidence = _normalized_evidence(
        study_input.evidence,
        bar_count=len(study_input.bars),
    )

    payload = {
        "symbol": symbol,
        "bars": [
            {
                "index": str(index),
                COL_CLOSE: float(row[COL_CLOSE]),
                COL_HIGH: float(row[COL_HIGH]),
                COL_LOW: float(row[COL_LOW]),
            }
            for index, row in study_input.bars.iterrows()
        ],
        "weekly_directions": [
            {
                "bar_index": item.bar_index,
                "direction": item.direction.value,
            }
            for item in assignments
        ],
        "evidence": [_canonical_value(item) for item in evidence],
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()

    return DailyBehaviorSequenceInputFingerprint(
        symbol=symbol,
        bar_count=len(study_input.bars),
        direction_assignment_count=len(assignments),
        evidence_count=len(evidence),
        first_index=None if study_input.bars.empty else str(study_input.bars.index[0]),
        last_index=None if study_input.bars.empty else str(study_input.bars.index[-1]),
        sha256=f"sha256:{digest}",
    )


def run_daily_behavior_sequence_symbol_study(
    study_input: DailyBehaviorSequenceStudyInput,
    *,
    horizons_bars: Iterable[int] = (1, 3, 5, 10, 15),
    lookback_bars: int = 5,
) -> DailyBehaviorSequenceSymbolStudy:
    """Replay K1/K2 across prepared point-in-time inputs for one symbol."""

    if lookback_bars <= 0:
        raise ValueError("lookback_bars must be positive")

    symbol = _normalize_symbol(study_input.symbol)
    bars = study_input.bars
    _validate_bars(bars)
    assignments = _normalized_assignments(
        study_input.weekly_directions,
        bar_count=len(bars),
    )
    evidence = _normalized_evidence(
        study_input.evidence,
        bar_count=len(bars),
    )
    horizons = _normalize_horizons(horizons_bars)
    fingerprint = fingerprint_daily_behavior_sequence_input(study_input)

    records: list[DailyBehaviorSequenceStudyRecord] = []
    for assignment in assignments:
        sequence = evaluate_daily_behavior_sequence(
            weekly_direction=assignment.direction,
            daily_bar_index=assignment.bar_index,
            evidence=evidence,
            lookback_bars=lookback_bars,
        )
        outcomes = build_daily_behavior_sequence_outcomes(
            bars,
            sequence=sequence,
            horizons=horizons,
        )
        records.append(
            DailyBehaviorSequenceStudyRecord(
                symbol=symbol,
                bar_index=assignment.bar_index,
                weekly_direction=assignment.direction,
                sequence=sequence,
                outcomes=outcomes,
            )
        )

    return DailyBehaviorSequenceSymbolStudy(
        symbol=symbol,
        input_fingerprint=fingerprint,
        records=tuple(records),
    )


def _fingerprints_by_symbol(
    fingerprints: Sequence[DailyBehaviorSequenceInputFingerprint] | None,
) -> dict[str, DailyBehaviorSequenceInputFingerprint]:
    items = tuple(fingerprints or ())
    result = {_normalize_symbol(item.symbol): item for item in items}
    if len(result) != len(items):
        raise ValueError("expected fingerprints require unique symbols")
    return result


def run_daily_behavior_sequence_historical_study(
    inputs: Sequence[DailyBehaviorSequenceStudyInput]
    | Iterable[DailyBehaviorSequenceStudyInput],
    *,
    horizons_bars: Iterable[int] = (1, 3, 5, 10, 15),
    lookback_bars: int = 5,
    expected_fingerprints: Sequence[DailyBehaviorSequenceInputFingerprint]
    | None = None,
    continue_on_symbol_error: bool = False,
) -> DailyBehaviorSequenceHistoricalStudy:
    """Run a reproducible K1/K2 study across an explicit prepared universe."""

    prepared_inputs = tuple(inputs)
    if not prepared_inputs:
        raise ValueError("inputs must contain at least one symbol")

    requested_symbols = tuple(_normalize_symbol(item.symbol) for item in prepared_inputs)
    if len(set(requested_symbols)) != len(requested_symbols):
        raise ValueError("inputs require unique symbols")

    horizons = _normalize_horizons(horizons_bars)
    if lookback_bars <= 0:
        raise ValueError("lookback_bars must be positive")

    expected_by_symbol = _fingerprints_by_symbol(expected_fingerprints)
    results: list[DailyBehaviorSequenceSymbolStudy] = []
    failures: list[DailyBehaviorSequenceSymbolFailure] = []

    for study_input in prepared_inputs:
        symbol = _normalize_symbol(study_input.symbol)
        stage = "study"
        try:
            result = run_daily_behavior_sequence_symbol_study(
                study_input,
                horizons_bars=horizons,
                lookback_bars=lookback_bars,
            )
            if expected_fingerprints is not None:
                stage = "fingerprint_gate"
                expected = expected_by_symbol.get(symbol)
                if expected is None:
                    raise ValueError(
                        f"{symbol} is missing from the expected fingerprint manifest"
                    )
                if result.input_fingerprint.sha256 != expected.sha256:
                    raise ValueError(
                        f"{symbol} input fingerprint mismatch: "
                        f"expected {expected.sha256}, "
                        f"observed {result.input_fingerprint.sha256}"
                    )
            results.append(result)
        except Exception as exc:
            if not continue_on_symbol_error:
                raise
            failures.append(
                DailyBehaviorSequenceSymbolFailure(
                    symbol=symbol,
                    stage=stage,
                    error_type=type(exc).__name__,
                    message=str(exc),
                )
            )

    if not results:
        raise ValueError("no symbols survived daily sequence historical study")

    observations = tuple(
        outcome
        for result in results
        for record in result.records
        for outcome in record.outcomes
    )
    summaries = summarize_daily_behavior_sequence_outcomes(observations)

    return DailyBehaviorSequenceHistoricalStudy(
        requested_symbols=requested_symbols,
        successful_symbols=tuple(item.symbol for item in results),
        horizons_bars=horizons,
        lookback_bars=lookback_bars,
        symbol_results=tuple(results),
        failures=tuple(failures),
        summaries=summaries,
        external_baseline_used=expected_fingerprints is not None,
        continue_on_symbol_error=continue_on_symbol_error,
    )


def _signature_text(sequence: DailyBehaviorSequence) -> str:
    signature = daily_behavior_sequence_signature(sequence)
    return ";".join(
        f"{step.offset_from_signal}:"
        + ",".join(dimension.value for dimension in step.dimensions)
        for step in signature
    )


def _summary_signature_text(
    summary: DailyBehaviorSequenceOutcomeSummary,
) -> str:
    return ";".join(
        f"{step.offset_from_signal}:"
        + ",".join(dimension.value for dimension in step.dimensions)
        for step in summary.signature
    )


def write_daily_behavior_sequence_study_bundle(
    study: DailyBehaviorSequenceHistoricalStudy,
    output_dir: str | Path = DEFAULT_DAILY_SEQUENCE_STUDY_OUTPUT_DIR,
) -> DailyBehaviorSequenceStudyBundlePaths:
    """Write transparent JSON/CSV artifacts for manual M11 review."""

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    paths = DailyBehaviorSequenceStudyBundlePaths(
        summary_json=root / "daily_sequence_study_summary.json",
        input_fingerprints_json=root / "daily_sequence_input_fingerprints.json",
        input_fingerprints_csv=root / "daily_sequence_input_fingerprints.csv",
        failures_csv=root / "daily_sequence_symbol_failures.csv",
        sequence_records_csv=root / "daily_sequence_records.csv",
        outcomes_csv=root / "daily_sequence_outcomes.csv",
        summaries_csv=root / "daily_sequence_signature_summaries.csv",
    )

    summary_payload = {
        "requested_symbols": list(study.requested_symbols),
        "requested_symbol_count": len(study.requested_symbols),
        "successful_symbols": list(study.successful_symbols),
        "successful_symbol_count": len(study.successful_symbols),
        "failed_symbols": list(study.failed_symbols),
        "failed_symbol_count": len(study.failures),
        "horizons_bars": list(study.horizons_bars),
        "lookback_bars": study.lookback_bars,
        "record_count": study.record_count,
        "fresh_sequence_count": study.fresh_sequence_count,
        "outcome_observation_count": study.outcome_observation_count,
        "signature_summary_count": len(study.summaries),
        "external_baseline_used": study.external_baseline_used,
        "continue_on_symbol_error": study.continue_on_symbol_error,
        "is_actionable": False,
    }
    paths.summary_json.write_text(
        json.dumps(summary_payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    fingerprint_rows = [asdict(item) for item in study.input_fingerprints]
    paths.input_fingerprints_json.write_text(
        json.dumps(
            {
                "symbols": list(study.successful_symbols),
                "is_actionable": False,
                "fingerprints": fingerprint_rows,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    pd.DataFrame(fingerprint_rows).to_csv(paths.input_fingerprints_csv, index=False)

    pd.DataFrame(
        [asdict(item) for item in study.failures],
        columns=("symbol", "stage", "error_type", "message"),
    ).to_csv(paths.failures_csv, index=False)

    sequence_rows: list[dict[str, object]] = []
    outcome_rows: list[dict[str, object]] = []
    for symbol_result in study.symbol_results:
        for record in symbol_result.records:
            sequence_rows.append(
                {
                    "symbol": record.symbol,
                    "bar_index": record.bar_index,
                    "weekly_direction": record.weekly_direction.value,
                    "fresh_behavior": record.fresh_behavior,
                    "step_count": len(record.sequence.steps),
                    "signature": _signature_text(record.sequence),
                    "outcome_observation_count": len(record.outcomes),
                    "is_actionable": False,
                }
            )
            for observation in record.outcomes:
                outcome = observation.outcome
                outcome_rows.append(
                    {
                        "symbol": record.symbol,
                        "signal_bar_index": observation.signal_bar_index,
                        "weekly_direction": observation.weekly_direction.value,
                        "signature": _signature_text(record.sequence),
                        "horizon_bars": observation.horizon_bars,
                        "outcome_available": observation.outcome_available,
                        "complete": observation.complete,
                        "execution_bar_index": (
                            None if outcome is None else outcome.execution_bar_index
                        ),
                        "exit_bar_index": (
                            None if outcome is None else outcome.exit_bar_index
                        ),
                        "raw_return": None if outcome is None else outcome.raw_return,
                        "favorable_return": (
                            None if outcome is None else outcome.favorable_return
                        ),
                        "mfe": None if outcome is None else outcome.mfe,
                        "mae": None if outcome is None else outcome.mae,
                        "is_actionable": False,
                    }
                )

    pd.DataFrame(
        sequence_rows,
        columns=(
            "symbol",
            "bar_index",
            "weekly_direction",
            "fresh_behavior",
            "step_count",
            "signature",
            "outcome_observation_count",
            "is_actionable",
        ),
    ).to_csv(paths.sequence_records_csv, index=False)
    pd.DataFrame(
        outcome_rows,
        columns=(
            "symbol",
            "signal_bar_index",
            "weekly_direction",
            "signature",
            "horizon_bars",
            "outcome_available",
            "complete",
            "execution_bar_index",
            "exit_bar_index",
            "raw_return",
            "favorable_return",
            "mfe",
            "mae",
            "is_actionable",
        ),
    ).to_csv(paths.outcomes_csv, index=False)

    summary_rows = [
        {
            "weekly_direction": item.weekly_direction.value,
            "signature": _summary_signature_text(item),
            "horizon_bars": item.horizon_bars,
            "observation_count": item.observation_count,
            "outcome_available_count": item.outcome_available_count,
            "complete_outcome_count": item.complete_outcome_count,
            "mean_favorable_return": item.mean_favorable_return,
            "median_favorable_return": item.median_favorable_return,
            "mean_mfe": item.mean_mfe,
            "mean_mae": item.mean_mae,
            "is_actionable": False,
        }
        for item in study.summaries
    ]
    pd.DataFrame(
        summary_rows,
        columns=(
            "weekly_direction",
            "signature",
            "horizon_bars",
            "observation_count",
            "outcome_available_count",
            "complete_outcome_count",
            "mean_favorable_return",
            "median_favorable_return",
            "mean_mfe",
            "mean_mae",
            "is_actionable",
        ),
    ).to_csv(paths.summaries_csv, index=False)
    return paths


__all__ = [
    "DEFAULT_DAILY_SEQUENCE_STUDY_OUTPUT_DIR",
    "DailyBehaviorSequenceDirectionAssignment",
    "DailyBehaviorSequenceHistoricalStudy",
    "DailyBehaviorSequenceInputFingerprint",
    "DailyBehaviorSequenceStudyBundlePaths",
    "DailyBehaviorSequenceStudyInput",
    "DailyBehaviorSequenceStudyRecord",
    "DailyBehaviorSequenceSymbolFailure",
    "DailyBehaviorSequenceSymbolStudy",
    "fingerprint_daily_behavior_sequence_input",
    "run_daily_behavior_sequence_historical_study",
    "run_daily_behavior_sequence_symbol_study",
    "write_daily_behavior_sequence_study_bundle",
]
