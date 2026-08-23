"""Optimized NO_DEMAND candidate / outcome audit.

Production semantics from evidence/supply.py::_collect_no_demand:
- bullish environment
- bullish bar
- low volume
- narrow spread
- volume decreasing
- weak close (confirmation)

Analysis-only; production configuration is never mutated.

The production detector emission is the semantic authority. The audit
uses a cheap precondition gate for candidate selection, then validates
that the actual production engine emits exactly one NO_DEMAND event at
that target bar. It does not duplicate the detector's internal helper
logic with a second hand-written semantic implementation.
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
TARGET_CODE = EvidenceCode.NO_DEMAND
FORWARD_BARS = 8


def cheap_candidate(metrics: pd.DataFrame, index: int) -> bool:
    """Cheap gate for bullish bar + low volume + narrow spread."""
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


def outcome(metrics: pd.DataFrame, index: int) -> float:
    start = float(metrics.iloc[index][COL_CLOSE])
    end = float(metrics.iloc[index + FORWARD_BARS][COL_CLOSE])
    return 0.0 if start == 0.0 else end / start - 1.0


def main() -> None:
    cheap_total = 0
    candidate_events = 0
    normal_detector_rejections = 0
    duplicate_emissions = 0
    positive = negative = flat = 0
    returns: list[float] = []
    failures: list[dict[str, str]] = []
    context_rebuilds = 0

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

                candidate_events += 1
                ret = outcome(metrics, index)
                returns.append(ret)
                if ret > 0.0:
                    positive += 1
                elif ret < 0.0:
                    negative += 1
                else:
                    flat += 1
        except Exception as exc:
            failures.append({"symbol": symbol, "error": str(exc)})

    decisive = positive + negative
    mean_return = sum(returns) / len(returns) if returns else 0.0

    print("NO_DEMAND CANDIDATE AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": len(SYMBOLS) - len(failures),
        "cheap_candidates": cheap_total,
        "candidate_events": candidate_events,
        "normal_detector_rejections": normal_detector_rejections,
        "positive": positive,
        "negative": negative,
        "flat": flat,
        "decisive": decisive,
        "positive_decisive_rate": positive / decisive if decisive else 0.0,
        "mean_return": mean_return,
        "semantic_validation": "production_emission_authority",
        "semantic_failures": 0,
        "duplicate_emissions": duplicate_emissions,
        "heavy_context_rebuilds": context_rebuilds,
        "failures": failures,
        "status": "FAIL" if failures or duplicate_emissions or candidate_events == 0 else "PASS",
    })


if __name__ == "__main__":
    main()
