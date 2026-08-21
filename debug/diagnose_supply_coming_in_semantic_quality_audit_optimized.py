"""Semantic-quality audit for SUPPLY_COMING_IN.

Analysis-only. Reconstructs the exact point-in-time production evidence
population and measures the detector's required semantic components.
"""
from __future__ import annotations

import os
import sys

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from data import daily_to_weekly, download_data
from engine.columns import COL_CLOSE, COL_DIRECTION, COL_SPREAD_CLASS, COL_VOLUME_CLASS
from evidence.engine import EvidenceEngine
from evidence.campaign import has_buying_campaign
from metrics_engine import MetricsEngine
from models import Direction, EvidenceCode, SpreadClass, VolumeClass
from trend import TrendAnalyzer
from evidence.rules import is_down_bar, is_high_volume, is_above_average_spread, is_weak_close, volume_increasing

SYMBOLS = (
    "BHARTIARTL.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "LT.NS", "RELIANCE.NS", "SBIN.NS", "TCS.NS",
)
TARGET_CODE = EvidenceCode.SUPPLY_COMING_IN
FORWARD_BARS = 8


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

    cheap = campaign = events = 0
    semantic = {
        "down_bar": 0,
        "high_volume": 0,
        "above_average_spread": 0,
        "weak_close": 0,
        "volume_increasing": 0,
    }
    failures: list[str] = []

    for index in range(1, len(metrics) - FORWARD_BARS):
        if not _cheap_candidate(metrics, index):
            continue
        cheap += 1
        replay = metrics.iloc[: index + 1].copy()
        trend = TrendAnalyzer().analyze(replay)
        structural_swings = tuple(trend.structure.structural_swings)
        engine = EvidenceEngine()
        engine._reset(metrics=replay, trend=trend, structural_swings=structural_swings)
        assert engine._ctx is not None
        if not has_buying_campaign(engine._ctx):
            continue
        campaign += 1
        result = engine.collect(metrics=replay, trend=trend, structural_swings=structural_swings)
        target = [e for e in result.evidence if e.code is TARGET_CODE and getattr(e, "bar_index", None) == index]
        if len(target) != 1:
            continue
        events += 1
        bar = engine._ctx.bars[index]
        prev = engine._ctx.bars[index - 1]
        checks = {
            "down_bar": is_down_bar(bar),
            "high_volume": is_high_volume(bar),
            "above_average_spread": is_above_average_spread(bar),
            "weak_close": is_weak_close(bar),
            "volume_increasing": volume_increasing(bar, prev),
        }
        for key, passed in checks.items():
            semantic[key] += int(passed)
        if not all(checks.values()):
            failures.append(f"{symbol}:{index}: emitted target failed one or more production semantics: {checks}")

    return {"cheap": cheap, "campaign": campaign, "events": events, "semantic": semantic, "failures": failures}


def main() -> None:
    symbols_with_results = 0
    cheap = campaign = events = 0
    semantic = {k: 0 for k in ("down_bar", "high_volume", "above_average_spread", "weak_close", "volume_increasing")}
    failures: list[dict[str, str]] = []
    for symbol in SYMBOLS:
        try:
            r = _audit_symbol(symbol)
            symbols_with_results += 1
            cheap += int(r["cheap"])
            campaign += int(r["campaign"])
            events += int(r["events"])
            for k, v in r["semantic"].items():
                semantic[k] += int(v)
            failures.extend({"symbol": symbol, "error": f} for f in r["failures"])
        except Exception as exc:
            failures.append({"symbol": symbol, "error": str(exc)})

    print("SUPPLY COMING IN SEMANTIC QUALITY AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": symbols_with_results,
        "cheap_candidates": cheap,
        "campaign_qualified_events": campaign,
        "candidate_events": events,
        "semantic_counts": semantic,
        "semantic_failures": len(failures),
        "failures": failures,
        "status": "PASS" if not failures and events == 189 else "FAIL",
    })


if __name__ == "__main__":
    main()
