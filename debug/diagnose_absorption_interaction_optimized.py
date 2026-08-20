"""Analysis-only interaction audit for ABSORPTION.

Uses the same EvidenceEngine bar-context construction pattern as the
validated interaction audits. No production detector, weight, or scoring
logic is modified.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from engine.columns import (
    COL_CLOSE_POSITION,
    COL_DIRECTION,
    COL_LOW,
    COL_SPREAD_CLASS,
    COL_VOLUME_CLASS,
)
from evidence.engine import EvidenceEngine
from evidence.rules import (
    closes_lower,
    closes_lower_than_previous,
    has_strong_spread,
    is_above_average_spread,
    is_bullish_bar,
    is_high_volume,
    is_low_volume,
    is_narrow_spread,
    is_strong_close,
    is_weak_close,
    is_down_bar,
    is_very_high_volume,
    is_up_bar,
    makes_higher_low,
    spread_increasing,
    volume_decreasing,
    volume_increasing,
)
from metrics_engine import MetricsEngine
from models import ClosePosition, Direction, SpreadClass, VolumeClass

SYMBOLS = (
    "BHARTIARTL.NS", "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "INFY.NS", "TCS.NS", "SBIN.NS", "LT.NS",
)


def _candidate(bar, previous) -> bool:
    return (
        Direction(int(bar[COL_DIRECTION])) == Direction.DOWN
        and VolumeClass(int(bar[COL_VOLUME_CLASS])) >= VolumeClass.HIGH
        and SpreadClass(int(bar[COL_SPREAD_CLASS])) >= SpreadClass.ABOVE_AVERAGE
        and ClosePosition(int(bar[COL_CLOSE_POSITION])) >= ClosePosition.UPPER
        and float(bar[COL_LOW]) < float(previous[COL_LOW])
    )


def _audit_symbol(symbol: str) -> dict:
    metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
    builder = EvidenceEngine()
    events = 0
    supply_conflict_events = 0
    demand_interaction_events = 0
    supply = {
        "SUPPLY_COMING_IN_LIKE": 0,
        "INCREASING_SUPPLY_LIKE": 0,
        "HIDDEN_SUPPLY_LIKE": 0,
        "UPTHRUST_LIKE": 0,
        "NO_DEMAND_LIKE": 0,
        "BUYING_CLIMAX_LIKE": 0,
    }
    demand = {
        "STOPPING_VOLUME_LIKE": 0,
        "NO_SUPPLY_LIKE": 0,
        "TEST_LIKE": 0,
        "DEMAND_COMING_IN_LIKE": 0,
        "INCREASING_DEMAND_LIKE": 0,
    }

    for index in range(21, len(metrics)):
        if index + 8 >= len(metrics):
            continue
        bar = builder._create_bar_context(metrics.iloc[index], index)
        previous = builder._create_bar_context(metrics.iloc[index - 1], index - 1)
        if not _candidate(metrics.iloc[index], metrics.iloc[index - 1]):
            continue

        events += 1

        supply_flags = {
            "SUPPLY_COMING_IN_LIKE": (
                is_down_bar(bar)
                and is_high_volume(bar)
                and is_above_average_spread(bar)
                and is_weak_close(bar)
                and volume_increasing(bar, previous)
            ),
            "INCREASING_SUPPLY_LIKE": (
                is_down_bar(bar)
                and volume_increasing(bar, previous)
                and spread_increasing(bar, previous)
            ),
            "HIDDEN_SUPPLY_LIKE": (
                is_up_bar(bar)
                and is_high_volume(bar)
                and closes_lower(bar)
            ),
            "UPTHRUST_LIKE": (
                is_bullish_bar(bar)
                and is_very_high_volume(bar)
                and is_above_average_spread(bar)
                and has_strong_spread(bar)
                and is_weak_close(bar)
                and closes_lower_than_previous(bar, previous)
            ),
            "NO_DEMAND_LIKE": (
                is_bullish_bar(bar)
                and is_low_volume(bar)
                and is_narrow_spread(bar)
            ),
            "BUYING_CLIMAX_LIKE": (
                is_bullish_bar(bar)
                and is_very_high_volume(bar)
                and is_above_average_spread(bar)
                and has_strong_spread(bar)
                and is_weak_close(bar)
            ),
        }

        demand_flags = {
            "STOPPING_VOLUME_LIKE": (
                is_down_bar(bar)
                and is_high_volume(bar)
                and is_above_average_spread(bar)
                and is_strong_close(bar)
            ),
            "NO_SUPPLY_LIKE": (
                is_down_bar(bar)
                and is_low_volume(bar)
                and is_narrow_spread(bar)
                and volume_decreasing(bar, previous)
                and is_weak_close(bar)
            ),
            "TEST_LIKE": (
                is_down_bar(bar)
                and is_low_volume(bar)
                and is_narrow_spread(bar)
                and volume_decreasing(bar, previous)
                and is_strong_close(bar)
                and makes_higher_low(bar, previous)
            ),
            "DEMAND_COMING_IN_LIKE": (
                is_bullish_bar(bar)
                and is_high_volume(bar)
                and is_above_average_spread(bar)
                and volume_increasing(bar, previous)
            ),
            "INCREASING_DEMAND_LIKE": (
                is_bullish_bar(bar)
                and is_high_volume(bar)
                and is_above_average_spread(bar)
                and volume_increasing(bar, previous)
            ),
        }

        supply_hit = any(supply_flags.values())
        demand_hit = any(demand_flags.values())
        supply_conflict_events += int(supply_hit)
        demand_interaction_events += int(demand_hit)

        for name, passed in supply_flags.items():
            if passed:
                supply[name] += 1
        for name, passed in demand_flags.items():
            if passed:
                demand[name] += 1

    return {
        "symbol": symbol,
        "events": events,
        "events_with_supply_conflict": supply_conflict_events,
        "supply_conflict_rate": supply_conflict_events / events if events else 0.0,
        "demand_interaction_events": demand_interaction_events,
        "supply_conflicts": supply,
        "demand_interactions": demand,
    }


def main() -> None:
    failures = []
    results = []
    with ThreadPoolExecutor(max_workers=min(4, len(SYMBOLS))) as executor:
        futures = {executor.submit(_audit_symbol, symbol): symbol for symbol in SYMBOLS}
        for future, symbol in futures.items():
            try:
                results.append(future.result())
            except Exception as exc:
                failures.append({"symbol": symbol, "error": repr(exc)})

    total_events = sum(item["events"] for item in results)
    total_supply_conflicts = sum(item["events_with_supply_conflict"] for item in results)
    total_demand_interactions = sum(item["demand_interaction_events"] for item in results)

    aggregate_supply = {}
    aggregate_demand = {}
    for item in results:
        for name, count in item["supply_conflicts"].items():
            aggregate_supply[name] = aggregate_supply.get(name, 0) + count
        for name, count in item["demand_interactions"].items():
            aggregate_demand[name] = aggregate_demand.get(name, 0) + count

    print("ABSORPTION INTERACTION / CONTRADICTION OPTIMIZED AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": len(results),
        "events": total_events,
        "events_with_supply_conflict": total_supply_conflicts,
        "supply_conflict_rate": total_supply_conflicts / total_events if total_events else 0.0,
        "aggregate_supply_conflicts": aggregate_supply,
        "demand_interaction_events": total_demand_interactions,
        "aggregate_demand_interactions": aggregate_demand,
        "failures": failures,
        "status": "PASS" if not failures and total_events > 0 else "FAIL",
    })
    print("ABSORPTION INTERACTION BY_SYMBOL")
    for item in sorted(results, key=lambda x: x["symbol"]):
        print(item)


if __name__ == "__main__":
    main()
