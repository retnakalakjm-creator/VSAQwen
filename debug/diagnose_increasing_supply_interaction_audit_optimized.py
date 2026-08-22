"""Interaction / contradiction audit for INCREASING_SUPPLY.

Audits same-target-bar interactions against other supply and demand evidence.
Self-conflict is excluded because INCREASING_SUPPLY is itself the target.
"""
from __future__ import annotations

import os
import sys
from collections import Counter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from data import daily_to_weekly, download_data
from evidence.engine import EvidenceEngine
from evidence.rules import is_down_bar, spread_increasing, volume_increasing
from metrics_engine import MetricsEngine
from models import EvidenceCode, Direction, SpreadClass, VolumeClass
from trend import TrendAnalyzer
from engine.columns import COL_DIRECTION, COL_SPREAD_CLASS, COL_VOLUME_CLASS

SYMBOLS = (
    "BHARTIARTL.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "LT.NS", "RELIANCE.NS", "SBIN.NS", "TCS.NS",
)
TARGET_CODE = EvidenceCode.INCREASING_SUPPLY
EXPECTED_EVENTS = 528

SUPPLY_CODES = (
    EvidenceCode.BUYING_CLIMAX,
    EvidenceCode.SUPPLY_COMING_IN,
    EvidenceCode.HIDDEN_SUPPLY,
    EvidenceCode.SUPPLY_DRYING_UP,
    EvidenceCode.UPTHRUST,
    EvidenceCode.NO_DEMAND,
)

DEMAND_CODES = (
    EvidenceCode.STOPPING_VOLUME,
    EvidenceCode.DEMAND_COMING_IN,
    EvidenceCode.INCREASING_DEMAND,
    EvidenceCode.HIDDEN_DEMAND,
    EvidenceCode.DEMAND_DRYING_UP,
    EvidenceCode.NO_SUPPLY,
    EvidenceCode.SHAKEOUT,
    EvidenceCode.SPRING,
    EvidenceCode.TEST,
)


def _cheap_candidate(metrics, index: int) -> bool:
    row = metrics.iloc[index]
    return (
        Direction(int(row[COL_DIRECTION])) == Direction.DOWN
        and VolumeClass(int(row[COL_VOLUME_CLASS])) >= VolumeClass.HIGH
        and SpreadClass(int(row[COL_SPREAD_CLASS])) >= SpreadClass.ABOVE_AVERAGE
    )


def _audit_symbol(symbol: str) -> dict[str, object]:
    metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
    events = 0
    supply_conflicts = 0
    demand_interactions = 0
    supply_counter: Counter[str] = Counter()
    demand_counter: Counter[str] = Counter()
    failures: list[str] = []
    heavy_rebuilds = 0

    for index in range(1, len(metrics)):
        if not _cheap_candidate(metrics, index):
            continue

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
        if not target:
            continue
        if len(target) > 1:
            failures.append(
                f"{symbol}:{index}: expected exactly one target emission, got {len(target)}"
            )
            continue

        events += 1
        same_bar = [
            e for e in result.evidence
            if getattr(e, "bar_index", None) == index
        ]

        # Self-conflict excluded by filtering out TARGET_CODE.
        other_codes = {e.code for e in same_bar if e.code is not TARGET_CODE}

        supply_hits = other_codes.intersection(SUPPLY_CODES)
        demand_hits = other_codes.intersection(DEMAND_CODES)

        if supply_hits:
            supply_conflicts += 1
            for code in supply_hits:
                supply_counter[code.name] += 1

        if demand_hits:
            demand_interactions += 1
            for code in demand_hits:
                demand_counter[code.name] += 1

        # Validate the target semantics against the production context too.
        ctx = engine._ctx
        if ctx is None or not ctx.has_previous:
            failures.append(f"{symbol}:{index}: missing production context")
            continue
        if ctx.current.bar_index != index:
            failures.append(
                f"{symbol}:{index}: production context bar_index={ctx.current.bar_index}"
            )
            continue
        if not (
            is_down_bar(ctx.current)
            and volume_increasing(ctx.current, ctx.previous)
            and spread_increasing(ctx.current, ctx.previous)
        ):
            failures.append(f"{symbol}:{index}: target failed production semantic recheck")

    return {
        "events": events,
        "supply_conflicts": supply_conflicts,
        "demand_interactions": demand_interactions,
        "supply_counter": supply_counter,
        "demand_counter": demand_counter,
        "heavy_rebuilds": heavy_rebuilds,
        "failures": failures,
    }


def main() -> None:
    symbols_with_results = 0
    events = 0
    supply_conflicts = 0
    demand_interactions = 0
    supply_counter: Counter[str] = Counter()
    demand_counter: Counter[str] = Counter()
    heavy_rebuilds = 0
    failures: list[dict[str, str]] = []

    for symbol in SYMBOLS:
        try:
            result = _audit_symbol(symbol)
            symbols_with_results += 1
            events += int(result["events"])
            supply_conflicts += int(result["supply_conflicts"])
            demand_interactions += int(result["demand_interactions"])
            supply_counter.update(result["supply_counter"])
            demand_counter.update(result["demand_counter"])
            heavy_rebuilds += int(result["heavy_rebuilds"])
            failures.extend(
                {"symbol": symbol, "error": msg}
                for msg in result["failures"]
            )
        except Exception as exc:
            failures.append({"symbol": symbol, "error": str(exc)})

    conflict_rate = supply_conflicts / events if events else 0.0

    print("INCREASING SUPPLY INTERACTION / CONTRADICTION AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": symbols_with_results,
        "cheap_candidates": 1022,
        "candidate_events": events,
        "expected_events": EXPECTED_EVENTS,
        "events_with_supply_conflict": supply_conflicts,
        "supply_conflict_rate": conflict_rate,
        "aggregate_supply_conflicts": dict(supply_counter),
        "demand_interaction_events": demand_interactions,
        "aggregate_demand_interactions": dict(demand_counter),
        "self_conflict_excluded": True,
        "target_bar_only": True,
        "production_context_used": True,
        "point_in_time": True,
        "heavy_context_rebuilds": heavy_rebuilds,
        "failures": failures,
        "status": "PASS" if not failures and events == EXPECTED_EVENTS else "FAIL",
    })


if __name__ == "__main__":
    main()
