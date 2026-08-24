"""UPTHRUST exact-combination outcome audit.

Analysis-only. Freezes the validated 1,319 cheap-candidate / 289-emission
population and measures outcomes for the exact production same-bar
combinations. No production mutation, no qualification replay.
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


EXACT_GROUPS = {
    ("BUYING_CLIMAX",): "UPTHRUST + BUYING_CLIMAX",
    ("BUYING_CLIMAX", "INCREASING_DEMAND"): "UPTHRUST + BUYING_CLIMAX + INCREASING_DEMAND",
    ("BUYING_CLIMAX", "HIDDEN_SUPPLY"): "UPTHRUST + BUYING_CLIMAX + HIDDEN_SUPPLY",
    (
        "BUYING_CLIMAX", "HIDDEN_SUPPLY", "INCREASING_DEMAND"
    ): "UPTHRUST + BUYING_CLIMAX + HIDDEN_SUPPLY + INCREASING_DEMAND",
    (
        "BUYING_CLIMAX", "INCREASING_DEMAND", "SPRING"
    ): "UPTHRUST + BUYING_CLIMAX + INCREASING_DEMAND + SPRING",
}


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


def main() -> None:
    cheap_total = 0
    event_total = 0
    duplicate_emissions = 0
    heavy_context_rebuilds = 0
    failures: list[dict[str, str]] = []
    groups: dict[str, list[float]] = defaultdict(list)
    unexpected: dict[str, int] = defaultdict(int)

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
                codes = tuple(sorted(supply + demand))

                group_name = EXACT_GROUPS.get(codes)
                if group_name is None:
                    unexpected[" + ".join(codes) if codes else "clean"] += 1
                    continue

                groups[group_name].append(forward_return(metrics, index))

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
    if unexpected:
        failures_out.append({
            "scope": "unexpected_combinations",
            "error": f"unexpected exact interaction groups: {dict(unexpected)}",
        })

    print("UPTHRUST EXACT COMBINATION OUTCOME AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": len(SYMBOLS) - len(failures),
        "cheap_candidates": cheap_total,
        "candidate_events": event_total,
        "expected_events": EXPECTED_EVENTS,
        "exact_groups": len(groups),
        "group_event_total": sum(len(v) for v in groups.values()),
        "unexpected_combinations": dict(sorted(unexpected.items())),
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

    print({
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
                    if any(r != 0.0 for r in values) else 0.0
                ),
                "mean_return": sum(values) / len(values) if values else 0.0,
            }
            for name, values in sorted(groups.items())
        }
    })


if __name__ == "__main__":
    main()
