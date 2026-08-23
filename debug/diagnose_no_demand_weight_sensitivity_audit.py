"""Optimized NO_DEMAND weight sensitivity audit.

Qualification and actionability are weight-independent and are validated by
separate NO_DEMAND audits. This script isolates the professional scoring and
ranking layer, so it replays only emitted NO_DEMAND target bars and varies the
live SUPPLY_EVIDENCE_WEIGHTS mapping during scoring.

This avoids the historical-bar qualification rebuild for every tested weight.
Production configuration is restored in finally.
"""
from __future__ import annotations

import os
import sys

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import config
from data import daily_to_weekly, download_data
from engine.columns import COL_DIRECTION, COL_SPREAD_CLASS, COL_VOLUME_CLASS
from evidence.engine import EvidenceEngine
from evidence.profiles import EVIDENCE_REGISTRY
from metrics_engine import MetricsEngine
from model.evidence_result_model import EvidenceResult
from models import Direction, EvidenceCategory, EvidenceCode, SpreadClass, VolumeClass
from professional.scoring_engine import ProfessionalScoringEngine
from trend import TrendAnalyzer

SYMBOLS = (
    "BHARTIARTL.NS",
    "HDFCBANK.NS",
    "ICICIBANK.NS",
    "INFY.NS",
    "LT.NS",
    "RELIANCE.NS",
    "SBIN.NS",
    "TCS.NS",
)
TARGET_CODE = EvidenceCode.NO_DEMAND
WEIGHTS = (0.40, 0.50, 0.60, 0.70, 0.80, 1.00)
EXPECTED_CANDIDATES = 202
EXPECTED_EVENTS = 109
FORWARD_BARS = 8
REFERENCE_WEIGHT = 0.60


def cheap_candidate(metrics: pd.DataFrame, index: int) -> bool:
    row = metrics.iloc[index]
    return (
        Direction(int(row[COL_DIRECTION])) == Direction.UP
        and VolumeClass(int(row[COL_VOLUME_CLASS])) <= VolumeClass.LOW
        and SpreadClass(int(row[COL_SPREAD_CLASS])) <= SpreadClass.NARROW
    )


def score_target(trend, evidence: EvidenceResult):
    scoring_evidence = tuple(
        item
        for item in evidence.evidence
        if item.category in {
            EvidenceCategory.SUPPLY,
            EvidenceCategory.DEMAND,
            EvidenceCategory.EFFORT,
            EvidenceCategory.RESULT,
        }
    )
    return ProfessionalScoringEngine().calculate(
        trend,
        EvidenceResult(context=evidence.context, evidence=scoring_evidence),
    )


def rank_map(results):
    ordered = sorted(
        results,
        key=lambda item: item[2].scores.net_strength,
        reverse=True,
    )
    return {
        (symbol, index): rank
        for rank, (symbol, index, _result) in enumerate(ordered, start=1)
    }


