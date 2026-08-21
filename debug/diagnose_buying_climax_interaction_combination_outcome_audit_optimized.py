"""Combination-level interaction outcome audit for BUYING_CLIMAX.

Analysis-only. Replays cheap BUYING_CLIMAX candidates through the real
campaign/context path and groups each campaign-qualified event by the exact
non-self supply/demand evidence-code combination produced by engine.collect()
on the target bar. No production scoring mutation.
"""
from __future__ import annotations

import os
import sys
from collections import defaultdict

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from data import daily_to_weekly, download_data
from engine.columns import COL_CLOSE, COL_DIRECTION, COL_VOLUME_CLASS
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
SELF_CODES = {
    "EvidenceCode.BUYING_CLIMAX",
    "BUYING_CLIMAX",
    "BUYING_CLIMAX_LIKE",
}
SUPPLY_CODES = {
    "UPTHRUST", "UPTHRUST_LIKE", "HIDDEN_SUPPLY", "HIDDEN_SUPPLY_LIKE",
    "INCREASING_SUPPLY", "INCREASING_SUPPLY_LIKE",
    "SUPPLY_COMING_IN", "SUPPLY_COMING_IN_LIKE",
    "SUPPLY_HIGH_VOLUME", "SUPPLY_HIGH_VOLUME_LIKE",
    "SUPPLY_WIDE_SPREAD", "SUPPLY_WIDE_SPREAD_LIKE",
}
DEMAND_CODES = {
    "INCREASING_DEMAND", "INCREASING_DEMAND_LIKE",
    "DEMAND_COMING_IN", "DEMAND_COMING_IN_LIKE",
    "STOPPING_VOLUME", "STOPPING_VOLUME_LIKE",
    "SPRING", "SPRING_LIKE", "TEST", "TEST_LIKE",
    "NO_SUPPLY", "NO_SUPPLY_LIKE", "SHAKEOUT", "SHAKEOUT_LIKE",
    "SELLING_CLIMAX", "SELLING_CLIMAX_LIKE",
}


def _cheap_candidate(metrics, index: int) -> bool:
    row = metrics.iloc[index]
    return (
        Direction(int(row[COL_DIRECTION])) == Direction.UP
        and VolumeClass(int(row[COL_VOLUME_CLASS])) == VolumeClass.VERY_HIGH
        and SpreadClass(int(row["spread_class"])) >= SpreadClass.ABOVE_AVERAGE
    )


def _context(metrics, index: int):
    replay = metrics.iloc[: index + 1].copy()
    trend = TrendAnalyzer().analyze(replay)
    structural_swings = tuple(trend.structure.structural_swings)
    return replay, trend, structural_swings


def _norm_code(code: object) -> str:
    return str(code).split(".")[-1]


def _group_for(codes: set[str]) -> str:
    supply = sorted(code for code in codes if code in SUPPLY_CODES)
    demand = sorted(code for code in codes if code in DEMAND_CODES)
    if not supply and not demand:
        return "no_interaction"
    return " + ".join([*supply, *demand])


def _audit_symbol(symbol: str) -> tuple[list[tuple[str, float]], int, int]:
    metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
    closes = metrics[COL_CLOSE].to_numpy(dtype=float)
    observations: list[tuple[str, float]] = []
    cheap_count = 0
    rebuilds = 0

    for index in range(1, len(metrics) - FORWARD_BARS):
        if not _cheap_candidate(metrics, index):
            continue
        cheap_count += 1
        replay, trend, structural_swings = _context(metrics, index)
        rebuilds += 1

        engine = EvidenceEngine()
        engine._reset(
            metrics=replay,
            trend=trend,
            structural_swings=structural_swings,
        )
        assert engine._ctx is not None
        if not has_buying_campaign(engine._ctx):
            continue

        result = engine.collect(
            metrics=replay,
            trend=trend,
            structural_swings=structural_swings,
        )

        target_codes = {
            _norm_code(item.code)
            for item in result.evidence
            if getattr(item, "bar_index", None) == index
        }
        target_codes.difference_update(SELF_CODES)

        group = _group_for(target_codes)
        forward_return = float(
            closes[index + FORWARD_BARS] / closes[index] - 1.0
        )
        observations.append((group, forward_return))

    return observations, cheap_count, rebuilds


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
    groups: dict[str, list[float]] = defaultdict(list)
    cheap_total = 0
    rebuild_total = 0
    failures: list[dict[str, str]] = []

    for symbol in SYMBOLS:
        try:
            observations, cheap, rebuilds = _audit_symbol(symbol)
            cheap_total += cheap
            rebuild_total += rebuilds
            for group, value in observations:
                groups[group].append(value)
        except Exception as exc:
            failures.append({"symbol": symbol, "error": str(exc)})

    print("BUYING CLIMAX INTERACTION COMBINATION OUTCOME AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "cheap_candidates": cheap_total,
        "campaign_qualified_events": sum(len(v) for v in groups.values()),
        "combination_groups": len(groups),
        "self_conflict_excluded": True,
        "target_bar_only": True,
        "heavy_context_rebuilds": rebuild_total,
        "failures": failures,
        "status": "PASS" if not failures else "FAIL",
    })

    ranked = sorted(groups.items(), key=lambda item: len(item[1]), reverse=True)
    for group, values in ranked:
        print({"combination": group, **_stats(values)})


if __name__ == "__main__":
    main()
