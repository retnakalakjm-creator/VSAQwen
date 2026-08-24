"""UPTHRUST interaction / contradiction audit.

Analysis-only. Uses the validated UPTHRUST candidate boundary and production
emissions, then inspects same-bar interactions excluding UPTHRUST itself.
"""
from __future__ import annotations

import os
import sys
from collections import Counter

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from data import daily_to_weekly, download_data
from engine.columns import COL_DIRECTION, COL_SPREAD_CLASS, COL_VOLUME_CLASS
from evidence.engine import EvidenceEngine
from metrics_engine import MetricsEngine
from models import Direction, EvidenceCategory, EvidenceCode, SpreadClass, VolumeClass
from trend import TrendAnalyzer

SYMBOLS = (
    "BHARTIARTL.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "LT.NS", "RELIANCE.NS", "SBIN.NS", "TCS.NS",
)
TARGET_CODE = EvidenceCode.UPTHRUST
EXPECTED_CANDIDATES = 1319
EXPECTED_EVENTS = 289
FORWARD_BARS = 8


def cheap_candidate(metrics: pd.DataFrame, index: int) -> bool:
    row = metrics.iloc[index]
    return (
        Direction(int(row[COL_DIRECTION])) == Direction.UP
        and VolumeClass(int(row[COL_VOLUME_CLASS])) >= VolumeClass.HIGH
        and SpreadClass(int(row[COL_SPREAD_CLASS])) >= SpreadClass.ABOVE_AVERAGE
    )


def main() -> None:
    cheap_total = 0
    event_total = 0
    interaction_events = 0
    supply_interaction_events = 0
    demand_interaction_events = 0
    duplicate_emissions = 0
    heavy_context_rebuilds = 0
    failures: list[dict[str, str]] = []
    supply_counts = Counter()
    demand_counts = Counter()
    combinations = Counter()

    for symbol in SYMBOLS:
        try:
            metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
            indices = [
                i for i in range(1, len(metrics) - FORWARD_BARS)
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

                event_total += 1
                same_bar = [
                    item for item in result.evidence
                    if item.bar_index == index and item.code is not TARGET_CODE
                ]

                supply = sorted({
                    item.code.name for item in same_bar
                    if item.category == EvidenceCategory.SUPPLY
                })
                demand = sorted({
                    item.code.name for item in same_bar
                    if item.category == EvidenceCategory.DEMAND
                })

                if supply or demand:
                    interaction_events += 1
                for code in supply:
                    supply_counts[code] += 1
                    supply_interaction_events += 1
                for code in demand:
                    demand_counts[code] += 1
                    demand_interaction_events += 1

                parts = []
                if supply:
                    parts.append("supply:" + "+".join(supply))
                if demand:
                    parts.append("demand:" + "+".join(demand))
                combinations[" | ".join(parts) if parts else "clean"] += 1

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
    if duplicate_emissions:
        failures_out.append({
            "scope": "duplicates",
            "error": f"duplicate emissions: {duplicate_emissions}",
        })

    print("UPTHRUST INTERACTION AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": len(SYMBOLS) - len(failures),
        "cheap_candidates": cheap_total,
        "candidate_events": event_total,
        "expected_events": EXPECTED_EVENTS,
        "events_with_interaction": interaction_events,
        "interaction_rate": interaction_events / event_total if event_total else 0.0,
        "events_with_supply_interaction": supply_interaction_events,
        "aggregate_supply_interactions": dict(sorted(supply_counts.items())),
        "demand_interaction_events": demand_interaction_events,
        "aggregate_demand_interactions": dict(sorted(demand_counts.items())),
        "self_conflict_excluded": True,
        "target_bar_only": True,
        "point_in_time": True,
        "production_context_used": True,
        "heavy_context_rebuilds": heavy_context_rebuilds,
        "duplicate_emissions": duplicate_emissions,
        "failures": failures_out,
        "status": "FAIL" if failures_out else "PASS",
    })
    print({
        "combination_groups": len(combinations),
        "group_event_total": sum(combinations.values()),
        "combinations": dict(sorted(combinations.items())),
    })


if __name__ == "__main__":
    main()
