"""Optimized SUPPLY_DRYING_UP standalone decision-value audit.

Compares the frozen production-emission population against the eligible-market
baseline using the same 8-bar forward return contract used by prior event audits.
Analysis-only; production configuration is never mutated.
"""
from __future__ import annotations

import os
import sys

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
    candidate_events = 0
    detector_rejections = 0
    duplicate_emissions = 0
    candidate_returns: list[float] = []
    market_returns: list[float] = []
    failures: list[dict[str, str]] = []
    context_rebuilds = 0
    market_population_total = 0

    for symbol in SYMBOLS:
        try:
            metrics = MetricsEngine().calculate(
                daily_to_weekly(download_data(symbol))
            )

            candidate_indices = [
                i
                for i in range(1, len(metrics) - FORWARD_BARS)
                if cheap_candidate(metrics, i)
            ]
            cheap_total += len(candidate_indices)
            candidate_set = set(candidate_indices)

            # Eligible market = all target bars with valid forward outcome.
            for i in range(1, len(metrics) - FORWARD_BARS):
                market_returns.append(outcome(metrics, i))
            market_population_total += max(0, len(metrics) - FORWARD_BARS - 1)

            for index in candidate_indices:
                replay = metrics.iloc[: index + 1].copy()
                trend = TrendAnalyzer().analyze(replay)
                context_rebuilds += 1

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
                    detector_rejections += 1
                    continue

                candidate_events += 1
                candidate_returns.append(outcome(metrics, index))

        except Exception as exc:
            failures.append({"symbol": symbol, "error": str(exc)})

    failures_out = list(failures)
    if cheap_total != EXPECTED_CANDIDATES:
        failures_out.append({
            "scope": "candidate_population",
            "error": f"expected {EXPECTED_CANDIDATES}, got {cheap_total}",
        })
    if candidate_events != EXPECTED_EVENTS:
        failures_out.append({
            "scope": "production_emissions",
            "error": f"expected {EXPECTED_EVENTS}, got {candidate_events}",
        })
    if duplicate_emissions:
        failures_out.append({
            "scope": "duplicates",
            "error": f"duplicate emissions: {duplicate_emissions}",
        })

    candidate_summary = summarize(candidate_returns)
    market_summary = summarize(market_returns)

    print("SUPPLY_DRYING_UP DECISION-VALUE AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": len(SYMBOLS) - len(failures),
        "cheap_candidates": cheap_total,
        "candidate_events": candidate_events,
        "eligible_market_events": len(market_returns),
        "candidate_summary": candidate_summary,
        "eligible_market_summary": market_summary,
        "positive_decisive_rate_lift_vs_market": (
            candidate_summary["positive_decisive_rate"]
            - market_summary["positive_decisive_rate"]
        ),
        "mean_return_lift_vs_market": (
            candidate_summary["mean_return"] - market_summary["mean_return"]
        ),
        "candidate_share_of_eligible": (
            candidate_events / len(market_returns)
            if market_returns else 0.0
        ),
        "frozen_candidate_population": True,
        "target_bar_only": True,
        "point_in_time": True,
        "production_path_mutation": False,
        "production_context_used": True,
        "production_emission_authority": True,
        "normal_detector_rejections": detector_rejections,
        "heavy_context_rebuilds": context_rebuilds,
        "market_population_expected_from_data": market_population_total,
        "duplicate_emissions": duplicate_emissions,
        "failures": failures_out,
        "status": "FAIL" if failures_out else "PASS",
    })


if __name__ == "__main__":
    main()
