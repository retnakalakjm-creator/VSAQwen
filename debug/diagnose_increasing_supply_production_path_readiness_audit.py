"""Production-path readiness audit for INCREASING_SUPPLY.

Analysis-only.

Verifies:
- frozen cheap-candidate population;
- emitted target-event population;
- target-bar semantic integrity;
- evidence-registry reference weight;
- emitted Evidence.weight observed at runtime;
- configured supply-map weight used by ProfessionalScoringEngine;
- no duplicate target emissions;
- no production configuration mutation.

This audit deliberately does not change production configuration.
"""
from __future__ import annotations

import copy
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
TARGET_CODE = EvidenceCode.INCREASING_SUPPLY
FORWARD_BARS = 8
EXPECTED_CANDIDATES = 1022
EXPECTED_EVENTS = 528
RUNTIME_WEIGHT_REFERENCE = 1.0


def cheap_candidate(metrics: pd.DataFrame, index: int) -> bool:
    row = metrics.iloc[index]
    return (
        Direction(int(row[COL_DIRECTION])) == Direction.DOWN
        and VolumeClass(int(row[COL_VOLUME_CLASS])) >= VolumeClass.HIGH
        and SpreadClass(int(row[COL_SPREAD_CLASS])) >= SpreadClass.ABOVE_AVERAGE
    )


def candidate_indices(metrics: pd.DataFrame) -> list[int]:
    return [
        i
        for i in range(1, len(metrics) - FORWARD_BARS)
        if cheap_candidate(metrics, i)
    ]


def main() -> None:
    original_supply_map = copy.deepcopy(config.SUPPLY_EVIDENCE_WEIGHTS)
    registry_weight = float(EVIDENCE_REGISTRY[TARGET_CODE].weight)

    cheap_total = 0
    event_total = 0
    target_weight_values: list[float] = []
    semantic_failures: list[dict[str, object]] = []
    duplicate_emissions = 0
    failures: list[dict[str, str]] = []

    try:
        for symbol in SYMBOLS:
            try:
                metrics = MetricsEngine().calculate(
                    daily_to_weekly(download_data(symbol))
                )
                indices = candidate_indices(metrics)
                cheap_total += len(indices)

                for index in indices:
                    replay = metrics.iloc[: index + 1].copy()
                    trend = TrendAnalyzer().analyze(replay)
                    result = EvidenceEngine().collect(
                        metrics=replay,
                        trend=trend,
                        structural_swings=tuple(trend.structure.structural_swings),
                    )

                    targets = [
                        item
                        for item in result.evidence
                        if item.code is TARGET_CODE
                        and item.bar_index == index
                    ]

                    if len(targets) > 1:
                        duplicate_emissions += len(targets) - 1

                    if not targets:
                        continue

                    event_total += 1
                    target = targets[0]
                    target_weight_values.append(float(target.weight))

                    down_bar = Direction(int(metrics.iloc[index][COL_DIRECTION])) == Direction.DOWN
                    volume_increasing = (
                        VolumeClass(int(metrics.iloc[index][COL_VOLUME_CLASS]))
                        > VolumeClass(int(metrics.iloc[index - 1][COL_VOLUME_CLASS]))
                    )
                    spread_increasing = (
                        SpreadClass(int(metrics.iloc[index][COL_SPREAD_CLASS]))
                        > SpreadClass(int(metrics.iloc[index - 1][COL_SPREAD_CLASS]))
                    )

                    if not (down_bar and volume_increasing and spread_increasing):
                        semantic_failures.append({
                            "symbol": symbol,
                            "bar": index,
                            "down_bar": down_bar,
                            "volume_increasing": volume_increasing,
                            "spread_increasing": spread_increasing,
                            "emitted_weight": float(target.weight),
                        })
            except Exception as exc:
                failures.append({"symbol": symbol, "error": str(exc)})

        runtime_min = min(target_weight_values) if target_weight_values else None
        runtime_max = max(target_weight_values) if target_weight_values else None
        runtime_mean = (
            sum(target_weight_values) / len(target_weight_values)
            if target_weight_values else None
        )

        production_mutation = config.SUPPLY_EVIDENCE_WEIGHTS != original_supply_map
        emitted_weight_is_consistent = bool(
            target_weight_values
            and all(abs(value - RUNTIME_WEIGHT_REFERENCE) <= 1e-12 for value in target_weight_values)
        )

        readiness_failures = list(failures)
        if cheap_total != EXPECTED_CANDIDATES:
            readiness_failures.append({
                "scope": "candidate_population",
                "error": f"expected {EXPECTED_CANDIDATES} cheap candidates, got {cheap_total}",
            })
        if event_total != EXPECTED_EVENTS:
            readiness_failures.append({
                "scope": "production_emissions",
                "error": f"expected {EXPECTED_EVENTS} emissions, got {event_total}",
            })
        if duplicate_emissions:
            readiness_failures.append({
                "scope": "duplicates",
                "error": f"duplicate target emissions: {duplicate_emissions}",
            })
        if semantic_failures:
            readiness_failures.append({
                "scope": "semantics",
                "error": f"semantic failures: {len(semantic_failures)}",
            })
        if not emitted_weight_is_consistent:
            readiness_failures.append({
                "scope": "runtime_weight",
                "error": (
                    f"expected emitted runtime weight {RUNTIME_WEIGHT_REFERENCE}, "
                    f"observed min={runtime_min}, max={runtime_max}, mean={runtime_mean}"
                ),
            })
        if production_mutation:
            readiness_failures.append({
                "scope": "production_mutation",
                "error": "production supply-weight configuration was mutated",
            })

        print("INCREASING SUPPLY PRODUCTION PATH READINESS AUDIT")
        print({
            "symbols_requested": len(SYMBOLS),
            "symbols_with_results": len(SYMBOLS) - len(failures),
            "cheap_candidates": cheap_total,
            "production_emissions": event_total,
            "expected_campaign_events": EXPECTED_EVENTS,
            "registry_weight": registry_weight,
            "runtime_weight_reference": RUNTIME_WEIGHT_REFERENCE,
            "runtime_weight_observed": {
                "min": runtime_min,
                "max": runtime_max,
                "mean": runtime_mean,
            },
            "configured_supply_map_weight": float(original_supply_map[TARGET_CODE]),
            "runtime_weight_matches_emission": emitted_weight_is_consistent,
            "duplicate_emissions": duplicate_emissions,
            "semantic_failures": len(semantic_failures),
            "production_path_mutation": production_mutation,
            "failures": readiness_failures,
            "status": "FAIL" if readiness_failures else "PASS",
        })

        if semantic_failures:
            print({"semantic_samples": semantic_failures[:20]})

    finally:
        config.SUPPLY_EVIDENCE_WEIGHTS = original_supply_map


if __name__ == "__main__":
    main()
