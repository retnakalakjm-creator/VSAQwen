"""NO_SUPPLY candidate-population audit.

Analysis-only. Uses a cheap bar-level prefilter, then checks actual production
NO_SUPPLY emission from the point-in-time EvidenceEngine. Confirmation fields
are not treated as mandatory requirements.
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
    COL_CLOSE,
    COL_DIRECTION,
    COL_SPREAD_CLASS,
    COL_VOLUME_CLASS,
)
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
FORWARD_BARS = 8


def cheap_candidate(metrics: pd.DataFrame, index: int) -> bool:
    """Broad demand-side absence gate; production emission is authoritative."""
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
    cheap_candidates = 0
    candidate_events = 0
    normal_detector_rejections = 0
    duplicate_emissions = 0
    semantic_failures = 0
    heavy_context_rebuilds = 0
    failures: list[dict[str, str]] = []
    outcomes: list[float] = []

    for symbol in SYMBOLS:
        try:
            metrics = MetricsEngine().calculate(
                daily_to_weekly(download_data(symbol))
            )
            indices = candidate_indices(metrics)
            cheap_candidates += len(indices)

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
                    normal_detector_rejections += 1
                    continue

                emitted = targets[0]
                candidate_events += 1

                if emitted.code is not TARGET_CODE or emitted.bar_index != index:
                    semantic_failures += 1
                    continue

                close = float(metrics.iloc[index][COL_CLOSE])
                future_index = index + FORWARD_BARS
                if future_index < len(metrics):
                    future_close = float(metrics.iloc[future_index][COL_CLOSE])
                    outcomes.append((future_close / close) - 1.0)

        except Exception as exc:
            failures.append({"symbol": symbol, "error": str(exc)})

    decisive = [value for value in outcomes if value != 0.0]
    positive = sum(value > 0.0 for value in outcomes)
    negative = sum(value < 0.0 for value in outcomes)
    flat = sum(value == 0.0 for value in outcomes)

    failures_out = list(failures)
    if duplicate_emissions:
        failures_out.append({
            "scope": "duplicates",
            "error": f"duplicate emissions: {duplicate_emissions}",
        })
    if semantic_failures:
        failures_out.append({
            "scope": "semantics",
            "error": f"production emission provenance failures: {semantic_failures}",
        })
    if failures:
        failures_out.append({
            "scope": "symbol_failures",
            "error": f"{len(failures)} symbol(s) failed; audit population is incomplete",
        })

    print("NO_SUPPLY CANDIDATE AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": len(SYMBOLS) - len(failures),
        "cheap_candidates": cheap_candidates,
        "candidate_events": candidate_events,
        "normal_detector_rejections": normal_detector_rejections,
        "positive": positive,
        "negative": negative,
        "flat": flat,
        "decisive": len(decisive),
        "positive_decisive_rate": positive / len(decisive) if decisive else 0.0,
        "mean_return": sum(outcomes) / len(outcomes) if outcomes else 0.0,
        "semantic_validation": "production_emission_authority",
        "semantic_failures": semantic_failures,
        "duplicate_emissions": duplicate_emissions,
        "heavy_context_rebuilds": heavy_context_rebuilds,
        "target_bar_only": True,
        "point_in_time": True,
        "production_context_used": True,
        "failures": failures_out,
        "status": "FAIL" if failures_out else "PASS",
    })


if __name__ == "__main__":
    main()
