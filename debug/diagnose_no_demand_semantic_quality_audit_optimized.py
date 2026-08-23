"""Semantic-quality audit for NO_DEMAND.

Analysis-only. Mandatory requirements are validated by the production emission.
Confirmations are measured separately and are not treated as emission failures.
"""
from __future__ import annotations

import os
import sys

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from data import daily_to_weekly, download_data
from engine.columns import (
    COL_CLOSE_POSITION,
    COL_DIRECTION,
    COL_SPREAD_CLASS,
    COL_VOLUME_CLASS,
)
from evidence.engine import EvidenceEngine
from metrics_engine import MetricsEngine
from models import ClosePosition, Direction, EvidenceCode, SpreadClass, VolumeClass
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
TARGET_CODE = EvidenceCode.NO_DEMAND
EXPECTED_CHEAP_CANDIDATES = 202
EXPECTED_EVENTS = 109
FORWARD_BARS = 8


def cheap_candidate(metrics: pd.DataFrame, index: int) -> bool:
    row = metrics.iloc[index]
    return (
        Direction(int(row[COL_DIRECTION])) == Direction.UP
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
    normal_rejections = 0
    duplicate_emissions = 0
    failures: list[dict[str, str]] = []
    semantic_counts = {
        "bullish_environment": 0,
        "bullish_bar": 0,
        "low_volume": 0,
        "narrow_spread": 0,
        "volume_decreasing_confirmation": 0,
        "weak_close_confirmation": 0,
    }
    semantic_failures: list[dict[str, object]] = []
    heavy_context_rebuilds = 0

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
                    normal_rejections += 1
                    continue

                event_total += 1
                row = metrics.iloc[index]
                previous = metrics.iloc[index - 1]

                bullish_environment = trend.structure.direction.name == "UP"
                bullish_bar = Direction(int(row[COL_DIRECTION])) == Direction.UP
                low_volume = VolumeClass(int(row[COL_VOLUME_CLASS])) <= VolumeClass.LOW
                narrow_spread = SpreadClass(int(row[COL_SPREAD_CLASS])) <= SpreadClass.NARROW
                volume_decreasing = (
                    VolumeClass(int(row[COL_VOLUME_CLASS]))
                    < VolumeClass(int(previous[COL_VOLUME_CLASS]))
                )
                weak_close = ClosePosition(int(row[COL_CLOSE_POSITION])) in (
                    ClosePosition.LOWER,
                    ClosePosition.ON_LOW,
                )

                mandatory_checks = {
                    "bullish_environment": bullish_environment,
                    "bullish_bar": bullish_bar,
                    "low_volume": low_volume,
                    "narrow_spread": narrow_spread,
                }
                confirmation_checks = {
                    "volume_decreasing_confirmation": volume_decreasing,
                    "weak_close_confirmation": weak_close,
                }

                for key, passed in mandatory_checks.items():
                    if passed:
                        semantic_counts[key] += 1
                for key, passed in confirmation_checks.items():
                    if passed:
                        semantic_counts[key] += 1

                failed_mandatory = [
                    key for key, passed in mandatory_checks.items() if not passed
                ]
                if failed_mandatory:
                    semantic_failures.append({
                        "symbol": symbol,
                        "bar": index,
                        "failed_mandatory_semantics": failed_mandatory,
                    })
        except Exception as exc:
            failures.append({"symbol": symbol, "error": str(exc)})

    failures_out = list(failures)
    if cheap_total != EXPECTED_CHEAP_CANDIDATES:
        failures_out.append({
            "scope": "candidate_population",
            "error": f"expected {EXPECTED_CHEAP_CANDIDATES} cheap candidates, got {cheap_total}",
        })
    if event_total != EXPECTED_EVENTS:
        failures_out.append({
            "scope": "candidate_events",
            "error": f"expected {EXPECTED_EVENTS} emitted events, got {event_total}",
        })
    if duplicate_emissions:
        failures_out.append({
            "scope": "duplicates",
            "error": f"duplicate emissions: {duplicate_emissions}",
        })
    if semantic_failures:
        failures_out.append({
            "scope": "mandatory_semantics",
            "error": f"mandatory semantic failures: {len(semantic_failures)}",
        })

    print("NO_DEMAND SEMANTIC QUALITY AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": len(SYMBOLS) - len(failures),
        "cheap_candidates": cheap_total,
        "candidate_events": event_total,
        "expected_candidate_events": EXPECTED_EVENTS,
        "semantic_counts": semantic_counts,
        "mandatory_semantic_failures": len(semantic_failures),
        "normal_detector_rejections": normal_rejections,
        "duplicate_emissions": duplicate_emissions,
        "heavy_context_rebuilds": heavy_context_rebuilds,
        "target_bar_only": True,
        "point_in_time": True,
        "production_context_used": True,
        "production_emission_authority": True,
        "confirmations_are_non_mandatory": True,
        "failures": failures_out,
        "status": "FAIL" if failures_out else "PASS",
    })

    if semantic_failures:
        print({"semantic_samples": semantic_failures[:20]})


if __name__ == "__main__":
    main()
