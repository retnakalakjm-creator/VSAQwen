"""Counterfactual UPTHRUST + INCREASING_DEMAND penalty study.

Freezes the 289 production UPTHRUST events, computes the current professional
score once, and applies hypothetical penalties only to the exact
UPTHRUST + BUYING_CLIMAX + INCREASING_DEMAND subgroup. Production configuration
is never mutated.
"""
from __future__ import annotations

import os
import sys

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from data import daily_to_weekly, download_data
from engine.columns import COL_DIRECTION, COL_SPREAD_CLASS, COL_VOLUME_CLASS
from evidence.engine import EvidenceEngine
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
TARGET_CODE = EvidenceCode.UPTHRUST
EXPECTED_CANDIDATES = 1319
EXPECTED_EVENTS = 289
EXPECTED_PURE_INTERACTION = 212
PENALTIES = (0.00, 0.02, 0.04, 0.06, 0.08, 0.10)


def cheap_candidate(metrics: pd.DataFrame, index: int) -> bool:
    row = metrics.iloc[index]
    return (
        Direction(int(row[COL_DIRECTION])) == Direction.UP
        and VolumeClass(int(row[COL_VOLUME_CLASS])) >= VolumeClass.HIGH
        and SpreadClass(int(row[COL_SPREAD_CLASS])) >= SpreadClass.ABOVE_AVERAGE
    )


def base_score(trend, evidence):
    scoring_evidence = tuple(
        item for item in evidence.evidence
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


def pure_interaction(evidence, index: int) -> bool:
    codes = {
        item.code
        for item in evidence.evidence
        if item.bar_index == index
    }
    return (
        EvidenceCode.BUYING_CLIMAX in codes
        and EvidenceCode.INCREASING_DEMAND in codes
        and EvidenceCode.HIDDEN_SUPPLY not in codes
        and EvidenceCode.SPRING not in codes
    )


def main() -> None:
    cheap_total = 0
    event_total = 0
    pure_interaction_total = 0
    duplicate_emissions = 0
    failures: list[dict[str, str]] = []
    frozen: list[dict[str, object]] = []

    for symbol in SYMBOLS:
        try:
            metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
            indices = [
                i for i in range(1, len(metrics))
                if i < len(metrics) - 8 and cheap_candidate(metrics, i)
            ]
            cheap_total += len(indices)

            for index in indices:
                replay = metrics.iloc[: index + 1].copy()
                trend = TrendAnalyzer().analyze(replay)
                evidence = EvidenceEngine().collect(
                    metrics=replay,
                    trend=trend,
                    structural_swings=list(trend.structure.structural_swings),
                )
                targets = [
                    item for item in evidence.evidence
                    if item.code is TARGET_CODE and item.bar_index == index
                ]
                if len(targets) > 1:
                    duplicate_emissions += len(targets) - 1
                    continue
                if not targets:
                    continue

                scored = base_score(trend, evidence)
                interaction = pure_interaction(evidence, index)
                pure_interaction_total += int(interaction)
                frozen.append({
                    "symbol": symbol,
                    "index": index,
                    "net_strength": float(scored.scores.net_strength),
                    "score": float(scored.scores.strength),
                    "interaction": interaction,
                })
                event_total += 1

        except Exception as exc:
            failures.append({"symbol": symbol, "error": str(exc)})

    failures_out = list(failures)

    if cheap_total != EXPECTED_CANDIDATES:
        failures_out.append({
            "scope": "candidate_population",
            "error": f"expected {EXPECTED_CANDIDATES}, got {cheap_total}",
        })
    if event_total != EXPECTED_EVENTS:
        failures_out.append({
            "scope": "production_emissions",
            "error": f"expected {EXPECTED_EVENTS}, got {event_total}",
        })
    if pure_interaction_total != EXPECTED_PURE_INTERACTION:
        failures_out.append({
            "scope": "pure_interaction_population",
            "error": f"expected {EXPECTED_PURE_INTERACTION}, got {pure_interaction_total}",
        })
    if duplicate_emissions:
        failures_out.append({
            "scope": "duplicates",
            "error": f"duplicate emissions: {duplicate_emissions}",
        })

    reference_order = sorted(
        frozen,
        key=lambda row: row["net_strength"],
        reverse=True,
    )
    reference_rank = {
        (row["symbol"], row["index"]): rank
        for rank, row in enumerate(reference_order, start=1)
    }

    print("UPTHRUST + INCREASING_DEMAND COUNTERFACTUAL PENALTY AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": len(SYMBOLS) - len(failures),
        "cheap_candidates": cheap_total,
        "candidate_events": event_total,
        "expected_events": EXPECTED_EVENTS,
        "pure_interaction_events": pure_interaction_total,
        "expected_pure_interaction_events": EXPECTED_PURE_INTERACTION,
        "penalties_tested": PENALTIES,
        "production_path_mutation": False,
        "target_bar_only": True,
        "point_in_time": True,
        "frozen_scores_built_once": True,
        "failures": failures_out,
        "status": "FAIL" if failures_out else "PASS",
    })

    if failures_out:
        return

    for penalty in PENALTIES:
        adjusted = []
        for row in frozen:
            strength = float(row["net_strength"])
            if row["interaction"]:
                strength = max(0.0, strength - penalty)
            adjusted.append({
                **row,
                "adjusted": strength,
            })

        order = sorted(
            adjusted,
            key=lambda row: row["adjusted"],
            reverse=True,
        )
        ranks = {
            (row["symbol"], row["index"]): rank
            for rank, row in enumerate(order, start=1)
        }

        rank_changed = sum(
            ranks[key] != reference_rank[key]
            for key in ranks
        )
        score_changed = sum(
            abs(row["adjusted"] - row["net_strength"]) > 1e-12
            for row in adjusted
        )
        interaction_scores = [
            row["adjusted"] for row in adjusted if row["interaction"]
        ]

        print({
            "penalty": penalty,
            "events": len(adjusted),
            "score_changed_events": score_changed,
            "rank_positions_changed": rank_changed,
            "mean_interaction_net_strength_after_penalty": (
                sum(interaction_scores) / len(interaction_scores)
                if interaction_scores else 0.0
            ),
            "interaction_score_mass_after_penalty": sum(interaction_scores),
            "production_decision": "STUDY_ONLY_NO_PRODUCTION_CHANGE",
        })


if __name__ == "__main__":
    main()
