"""Exact SUPPLY_DRYING_UP interaction outcome audit.

Freezes the already validated 225 production emissions and measures forward
outcomes by exact same-bar interaction combination. The candidate population
must remain unchanged; no production configuration is mutated.
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
FORWARD_BARS = 8
EXPECTED_GROUPS = {
    "clean": 159,
    "demand:test": 43,
    "demand:no_supply": 19,
    "demand:no_supply+test": 4,
}


def cheap_candidate(metrics: pd.DataFrame, index: int) -> bool:
    row = metrics.iloc[index]
    return (
        Direction(int(row[COL_DIRECTION])) == Direction.DOWN
        and VolumeClass(int(row[COL_VOLUME_CLASS])) <= VolumeClass.LOW
        and SpreadClass(int(row[COL_SPREAD_CLASS])) <= SpreadClass.BELOW_AVERAGE
    )


def outcome(metrics: pd.DataFrame, index: int) -> float:
    start = float(metrics.iloc[index][COL_CLOSE])
    end = float(metrics.iloc[index + FORWARD_BARS][COL_CLOSE])
    return 0.0 if start == 0.0 else end / start - 1.0


def combination(other_codes: set[EvidenceCode]) -> str:
    supply = sorted(
        code.value
        for code in other_codes
        if code in {
            EvidenceCode.BUYING_CLIMAX,
            EvidenceCode.SUPPLY_COMING_IN,
            EvidenceCode.HIDDEN_SUPPLY,
            EvidenceCode.INCREASING_SUPPLY,
            EvidenceCode.UPTHRUST,
            EvidenceCode.NO_DEMAND,
        }
    )
    demand = sorted(
        code.value
        for code in other_codes
        if code in {
            EvidenceCode.NO_SUPPLY,
            EvidenceCode.STOPPING_VOLUME,
            EvidenceCode.SHAKEOUT,
            EvidenceCode.TEST,
            EvidenceCode.DEMAND_COMING_IN,
            EvidenceCode.INCREASING_DEMAND,
            EvidenceCode.SELLING_CLIMAX,
            EvidenceCode.SPRING,
        }
    )
    parts: list[str] = []
    if supply:
        parts.append("supply:" + "+".join(supply))
    if demand:
        parts.append("demand:" + "+".join(demand))
    return " | ".join(parts) if parts else "clean"


def summarize(values: list[float]) -> dict[str, float | int]:
    positive = sum(v > 0.0 for v in values)
    negative = sum(v < 0.0 for v in values)
    flat = sum(v == 0.0 for v in values)
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
    duplicate_emissions = 0
    heavy_context_rebuilds = 0
    failures: list[dict[str, str]] = []
    groups: dict[str, list[float]] = defaultdict(list)

    for symbol in SYMBOLS:
        try:
            metrics = MetricsEngine().calculate(
                daily_to_weekly(download_data(symbol))
            )
            indices = [
                i
                for i in range(1, len(metrics) - FORWARD_BARS)
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
                same_bar = [
                    item for item in result.evidence
                    if item.bar_index == index
                ]
                targets = [
                    item for item in same_bar
                    if item.code is TARGET_CODE
                ]

                if len(targets) > 1:
                    duplicate_emissions += len(targets) - 1
                    continue
                if not targets:
                    continue

                event_total += 1
                other_codes = {
                    item.code
                    for item in same_bar
                    if item.code is not TARGET_CODE
                }
                groups[combination(other_codes)].append(outcome(metrics, index))

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

    for group, expected in EXPECTED_GROUPS.items():
        actual = len(groups.get(group, []))
        if actual != expected:
            failures_out.append({
                "scope": "exact_group_population",
                "error": f"{group}: expected {expected}, got {actual}",
            })

    unexpected = {
        group: len(values)
        for group, values in groups.items()
        if group not in EXPECTED_GROUPS
    }
    if unexpected:
        failures_out.append({
            "scope": "unexpected_combinations",
            "error": repr(unexpected),
        })

    print("SUPPLY_DRYING_UP INTERACTION OUTCOME AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": len(SYMBOLS) - len(failures),
        "cheap_candidates": cheap_total,
        "candidate_events": event_total,
        "expected_events": EXPECTED_EVENTS,
        "exact_groups": len(EXPECTED_GROUPS),
        "group_event_total": sum(len(v) for v in groups.values()),
        "unexpected_combinations": unexpected,
        "target_bar_only": True,
        "point_in_time": True,
        "production_context_used": True,
        "self_conflict_excluded": True,
        "production_path_mutation": False,
        "heavy_context_rebuilds": heavy_context_rebuilds,
        "duplicate_emissions": duplicate_emissions,
        "failures": failures_out,
        "status": "FAIL" if failures_out else "PASS",
    })

    if failures_out:
        return

    clean = summarize(groups["clean"])
    results = {
        group: summarize(groups[group])
        for group in sorted(EXPECTED_GROUPS)
    }
    for group in sorted(EXPECTED_GROUPS):
        if group == "clean":
            continue
        results[group]["positive_decisive_rate_delta_vs_clean"] = (
            results[group]["positive_decisive_rate"]
            - clean["positive_decisive_rate"]
        )
        results[group]["mean_return_delta_vs_clean"] = (
            results[group]["mean_return"]
            - clean["mean_return"]
        )

    print({"reference_clean": clean})
    print({"groups": results})


if __name__ == "__main__":
    main()
