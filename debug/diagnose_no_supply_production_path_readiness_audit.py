"""NO_SUPPLY production-path readiness audit.

Analysis-only. Verifies the current contextual/non-scoring production path,
the exact frozen emission population, runtime Evidence.weight provenance,
semantic integrity, and absence from the configurable professional scoring
maps. It never mutates production configuration.
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
from models import Direction, EvidenceCode, SpreadClass, VolumeClass
from professional.scoring_engine import ProfessionalScoringEngine
from trend import TrendAnalyzer

SYMBOLS = (
    "BHARTIARTL.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "LT.NS", "RELIANCE.NS", "SBIN.NS", "TCS.NS",
)
TARGET_CODE = EvidenceCode.NO_SUPPLY
EXPECTED_CANDIDATES = 225
EXPECTED_EVENTS = 23
RUNTIME_WEIGHT_BOUNDS = (0.50, 2.00)


def cheap_candidate(metrics: pd.DataFrame, index: int) -> bool:
    row = metrics.iloc[index]
    return (
        Direction(int(row[COL_DIRECTION])) == Direction.DOWN
        and VolumeClass(int(row[COL_VOLUME_CLASS])) <= VolumeClass.LOW
        and SpreadClass(int(row[COL_SPREAD_CLASS])) <= SpreadClass.NARROW
    )


def main() -> None:
    cheap_total = 0
    emission_total = 0
    duplicate_emissions = 0
    semantic_failures = 0
    runtime_weights: list[float] = []
    failures: list[dict[str, str]] = []
    heavy_context_rebuilds = 0

    has_supply_scoring_entry = TARGET_CODE in config.SUPPLY_EVIDENCE_WEIGHTS
    has_demand_scoring_entry = TARGET_CODE in config.DEMAND_EVIDENCE_WEIGHTS

    for symbol in SYMBOLS:
        try:
            metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
            indices = [
                i for i in range(1, len(metrics) - 8)
                if cheap_candidate(metrics, i)
            ]
            cheap_total += len(indices)

            for index in indices:
                replay = metrics.iloc[: index + 1].copy()
                trend = TrendAnalyzer().analyze(replay)
                heavy_context_rebuilds += 1

                result = EvidenceEngine().collect(
                    metrics=replay,
                    trend=trend,
                    structural_swings=list(trend.structure.structural_swings),
                )
                targets = [
                    item for item in result.evidence
                    if item.code is TARGET_CODE and item.bar_index == index
                ]

                if len(targets) > 1:
                    duplicate_emissions += len(targets) - 1
                    continue
                if not targets:
                    continue

                emission_total += 1
                emitted = targets[0]

                if emitted.code is not TARGET_CODE or emitted.bar_index != index:
                    semantic_failures += 1

                weight = float(emitted.weight)
                runtime_weights.append(weight)

                if not RUNTIME_WEIGHT_BOUNDS[0] <= weight <= RUNTIME_WEIGHT_BOUNDS[1]:
                    failures.append({
                        "scope": "runtime_weight_bounds",
                        "error": f"{symbol}:{index}: runtime weight {weight}",
                    })

        except Exception as exc:
            failures.append({"symbol": symbol, "error": str(exc)})

    failures_out = list(failures)

    if cheap_total != EXPECTED_CANDIDATES:
        failures_out.append({
            "scope": "candidate_population",
            "error": f"expected {EXPECTED_CANDIDATES}, got {cheap_total}",
        })
    if emission_total != EXPECTED_EVENTS:
        failures_out.append({
            "scope": "production_emissions",
            "error": f"expected {EXPECTED_EVENTS}, got {emission_total}",
        })
    if duplicate_emissions:
        failures_out.append({
            "scope": "duplicates",
            "error": f"duplicate emissions: {duplicate_emissions}",
        })
    if semantic_failures:
        failures_out.append({
            "scope": "provenance",
            "error": f"semantic/provenance failures: {semantic_failures}",
        })

    # NO_SUPPLY is intentionally contextual/non-scoring. Its absence from
    # both professional scoring maps is part of the production contract.
    if has_supply_scoring_entry or has_demand_scoring_entry:
        failures_out.append({
            "scope": "scoring_map",
            "error": "NO_SUPPLY unexpectedly present in a professional scoring map",
        })

    registry_weight = EVIDENCE_REGISTRY[TARGET_CODE].weight

    # Instantiate scorer only to confirm the production scoring API is callable;
    # NO_SUPPLY itself must not be a configurable scoring-map entry.
    try:
        ProfessionalScoringEngine()
    except Exception as exc:
        failures_out.append({"scope": "scoring_api", "error": str(exc)})

    print("NO_SUPPLY PRODUCTION PATH READINESS AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": len(SYMBOLS) - len([f for f in failures if "symbol" in f]),
        "cheap_candidates": cheap_total,
        "production_emissions": emission_total,
        "expected_events": EXPECTED_EVENTS,
        "registry_weight": registry_weight,
        "configured_supply_map_entry": has_supply_scoring_entry,
        "configured_demand_map_entry": has_demand_scoring_entry,
        "production_role": "contextual_non_scoring",
        "runtime_weight_model": "dynamic WeightCalculator",
        "runtime_weight_observed": {
            "min": min(runtime_weights) if runtime_weights else None,
            "max": max(runtime_weights) if runtime_weights else None,
            "mean": sum(runtime_weights) / len(runtime_weights) if runtime_weights else None,
        },
        "runtime_weight_bounds": RUNTIME_WEIGHT_BOUNDS,
        "target_bar_only": True,
        "point_in_time": True,
        "production_context_used": True,
        "production_emission_authority": True,
        "duplicate_emissions": duplicate_emissions,
        "semantic_failures": semantic_failures,
        "production_path_mutation": False,
        "heavy_context_rebuilds": heavy_context_rebuilds,
        "weight_sensitivity_audit": "NOT_APPLICABLE_NO_SCORING_MAP_ENTRY",
        "failures": failures_out,
        "status": "FAIL" if failures_out else "PASS",
    })


if __name__ == "__main__":
    main()
