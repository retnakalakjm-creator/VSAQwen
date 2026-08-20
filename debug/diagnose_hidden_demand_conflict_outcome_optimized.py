"""Analysis-only outcome comparison for HIDDEN_DEMAND conflicts.

Uses the same validated candidate definition and the exact supply-conflict
logic from diagnose_hidden_demand_interaction_optimized.py.
No production detector, registry, weight, or scoring logic is modified.
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
FORWARD_BARS = 8


def _candidate(bar) -> bool:
    return (
        Direction(int(bar[COL_DIRECTION])) == Direction.DOWN
        and VolumeClass(int(bar[COL_VOLUME_CLASS])) >= VolumeClass.HIGH
        and ClosePosition(int(bar["close_position"])) >= ClosePosition.UPPER
    )


def _is_conflict(bar, previous) -> bool:
    volume = VolumeClass(int(bar[COL_VOLUME_CLASS]))
    spread = SpreadClass(int(bar[COL_SPREAD_CLASS]))
    previous_volume = VolumeClass(int(previous[COL_VOLUME_CLASS]))
    previous_spread = SpreadClass(int(previous[COL_SPREAD_CLASS]))
    direction = Direction(int(bar[COL_DIRECTION]))
    close_position = ClosePosition(int(bar["close_position"]))

    increasing_volume = volume > previous_volume
    increasing_spread = spread > previous_spread
    above_average_spread = spread >= SpreadClass.ABOVE_AVERAGE
    very_high_volume = volume >= VolumeClass.VERY_HIGH
    bullish = direction == Direction.UP
    bearish = direction == Direction.DOWN
    weak_close = close_position <= ClosePosition.LOWER
    low_volume = volume <= VolumeClass.LOW
    narrow_spread = spread == SpreadClass.NARROW

    return (
        bearish
        and volume >= VolumeClass.HIGH
        and above_average_spread
        and weak_close
        and increasing_volume
    ) or (
        bearish
        and increasing_volume
        and increasing_spread
    ) or (
        bullish
        and volume >= VolumeClass.HIGH
        and weak_close
    ) or (
        bullish
        and very_high_volume
        and above_average_spread
        and weak_close
    ) or (
        bullish
        and low_volume
        and narrow_spread
    ) or (
        bullish
        and very_high_volume
        and above_average_spread
    )


def _audit_symbol(symbol: str) -> dict:
    metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
    conflict_returns: list[float] = []
    clean_returns: list[float] = []
    conflict_positive = conflict_negative = conflict_flat = 0
    clean_positive = clean_negative = clean_flat = 0

    for index in range(21, len(metrics)):
        future_index = index + FORWARD_BARS
        if future_index >= len(metrics):
            continue

        bar = metrics.iloc[index]
        previous = metrics.iloc[index - 1]
        if not _candidate(bar):
            continue

        start = float(bar[COL_CLOSE])
        end = float(metrics.iloc[future_index][COL_CLOSE])
        if start == 0.0:
            continue

        forward = end / start - 1.0
        if _is_conflict(bar, previous):
            conflict_returns.append(forward)
            if forward > 0:
                conflict_positive += 1
            elif forward < 0:
                conflict_negative += 1
            else:
                conflict_flat += 1
        else:
            clean_returns.append(forward)
            if forward > 0:
                clean_positive += 1
            elif forward < 0:
                clean_negative += 1
            else:
                clean_flat += 1

    conflict_decisive = conflict_positive + conflict_negative
    clean_decisive = clean_positive + clean_negative
    return {
        "symbol": symbol,
        "conflict_events": len(conflict_returns),
        "conflict_positive": conflict_positive,
        "conflict_negative": conflict_negative,
        "conflict_flat": conflict_flat,
        "conflict_positive_decisive_rate": (
            conflict_positive / conflict_decisive if conflict_decisive else 0.0
        ),
        "conflict_mean_return": (
            sum(conflict_returns) / len(conflict_returns)
            if conflict_returns else 0.0
        ),
        "clean_events": len(clean_returns),
        "clean_positive": clean_positive,
        "clean_negative": clean_negative,
        "clean_flat": clean_flat,
        "clean_positive_decisive_rate": (
            clean_positive / clean_decisive if clean_decisive else 0.0
        ),
        "clean_mean_return": (
            sum(clean_returns) / len(clean_returns)
            if clean_returns else 0.0
        ),
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

    conflict_events = sum(item["conflict_events"] for item in results)
    conflict_positive = sum(item["conflict_positive"] for item in results)
    conflict_negative = sum(item["conflict_negative"] for item in results)
    conflict_flat = sum(item["conflict_flat"] for item in results)
    clean_events = sum(item["clean_events"] for item in results)
    clean_positive = sum(item["clean_positive"] for item in results)
    clean_negative = sum(item["clean_negative"] for item in results)
    clean_flat = sum(item["clean_flat"] for item in results)

    conflict_decisive = conflict_positive + conflict_negative
    clean_decisive = clean_positive + clean_negative
    conflict_mean = (
        sum(item["conflict_mean_return"] * item["conflict_events"] for item in results)
        / conflict_events
        if conflict_events else 0.0
    )
    clean_mean = (
        sum(item["clean_mean_return"] * item["clean_events"] for item in results)
        / clean_events
        if clean_events else 0.0
    )

    print("HIDDEN DEMAND CONFLICT OUTCOME AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": len(results),
        "conflict_events": conflict_events,
        "clean_events": clean_events,
        "conflict_rate": (
            conflict_events / (conflict_events + clean_events)
            if conflict_events + clean_events else 0.0
        ),
        "conflict_positive_decisive_rate": (
            conflict_positive / conflict_decisive if conflict_decisive else 0.0
        ),
        "clean_positive_decisive_rate": (
            clean_positive / clean_decisive if clean_decisive else 0.0
        ),
        "conflict_mean_return": conflict_mean,
        "clean_mean_return": clean_mean,
        "mean_return_gap": conflict_mean - clean_mean,
        "positive_rate_gap": (
            conflict_positive / conflict_decisive - clean_positive / clean_decisive
            if conflict_decisive and clean_decisive else 0.0
        ),
        "failures": failures,
        "status": "PASS" if not failures else "FAIL",
    })
    print("HIDDEN DEMAND CONFLICT OUTCOME BY_SYMBOL")
    for item in sorted(results, key=lambda x: x["symbol"]):
        print(item)


if __name__ == "__main__":
    main()
