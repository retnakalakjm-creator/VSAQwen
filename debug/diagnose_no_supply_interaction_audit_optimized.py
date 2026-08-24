"""Optimized same-bar interaction audit for NO_SUPPLY.

Analysis-only. Replays the frozen NO_SUPPLY candidate population and uses the
production EvidenceEngine emission set at the target bar. The target
NO_SUPPLY evidence is excluded from conflict classification so an event cannot
conflict with itself.
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

TARGET_CODE = EvidenceCode.NO_SUPPLY
EXPECTED_CHEAP_CANDIDATES = 225
EXPECTED_EVENTS = 23
FORWARD_BARS = 8

SUPPLY_CODES = {
    EvidenceCode.BUYING_CLIMAX,
    EvidenceCode.SUPPLY_COMING_IN,
    EvidenceCode.INCREASING_SUPPLY,
    EvidenceCode.HIDDEN_SUPPLY,
    EvidenceCode.SUPPLY_DRYING_UP,
    EvidenceCode.SUPPLY_HIGH_VOLUME,
    EvidenceCode.SUPPLY_WIDE_SPREAD,
    EvidenceCode.SUPPLY_ABSORPTION,
    EvidenceCode.UPTHRUST,
    EvidenceCode.NO_DEMAND,
}

DEMAND_CODES = {
    EvidenceCode.STOPPING_VOLUME,
    EvidenceCode.DEMAND_COMING_IN,
    EvidenceCode.INCREASING_DEMAND,
    EvidenceCode.HIDDEN_DEMAND,
    EvidenceCode.DEMAND_DRYING_UP,
    EvidenceCode.TEST,
    EvidenceCode.SHAKEOUT,
    EvidenceCode.SPRING,
    EvidenceCode.SELLING_CLIMAX,
}


def cheap_candidate(metrics: pd.DataFrame, index: int) -> bool:
    row = metrics.iloc[index]
    return (
        Direction(int(row[COL_DIRECTION])) == Direction.DOWN
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
    cheap_total = 0
    event_total = 0
    interaction_events = 0
    supply_conflict_events = 0
    demand_interaction_events = 0
    duplicate_emissions = 0
    heavy_context_rebuilds = 0
    failures: list[dict[str, str]] = []

    aggregate_supply = Counter()
    aggregate_demand = Counter()
    combinations = Counter()

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
                heavy_context_rebuilds += 1

                result = EvidenceEngine().collect(
                    metrics=replay,
                    trend=trend,
                    structural_swings=tuple(
                        trend.structure.structural_swings
                    ),
                )

                target_events = [
                    item
                    for item in result.evidence
                    if item.code is TARGET_CODE
                    and item.bar_index == index
                ]

                if len(target_events) > 1:
                    duplicate_emissions += len(target_events) - 1
                    continue

                if not target_events:
                    continue

                event_total += 1

                # Target-bar only; exclude NO_SUPPLY itself from all interaction
                # and contradiction counting.
                same_bar = [
                    item
                    for item in result.evidence
                    if item.bar_index == index
                    and item.code is not TARGET_CODE
                ]

                supply_codes = sorted(
                    {
                        item.code.name
                        for item in same_bar
                        if item.code in SUPPLY_CODES
                    }
                )
                demand_codes = sorted(
                    {
                        item.code.name
                        for item in same_bar
                        if item.code in DEMAND_CODES
                    }
                )

                if supply_codes or demand_codes:
                    interaction_events += 1

                for code in supply_codes:
                    aggregate_supply[code] += 1
                    supply_conflict_events += 1

                for code in demand_codes:
                    aggregate_demand[code] += 1
                    demand_interaction_events += 1

                combination = []
                if supply_codes:
                    combination.append(
                        "supply:" + "+".join(supply_codes)
                    )
                if demand_codes:
                    combination.append(
                        "demand:" + "+".join(demand_codes)
                    )

                combinations[
                    " | ".join(combination) if combination else "clean"
                ] += 1

        except Exception as exc:
            failures.append({"symbol": symbol, "error": str(exc)})

    failures_out = list(failures)

    if cheap_total != EXPECTED_CHEAP_CANDIDATES:
        failures_out.append({
            "scope": "candidate_population",
            "error": (
                f"expected {EXPECTED_CHEAP_CANDIDATES} cheap candidates, "
                f"got {cheap_total}"
            ),
        })

    if event_total != EXPECTED_EVENTS:
        failures_out.append({
            "scope": "target_events",
            "error": (
                f"expected {EXPECTED_EVENTS} NO_SUPPLY emissions, "
                f"got {event_total}"
            ),
        })

    if duplicate_emissions:
        failures_out.append({
            "scope": "duplicates",
            "error": (
                f"duplicate target emissions: {duplicate_emissions}"
            ),
        })

    print("NO_SUPPLY INTERACTION AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": len(SYMBOLS) - len(failures),
        "cheap_candidates": cheap_total,
        "candidate_events": event_total,
        "expected_events": EXPECTED_EVENTS,
        "events_with_interaction": interaction_events,
        "interaction_rate": (
            interaction_events / event_total if event_total else 0.0
        ),
        "events_with_supply_conflict": supply_conflict_events,
        "aggregate_supply_interactions": dict(
            sorted(aggregate_supply.items())
        ),
        "demand_interaction_events": demand_interaction_events,
        "aggregate_demand_interactions": dict(
            sorted(aggregate_demand.items())
        ),
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
        "combinations": dict(combinations),
    })


if __name__ == "__main__":
    main()
