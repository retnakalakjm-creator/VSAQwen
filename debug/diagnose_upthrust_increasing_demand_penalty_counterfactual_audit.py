"""UPTHRUST + INCREASING_DEMAND counterfactual penalty audit.

Analysis-only. Freezes the current 289 production UPTHRUST emissions, computes
the production professional scores once, then applies hypothetical penalties
to supply score only for the exact 212-event pure
UPTHRUST + BUYING_CLIMAX + INCREASING_DEMAND subgroup.

Production configuration is never mutated.
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
from models import Direction, EvidenceCategory, EvidenceCode, SpreadClass, VolumeClass
from professional.scoring_engine import ProfessionalScoringEngine
from model.evidence_result_model import EvidenceResult
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
FORWARD_BARS = 8

# Small hypothetical deductions applied to SUPPLY score.
PENALTIES = (0.00, 0.02, 0.04, 0.06, 0.08, 0.10)


def cheap_candidate(metrics: pd.DataFrame, index: int) -> bool:
    row = metrics.iloc[index]
    return (
        Direction(int(row[COL_DIRECTION])) == Direction.UP
        and VolumeClass(int(row[COL_VOLUME_CLASS])) >= VolumeClass.HIGH
        and SpreadClass(int(row[COL_SPREAD_CLASS])) >= SpreadClass.ABOVE_AVERAGE
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


def score_once(trend, evidence):
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
        EvidenceResult(
            context=evidence.context,
            evidence=scoring_evidence,
        ),
    )


def main() -> None:
    cheap_total = 0
    event_total = 0
    pure_interaction_total = 0
    duplicate_emissions = 0
    failures: list[dict[str, str]] = []
    frozen: list[dict[str, object]] = []
    context_rebuilds = 0

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
            cheap_total += len(indices)

            for index in indices:
                replay = metrics.iloc[: index + 1].copy()
                trend = TrendAnalyzer().analyze(replay)
                context_rebuilds += 1

                evidence = EvidenceEngine().collect(
                    metrics=replay,
                    trend=trend,
                    structural_swings=list(trend.structure.structural_swings),
                )

                targets = [
                    item
                    for item in evidence.evidence
                    if item.code is TARGET_CODE
                    and item.bar_index == index
                ]

                if len(targets) > 1:
                    duplicate_emissions += len(targets) - 1
                    continue

                if not targets:
                    continue

                scored = score_once(trend, evidence)
                interaction = pure_interaction(evidence, index)

                frozen.append({
                    "symbol": symbol,
                    "index": index,
                    "trend": float(scored.scores.trend),
                    "supply": float(scored.scores.supply),
                    "demand": float(scored.scores.demand),
                    "effort": float(scored.scores.effort),
                    "strength": float(scored.scores.strength),
                    "weakness": float(scored.scores.weakness),
                    "confidence": float(scored.scores.confidence),
                    "interaction": interaction,
                })

                event_total += 1
                pure_interaction_total += int(interaction)

        except Exception as exc:
            failures.append({
                "symbol": symbol,
                "error": str(exc),
            })

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
            "error": (
                f"expected {EXPECTED_PURE_INTERACTION}, "
                f"got {pure_interaction_total}"
            ),
        })

    if duplicate_emissions:
        failures_out.append({
            "scope": "duplicates",
            "error": f"duplicate emissions: {duplicate_emissions}",
        })

    print("UPTHRUST + INCREASING_DEMAND COUNTERFACTUAL PENALTY AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": len(SYMBOLS) - len(failures),
        "cheap_candidates": cheap_total,
        "production_emissions": event_total,
        "expected_events": EXPECTED_EVENTS,
        "pure_interaction_events": pure_interaction_total,
        "expected_pure_interaction_events": EXPECTED_PURE_INTERACTION,
        "penalties_tested": PENALTIES,
        "production_path_mutation": False,
        "target_bar_only": True,
        "point_in_time": True,
        "frozen_scores_built_once": True,
        "heavy_context_rebuilds": context_rebuilds,
        "failures": failures_out,
        "status": "FAIL" if failures_out else "PASS",
    })

    if failures_out:
        return

    base_order = sorted(
        frozen,
        key=lambda row: (
            float(row["strength"]) - float(row["weakness"])
        ),
        reverse=True,
    )
    base_rank = {
        (row["symbol"], row["index"]): rank
        for rank, row in enumerate(base_order, start=1)
    }

    for penalty in PENALTIES:
        adjusted = []

        for row in frozen:
            supply = float(row["supply"])
            if row["interaction"]:
                supply = max(0.0, supply - penalty)

            demand = float(row["demand"])
            trend = float(row["trend"])
            effort = float(row["effort"])

            demand_advantage = max(demand - supply, 0.0)
            supply_advantage = max(supply - demand, 0.0)

            strength = max(
                0.0,
                min(
                    0.40 * trend
                    + 0.40 * demand_advantage
                    + 0.20 * effort,
                    1.0,
                ),
            )

            weakness = max(
                0.0,
                min(
                    0.40 * (1.0 - trend)
                    + 0.40 * supply_advantage
                    + 0.20 * (1.0 - effort),
                    1.0,
                ),
            )

            confidence = max(
                0.0,
                min(
                    0.40 * trend
                    + 0.40 * abs(demand - supply)
                    + 0.20 * effort,
                    1.0,
                ),
            )

            adjusted.append({
                **row,
                "adjusted_supply": supply,
                "adjusted_strength": strength,
                "adjusted_weakness": weakness,
                "adjusted_confidence": confidence,
                "adjusted_net_strength": strength - weakness,
            })

        order = sorted(
            adjusted,
            key=lambda row: row["adjusted_net_strength"],
            reverse=True,
        )
        ranks = {
            (row["symbol"], row["index"]): rank
            for rank, row in enumerate(order, start=1)
        }

        changed_rank = sum(
            ranks[key] != base_rank[key]
            for key in ranks
        )

        changed_supply = sum(
            abs(float(row["adjusted_supply"]) - float(row["supply"]))
            > 1e-12
            for row in adjusted
        )

        interaction_rows = [
            row
            for row in adjusted
            if row["interaction"]
        ]

        mean_interaction_supply = (
            sum(float(row["adjusted_supply"]) for row in interaction_rows)
            / len(interaction_rows)
            if interaction_rows
            else 0.0
        )

        mean_interaction_net_strength = (
            sum(float(row["adjusted_net_strength"]) for row in interaction_rows)
            / len(interaction_rows)
            if interaction_rows
            else 0.0
        )

        print({
            "penalty": penalty,
            "events": len(adjusted),
            "supply_score_changed_events": changed_supply,
            "rank_positions_changed": changed_rank,
            "mean_interaction_supply_score_after_penalty": mean_interaction_supply,
            "mean_interaction_net_strength_after_penalty": mean_interaction_net_strength,
            "production_decision": "STUDY_ONLY_NO_PRODUCTION_CHANGE",
        })


if __name__ == "__main__":
    main()
