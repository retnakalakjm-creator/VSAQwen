"""UPTHRUST interaction-outcome audit.

Analysis-only. Uses the validated 1,319 cheap-candidate / 289-emission
population and measures forward 8-bar outcomes by same-bar interaction group.
UPTHRUST itself is excluded from the interaction set.
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
from engine.columns import COL_CLOSE, COL_DIRECTION, COL_SPREAD_CLASS, COL_VOLUME_CLASS
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


def forward_return(metrics: pd.DataFrame, index: int) -> float:
    start = float(metrics.iloc[index][COL_CLOSE])
    end = float(metrics.iloc[index + FORWARD_BARS][COL_CLOSE])
    return 0.0 if start == 0.0 else end / start - 1.0


def classify(items: list) -> tuple[str, tuple[str, ...]]:
    others = [item for item in items if item.code is not TARGET_CODE]
    supply = sorted({item.code.name for item in others if item.category is EvidenceCategory.SUPPLY})
    demand = sorted({item.code.name for item in others if item.category is EvidenceCategory.DEMAND})
    if not supply and not demand:
        return "clean", ()
    if supply and not demand:
        return "other_supply", tuple(supply)
    if demand and not supply:
        return "other_demand", tuple(demand)
    return "mixed", tuple(sorted(supply + demand))


def summarize(values: list[float]) -> dict[str, float | int]:
    positive = sum(v > 0 for v in values)
    negative = sum(v < 0 for v in values)
    flat = sum(v == 0 for v in values)
    decisive = positive + negative
    return {
        "events": len(values),
        "positive": positive,
        "negative": negative,
        "flat": flat,
        "decisive": decisive,
        "positive_decisive_rate": positive / decisive if decisive else 0.0,
        "mean_return": sum(values) / len(values) if values else 0.0,
    }


def main() -> None:
    cheap_total = 0
    event_total = 0
    normal_detector_rejections = 0
    duplicate_emissions = 0
    heavy_context_rebuilds = 0
    interaction_events = 0
    supply_interaction_events = 0
    demand_interaction_events = 0
    failures: list[dict[str, str]] = []
    groups: dict[str, list[float]] = defaultdict(list)
    combinations: dict[str, int] = defaultdict(int)

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
                    normal_detector_rejections += 1
                    continue

                event_total += 1
                same_bar = [
                    item for item in result.evidence
                    if item.bar_index == index and item.code is not TARGET_CODE
                ]
                group, codes = classify(same_bar)
                groups[group].append(forward_return(metrics, index))

                if codes:
                    interaction_events += 1
                    combinations[" + ".join(codes)] += 1
                if any(item.category is EvidenceCategory.SUPPLY for item in same_bar):
                    supply_interaction_events += 1
                if any(item.category is EvidenceCategory.DEMAND for item in same_bar):
                    demand_interaction_events += 1

        except Exception as exc:
            failures.append({"symbol": symbol, "error": str(exc)})

    failures_out = list(failures)
    if cheap_total != EXPECTED_CANDIDATES:
        failures_out.append({"scope": "candidate_population", "error": f"expected {EXPECTED_CANDIDATES}, got {cheap_total}"})
    if event_total != EXPECTED_EVENTS:
        failures_out.append({"scope": "production_emissions", "error": f"expected {EXPECTED_EVENTS}, got {event_total}"})
    if duplicate_emissions:
        failures_out.append({"scope": "duplicates", "error": f"duplicate emissions: {duplicate_emissions}"})

    print("UPTHRUST INTERACTION OUTCOME AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": len(SYMBOLS) - len(failures),
        "cheap_candidates": cheap_total,
        "candidate_events": event_total,
        "expected_events": EXPECTED_EVENTS,
        "events_with_interaction": interaction_events,
        "interaction_rate": interaction_events / event_total if event_total else 0.0,
        "events_with_supply_interaction": supply_interaction_events,
        "events_with_demand_interaction": demand_interaction_events,
        "self_conflict_excluded": True,
        "target_bar_only": True,
        "point_in_time": True,
        "production_context_used": True,
        "heavy_context_rebuilds": heavy_context_rebuilds,
        "duplicate_emissions": duplicate_emissions,
        "normal_detector_rejections": normal_detector_rejections,
        "failures": failures_out,
        "status": "FAIL" if failures_out else "PASS",
    })
    print({
        "combination_groups": len(groups),
        "group_event_total": sum(len(v) for v in groups.values()),
        "groups": {name: summarize(values) for name, values in sorted(groups.items())},
    })
    print({"interaction_combinations": dict(sorted(combinations.items()))})


if __name__ == "__main__":
    main()
