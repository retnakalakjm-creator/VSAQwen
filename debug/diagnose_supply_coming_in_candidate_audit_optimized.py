"""Candidate audit for SUPPLY_COMING_IN.

Analysis-only. Mirrors the real production collector at each point in time:
cheap semantic prefilter -> point-in-time TrendAnalyzer/EvidenceEngine context
-> campaign gate -> real engine.collect() -> exact target-bar emission.
No production mutation.
"""
from __future__ import annotations

import os
import sys

import numpy as np

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
from evidence.campaign import has_buying_campaign
from evidence.engine import EvidenceEngine
from metrics_engine import MetricsEngine
from models import Direction, EvidenceCode, SpreadClass, VolumeClass
from trend import TrendAnalyzer

SYMBOLS = (
    "BHARTIARTL.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "LT.NS", "RELIANCE.NS", "SBIN.NS", "TCS.NS",
)
FORWARD_BARS = 8
TARGET_CODE = EvidenceCode.SUPPLY_COMING_IN


def _cheap_candidate(metrics, index: int) -> bool:
    row = metrics.iloc[index]
    return (
        Direction(int(row[COL_DIRECTION])) == Direction.DOWN
        and VolumeClass(int(row[COL_VOLUME_CLASS])) >= VolumeClass.HIGH
        and SpreadClass(int(row[COL_SPREAD_CLASS])) >= SpreadClass.ABOVE_AVERAGE
    )


def _audit_symbol(symbol: str) -> dict[str, object]:
    metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
    closes = metrics[COL_CLOSE].to_numpy(dtype=float)

    bars_scanned = max(0, len(metrics) - 1 - FORWARD_BARS)
    cheap_candidates = 0
    campaign_qualified = 0
    candidate_returns: list[float] = []
    semantic_failures = 0
    heavy_context_rebuilds = 0
    failures: list[str] = []

    for index in range(1, len(metrics) - FORWARD_BARS):
        if not _cheap_candidate(metrics, index):
            continue
        cheap_candidates += 1

        replay = metrics.iloc[: index + 1].copy()
        trend = TrendAnalyzer().analyze(replay)
        structural_swings = tuple(trend.structure.structural_swings)

        engine = EvidenceEngine()
        engine._reset(
            metrics=replay,
            trend=trend,
            structural_swings=structural_swings,
        )
        heavy_context_rebuilds += 1
        assert engine._ctx is not None

        if not has_buying_campaign(engine._ctx):
            continue
        campaign_qualified += 1

        result = engine.collect(
            metrics=replay,
            trend=trend,
            structural_swings=structural_swings,
        )

        target_items = [
            item for item in result.evidence
            if item.code is TARGET_CODE
            and getattr(item, "bar_index", None) == index
        ]

        if len(target_items) != 1:
            semantic_failures += 1
            failures.append(
                f"{symbol}:{index}: expected exactly one target-bar SUPPLY_COMING_IN emission, got {len(target_items)}"
            )
            continue

        candidate_returns.append(
            float(closes[index + FORWARD_BARS] / closes[index] - 1.0)
        )

    return {
        "bars_scanned": bars_scanned,
        "cheap_candidates": cheap_candidates,
        "campaign_qualified": campaign_qualified,
        "candidate_returns": candidate_returns,
        "semantic_failures": semantic_failures,
        "heavy_context_rebuilds": heavy_context_rebuilds,
        "failures": failures,
    }


def main() -> None:
    symbols_with_results = 0
    bars_scanned = 0
    cheap_candidates = 0
    campaign_qualified = 0
    all_returns: list[float] = []
    semantic_failures = 0
    heavy_context_rebuilds = 0
    failures: list[dict[str, str]] = []

    for symbol in SYMBOLS:
        try:
            result = _audit_symbol(symbol)
            symbols_with_results += 1
            bars_scanned += int(result["bars_scanned"])
            cheap_candidates += int(result["cheap_candidates"])
            campaign_qualified += int(result["campaign_qualified"])
            all_returns.extend(result["candidate_returns"])
            semantic_failures += int(result["semantic_failures"])
            heavy_context_rebuilds += int(result["heavy_context_rebuilds"])
            failures.extend(
                {"symbol": symbol, "error": message}
                for message in result["failures"]
            )
        except Exception as exc:
            failures.append({"symbol": symbol, "error": str(exc)})

    positive = sum(r > 0.0 for r in all_returns)
    negative = sum(r < 0.0 for r in all_returns)
    flat = sum(r == 0.0 for r in all_returns)
    decisive = positive + negative

    print("SUPPLY COMING IN CANDIDATE AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": symbols_with_results,
        "bars_scanned": bars_scanned,
        "cheap_candidates": cheap_candidates,
        "campaign_qualified_events": campaign_qualified,
        "candidate_events": len(all_returns),
        "positive": positive,
        "negative": negative,
        "flat": flat,
        "decisive": decisive,
        "positive_decisive_rate": positive / decisive if decisive else 0.0,
        "mean_return": float(np.mean(all_returns)) if all_returns else 0.0,
        "semantic_failures": semantic_failures,
        "heavy_context_rebuilds": heavy_context_rebuilds,
        "failures": failures,
        "status": "PASS" if not failures and semantic_failures == 0 else "FAIL",
    })


if __name__ == "__main__":
    main()
