from __future__ import annotations

from collections.abc import Callable, MutableSequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from historical_scanner import HistoricalScannerRunner
from production_scanner import (
    DEFAULT_TIMEFRAME,
    scan_actionable_production,
    scan_latest_candidate_production,
)
from scanner import ScannerCandidate, ScannerEngine
from scanner_state import ScannerStateStore

CandidateSignature = Callable[[ScannerCandidate | None], Any]
CandidateListSignature = Callable[[list[ScannerCandidate]], Any]


@dataclass(frozen=True, slots=True)
class ProductionTransitionShadowComparison:
    """Non-production comparison result for production-vs-transition parity.

    The comparison runs the current production path and the transition runner side
    by side in tests or diagnostics. It does not choose or replace production
    output; it only reports whether the current production result matches an
    independently computed transition-runner result.
    """

    matched: bool
    production_signature: Any
    transition_signature: Any
    fallback_diagnostics: tuple[str, ...]
    production_candidate: ScannerCandidate | None = None
    transition_candidate: ScannerCandidate | None = None


@dataclass(frozen=True, slots=True)
class ProductionTransitionActionableComparison:
    """Shadow comparison result for latest-actionable production output."""

    matched: bool
    production_signature: Any
    transition_signature: Any
    fallback_diagnostics: tuple[str, ...]
    production_candidates: tuple[ScannerCandidate, ...]
    transition_candidates: tuple[ScannerCandidate, ...]


def _value(item: object) -> object:
    return getattr(item, "value", item)


def _rounded(item: float | None) -> float | None:
    if item is None:
        return None
    return round(float(item), 10)


def _evidence_signature(items) -> tuple[tuple[object, int, str], ...]:
    return tuple(
        (
            _value(item.code),
            int(item.bar_index),
            str(item.week_beginning),
        )
        for item in items
    )


def default_candidate_signature(candidate: ScannerCandidate | None) -> tuple[object, ...] | None:
    """Return a stable semantic signature for shadow parity checks."""

    if candidate is None:
        return None
    qualification = candidate.qualification_result
    scores = candidate.professional.scores
    return (
        _value(candidate.qualification),
        bool(candidate.actionable),
        candidate.reason,
        _rounded(candidate.base_score),
        _rounded(candidate.ranking_score),
        _rounded(candidate.net_strength),
        _rounded(candidate.net_pressure),
        _rounded(candidate.confidence),
        _value(qualification.qualification),
        bool(qualification.is_actionable_evidence),
        qualification.reason,
        tuple(_value(code) for code in qualification.evidence_codes),
        tuple(qualification.evidence_bar_indices),
        _rounded(scores.trend),
        _rounded(scores.supply),
        _rounded(scores.demand),
        _rounded(scores.effort),
        _rounded(scores.strength),
        _rounded(scores.weakness),
        _rounded(scores.confidence),
        _evidence_signature(candidate.target_bar_evidence),
        _evidence_signature(candidate.qualifying_evidence),
        _evidence_signature(candidate.scoring_evidence),
        candidate.scoring_bar_index,
        candidate.scoring_evidence_age,
        candidate.used_fallback_evidence,
        candidate.bar_index,
        candidate.week,
        candidate.signal_bar_index,
        candidate.signal_week,
        candidate.execution_bar_index,
        candidate.execution_week,
        candidate.execution_available,
        candidate.execution_pending,
        candidate.signal_bar_anomaly,
        candidate.signal_bar_anomaly_reason,
        candidate.effort_result_evidence_codes,
        candidate.absorption_evidence_codes,
        candidate.high_volume_reversal_evidence_codes,
    )


def default_candidate_list_signature(candidates: list[ScannerCandidate]) -> tuple[tuple[object, ...] | None, ...]:
    return tuple(default_candidate_signature(candidate) for candidate in candidates)


def compare_latest_candidate_with_transition(
    metrics: pd.DataFrame,
    *,
    symbol: str,
    timeframe: str = DEFAULT_TIMEFRAME,
    state_store: ScannerStateStore | None = None,
    state_root: str | Path = "state",
    allow_full_replay_fallback: bool = True,
    fallback_diagnostics: MutableSequence[str] | None = None,
    transition_runner: HistoricalScannerRunner | None = None,
    signature: CandidateSignature = default_candidate_signature,
) -> ProductionTransitionShadowComparison:
    """Compare current production latest-candidate output with transition output.

    This is an explicit shadow helper for tests and diagnostics. The production
    candidate is still produced by ``scan_latest_candidate_production``. The
    transition result is computed independently and never replaces production
    output in this function.
    """

    diagnostics: list[str] = []
    production = scan_latest_candidate_production(
        metrics,
        symbol=symbol,
        timeframe=timeframe,
        state_store=state_store,
        state_root=state_root,
        allow_full_replay_fallback=allow_full_replay_fallback,
        fallback_diagnostics=diagnostics,
    )
    if fallback_diagnostics is not None:
        fallback_diagnostics.extend(diagnostics)

    transition: ScannerCandidate | None
    if len(metrics) <= ScannerEngine.MIN_REPLAY_BARS:
        transition = None
    else:
        runner = transition_runner or HistoricalScannerRunner()
        transition = runner.scan_to_index(metrics, len(metrics) - 1)

    production_signature = signature(production)
    transition_signature = signature(transition)
    return ProductionTransitionShadowComparison(
        matched=production_signature == transition_signature,
        production_signature=production_signature,
        transition_signature=transition_signature,
        fallback_diagnostics=tuple(diagnostics),
        production_candidate=production,
        transition_candidate=transition,
    )


def compare_actionable_with_transition(
    metrics: pd.DataFrame,
    *,
    symbol: str,
    timeframe: str = DEFAULT_TIMEFRAME,
    state_store: ScannerStateStore | None = None,
    state_root: str | Path = "state",
    allow_full_replay_fallback: bool = True,
    fallback_diagnostics: MutableSequence[str] | None = None,
    transition_runner: HistoricalScannerRunner | None = None,
    signature: CandidateListSignature = default_candidate_list_signature,
) -> ProductionTransitionActionableComparison:
    """Compare production latest-actionable output with transition output."""

    diagnostics: list[str] = []
    production = scan_actionable_production(
        metrics,
        symbol=symbol,
        timeframe=timeframe,
        state_store=state_store,
        state_root=state_root,
        allow_full_replay_fallback=allow_full_replay_fallback,
        fallback_diagnostics=diagnostics,
    )
    if fallback_diagnostics is not None:
        fallback_diagnostics.extend(diagnostics)

    runner = transition_runner or HistoricalScannerRunner()
    transition = runner.scan_actionable(metrics)
    production_signature = signature(production)
    transition_signature = signature(transition)
    return ProductionTransitionActionableComparison(
        matched=production_signature == transition_signature,
        production_signature=production_signature,
        transition_signature=transition_signature,
        fallback_diagnostics=tuple(diagnostics),
        production_candidates=tuple(production),
        transition_candidates=tuple(transition),
    )


__all__ = [
    "ProductionTransitionActionableComparison",
    "ProductionTransitionShadowComparison",
    "compare_actionable_with_transition",
    "compare_latest_candidate_with_transition",
    "default_candidate_list_signature",
    "default_candidate_signature",
]
