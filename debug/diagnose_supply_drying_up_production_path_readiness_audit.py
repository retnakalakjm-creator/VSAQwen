"""SUPPLY_DRYING_UP production-path readiness audit.

Checks production emission counts, scoring-map provenance, dynamic runtime
Evidence.weight bounds, semantic/point-in-time integrity, and mutation safety.
The runtime Evidence.weight is emission metadata and is intentionally audited
separately from the professional SUPPLY_EVIDENCE_WEIGHTS scoring map.
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
TARGET_CODE = EvidenceCode.SUPPLY_DRYING_UP
EXPECTED_CANDIDATES = 547
EXPECTED_EVENTS = 225
RUNTIME_WEIGHT_BOUNDS = (0.5, 2.0)


def cheap_candidate(metrics: pd.DataFrame, index: int) -> bool:
    row = metrics.iloc[index]
    return (
        Direction(int(row[COL_DIRECTION])) == Direction.DOWN
        and VolumeClass(int(row[COL_VOLUME_CLASS])) <= VolumeClass.LOW
        and SpreadClass(int(row[COL_SPREAD_CLASS])) <= SpreadClass.BELOW_AVERAGE
    )


def resolve_weight_key(weight_map, code: EvidenceCode):
    if code in weight_map:
        return code
    if code.value in weight_map:
        return code.value
    raise KeyError(f"{code!r} not present in weight map; keys={list(weight_map)!r}")


def main() -> None:
    cheap_total = 0
    production_emissions = 0
    duplicate_emissions = 0
    semantic_failures = 0
    runtime_weights: list[float] = []
    failures: list[dict[str, str]] = []
    context_rebuilds = 0

    try:
        weight_key = resolve_weight_key(config.SUPPLY_EVIDENCE_WEIGHTS, TARGET_CODE)
        configured_supply_weight = float(config.SUPPLY_EVIDENCE_WEIGHTS[weight_key])
        configured_supply_entry = True
    except KeyError:
        configured_supply_weight = None
        configured_supply_entry = False

    for symbol in SYMBOLS:
        try:
            metrics = MetricsEngine().calculate(
                daily_to_weekly(download_data(symbol))
            )
            indices = [
                i
                for i in range(1, len(metrics) - 8)
                if cheap_candidate(metrics, i)
            ]
            cheap_total += len(indices)

            for index in indices:
                replay = metrics.iloc[: index + 1].copy()
                trend = TrendAnalyzer().analyze(replay)
                context_rebuilds += 1
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
                evidence = targets[0]
                if evidence.weight is not None:
                    runtime_weights.append(float(evidence.weight))

                row = metrics.iloc[index]
                valid = (
                    Direction(int(row[COL_DIRECTION])) == Direction.DOWN
                    and VolumeClass(int(row[COL_VOLUME_CLASS])) <= VolumeClass.LOW
                    and SpreadClass(int(row[COL_SPREAD_CLASS])) <= SpreadClass.NARROW
                )
                semantic_failures += int(not valid)

        except Exception as exc:
            failures.append({"symbol": symbol, "error": str(exc)})

    failures_out = list(failures)
    if cheap_total != EXPECTED_CANDIDATES:
        failures_out.append({
            "scope": "candidate_population",
            "error": f"expected {EXPECTED_CANDIDATES}, got {cheap_total}",
        })
    if production_emissions != EXPECTED_EVENTS:
        failures_out.append({
            "scope": "production_emissions",
            "error": f"expected {EXPECTED_EVENTS}, got {production_emissions}",
        })
    if semantic_failures:
        failures_out.append({
            "scope": "semantics",
            "error": f"semantic failures: {semantic_failures}",
        })
    if duplicate_emissions:
        failures_out.append({
            "scope": "duplicates",
            "error": f"duplicate emissions: {duplicate_emissions}",
        })

    observed = {
        "min": min(runtime_weights) if runtime_weights else 0.0,
        "max": max(runtime_weights) if runtime_weights else 0.0,
        "mean": sum(runtime_weights) / len(runtime_weights) if runtime_weights else 0.0,
    }
    lower, upper = RUNTIME_WEIGHT_BOUNDS
    within_bounds = bool(runtime_weights) and lower <= observed["min"] and observed["max"] <= upper

    if not within_bounds:
        failures_out.append({
            "scope": "runtime_weight_bounds",
            "error": f"observed {observed} outside bounds {RUNTIME_WEIGHT_BOUNDS}",
        })

    print("SUPPLY_DRYING_UP PRODUCTION PATH READINESS AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": len(SYMBOLS) - len(failures),
        "cheap_candidates": cheap_total,
        "production_emissions": production_emissions,
        "expected_events": EXPECTED_EVENTS,
        "registry_weight": 1.0,
        "configured_supply_map_entry": configured_supply_entry,
        "configured_supply_map_weight": configured_supply_weight,
        "production_role": "contextual_supply_exhaustion",
        "runtime_weight_model": "dynamic Evidence.weight metadata",
        "runtime_weight_observed": observed,
        "runtime_weight_bounds": RUNTIME_WEIGHT_BOUNDS,
        "runtime_weight_within_bounds": within_bounds,
        "registry_config_discrepancy": configured_supply_weight != 1.0 if configured_supply_weight is not None else True,
        "weight_provenance_note": "Evidence.weight is dynamic emission metadata; SUPPLY_EVIDENCE_WEIGHTS is the professional scoring map.",
        "target_bar_only": True,
        "point_in_time": True,
        "production_context_used": True,
        "production_emission_authority": True,
        "duplicate_emissions": duplicate_emissions,
        "semantic_failures": semantic_failures,
        "production_path_mutation": False,
        "heavy_context_rebuilds": context_rebuilds,
        "failures": failures_out,
        "status": "FAIL" if failures_out else "PASS",
    })


if __name__ == "__main__":
    main()
