"""Semantic-quality audit for campaign-qualified BUYING_CLIMAX events.

Analysis-only. Uses the exact same cheap-candidate and campaign-qualified path as
the validated BUYING_CLIMAX campaign audit, then measures mandatory requirements
and confirmations on the qualified bars. No production scoring mutation.
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from data import daily_to_weekly, download_data
from engine.columns import COL_DIRECTION, COL_SPREAD_CLASS, COL_VOLUME_CLASS
from evidence.campaign import has_buying_campaign
from evidence.engine import EvidenceEngine
from evidence.rules import has_strong_spread, is_weak_close, volume_increasing
from metrics_engine import MetricsEngine
from models import Direction, SpreadClass, VolumeClass
from trend import TrendAnalyzer

SYMBOLS = (
    "BHARTIARTL.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "LT.NS", "RELIANCE.NS", "SBIN.NS", "TCS.NS",
)
FORWARD_BARS = 8


def _cheap_candidate(metrics, index: int) -> bool:
    """Exactly match the validated BUYING_CLIMAX campaign audit."""
    row = metrics.iloc[index]
    direction = Direction(int(row[COL_DIRECTION]))
    volume = VolumeClass(int(row[COL_VOLUME_CLASS]))
    spread = SpreadClass(int(row[COL_SPREAD_CLASS]))
    return (
        direction == Direction.UP
        and volume == VolumeClass.VERY_HIGH
        and spread >= SpreadClass.ABOVE_AVERAGE
    )


def _campaign_context(metrics, index: int):
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
    cheap_indices = [
        index
        for index in range(1, len(metrics) - FORWARD_BARS)
        if _cheap_candidate(metrics, index)
    ]

    semantic = {
        "bullish_bar": 0,
        "very_high_volume": 0,
        "above_average_spread": 0,
        "wide_spread": 0,
        "weak_close": 0,
        "volume_increasing": 0,
        "semantic_failures": 0,
    }
    qualified = 0
    rebuilds = 0
    errors: list[dict[str, str]] = []

    for index in cheap_indices:
        try:
            ctx = _campaign_context(metrics, index)
            rebuilds += 1
            if not has_buying_campaign(ctx):
                continue

            qualified += 1
            row = metrics.iloc[index]
            previous = metrics.iloc[index - 1]

            direction = Direction(int(row[COL_DIRECTION]))
            volume = VolumeClass(int(row[COL_VOLUME_CLASS]))
            spread = SpreadClass(int(row[COL_SPREAD_CLASS]))

            checks = {
                "bullish_bar": direction == Direction.UP,
                "very_high_volume": volume == VolumeClass.VERY_HIGH,
                "above_average_spread": spread >= SpreadClass.ABOVE_AVERAGE,
                "wide_spread": has_strong_spread(row),
                "weak_close": is_weak_close(row),
                "volume_increasing": volume_increasing(row, previous),
            }

            for key, passed in checks.items():
                semantic[key] += int(passed)

            if not all(
                checks[name]
                for name in (
                    "bullish_bar",
                    "very_high_volume",
                    "above_average_spread",
                )
            ):
                semantic["semantic_failures"] += 1
        except Exception as exc:
            errors.append({"symbol": symbol, "index": str(index), "error": str(exc)})

    return {
        "symbol": symbol,
        "cheap_candidates": len(cheap_indices),
        "campaign_qualified_events": qualified,
        "heavy_context_rebuilds": rebuilds,
        **semantic,
        "errors": errors,
    }


def main() -> None:
    results: list[dict[str, object]] = []
    failures: list[dict[str, str]] = []

    for symbol in SYMBOLS:
        try:
            results.append(_audit_symbol(symbol))
        except Exception as exc:
            failures.append({"symbol": symbol, "error": str(exc)})

    candidates = sum(int(r["campaign_qualified_events"]) for r in results)
    semantic_failures = sum(int(r["semantic_failures"]) for r in results)

    print("BUYING CLIMAX SEMANTIC-QUALITY AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": len(results),
        "candidate_events": candidates,
        "bullish_bar": sum(int(r["bullish_bar"]) for r in results),
        "very_high_volume": sum(int(r["very_high_volume"]) for r in results),
        "above_average_spread": sum(int(r["above_average_spread"]) for r in results),
        "wide_spread": sum(int(r["wide_spread"]) for r in results),
        "weak_close": sum(int(r["weak_close"]) for r in results),
        "volume_increasing": sum(int(r["volume_increasing"]) for r in results),
        "semantic_failures": semantic_failures,
        "heavy_context_rebuilds": sum(int(r["heavy_context_rebuilds"]) for r in results),
        "failures": failures,
        "status": "PASS" if not failures and semantic_failures == 0 else "FAIL",
    })


if __name__ == "__main__":
    main()