def main() -> None:
    original_weight = config.SUPPLY_EVIDENCE_WEIGHTS[TARGET_CODE]
    registry_weight = EVIDENCE_REGISTRY[TARGET_CODE].weight

    cheap_candidates = 0
    candidate_events = 0
    target_records = []
    failures: list[dict[str, str]] = []
    target_replays = 0

    # Phase 1: replay only cheap candidates until the actual NO_DEMAND
    # emission is found. Do not build chronological qualification history.
    for symbol in SYMBOLS:
        try:
            metrics = MetricsEngine().calculate(
                daily_to_weekly(download_data(symbol))
            )
            indices = [
                index
                for index in range(1, len(metrics) - FORWARD_BARS)
                if cheap_candidate(metrics, index)
            ]
            cheap_candidates += len(indices)

            for index in indices:
                replay = metrics.iloc[: index + 1].copy()
                trend = TrendAnalyzer().analyze(replay)
                target_replays += 1

                evidence = EvidenceEngine().collect(
                    metrics=replay,
                    trend=trend,
                    structural_swings=list(trend.structure.structural_swings),
                )

                targets = tuple(
                    item
                    for item in evidence.evidence
                    if item.code is TARGET_CODE and item.bar_index == index
                )
                if len(targets) != 1:
                    continue

                target_records.append((symbol, index, trend, evidence))
                candidate_events += 1
        except Exception as exc:
            failures.append({"symbol": symbol, "error": str(exc)})

    failures_out = list(failures)
    if cheap_candidates != EXPECTED_CANDIDATES:
        failures_out.append({
            "scope": "candidate_population",
            "error": f"expected {EXPECTED_CANDIDATES} cheap candidates, got {cheap_candidates}",
        })
    if candidate_events != EXPECTED_EVENTS:
        failures_out.append({
            "scope": "candidate_events",
            "error": f"expected {EXPECTED_EVENTS} emitted events, got {candidate_events}",
        })

    results_by_weight = {}
    try:
        # Phase 2: live-weight scoring only. No qualification replay.
        for weight in WEIGHTS:
            config.SUPPLY_EVIDENCE_WEIGHTS[TARGET_CODE] = weight
            results_by_weight[weight] = [
                (symbol, index, score_target(trend, evidence))
                for symbol, index, trend, evidence in target_records
            ]
    finally:
        config.SUPPLY_EVIDENCE_WEIGHTS[TARGET_CODE] = original_weight

    if REFERENCE_WEIGHT not in results_by_weight:
        failures_out.append({
            "scope": "reference_weight",
            "error": f"reference weight {REFERENCE_WEIGHT} was not tested",
        })

    reference = results_by_weight.get(REFERENCE_WEIGHT, [])
    reference_map = {(symbol, index): result for symbol, index, result in reference}
    reference_ranks = rank_map(reference)

    print("NO_DEMAND WEIGHT SENSITIVITY AUDIT - OPTIMIZED")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": len(SYMBOLS) - len(failures),
        "cheap_candidates": cheap_candidates,
        "candidate_events": candidate_events,
        "expected_events": EXPECTED_EVENTS,
        "registry_weight": registry_weight,
        "configured_reference_weight": original_weight,
        "weights_tested": WEIGHTS,
        "reference_weight": REFERENCE_WEIGHT,
        "qualification_replay": False,
        "qualification_actionability_note": (
            "Qualification and actionability are weight-independent and were validated by separate audits."
        ),
        "target_replays": target_replays,
        "production_path_mutation": False,
        "failures": failures_out,
        "status": "FAIL" if failures_out else "PASS",
    })

    for weight in WEIGHTS:
        results = results_by_weight.get(weight, [])
        result_objects = [result for _, _, result in results]
        strengths = [result.scores.net_strength for result in result_objects]
        confidences = [result.scores.confidence for result in result_objects]
        supply_scores = [result.scores.supply for result in result_objects]

        score_changed = 0
        score_deltas = []
        for symbol, index, result in results:
            base = reference_map.get((symbol, index))
            if base is None:
                continue
            delta = result.scores.net_strength - base.scores.net_strength
            score_deltas.append(delta)
            if abs(delta) > 1e-12:
                score_changed += 1

        ranks = rank_map(results)
        rank_changed = sum(
            ranks[key] != reference_ranks[key]
            for key in ranks
            if key in reference_ranks
        )

        print({
            "weight": weight,
            "events": len(results),
            "score_changed_vs_reference": score_changed,
            "rank_positions_changed_vs_reference": rank_changed,
            "mean_net_strength": sum(strengths) / len(strengths) if strengths else 0.0,
            "mean_confidence": sum(confidences) / len(confidences) if confidences else 0.0,
            "mean_supply_score": sum(supply_scores) / len(supply_scores) if supply_scores else 0.0,
            "mean_net_strength_delta_vs_reference": sum(score_deltas) / len(score_deltas) if score_deltas else 0.0,
            "candidate_score_mass": sum(strengths),
        })


if __name__ == "__main__":
    main()
