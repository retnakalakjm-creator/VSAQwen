from __future__ import annotations

from dataclasses import dataclass
from math import isclose

import pandas as pd

from scanner import ScannerCandidate, ScannerEngine


@dataclass(frozen=True, slots=True)
class FullScannerEquivalenceResult:
    target_index: int
    equivalent: bool
    scan_to_index: ScannerCandidate
    scan_actionable: ScannerCandidate | None


def _float_equal(left: float, right: float) -> bool:
    return isclose(left, right, rel_tol=0.0, abs_tol=1e-12)


def _evidence_identity(evidence) -> tuple:
    return tuple(
        (
            int(item.bar_index),
            item.code,
            item.category,
            item.direction,
            float(item.weight),
            str(item.observation),
        )
        for item in evidence
    )


def candidate_signature(candidate: ScannerCandidate | None) -> tuple | None:
    if candidate is None:
        return None

    scores = candidate.professional.scores
    return (
        candidate.bar_index,
        candidate.week,
        candidate.qualification,
        candidate.actionable,
        candidate.reason,
        candidate.scoring_bar_index,
        candidate.scoring_evidence_age,
        candidate.used_fallback_evidence,
        tuple(str(code) for code in candidate.target_bar_evidence_codes),
        tuple(str(code) for code in candidate.campaign_evidence_codes),
        tuple(str(code) for code in candidate.qualifying_evidence_codes),
        tuple(str(code) for code in candidate.scoring_evidence_codes),
        _evidence_identity(candidate.target_bar_evidence),
        _evidence_identity(candidate.qualifying_evidence),
        _evidence_identity(candidate.scoring_evidence),
        float(scores.trend),
        float(scores.supply),
        float(scores.demand),
        float(scores.effort),
        float(scores.strength),
        float(scores.weakness),
        float(scores.confidence),
        float(scores.net_pressure),
        float(scores.net_strength),
    )


def compare_candidates(
    left: ScannerCandidate | None,
    right: ScannerCandidate | None,
) -> bool:
    if left is None:
        return right is None

    # scan_actionable() intentionally omits non-actionable candidates. In that
    # case, equivalence means the latest production path also emits no
    # actionable candidate.
    if not left.actionable:
        return right is None

    if right is None or not right.actionable:
        return False

    if candidate_signature(left)[:15] != candidate_signature(right)[:15]:
        return False

    left_scores = left.professional.scores
    right_scores = right.professional.scores
    return all(
        _float_equal(a, b)
        for a, b in (
            (left_scores.trend, right_scores.trend),
            (left_scores.supply, right_scores.supply),
            (left_scores.demand, right_scores.demand),
            (left_scores.effort, right_scores.effort),
            (left_scores.strength, right_scores.strength),
            (left_scores.weakness, right_scores.weakness),
            (left_scores.confidence, right_scores.confidence),
            (left_scores.net_pressure, right_scores.net_pressure),
            (left_scores.net_strength, right_scores.net_strength),
        )
    )


def run_production_path_equivalence(
    metrics: pd.DataFrame,
    *,
    target_index: int,
) -> FullScannerEquivalenceResult:
    """Compare the two existing production scanner paths at one historical cutoff.

    This is a baseline correctness check. It is deliberately not presented as
    incremental equivalence: ScannerEngine has no full-pipeline state-resume API
    yet. The test ensures the historical replay and latest-bar production paths
    produce the same production outcome from the same cutoff dataset.
    """
    if target_index < ScannerEngine.MIN_REPLAY_BARS:
        raise ValueError(
            f"target_index must be >= {ScannerEngine.MIN_REPLAY_BARS}"
        )
    if target_index >= len(metrics):
        raise IndexError("target_index is outside metrics")

    cutoff_metrics = metrics.iloc[: target_index + 1].copy()
    historical_candidate = ScannerEngine().scan_to_index(
        cutoff_metrics,
        target_index,
    )
    latest = ScannerEngine().scan_actionable(cutoff_metrics)
    latest_candidate = latest[0] if latest else None

    return FullScannerEquivalenceResult(
        target_index=target_index,
        equivalent=compare_candidates(
            historical_candidate,
            latest_candidate,
        ),
        scan_to_index=historical_candidate,
        scan_actionable=latest_candidate,
    )
