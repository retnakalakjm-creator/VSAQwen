"""Outcome audit for BUYING_CLIMAX interaction groups.

Analysis-only. Uses real point-in-time EvidenceEngine output for the
campaign-qualified BUYING_CLIMAX population and splits outcomes by
same-bar supply/demand interactions. BUYING_CLIMAX self-conflict is excluded.
"""
from __future__ import annotations

import os
import sys

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from data import daily_to_weekly, download_data
from engine.columns import COL_CLOSE, COL_DIRECTION, COL_VOLUME_CLASS
from evidence.campaign import has_buying_campaign
from evidence.engine import EvidenceEngine
from evidence.rules import (
    has_strong_spread,
    is_above_average_spread,
    is_bullish_bar,
    is_very_high_volume,
    is_weak_close,
    volume_increasing,
)
from metrics_engine import MetricsEngine
from models import EvidenceCode, Direction, VolumeClass, SpreadClass
from trend import TrendAnalyzer

SYMBOLS = (
    "BHARTIARTL.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "LT.NS", "RELIANCE.NS", "SBIN.NS", "TCS.NS",
)
FORWARD_BARS = 8

SUPPLY_CODES = {
    EvidenceCode.UPTHRUST: "upthrust",
    EvidenceCode.HIDDEN_SUPPLY: "hidden_supply",
    EvidenceCode.SUPPLY_COMING_IN: "supply_coming_in",
    EvidenceCode.INCREASING_SUPPLY: "increasing_supply",
    EvidenceCode.NO_DEMAND: "no_demand",
}
DEMAND_CODES = {
    EvidenceCode.INCREASING_DEMAND: "increasing_demand",
    EvidenceCode.HIDDEN_DEMAND: "hidden_demand",
    EvidenceCode.DEMAND_COMING_IN: "demand_coming_in",
    EvidenceCode.STOPPING_VOLUME: "stopping_volume",
    EvidenceCode.SPRING: "spring",
    EvidenceCode.TEST: "test",
}


def _cheap_candidate(metrics, index: int) -> bool:
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
    replay = metrics.iloc[: index + 1].copy()
    trend = TrendAnalyzer().analyze(replay)
    structural_swings = tuple(trend.structure.structural_swings)
    engine = EvidenceEngine()
    engine._reset(metrics=replay, trend=trend, structural_swings=structural_swings)
    assert engine._ctx is not None
    return engine._ctx


def _collect_result(metrics, index: int):
    replay = metrics.iloc[: index + 1].copy()
    trend = TrendAnalyzer().analyze(replay)
    structural_swings = tuple(trend.structure.structural_swings)
    engine = EvidenceEngine()
    result = engine.collect(metrics=replay, trend=trend, structural_swings=structural_swings)
    return result


def _audit_symbol(symbol: str) -> dict[str, object]:
    metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
    closes = metrics[COL_CLOSE].to_numpy(dtype=float)

    groups: dict[str, list[float]] = {
        "clean": [],
        "upthrust": [],
        "hidden_supply": [],
        "other_supply": [],
        "increasing_demand": [],
        "other_demand": [],
        "multiple_interactions": [],
    }
    qualified = 0
    rebuilds = 0
    errors: list[dict[str, str]] = []

    for index in range(1, len(metrics) - FORWARD_BARS):
        if not _cheap_candidate(metrics, index):
            continue
        try:
            ctx = _campaign_context(metrics, index)
            rebuilds += 1
            if not has_buying_campaign(ctx):
                continue
            qualified += 1

            result = _collect_result(metrics, index)
            codes = [item.code for item in result.evidence if item.bar_index == index]
            codes = [code for code in codes if code != EvidenceCode.BUYING_CLIMAX]

            supply = {SUPPLY_CODES[code] for code in codes if code in SUPPLY_CODES}
            demand = {DEMAND_CODES[code] for code in codes if code in DEMAND_CODES}

            value = float(closes[index + FORWARD_BARS] / closes[index] - 1.0)
            interaction_count = len(supply) + len(demand)

            if interaction_count == 0:
                groups["clean"].append(value)
            elif interaction_count > 1:
                groups["multiple_interactions"].append(value)
            elif supply == {"upthrust"}:
                groups["upthrust"].append(value)
            elif supply == {"hidden_supply"}:
                groups["hidden_supply"].append(value)
            elif supply:
                groups["other_supply"].append(value)
            elif demand == {"increasing_demand"}:
                groups["increasing_demand"].append(value)
            else:
                groups["other_demand"].append(value)
        except Exception as exc:
            errors.append({"symbol": symbol, "index": str(index), "error": str(exc)})

    return {
        "symbol": symbol,
        "campaign_qualified_events": qualified,
        "groups": groups,
        "heavy_context_rebuilds": rebuilds,
        "errors": errors,
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

    aggregate: dict[str, list[float]] = {
        "clean": [],
        "upthrust": [],
        "hidden_supply": [],
        "other_supply": [],
        "increasing_demand": [],
        "other_demand": [],
        "multiple_interactions": [],
    }
    qualified = 0
    rebuilds = 0
    for result in results:
        qualified += int(result["campaign_qualified_events"])
        rebuilds += int(result["heavy_context_rebuilds"])
        for name, values in result["groups"].items():
            aggregate[name].extend(values)

    print("BUYING CLIMAX INTERACTION OUTCOME AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": len(results),
        "events": qualified,
        "heavy_context_rebuilds": rebuilds,
        "failures": failures,
        "status": "PASS" if not failures else "FAIL",
    })
    for group, values in aggregate.items():
        print({"group": group, **_stats(values)})


if __name__ == "__main__":
    main()
