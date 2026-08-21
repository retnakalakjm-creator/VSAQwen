"""Interaction outcome audit for SUPPLY_COMING_IN.

Splits the frozen 189-event SUPPLY_COMING_IN population into clean events and
INCREASING_SUPPLY overlap events, using same-bar evidence only and an 8-bar
forward return. Analysis-only; no production mutation.
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
from evidence.campaign import has_buying_campaign
from evidence.engine import EvidenceEngine
from evidence.rules import spread_increasing
from metrics_engine import MetricsEngine
from models import Direction, EvidenceCode, SpreadClass, VolumeClass
from trend import TrendAnalyzer

SYMBOLS = (
    "BHARTIARTL.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "LT.NS", "RELIANCE.NS", "SBIN.NS", "TCS.NS",
)
TARGET_CODE = EvidenceCode.SUPPLY_COMING_IN
FORWARD_BARS = 8
EXPECTED_EVENTS = 189


def _cheap_candidate(metrics, index: int) -> bool:
    row = metrics.iloc[index]
    return (
        Direction(int(row[COL_DIRECTION])) == Direction.DOWN
        and VolumeClass(int(row[COL_VOLUME_CLASS])) >= VolumeClass.HIGH
        and SpreadClass(int(row[COL_SPREAD_CLASS])) >= SpreadClass.ABOVE_AVERAGE
    )


def _find_bar(ctx, bar_index: int):
    return next((bar for bar in ctx.bars if bar.bar_index == bar_index), None)


def _audit_symbol(symbol: str) -> dict[str, object]:
    metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
    closes = metrics[COL_CLOSE].to_numpy(dtype=float)

    cheap = campaign = events = heavy_rebuilds = 0
    groups: dict[str, list[float]] = {"clean": [], "increasing_supply": []}
    failures: list[str] = []

    for index in range(1, len(metrics) - FORWARD_BARS):
        if not _cheap_candidate(metrics, index):
            continue
        cheap += 1

        replay = metrics.iloc[: index + 1].copy()
        trend = TrendAnalyzer().analyze(replay)
        structural_swings = tuple(trend.structure.structural_swings)
        engine = EvidenceEngine()
        result = engine.collect(
            metrics=replay,
            trend=trend,
            structural_swings=structural_swings,
        )
        heavy_rebuilds += 1
        ctx = engine._ctx
        assert ctx is not None

        if not has_buying_campaign(ctx):
            continue
        campaign += 1

        target = [
            e for e in result.evidence
            if e.code is TARGET_CODE
            and getattr(e, "bar_index", None) == index
        ]
        if len(target) != 1:
            continue
        events += 1

        bar = _find_bar(ctx, index)
        previous = _find_bar(ctx, index - 1)
        if bar is None or previous is None:
            failures.append(f"{symbol}:{index}: target/previous bar missing from context")
            continue

        increasing_supply = (
            bar.direction is Direction.DOWN
            and volume_class_is_increasing(bar, previous)
            and spread_increasing(bar, previous)
        )

        forward_return = float(closes[index + FORWARD_BARS] / closes[index] - 1.0)
        groups["increasing_supply" if increasing_supply else "clean"].append(forward_return)

    return {
        "cheap": cheap,
        "campaign": campaign,
        "events": events,
        "groups": groups,
        "heavy_rebuilds": heavy_rebuilds,
        "failures": failures,
    }


def volume_class_is_increasing(bar, previous) -> bool:
    return bar.volume > previous.volume


def _summary(values: list[float]) -> dict[str, object]:
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
    symbols_with_results = 0
    cheap = campaign = events = heavy_rebuilds = 0
    all_groups = {"clean": [], "increasing_supply": []}
    failures: list[dict[str, str]] = []

    for symbol in SYMBOLS:
        try:
            r = _audit_symbol(symbol)
            symbols_with_results += 1
            cheap += int(r["cheap"])
            campaign += int(r["campaign"])
            events += int(r["events"])
            heavy_rebuilds += int(r["heavy_rebuilds"])
            for group, values in r["groups"].items():
                all_groups[group].extend(values)
            failures.extend({"symbol": symbol, "error": msg} for msg in r["failures"])
        except Exception as exc:
            failures.append({"symbol": symbol, "error": str(exc)})

    print("SUPPLY COMING IN INTERACTION OUTCOME AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": symbols_with_results,
        "cheap_candidates": cheap,
        "campaign_qualified_events": campaign,
        "events": events,
        "expected_events": EXPECTED_EVENTS,
        "heavy_context_rebuilds": heavy_rebuilds,
        "self_conflict_excluded": True,
        "target_bar_only": True,
        "failures": failures,
        "status": "PASS" if not failures and events == EXPECTED_EVENTS else "FAIL",
    })
    for group in ("clean", "increasing_supply"):
        print({"group": group, **_summary(all_groups[group])})


if __name__ == "__main__":
    main()
