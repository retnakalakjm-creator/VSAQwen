from __future__ import annotations

from dataclasses import dataclass
from math import isclose

import pandas as pd

from incremental_scanner import IncrementalScannerEngine
from scanner import ScannerCandidate, ScannerEngine
from tests.full_scanner_equivalence_harness import candidate_signature


@dataclass(frozen=True, slots=True)
class IncrementalEquivalenceResult:
    target_index: int
    state_schema_version: int
    equivalent: bool
    full: ScannerCandidate
    incremental: ScannerCandidate


def _float_equal(left: float, right: float) -> bool:
    return isclose(left, right, rel_tol=0.0, abs_tol=1e-12)


def _production_outcome_equal(full: ScannerCandidate, incremental: ScannerCandidate) -> bool:
    if full.actionable != incremental.actionable:
        return False
    if full.qualification != incremental.qualification:
        return False
    if full.reason != incremental.reason:
        return False
    if full.scoring_bar_index != incremental.scoring_bar_index:
        return False
    if full.scoring_evidence_age != incremental.scoring_evidence_age:
        return False
    if full.used_fallback_evidence != incremental.used_fallback_evidence:
        return False

    full_scores = full.professional.scores
    incremental_scores = incremental.professional.scores
    if not all(
        _float_equal(left, right)
        for left, right in (
            (full_scores.trend, incremental_scores.trend),
            (full_scores.supply, incremental_scores.supply),
            (full_scores.demand, incremental_scores.demand),
            (full_scores.effort, incremental_scores.effort),
            (full_scores.strength, incremental_scores.strength),
            (full_scores.weakness, incremental_scores.weakness),
            (full_scores.confidence, incremental_scores.confidence),
            (full_scores.net_pressure, incremental_scores.net_pressure),
            (full_scores.net_strength, incremental_scores.net_strength),
        )
    ):
        return False

    if not full.actionable:
        return True

    return candidate_signature(full)[:15] == candidate_signature(incremental)[:15]


def run_incremental_equivalence(
    metrics: pd.DataFrame,
    *,
    target_index: int,
    symbol: str,
    timeframe: str = "weekly",
) -> IncrementalEquivalenceResult:
    if target_index < ScannerEngine.MIN_REPLAY_BARS:
        raise ValueError(
            f"target_index must be >= {ScannerEngine.MIN_REPLAY_BARS}"
        )
    if target_index >= len(metrics):
        raise IndexError("target_index is outside metrics")

    state_engine = IncrementalScannerEngine()
    state = state_engine.snapshot(
        metrics,
        target_index=target_index,
        symbol=symbol,
        timeframe=timeframe,
    )
    full = ScannerEngine().scan_to_index(metrics, len(metrics) - 1)
    incremental = state_engine.resume_latest(metrics, state)

    return IncrementalEquivalenceResult(
        target_index=target_index,
        state_schema_version=state.schema_version,
        equivalent=_production_outcome_equal(full, incremental),
        full=full,
        incremental=incremental,
    )
