"""Analysis-only interaction audit for DEMAND_DRYING_UP.

Candidate semantics:
- bullish/up bar
- declining volume versus previous bar
- declining spread versus previous bar

The event is treated as contextual demand-exhaustion evidence. Supply-side
observations are measured for overlap/conflict only; nothing here changes
production detector, registry, weight, or scoring logic.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from engine.columns import COL_DIRECTION, COL_SPREAD_CLASS, COL_VOLUME_CLASS
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


def _audit_symbol(symbol: str) -> dict:
    metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
    events = 0
    conflicts = {
        "SUPPLY_COMING_IN_LIKE": 0,
        "INCREASING_SUPPLY_LIKE": 0,
        "HIDDEN_SUPPLY_LIKE": 0,
        "UPTHRUST_LIKE": 0,
        "NO_DEMAND_LIKE": 0,
        "BUYING_CLIMAX_LIKE": 0,
    }
    conflict_events = 0

    for index in range(21, len(metrics)):
        bar = metrics.iloc[index]
        previous = metrics.iloc[index - 1]
        if index + FORWARD_BARS >= len(metrics) or not _candidate(bar, previous):
            continue

        events += 1
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
        bearish = direction == Direction.DOWN
        weak_close = False
        low_volume = volume <= VolumeClass.LOW
        narrow_spread = spread == SpreadClass.NARROW

        hits = {
            "SUPPLY_COMING_IN_LIKE": bearish and volume >= VolumeClass.HIGH and above_average_spread and weak_close and increasing_volume,
            "INCREASING_SUPPLY_LIKE": bearish and increasing_volume and increasing_spread,
            "HIDDEN_SUPPLY_LIKE": bullish and volume >= VolumeClass.HIGH and weak_close,
            "UPTHRUST_LIKE": bullish and very_high_volume and above_average_spread and weak_close,
            "NO_DEMAND_LIKE": bullish and low_volume and narrow_spread,
            "BUYING_CLIMAX_LIKE": bullish and very_high_volume and above_average_spread,
        }

        event_conflict = False
        for code, hit in hits.items():
            if hit:
                conflicts[code] += 1
                event_conflict = True
        conflict_events += int(event_conflict)

    return {"symbol": symbol, "events": events, "events_with_supply_conflict": conflict_events, "conflicts": conflicts}


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

    events = sum(item["events"] for item in results)
    conflict_events = sum(item["events_with_supply_conflict"] for item in results)
    aggregate = {}
    for item in results:
        for code, value in item["conflicts"].items():
            aggregate[code] = aggregate.get(code, 0) + value

    print("DEMAND DRYING UP INTERACTION / CONTRADICTION OPTIMIZED AUDIT")
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
    print("DEMAND DRYING UP INTERACTION / CONTRADICTION BY_SYMBOL")
    for item in sorted(results, key=lambda x: x["symbol"]):
        print(item)


if __name__ == "__main__":
    main()
