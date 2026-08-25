"""Optimized SUPPLY_DRYING_UP interaction audit.

Freezes the validated 225 production SUPPLY_DRYING_UP emissions and audits
same-bar interactions using the production EvidenceEngine. Self-overlap with
SUPPLY_DRYING_UP is excluded from conflict accounting.
"""
from __future__ import annotations

import os
import sys
from collections import Counter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pandas as pd

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
TARGET_CODE = EvidenceCode.SUPPLY_DRYING_UP
EXPECTED_CANDIDATES = 547
EXPECTED_EVENTS = 225
FORWARD_BARS = 8


def cheap_candidate(metrics: pd.DataFrame, index: int) -> bool:
    row = metrics.iloc[index]
    return (
        Direction(int(row[COL_DIRECTION])) == Direction.DOWN
        and VolumeClass(int(row[COL_VOLUME_CLASS])) <= VolumeClass.LOW
        and SpreadClass(int(row[COL_SPREAD_CLASS])) <= SpreadClass.BELOW_AVERAGE
    )


def main() -> None:
    cheap_total = emitted_total = context_rebuilds = duplicate_emissions = 0
    events_with_supply = events_with_demand = 0
    supply_counts = Counter()
    demand_counts = Counter()
    combinations = Counter()
    failures: list[dict[str, str]] = []

    for symbol in SYMBOLS:
        try:
            metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
            indices = [i for i in range(1, len(metrics) - FORWARD_BARS) if cheap_candidate(metrics, i)]
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
                same_bar = [item for item in result.evidence if item.bar_index == index]
                targets = [item for item in same_bar if item.code is TARGET_CODE]
                if len(targets) > 1:
                    duplicate_emissions += len(targets) - 1
                    continue
                if not targets:
                    continue

                emitted_total += 1
                other = [item.code for item in same_bar if item.code is not TARGET_CODE]
                supply = sorted(code.value for code in other if code in {
                    EvidenceCode.BUYING_CLIMAX, EvidenceCode.SUPPLY_COMING_IN,
                    EvidenceCode.HIDDEN_SUPPLY, EvidenceCode.INCREASING_SUPPLY,
                    EvidenceCode.UPTHRUST, EvidenceCode.NO_DEMAND,
                })
                demand = sorted(code.value for code in other if code in {
                    EvidenceCode.NO_SUPPLY, EvidenceCode.STOPPING_VOLUME,
                    EvidenceCode.SHAKEOUT, EvidenceCode.TEST,
                    EvidenceCode.DEMAND_COMING_IN, EvidenceCode.INCREASING_DEMAND,
                    EvidenceCode.SELLING_CLIMAX, EvidenceCode.SPRING,
                })

                if supply:
                    events_with_supply += 1
                    supply_counts.update(supply)
                if demand:
                    events_with_demand += 1
                    demand_counts.update(demand)

                combination = (
                    "supply:" + "+".join(supply) if supply else "clean"
                )
                if demand:
                    combination += " | demand:" + "+".join(demand)
                combinations[combination] += 1

        except Exception as exc:
            failures.append({"symbol": symbol, "error": str(exc)})

    failures_out = list(failures)
    if cheap_total != EXPECTED_CANDIDATES:
        failures_out.append({"scope": "candidate_population", "error": f"expected {EXPECTED_CANDIDATES}, got {cheap_total}"})
    if emitted_total != EXPECTED_EVENTS:
        failures_out.append({"scope": "production_emissions", "error": f"expected {EXPECTED_EVENTS}, got {emitted_total}"})
    if duplicate_emissions:
        failures_out.append({"scope": "duplicates", "error": f"duplicate emissions: {duplicate_emissions}"})

    print("SUPPLY_DRYING_UP INTERACTION AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": len(SYMBOLS) - len(failures),
        "cheap_candidates": cheap_total,
        "candidate_events": emitted_total,
        "expected_events": EXPECTED_EVENTS,
        "events_with_supply_interaction": events_with_supply,
        "events_with_demand_interaction": events_with_demand,
        "aggregate_supply_interactions": dict(supply_counts),
        "aggregate_demand_interactions": dict(demand_counts),
        "self_conflict_excluded": True,
        "target_bar_only": True,
        "point_in_time": True,
        "production_context_used": True,
        "production_emission_authority": True,
        "heavy_context_rebuilds": context_rebuilds,
        "duplicate_emissions": duplicate_emissions,
        "failures": failures_out,
        "status": "FAIL" if failures_out else "PASS",
    })
    print({
        "combination_groups": len(combinations),
        "group_event_total": sum(combinations.values()),
        "combinations": dict(combinations),
    })


if __name__ == "__main__":
    main()
