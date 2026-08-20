"""Analysis-only interaction audit for HIDDEN_DEMAND.

Candidate definition matches the validated HIDDEN_DEMAND population:
- bearish/down bar
- high volume
- strong close

Supply-side contradiction classes are evaluated using the same point-in-time
semantic rule families used by the current supply collector. The audit does
not modify production detection, weights, or scoring.
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
from metrics_engine import MetricsEngine
from models import ClosePosition, Direction, SpreadClass, VolumeClass

SYMBOLS = (
    "BHARTIARTL.NS", "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "INFY.NS", "TCS.NS", "SBIN.NS", "LT.NS",
)


def _candidate(bar) -> bool:
    return (
        Direction(int(bar[COL_DIRECTION])) == Direction.DOWN
        and VolumeClass(int(bar[COL_VOLUME_CLASS])) >= VolumeClass.HIGH
        and ClosePosition(int(bar[COL_CLOSE_POSITION])) >= ClosePosition.UPPER
    )


def _audit_symbol(symbol: str) -> dict:
    metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
    events = 0
    conflict_events = 0
    counts = {
        "SUPPLY_COMING_IN_LIKE": 0,
        "INCREASING_SUPPLY_LIKE": 0,
        "HIDDEN_SUPPLY_LIKE": 0,
        "UPTHRUST_LIKE": 0,
        "NO_DEMAND_LIKE": 0,
        "BUYING_CLIMAX_LIKE": 0,
    }

    for index in range(21, len(metrics)):
        bar = metrics.iloc[index]
        previous = metrics.iloc[index - 1]
        if index + 8 >= len(metrics) or not _candidate(bar):
            continue

        events += 1
        direction = Direction(int(bar[COL_DIRECTION]))
        volume = VolumeClass(int(bar[COL_VOLUME_CLASS]))
        spread = SpreadClass(int(bar[COL_SPREAD_CLASS]))
        close_position = ClosePosition(int(bar[COL_CLOSE_POSITION]))
        previous_volume = VolumeClass(int(previous[COL_VOLUME_CLASS]))
        previous_spread = SpreadClass(int(previous[COL_SPREAD_CLASS]))

        increasing_volume = volume > previous_volume
        increasing_spread = spread > previous_spread
        above_average_spread = spread >= SpreadClass.ABOVE_AVERAGE
        very_high_volume = volume >= VolumeClass.VERY_HIGH
        bullish = direction == Direction.UP
        bearish = direction == Direction.DOWN
        weak_close = close_position <= ClosePosition.LOWER
        low_volume = volume <= VolumeClass.LOW
        narrow_spread = spread == SpreadClass.NARROW

        supply_coming_in = (
            bearish
            and volume >= VolumeClass.HIGH
            and above_average_spread
            and weak_close
            and increasing_volume
        )
        increasing_supply = (
            bearish and increasing_volume and increasing_spread
        )
        hidden_supply = bullish and volume >= VolumeClass.HIGH and weak_close
        upthrust = bullish and very_high_volume and above_average_spread and weak_close
        no_demand = bullish and low_volume and narrow_spread
        buying_climax = bullish and very_high_volume and above_average_spread

        flags = {
            "SUPPLY_COMING_IN_LIKE": supply_coming_in,
            "INCREASING_SUPPLY_LIKE": increasing_supply,
            "HIDDEN_SUPPLY_LIKE": hidden_supply,
            "UPTHRUST_LIKE": upthrust,
            "NO_DEMAND_LIKE": no_demand,
            "BUYING_CLIMAX_LIKE": buying_climax,
        }

        for code, flag in flags.items():
            counts[code] += int(flag)
        conflict_events += int(any(flags.values()))

    return {
        "symbol": symbol,
        "events": events,
        "events_with_supply_conflict": conflict_events,
        "conflicts": counts,
    }


def main() -> None:
    failures = []
    results = []
    with ThreadPoolExecutor(max_workers=min(4, len(SYMBOLS))) as executor:
        futures = {executor.submit(_audit_symbol, s): s for s in SYMBOLS}
        for future, symbol in futures.items():
            try:
                results.append(future.result())
            except Exception as exc:
                failures.append({"symbol": symbol, "error": repr(exc)})

    events = sum(item["events"] for item in results)
    conflict_events = sum(item["events_with_supply_conflict"] for item in results)
    aggregate = {}
    for item in results:
        for code, value in item["conflicts"].items():
            aggregate[code] = aggregate.get(code, 0) + value

    print("HIDDEN DEMAND INTERACTION / CONTRADICTION OPTIMIZED AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": len(results),
        "events": events,
        "events_with_supply_conflict": conflict_events,
        "conflict_rate": conflict_events / events if events else 0.0,
        "aggregate_conflicts": aggregate,
        "failures": failures,
        "status": "PASS" if not failures else "FAIL",
    })
    print("HIDDEN DEMAND INTERACTION / CONTRADICTION BY_SYMBOL")
    for item in sorted(results, key=lambda x: x["symbol"]):
        print(item)


if __name__ == "__main__":
    main()
