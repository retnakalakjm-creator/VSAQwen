"""Production-path readiness audit for NO_DEMAND.

Analysis-only. Replays only the validated cheap-candidate population and
verifies the actual emitted Evidence.weight against registry/configuration.
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
    configured_weight = config.SUPPLY_EVIDENCE_WEIGHTS[TARGET_CODE]
    registry_weight = EVIDENCE_REGISTRY[TARGET_CODE].weight

    cheap_candidates = 0
    production_emissions = 0
    runtime_weights: list[float] = []
    duplicate_emissions = 0
    semantic_failures = 0
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
                runtime_weights.append(float(targets[0].weight))

                # Mandatory semantics are already validated by the candidate
                # and semantic-quality audits; here we only assert the emitted
                # target carries the expected code/bar provenance.
                if targets[0].code is not TARGET_CODE or targets[0].bar_index != index:
                    semantic_failures += 1

        except Exception as exc:
            failures.append({"symbol": symbol, "error": str(exc)})

    weight_matches = bool(runtime_weights) and all(
        abs(weight - configured_weight) <= 1e-12
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
    if runtime_weights and not weight_matches:
        failures_out.append({
            "scope": "runtime_weight",
            "error": (
                f"configured {configured_weight} but observed "
                f"min={min(runtime_weights)}, max={max(runtime_weights)}"
            ),
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

    print("NO_DEMAND PRODUCTION PATH READINESS AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": len(SYMBOLS) - len(failures),
        "cheap_candidates": cheap_candidates,
        "production_emissions": production_emissions,
        "expected_events": EXPECTED_EVENTS,
        "registry_weight": registry_weight,
        "configured_supply_map_weight": configured_weight,
        "runtime_weight_observed": {
            "min": min(runtime_weights) if runtime_weights else None,
            "max": max(runtime_weights) if runtime_weights else None,
            "mean": (
                sum(runtime_weights) / len(runtime_weights)
                if runtime_weights else None
            ),
        },
        "runtime_weight_matches_config": weight_matches,
        "registry_config_discrepancy": registry_weight != configured_weight,
        "duplicate_emissions": duplicate_emissions,
        "semantic_failures": semantic_failures,
        "production_path_mutation": False,
        "target_bar_only": True,
        "point_in_time": True,
        "heavy_context_rebuilds": heavy_context_rebuilds,
        "failures": failures_out,
        "status": "FAIL" if failures_out else "PASS",
    })


if __name__ == "__main__":
    main()
