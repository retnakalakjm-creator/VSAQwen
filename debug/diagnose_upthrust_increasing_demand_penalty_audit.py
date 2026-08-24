"""UPTHRUST + INCREASING_DEMAND interaction penalty study.

Analysis-only. Uses the frozen 289 UPTHRUST production-emission population.
No production scoring map or detector behavior is changed. The exact
UPTHRUST + BUYING_CLIMAX + INCREASING_DEMAND subgroup is compared against the
UPTHRUST + BUYING_CLIMAX reference subgroup and, separately, against all other
UPTHRUST events.
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
    "BHARTIARTL.NS",
    "HDFCBANK.NS",
    "ICICIBANK.NS",
    "INFY.NS",
    "LT.NS",
    "RELIANCE.NS",
    "SBIN.NS",
    "TCS.NS",
)
TARGET_CODE = EvidenceCode.UPTHRUST
EXPECTED_CANDIDATES = 1319
EXPECTED_EVENTS = 289
EXPECTED_PURE_INCREASING_DEMAND = 212
EXPECTED_VARIANT_INCREASING_DEMAND = 12
EXPECTED_WITHOUT_INCREASING_DEMAND = 65
FORWARD_BARS = 8


def cheap_candidate(metrics: pd.DataFrame, index: int) -> bool:
    row = metrics.iloc[index]
    return (
        Direction(int(row[COL_DIRECTION])) == Direction.UP
        and VolumeClass(int(row[COL_VOLUME_CLASS])) >= VolumeClass.HIGH
        and SpreadClass(int(row[COL_SPREAD_CLASS])) >= SpreadClass.ABOVE_AVERAGE
    )


def group_for_event(evidence) -> str:
    codes = {
        item.code
        for item in evidence
        if item.bar_index == evidence[0].bar_index
        and item.code is not TARGET_CODE
    }
    if (
        EvidenceCode.BUYING_CLIMAX in codes
        and EvidenceCode.INCREASING_DEMAND in codes
        and EvidenceCode.HIDDEN_SUPPLY not in codes
        and EvidenceCode.SPRING not in codes
    ):
        return "pure_upthrust_buying_climax_increasing_demand"
    if (
        EvidenceCode.BUYING_CLIMAX in codes
        and EvidenceCode.INCREASING_DEMAND in codes
    ):
        return "variant_increasing_demand"
    if EvidenceCode.BUYING_CLIMAX in codes:
        return "upthrust_buying_climax_only"
    return "other_upthrust"


def main() -> None:
    cheap_total = 0
    emission_total = 0
    duplicate_emissions = 0
    heavy_context_rebuilds = 0
    failures: list[dict[str, str]] = []
    groups: dict[str, list[float]] = defaultdict(list)

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

                same_bar = [
                    item for item in result.evidence
                    if item.bar_index == index
                ]

                class _E:
                    pass

                marker = _E()
                marker.bar_index = index
                marker_group = group_for_event(same_bar)
                start = float(metrics.iloc[index][COL_CLOSE])
                end = float(metrics.iloc[index + FORWARD_BARS][COL_CLOSE])
                forward = 0.0 if start == 0.0 else end / start - 1.0
                groups[marker_group].append(forward)
                emission_total += 1

        except Exception as exc:
            failures.append({"symbol": symbol, "error": str(exc)})

    failures_out = list(failures)

    if cheap_total != EXPECTED_CANDIDATES:
        failures_out.append({
            "scope": "candidate_population",
            "error": f"expected {EXPECTED_CANDIDATES}, got {cheap_total}",
        })
    if emission_total != EXPECTED_EVENTS:
        failures_out.append({
            "scope": "production_emissions",
            "error": f"expected {EXPECTED_EVENTS}, got {emission_total}",
        })
    if duplicate_emissions:
        failures_out.append({
            "scope": "duplicates",
            "error": f"duplicate emissions: {duplicate_emissions}",
        })

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

    with_demand = groups["pure_upthrust_buying_climax_increasing_demand"]
    variant_demand = groups["variant_increasing_demand"]
    without_demand = groups["upthrust_buying_climax_only"]

    rate_delta = (
        summarize(with_demand)["positive_decisive_rate"]
        - summarize(without_demand)["positive_decisive_rate"]
    )
    return_delta = (
        summarize(with_demand)["mean_return"]
        - summarize(without_demand)["mean_return"]
    )

    if len(with_demand) != EXPECTED_PURE_INCREASING_DEMAND:
        failures_out.append({
            "scope": "pure_increasing_demand_group",
            "error": f"expected {EXPECTED_PURE_INCREASING_DEMAND}, got {len(with_demand)}",
        })
    if len(without_demand) != EXPECTED_WITHOUT_INCREASING_DEMAND:
        failures_out.append({
            "scope": "without_increasing_demand_group",
            "error": f"expected {EXPECTED_WITHOUT_INCREASING_DEMAND}, got {len(without_demand)}",
        })

    if len(variant_demand) != EXPECTED_VARIANT_INCREASING_DEMAND:
        failures_out.append({
            "scope": "variant_increasing_demand_group",
            "error": f"expected {EXPECTED_VARIANT_INCREASING_DEMAND}, got {len(variant_demand)}",
        })

    print("UPTHRUST + INCREASING_DEMAND PENALTY AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": len(SYMBOLS) - len(failures),
        "cheap_candidates": cheap_total,
        "production_emissions": emission_total,
        "expected_events": EXPECTED_EVENTS,
        "heavy_context_rebuilds": heavy_context_rebuilds,
        "target_bar_only": True,
        "point_in_time": True,
        "production_context_used": True,
        "production_path_mutation": False,
        "duplicate_emissions": duplicate_emissions,
        "failures": failures_out,
        "status": "FAIL" if failures_out else "PASS",
    })

    print({
        "pure_increasing_demand": summarize(with_demand),
        "variant_increasing_demand": summarize(variant_demand),
        "buying_climax_only_reference": summarize(without_demand),
        "positive_decisive_rate_delta": rate_delta,
        "mean_return_delta": return_delta,
        "variant_population_total": len(variant_demand),
        "provisional_penalty_decision": (
            "STUDY_ONLY_NO_PRODUCTION_CHANGE"
            if not failures_out else "BLOCKED"
        ),
    })


if __name__ == "__main__":
    main()
