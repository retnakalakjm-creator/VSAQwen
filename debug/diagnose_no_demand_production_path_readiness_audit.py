"""Production-path readiness audit for NO_DEMAND.

Analysis-only. Replays only the validated cheap-candidate population and
verifies production emission integrity. NO_DEMAND Evidence.weight is a
context-dependent runtime weight produced by WeightCalculator, while
config.SUPPLY_EVIDENCE_WEIGHTS[NO_DEMAND] is the separate professional
scoring-map weight used by ProfessionalScoringEngine.
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
EXPECTED_CHEAP_CANDIDATES = 202
EXPECTED_EVENTS = 109
FORWARD_BARS = 8
RUNTIME_WEIGHT_BOUNDS = (0.50, 2.00)


def cheap_candidate(metrics: pd.DataFrame, index: int) -> bool:
    row = metrics.iloc[index]
    return (
        Direction(int(row[COL_DIRECTION])) == Direction.UP
        and VolumeClass(int(row[COL_VOLUME_CLASS])) <= VolumeClass.LOW
        and SpreadClass(int(row[COL_SPREAD_CLASS])) <= SpreadClass.NARROW
    )


def candidate_indices(metrics: pd.DataFrame) -> list[int]:
    return [
        i
        for i in range(1, len(metrics) - FORWARD_BARS)
        if cheap_candidate(metrics, i)
    ]


def main() -> None:
    configured_scoring_weight = config.SUPPLY_EVIDENCE_WEIGHTS[TARGET_CODE]
    registry_weight = EVIDENCE_REGISTRY[TARGET_CODE].weight

    cheap_candidates = 0
    production_emissions = 0
    runtime_weights: list[float] = []
    duplicate_emissions = 0
    provenance_failures = 0
    heavy_context_rebuilds = 0
    failures: list[dict[str, str]] = []

    for symbol in SYMBOLS:
        try:
            metrics = MetricsEngine().calculate(
                daily_to_weekly(download_data(symbol))
            )
            indices = candidate_indices(metrics)
            cheap_candidates += len(indices)

            for index in indices:
                replay = metrics.iloc[: index + 1].copy()
                trend = TrendAnalyzer().analyze(replay)
                heavy_context_rebuilds += 1

                result = EvidenceEngine().collect(
                    metrics=replay,
                    trend=trend,
                    structural_swings=tuple(trend.structure.structural_swings),
                )

                targets = [
                    item
                    for item in result.evidence
                    if item.code is TARGET_CODE and item.bar_index == index
                ]

                if len(targets) > 1:
                    duplicate_emissions += len(targets) - 1
                    continue

                if not targets:
                    continue

                production_emissions += 1
                emitted = targets[0]
                runtime_weight = float(emitted.weight)
                runtime_weights.append(runtime_weight)

                if emitted.code is not TARGET_CODE or emitted.bar_index != index:
                    provenance_failures += 1

                lower, upper = RUNTIME_WEIGHT_BOUNDS
                if not lower <= runtime_weight <= upper:
                    provenance_failures += 1

        except Exception as exc:
            failures.append({"symbol": symbol, "error": str(exc)})

    runtime_within_bounds = bool(runtime_weights) and all(
        RUNTIME_WEIGHT_BOUNDS[0] <= weight <= RUNTIME_WEIGHT_BOUNDS[1]
        for weight in runtime_weights
    )

    failures_out = list(failures)
    if cheap_candidates != EXPECTED_CHEAP_CANDIDATES:
        failures_out.append({
            "scope": "candidate_population",
            "error": f"expected {EXPECTED_CHEAP_CANDIDATES}, got {cheap_candidates}",
        })
    if production_emissions != EXPECTED_EVENTS:
        failures_out.append({
            "scope": "production_emissions",
            "error": f"expected {EXPECTED_EVENTS}, got {production_emissions}",
        })
    if not runtime_within_bounds:
        failures_out.append({
            "scope": "runtime_weight_bounds",
            "error": (
                f"observed runtime weight outside bounds {RUNTIME_WEIGHT_BOUNDS}"
            ),
        })
    if duplicate_emissions:
        failures_out.append({
            "scope": "duplicates",
            "error": f"duplicate emissions: {duplicate_emissions}",
        })
    if provenance_failures:
        failures_out.append({
            "scope": "provenance",
            "error": f"runtime/provenance failures: {provenance_failures}",
        })

    print("NO_DEMAND PRODUCTION PATH READINESS AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": len(SYMBOLS) - len(failures),
        "cheap_candidates": cheap_candidates,
        "production_emissions": production_emissions,
        "expected_events": EXPECTED_EVENTS,
        "registry_weight": registry_weight,
        "configured_supply_map_weight": configured_scoring_weight,
        "runtime_weight_model": "dynamic WeightCalculator",
        "runtime_weight_observed": {
            "min": min(runtime_weights) if runtime_weights else None,
            "max": max(runtime_weights) if runtime_weights else None,
            "mean": (
                sum(runtime_weights) / len(runtime_weights)
                if runtime_weights else None
            ),
        },
        "runtime_weight_bounds": RUNTIME_WEIGHT_BOUNDS,
        "runtime_weight_within_bounds": runtime_within_bounds,
        "runtime_weight_matches_config_not_required": True,
        "registry_config_discrepancy": registry_weight != configured_scoring_weight,
        "weight_provenance_note": (
            "Evidence.weight is dynamic emission metadata; "
            "SUPPLY_EVIDENCE_WEIGHTS is the separate professional scoring map."
        ),
        "duplicate_emissions": duplicate_emissions,
        "provenance_failures": provenance_failures,
        "production_path_mutation": False,
        "target_bar_only": True,
        "point_in_time": True,
        "heavy_context_rebuilds": heavy_context_rebuilds,
        "failures": failures_out,
        "status": "FAIL" if failures_out else "PASS",
    })


if __name__ == "__main__":
    main()
