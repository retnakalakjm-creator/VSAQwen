"""Optimized NO_DEMAND candidate / outcome audit.

Production semantics from evidence/supply.py::_collect_no_demand:
- bullish environment
- bullish bar
- low volume
- narrow spread
- volume decreasing
- weak close (confirmation)

Analysis-only; production configuration is never mutated.
"""
from __future__ import annotations

import os
import sys

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import config
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
    positive = negative = flat = 0
    returns: list[float] = []
    failures: list[dict[str, str]] = []
    semantic_failures: list[dict[str, object]] = []
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
                if len(targets) != 1:
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

                row = metrics.iloc[index]
                previous = metrics.iloc[index - 1]
                bullish_bar = Direction(int(row[COL_DIRECTION])) == Direction.UP
                low_volume = VolumeClass(int(row[COL_VOLUME_CLASS])) <= VolumeClass.LOW
                narrow_spread = SpreadClass(int(row[COL_SPREAD_CLASS])) <= SpreadClass.NARROW
                volume_decreasing = (
                    VolumeClass(int(row[COL_VOLUME_CLASS]))
                    < VolumeClass(int(previous[COL_VOLUME_CLASS]))
                )

                if not (bullish_bar and low_volume and narrow_spread and volume_decreasing):
                    semantic_failures.append({
                        "symbol": symbol,
                        "bar": index,
                        "bullish_bar": bullish_bar,
                        "low_volume": low_volume,
                        "narrow_spread": narrow_spread,
                        "volume_decreasing": volume_decreasing,
                    })
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
        "positive": positive,
        "negative": negative,
        "flat": flat,
        "decisive": decisive,
        "positive_decisive_rate": positive / decisive if decisive else 0.0,
        "mean_return": mean_return,
        "semantic_failures": len(semantic_failures),
        "heavy_context_rebuilds": context_rebuilds,
        "failures": failures,
        "status": "FAIL" if failures or semantic_failures or candidate_events == 0 else "PASS",
    })

    if semantic_failures:
        print({"semantic_samples": semantic_failures[:20]})


if __name__ == "__main__":
    main()
