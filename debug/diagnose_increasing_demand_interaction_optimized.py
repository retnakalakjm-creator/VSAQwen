"""Optimized interaction/contradiction audit for INCREASING_DEMAND.

Uses the same BarContext-based conditions as the production detector and
checks same-bar supply-side contradictions without rebuilding EvidenceEngine.
"""
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
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
    is_weak_close,
    is_down_bar,
    is_very_high_volume,
    is_up_bar,
    spread_increasing,
    volume_increasing,
)
from metrics_engine import MetricsEngine

SYMBOLS = (
    "BHARTIARTL.NS", "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "INFY.NS", "TCS.NS", "SBIN.NS", "LT.NS",
)


def _audit_symbol(symbol: str) -> dict:
    metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
    context_builder = EvidenceEngine()
    total = 0
    events_with_conflict = 0
    conflicts = {
        "SUPPLY_COMING_IN_LIKE": 0,
        "INCREASING_SUPPLY_LIKE": 0,
        "HIDDEN_SUPPLY_LIKE": 0,
        "UPTHRUST_LIKE": 0,
        "NO_DEMAND_LIKE": 0,
        "BUYING_CLIMAX_LIKE": 0,
    }

    for index in range(21, len(metrics)):
        bar = context_builder._create_bar_context(metrics.iloc[index], index)
        previous = context_builder._create_bar_context(metrics.iloc[index - 1], index - 1)

        demand = (
            is_bullish_bar(bar)
            and is_high_volume(bar)
            and is_above_average_spread(bar)
            and volume_increasing(bar, previous)
        )
        if not demand:
            continue

        total += 1

        flags = {
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

        if any(flags.values()):
            events_with_conflict += 1
            for name, passed in flags.items():
                if passed:
                    conflicts[name] += 1

    return {
        "symbol": symbol,
        "events": total,
        "events_with_supply_conflict": events_with_conflict,
        "conflict_rate": events_with_conflict / total if total else 0.0,
        "conflicts": conflicts,
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
    total_conflicts = sum(item["events_with_supply_conflict"] for item in results)
    aggregate = {}
    for item in results:
        for name, count in item["conflicts"].items():
            aggregate[name] = aggregate.get(name, 0) + count

    conflict_rate = total_conflicts / total_events if total_events else 0.0
    print("INCREASING DEMAND INTERACTION / CONTRADICTION OPTIMIZED AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": len(results),
        "events": total_events,
        "events_with_supply_conflict": total_conflicts,
        "conflict_rate": conflict_rate,
        "aggregate_conflicts": aggregate,
        "failures": failures,
        "status": "PASS" if not failures and total_events > 0 else "FAIL",
    })
    print("INCREASING DEMAND INTERACTION BY_SYMBOL")
    for item in results:
        print(item)


if __name__ == "__main__":
    main()
