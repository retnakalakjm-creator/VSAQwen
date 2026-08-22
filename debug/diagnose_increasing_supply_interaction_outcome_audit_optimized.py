"""Interaction outcome audit for INCREASING_SUPPLY.

Uses the frozen 528-event candidate population and the exact production
BackgroundContext. Self-conflict is excluded. Same-bar supply and demand
interactions are grouped, then evaluated with the standard 8-bar return.
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
from engine.columns import COL_CLOSE, COL_DIRECTION, COL_SPREAD_CLASS, COL_VOLUME_CLASS
from evidence.engine import EvidenceEngine
from models import Direction, EvidenceCode, SpreadClass, VolumeClass
from metrics_engine import MetricsEngine
from trend import TrendAnalyzer

SYMBOLS = (
    "BHARTIARTL.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "LT.NS", "RELIANCE.NS", "SBIN.NS", "TCS.NS",
)
TARGET_CODE = EvidenceCode.INCREASING_SUPPLY
EXPECTED_EVENTS = 528
SUPPLY_CODES = {
    EvidenceCode.BUYING_CLIMAX,
    EvidenceCode.SUPPLY_COMING_IN,
    EvidenceCode.HIDDEN_SUPPLY,
    EvidenceCode.INCREASING_SUPPLY,
    EvidenceCode.SUPPLY_DRYING_UP,
    EvidenceCode.UPTHRUST,
    EvidenceCode.NO_DEMAND,
}
DEMAND_CODES = {
    EvidenceCode.STOPPING_VOLUME,
    EvidenceCode.DEMAND_COMING_IN,
    EvidenceCode.INCREASING_DEMAND,
    EvidenceCode.HIDDEN_DEMAND,
    EvidenceCode.DEMAND_DRYING_UP,
    EvidenceCode.NO_SUPPLY,
    EvidenceCode.SHAKEOUT,
    EvidenceCode.SPRING,
    EvidenceCode.TEST,
    EvidenceCode.SELLING_CLIMAX,
}


def _cheap_candidate(metrics, index: int) -> bool:
    row = metrics.iloc[index]
    return (
        Direction(int(row[COL_DIRECTION])) == Direction.DOWN
        and VolumeClass(int(row[COL_VOLUME_CLASS])) >= VolumeClass.HIGH
        and SpreadClass(int(row[COL_SPREAD_CLASS])) >= SpreadClass.ABOVE_AVERAGE
    )


def _summary(returns: list[float]) -> dict[str, float | int]:
    positive = sum(r > 0 for r in returns)
    negative = sum(r < 0 for r in returns)
    flat = sum(r == 0 for r in returns)
    decisive = positive + negative
    return {
        "events": len(returns),
        "positive": positive,
        "negative": negative,
        "flat": flat,
        "decisive": decisive,
        "positive_decisive_rate": positive / decisive if decisive else 0.0,
        "mean_return": float(np.mean(returns)) if returns else 0.0,
    }


def main() -> None:
    symbols_with_results = 0
    cheap_candidates = 0
    heavy_rebuilds = 0
    failures: list[dict[str, str]] = []
    events: list[tuple[str, int, frozenset[EvidenceCode]]] = []

    for symbol in SYMBOLS:
        try:
            metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
            for index in range(1, len(metrics)):
                if not _cheap_candidate(metrics, index):
                    continue

                cheap_candidates += 1
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

                target = [
                    e for e in result.evidence
                    if e.code is TARGET_CODE
                    and getattr(e, "bar_index", None) == index
                ]
                if len(target) > 1:
                    failures.append({
                        "symbol": symbol,
                        "error": f"{index}: expected at most one target emission, got {len(target)}",
                    })
                    continue
                if not target:
                    continue

                codes = frozenset(
                    e.code
                    for e in result.evidence
                    if getattr(e, "bar_index", None) == index
                )
                events.append((symbol, index, codes))

            symbols_with_results += 1
        except Exception as exc:
            failures.append({"symbol": symbol, "error": str(exc)})

    groups: dict[str, list[tuple[str, int]]] = defaultdict(list)
    target_events = {(symbol, index): codes for symbol, index, codes in events}

    for symbol, index, codes in events:
        supply = sorted(c.name for c in (codes & SUPPLY_CODES) if c is not TARGET_CODE)
        demand = sorted(c.name for c in (codes & DEMAND_CODES))
        if supply and demand:
            key_parts = supply + demand
            group = " + ".join(key_parts)
        elif supply:
            group = "other_supply"
        elif demand:
            group = "other_demand"
        else:
            group = "clean"
        groups[group].append((symbol, index))

    # Keep the event universe frozen and self-conflict excluded.
    if len(events) != EXPECTED_EVENTS:
        failures.append({
            "symbol": "GLOBAL",
            "error": f"expected {EXPECTED_EVENTS} target events, got {len(events)}",
        })

    # Outcomes are calculated from the original full weekly metrics for each
    # symbol, using the frozen target index and canonical close column.
    metrics_cache: dict[str, object] = {}
    for symbol in SYMBOLS:
        try:
            metrics_cache[symbol] = MetricsEngine().calculate(
                daily_to_weekly(download_data(symbol))
            )
        except Exception as exc:
            failures.append({"symbol": symbol, "error": f"outcome data: {exc}"})

    summaries: dict[str, dict[str, float | int]] = {}
    for group, members in groups.items():
        returns: list[float] = []
        for symbol, index in members:
            metrics = metrics_cache.get(symbol)
            try:
                if metrics is None or index + 8 >= len(metrics):
                    continue
                start = float(metrics.iloc[index][COL_CLOSE])
                end = float(metrics.iloc[index + 8][COL_CLOSE])
                if start == 0.0:
                    continue
                returns.append((end - start) / start)
            except Exception as exc:
                failures.append({"symbol": symbol, "error": f"{index}: {exc}"})
        summaries[group] = _summary(returns)

    print("INCREASING SUPPLY INTERACTION OUTCOME AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": symbols_with_results,
        "cheap_candidates": cheap_candidates,
        "candidate_events": len(events),
        "expected_events": EXPECTED_EVENTS,
        "combination_groups": len(summaries),
        "self_conflict_excluded": True,
        "target_bar_only": True,
        "production_context_used": True,
        "point_in_time": True,
        "heavy_context_rebuilds": heavy_rebuilds,
        "failures": failures,
        "status": "PASS" if not failures else "FAIL",
    })
    for group in sorted(summaries, key=lambda k: (-int(summaries[k]["events"]), k)):
        print({"group": group, **summaries[group]})


if __name__ == "__main__":
    main()
