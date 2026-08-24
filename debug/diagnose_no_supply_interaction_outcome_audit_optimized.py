"""NO_SUPPLY interaction-outcome audit.

Analysis-only. Uses the frozen NO_SUPPLY candidate population and point-in-time
production evidence. The target event is excluded from its own interaction set.
Interactions are grouped into clean / other_supply / other_demand / mixed, then
compared by forward 8-bar outcome.
"""
from __future__ import annotations

import os
import sys
from collections import defaultdict

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from data import daily_to_weekly, download_data
from engine.columns import (
    COL_CLOSE,
    COL_DIRECTION,
    COL_SPREAD_CLASS,
    COL_VOLUME_CLASS,
)
from evidence.engine import EvidenceEngine
from metrics_engine import MetricsEngine
from models import Direction, EvidenceCategory, EvidenceCode, SpreadClass, VolumeClass
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


def forward_return(metrics: pd.DataFrame, index: int) -> float:
    start = float(metrics.iloc[index][COL_CLOSE])
    end = float(metrics.iloc[index + FORWARD_BARS][COL_CLOSE])
    return 0.0 if start == 0.0 else end / start - 1.0


def classify_interaction(items: list) -> tuple[str, tuple[str, ...]]:
    others = [item for item in items if item.code is not TARGET_CODE]

    supply = sorted({
        item.code.name
        for item in others
        if item.category == EvidenceCategory.SUPPLY
    })
    demand = sorted({
        item.code.name
        for item in others
        if item.category == EvidenceCategory.DEMAND
    })

    if not supply and not demand:
        return "clean", ()
    if supply and not demand:
        return "other_supply", tuple(supply)
    if demand and not supply:
        return "other_demand", tuple(demand)
    return "mixed", tuple(sorted(supply + demand))


def main() -> None:
    cheap_total = 0
    event_total = 0
    duplicate_emissions = 0
    failures: list[dict[str, str]] = []
    interaction_events = 0
    supply_interaction_events = 0
    demand_interaction_events = 0
    context_rebuilds = 0

    groups: dict[str, list[float]] = defaultdict(list)
    interactions: dict[str, int] = defaultdict(int)

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
                context_rebuilds += 1

                result = EvidenceEngine().collect(
                    metrics=replay,
                    trend=trend,
                    structural_swings=tuple(
                        trend.structure.structural_swings
                    ),
                )

                target = [
                    item
                    for item in result.evidence
                    if item.code is TARGET_CODE
                    and item.bar_index == index
                ]

                if len(target) > 1:
                    duplicate_emissions += len(target) - 1
                    continue

                if not target:
                    continue

                event_total += 1

                same_bar = [
                    item
                    for item in result.evidence
                    if item.bar_index == index
                    and item.code is not TARGET_CODE
                ]

                group, codes = classify_interaction(same_bar)
                groups[group].append(forward_return(metrics, index))

                if codes:
                    interaction_events += 1
                    interactions[" + ".join(codes)] += 1

                if any(
                    item.category == EvidenceCategory.SUPPLY
                    and item.code is not TARGET_CODE
                    for item in same_bar
                ):
                    supply_interaction_events += 1

                if any(
                    item.category == EvidenceCategory.DEMAND
                    and item.code is not TARGET_CODE
                    for item in same_bar
                ):
                    demand_interaction_events += 1

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
            "scope": "candidate_events",
            "error": (
                f"expected {EXPECTED_EVENTS} emitted events, "
                f"got {event_total}"
            ),
        })

    if duplicate_emissions:
        failures_out.append({
            "scope": "duplicates",
            "error": (
                f"duplicate emissions: {duplicate_emissions}"
            ),
        })

    print("NO_SUPPLY INTERACTION OUTCOME AUDIT")
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
        "events_with_supply_interaction": supply_interaction_events,
        "events_with_demand_interaction": demand_interaction_events,
        "self_conflict_excluded": True,
        "target_bar_only": True,
        "point_in_time": True,
        "production_context_used": True,
        "heavy_context_rebuilds": context_rebuilds,
        "duplicate_emissions": duplicate_emissions,
        "failures": failures_out,
        "status": "FAIL" if failures_out else "PASS",
    })

    total_group_events = sum(len(values) for values in groups.values())
    print({
        "combination_groups": len(groups),
        "group_event_total": total_group_events,
        "groups": {
            name: {
                "events": len(values),
                "positive": sum(r > 0.0 for r in values),
                "negative": sum(r < 0.0 for r in values),
                "flat": sum(r == 0.0 for r in values),
                "decisive": sum(r != 0.0 for r in values),
                "positive_decisive_rate": (
                    sum(r > 0.0 for r in values)
                    / sum(r != 0.0 for r in values)
                    if sum(r != 0.0 for r in values)
                    else 0.0
                ),
                "mean_return": (
                    sum(values) / len(values) if values else 0.0
                ),
            }
            for name, values in sorted(groups.items())
        },
    })
    print({
        "interaction_combinations": dict(
            sorted(interactions.items())
        )
    })


if __name__ == "__main__":
    main()
