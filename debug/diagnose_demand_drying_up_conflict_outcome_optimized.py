"""Analysis-only conflict-outcome audit for DEMAND_DRYING_UP.

Compares candidate events with a supply-side interaction against clean candidate
 events using the standard 8-bar forward outcome. No production logic changes.
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
    COL_CLOSE,
    COL_DIRECTION,
    COL_HIGH,
    COL_LOW,
    COL_SPREAD_CLASS,
    COL_VOLUME_CLASS,
)
from metrics_engine import MetricsEngine
from models import Direction, SpreadClass, VolumeClass

SYMBOLS = (
    "BHARTIARTL.NS", "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "INFY.NS", "TCS.NS", "SBIN.NS", "LT.NS",
)
FORWARD_BARS = 8


def _candidate(bar, previous) -> bool:
    direction = Direction(int(bar[COL_DIRECTION]))
    volume = VolumeClass(int(bar[COL_VOLUME_CLASS]))
    spread = SpreadClass(int(bar[COL_SPREAD_CLASS]))
    previous_volume = VolumeClass(int(previous[COL_VOLUME_CLASS]))
    previous_spread = SpreadClass(int(previous[COL_SPREAD_CLASS]))
    return (
        direction == Direction.UP
        and volume < previous_volume
        and spread < previous_spread
    )


def _conflict(bar, previous) -> bool:
    direction = Direction(int(bar[COL_DIRECTION]))
    volume = VolumeClass(int(bar[COL_VOLUME_CLASS]))
    spread = SpreadClass(int(bar[COL_SPREAD_CLASS]))
    previous_volume = VolumeClass(int(previous[COL_VOLUME_CLASS]))
    previous_spread = SpreadClass(int(previous[COL_SPREAD_CLASS]))
    increasing_volume = volume > previous_volume
    increasing_spread = spread > previous_spread
    above_average_spread = spread >= SpreadClass.ABOVE_AVERAGE
    very_high_volume = volume >= VolumeClass.VERY_HIGH
    bullish = direction == Direction.UP
    close_position = bar["close_position"] if "close_position" in bar else 0
    # Existing supply interaction semantics used in the prior audit.
    no_demand_like = bullish and volume <= VolumeClass.LOW and spread == SpreadClass.NARROW
    buying_climax_like = bullish and very_high_volume and above_average_spread
    return no_demand_like or buying_climax_like


def _audit_symbol(symbol: str) -> dict:
    metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
    conflict_returns: list[float] = []
    clean_returns: list[float] = []
    conflict_positive = conflict_negative = 0
    clean_positive = clean_negative = 0

    for index in range(21, len(metrics)):
        bar = metrics.iloc[index]
        previous = metrics.iloc[index - 1]
        future_index = index + FORWARD_BARS
        if future_index >= len(metrics) or not _candidate(bar, previous):
            continue

        start = float(bar[COL_CLOSE])
        end = float(metrics.iloc[future_index][COL_CLOSE])
        if start == 0.0:
            continue
        forward = end / start - 1.0
        if _conflict(bar, previous):
            conflict_returns.append(forward)
            if forward > 0:
                conflict_positive += 1
            elif forward < 0:
                conflict_negative += 1
        else:
            clean_returns.append(forward)
            if forward > 0:
                clean_positive += 1
            elif forward < 0:
                clean_negative += 1

    return {
        "symbol": symbol,
        "conflict_events": len(conflict_returns),
        "conflict_positive": conflict_positive,
        "conflict_negative": conflict_negative,
        "conflict_mean_return": sum(conflict_returns) / len(conflict_returns) if conflict_returns else 0.0,
        "clean_events": len(clean_returns),
        "clean_positive": clean_positive,
        "clean_negative": clean_negative,
        "clean_mean_return": sum(clean_returns) / len(clean_returns) if clean_returns else 0.0,
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

    conflict_events = sum(item["conflict_events"] for item in results)
    clean_events = sum(item["clean_events"] for item in results)
    conflict_positive = sum(item["conflict_positive"] for item in results)
    conflict_negative = sum(item["conflict_negative"] for item in results)
    clean_positive = sum(item["clean_positive"] for item in results)
    clean_negative = sum(item["clean_negative"] for item in results)

    conflict_mean = (
        sum(item["conflict_mean_return"] * item["conflict_events"] for item in results) / conflict_events
        if conflict_events else 0.0
    )
    clean_mean = (
        sum(item["clean_mean_return"] * item["clean_events"] for item in results) / clean_events
        if clean_events else 0.0
    )
    conflict_decisive = conflict_positive + conflict_negative
    clean_decisive = clean_positive + clean_negative

    print("DEMAND DRYING UP CONFLICT OUTCOME AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": len(results),
        "conflict_events": conflict_events,
        "clean_events": clean_events,
        "conflict_rate": conflict_events / (conflict_events + clean_events) if conflict_events + clean_events else 0.0,
        "conflict_positive_decisive_rate": conflict_positive / conflict_decisive if conflict_decisive else 0.0,
        "clean_positive_decisive_rate": clean_positive / clean_decisive if clean_decisive else 0.0,
        "conflict_mean_return": conflict_mean,
        "clean_mean_return": clean_mean,
        "mean_return_gap": conflict_mean - clean_mean,
        "failures": failures,
        "status": "PASS" if not failures else "FAIL",
    })
    print("DEMAND DRYING UP CONFLICT OUTCOME BY_SYMBOL")
    for item in sorted(results, key=lambda item: item["symbol"]):
        print(item)


if __name__ == "__main__":
    main()
