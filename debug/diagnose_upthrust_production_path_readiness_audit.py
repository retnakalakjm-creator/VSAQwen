"""UPTHRUST production-path readiness audit."""
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
    "BHARTIARTL.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "LT.NS", "RELIANCE.NS", "SBIN.NS", "TCS.NS",
)
TARGET_CODE = EvidenceCode.UPTHRUST
EXPECTED_CANDIDATES = 1319
EXPECTED_EVENTS = 289
RUNTIME_WEIGHT_BOUNDS = (0.50, 2.00)


def cheap_candidate(metrics: pd.DataFrame, index: int) -> bool:
    row = metrics.iloc[index]
    return (
        Direction(int(row[COL_DIRECTION])) == Direction.UP
        and VolumeClass(int(row[COL_VOLUME_CLASS])) >= VolumeClass.HIGH
        and SpreadClass(int(row[COL_SPREAD_CLASS])) >= SpreadClass.ABOVE_AVERAGE
    )


def main() -> None:
    cheap_total = 0
    emission_total = 0
    normal_rejections = 0
    duplicate_emissions = 0
    runtime_weights: list[float] = []
    failures: list[dict[str, str]] = []
    heavy_context_rebuilds = 0

    supply_map_entry = any(
        key is TARGET_CODE or key == TARGET_CODE.value
        for key in config.SUPPLY_EVIDENCE_WEIGHTS
    )
    demand_map_entry = any(
        key is TARGET_CODE or key == TARGET_CODE.value
        for key in config.DEMAND_EVIDENCE_WEIGHTS
    )

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
                    normal_rejections += 1
                    continue

                emission_total += 1
                runtime_weights.append(float(targets[0].weight))

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

    if not runtime_weights:
        failures_out.append({
            "scope": "runtime_weight",
            "error": "no runtime Evidence.weight observations",
        })
    else:
        out_of_bounds = [
            w for w in runtime_weights
            if not RUNTIME_WEIGHT_BOUNDS[0] <= w <= RUNTIME_WEIGHT_BOUNDS[1]
        ]
        if out_of_bounds:
            failures_out.append({
                "scope": "runtime_weight_bounds",
                "error": f"out-of-bounds runtime weights: {len(out_of_bounds)}",
            })

    print("UPTHRUST PRODUCTION PATH READINESS AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": len(SYMBOLS) - len(failures),
        "cheap_candidates": cheap_total,
        "production_emissions": emission_total,
        "expected_events": EXPECTED_EVENTS,
        "normal_detector_rejections": normal_rejections,
        "registry_weight": EVIDENCE_REGISTRY[TARGET_CODE].weight,
        "configured_supply_map_entry": supply_map_entry,
        "configured_demand_map_entry": demand_map_entry,
        "production_role": "active_supply_trap",
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
        "production_path_mutation": False,
        "heavy_context_rebuilds": heavy_context_rebuilds,
        "semantic_validation": "covered_by_upthrust_semantic_quality_audit",
        "decision_value": "covered_by_upthrust_decision_value_audit",
        "failures": failures_out,
        "status": "FAIL" if failures_out else "PASS",
    })


if __name__ == "__main__":
    main()
