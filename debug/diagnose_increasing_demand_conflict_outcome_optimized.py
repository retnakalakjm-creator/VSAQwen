"""Optimized outcome audit for INCREASING_DEMAND supply conflicts.

Compares 8-bar forward outcomes for validated INCREASING_DEMAND events
with and without same-bar supply-side contradiction evidence.
"""
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from engine.columns import COL_CLOSE
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
FORWARD_BARS = 8


def _bar_context(engine: EvidenceEngine, metrics, index: int):
    current = engine._create_bar_context(metrics.iloc[index], index)
    previous = engine._create_bar_context(metrics.iloc[index - 1], index - 1)
    return current, previous


def _conflicts(bar, previous) -> dict[str, bool]:
    return {
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


def _audit_symbol(symbol: str) -> dict:
    metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
    engine = EvidenceEngine()

    conflict_returns: list[float] = []
    clean_returns: list[float] = []
    conflict_positive = 0
    clean_positive = 0
    conflicts = {
        "SUPPLY_COMING_IN_LIKE": 0,
        "INCREASING_SUPPLY_LIKE": 0,
        "HIDDEN_SUPPLY_LIKE": 0,
        "UPTHRUST_LIKE": 0,
        "NO_DEMAND_LIKE": 0,
        "BUYING_CLIMAX_LIKE": 0,
    }

    demand_events = 0
    decisive_events = 0

    for index in range(21, len(metrics) - FORWARD_BARS):
        bar, previous = _bar_context(engine, metrics, index)

        if not (
            is_bullish_bar(bar)
            and is_high_volume(bar)
            and is_above_average_spread(bar)
            and volume_increasing(bar, previous)
        ):
            continue

        demand_events += 1
        flags = _conflicts(bar, previous)
        has_conflict = any(flags.values())
        for name, passed in flags.items():
            if passed:
                conflicts[name] += 1

        start = float(metrics.iloc[index][COL_CLOSE])
        end = float(metrics.iloc[index + FORWARD_BARS][COL_CLOSE])
        if start == 0.0:
            continue
        forward = end / start - 1.0
        decisive_events += 1

        if has_conflict:
            conflict_returns.append(forward)
            conflict_positive += forward > 0
        else:
            clean_returns.append(forward)
            clean_positive += forward > 0

    conflict_count = len(conflict_returns)
    clean_count = len(clean_returns)
    conflict_mean = sum(conflict_returns) / conflict_count if conflict_count else 0.0
    clean_mean = sum(clean_returns) / clean_count if clean_count else 0.0
    conflict_rate = conflict_count / demand_events if demand_events else 0.0

    return {
        "symbol": symbol,
        "demand_events": demand_events,
        "decisive_events": decisive_events,
        "conflict_events": conflict_count,
        "clean_events": clean_count,
        "conflict_rate": conflict_rate,
        "conflict_mean_return": conflict_mean,
        "clean_mean_return": clean_mean,
        "mean_return_delta_conflict_minus_clean": conflict_mean - clean_mean,
        "conflict_positive_rate": conflict_positive / conflict_count if conflict_count else 0.0,
        "clean_positive_rate": clean_positive / clean_count if clean_count else 0.0,
        "positive_rate_delta_conflict_minus_clean": (
            conflict_positive / conflict_count - clean_positive / clean_count
            if conflict_count and clean_count else 0.0
        ),
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

    demand_events = sum(item["demand_events"] for item in results)
    decisive_events = sum(item["decisive_events"] for item in results)
    conflict_events = sum(item["conflict_events"] for item in results)
    clean_events = sum(item["clean_events"] for item in results)

    conflict_returns_weighted = [
        (item["conflict_mean_return"], item["conflict_events"])
        for item in results if item["conflict_events"]
    ]
    clean_returns_weighted = [
        (item["clean_mean_return"], item["clean_events"])
        for item in results if item["clean_events"]
    ]
    conflict_mean = (
        sum(mean * count for mean, count in conflict_returns_weighted)
        / conflict_events if conflict_events else 0.0
    )
    clean_mean = (
        sum(mean * count for mean, count in clean_returns_weighted)
        / clean_events if clean_events else 0.0
    )

    conflict_positive = sum(
        item["conflict_positive_rate"] * item["conflict_events"]
        for item in results
    )
    clean_positive = sum(
        item["clean_positive_rate"] * item["clean_events"]
        for item in results
    )

    print("INCREASING DEMAND CONFLICT OUTCOME OPTIMIZED AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": len(results),
        "demand_events": demand_events,
        "decisive_events": decisive_events,
        "conflict_events": conflict_events,
        "clean_events": clean_events,
        "conflict_rate": conflict_events / demand_events if demand_events else 0.0,
        "conflict_mean_return": conflict_mean,
        "clean_mean_return": clean_mean,
        "mean_return_delta_conflict_minus_clean": conflict_mean - clean_mean,
        "conflict_positive_rate": conflict_positive / conflict_events if conflict_events else 0.0,
        "clean_positive_rate": clean_positive / clean_events if clean_events else 0.0,
        "positive_rate_delta_conflict_minus_clean": (
            conflict_positive / conflict_events - clean_positive / clean_events
            if conflict_events and clean_events else 0.0
        ),
        "failures": failures,
        "status": "PASS" if not failures and conflict_events > 0 else "FAIL",
    })
    print("INCREASING DEMAND CONFLICT OUTCOME BY_SYMBOL")
    for item in results:
        print(item)


if __name__ == "__main__":
    main()
