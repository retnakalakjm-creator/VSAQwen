"""Campaign-qualified audit for BUYING_CLIMAX.

Analysis-only. Replays only cheap BUYING_CLIMAX candidates through the
real historical campaign-context path. No production scoring mutation.
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
    COL_VOLUME_CLASS,
)
from evidence.campaign import has_buying_campaign
from evidence.engine import EvidenceEngine
from metrics_engine import MetricsEngine
from models import Direction, SpreadClass, VolumeClass
from trend import TrendAnalyzer

SYMBOLS = (
    "BHARTIARTL.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "LT.NS", "RELIANCE.NS", "SBIN.NS", "TCS.NS",
)
FORWARD_BARS = 8


def _cheap_candidate(metrics, index: int) -> bool:
    """Exactly match the validated cheap BUYING_CLIMAX candidate audit."""
    row = metrics.iloc[index]
    direction = Direction(int(row[COL_DIRECTION]))
    volume = VolumeClass(int(row[COL_VOLUME_CLASS]))
    spread = SpreadClass(int(row["spread_class"]))
    return (
        direction == Direction.UP
        and volume == VolumeClass.VERY_HIGH
        and spread >= SpreadClass.ABOVE_AVERAGE
    )


def _campaign_context(metrics, index: int):
    """Build the same BackgroundContext used by EvidenceEngine production flow."""
    replay = metrics.iloc[: index + 1].copy()
    trend = TrendAnalyzer().analyze(replay)
    structural_swings = tuple(trend.structure.structural_swings)
    engine = EvidenceEngine()
    engine._reset(
        metrics=replay,
        trend=trend,
        structural_swings=structural_swings,
    )
    assert engine._ctx is not None
    return engine._ctx


def _audit_symbol(symbol: str) -> dict[str, object]:
    metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
    closes = metrics[COL_CLOSE].to_numpy(dtype=float)
    cheap_indices: list[int] = []
    for index in range(1, len(metrics) - FORWARD_BARS):
        if _cheap_candidate(metrics, index):
            cheap_indices.append(index)

    qualified: list[int] = []
    qualified_returns: list[float] = []
    heavy_rebuilds = 0

    for index in cheap_indices:
        try:
            ctx = _campaign_context(metrics, index)
            heavy_rebuilds += 1
            if not has_buying_campaign(ctx):
                continue
            qualified.append(index)
            qualified_returns.append(
                float(closes[index + FORWARD_BARS] / closes[index] - 1.0)
            )
        except Exception as exc:
            raise RuntimeError(f"{symbol} index={index}: {exc}") from exc

    return {
        "symbol": symbol,
        "cheap_candidates": len(cheap_indices),
        "campaign_qualified": len(qualified),
        "qualified_returns": qualified_returns,
        "heavy_context_rebuilds": heavy_rebuilds,
        "qualified_indices": qualified,
    }


def _stats(values: list[float]) -> dict[str, object]:
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
        "mean_return": float(np.mean(values)) if values else 0.0,
    }


def main() -> None:
    results: list[dict[str, object]] = []
    failures: list[dict[str, str]] = []
    for symbol in SYMBOLS:
        try:
            results.append(_audit_symbol(symbol))
        except Exception as exc:
            failures.append({"symbol": symbol, "error": str(exc)})

    returns = [
        value
        for result in results
        for value in result["qualified_returns"]
    ]
    cheap = sum(int(result["cheap_candidates"]) for result in results)
    qualified = sum(int(result["campaign_qualified"]) for result in results)
    rebuilds = sum(int(result["heavy_context_rebuilds"]) for result in results)
    stats = _stats(returns)

    print("BUYING CLIMAX CAMPAIGN-QUALIFIED AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": len(results),
        "cheap_candidates": cheap,
        "campaign_qualified_events": qualified,
        "campaign_pass_rate": qualified / cheap if cheap else 0.0,
        "positive": stats["positive"],
        "negative": stats["negative"],
        "flat": stats["flat"],
        "decisive": stats["decisive"],
        "positive_decisive_rate": stats["positive_decisive_rate"],
        "mean_return": stats["mean_return"],
        "heavy_context_rebuilds": rebuilds,
        "failures": failures,
        "status": "PASS" if not failures else "FAIL",
    })


if __name__ == "__main__":
    main()
