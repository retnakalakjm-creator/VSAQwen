"""Analysis-only semantic-quality audit for HIDDEN_DEMAND.

Candidate definition matches the validated candidate audit exactly:
- bearish/down bar
- high volume
- strong close

Additional observations are treated as quality descriptors only:
- increasing volume
- higher low
- non-climactic volume

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
    COL_CLOSE_POSITION,
    COL_DIRECTION,
    COL_LOW,
    COL_VOLUME_CLASS,
)
from metrics_engine import MetricsEngine
from models import ClosePosition, Direction, VolumeClass

SYMBOLS = (
    "BHARTIARTL.NS", "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "INFY.NS", "TCS.NS", "SBIN.NS", "LT.NS",
)
FORWARD_BARS = 8


def _audit_symbol(symbol: str) -> dict:
    metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
    events = positive = negative = flat = 0
    volume_increasing_count = 0
    higher_low_count = 0
    non_climactic_count = 0
    returns: list[float] = []

    for index in range(21, len(metrics)):
        bar = metrics.iloc[index]
        previous = metrics.iloc[index - 1]

        direction = Direction(int(bar[COL_DIRECTION]))
        volume = VolumeClass(int(bar[COL_VOLUME_CLASS]))
        close_position = ClosePosition(int(bar[COL_CLOSE_POSITION]))

        candidate = (
            direction == Direction.DOWN
            and volume >= VolumeClass.HIGH
            and close_position >= ClosePosition.UPPER
        )
        if not candidate:
            continue

        future_index = index + FORWARD_BARS
        if future_index >= len(metrics):
            continue

        start = float(bar[COL_CLOSE])
        end = float(metrics.iloc[future_index][COL_CLOSE])
        if start == 0.0:
            continue

        events += 1

        previous_volume = VolumeClass(int(previous[COL_VOLUME_CLASS]))
        if volume > previous_volume:
            volume_increasing_count += 1
        if float(bar[COL_LOW]) > float(previous[COL_LOW]):
            higher_low_count += 1
        if volume < VolumeClass.VERY_HIGH:
            non_climactic_count += 1

        forward = end / start - 1.0
        returns.append(forward)
        if forward > 0:
            positive += 1
        elif forward < 0:
            negative += 1
        else:
            flat += 1

    decisive = positive + negative
    return {
        "symbol": symbol,
        "events": events,
        "positive": positive,
        "negative": negative,
        "flat": flat,
        "decisive": decisive,
        "positive_decisive_rate": positive / decisive if decisive else 0.0,
        "mean_return": sum(returns) / len(returns) if returns else 0.0,
        "volume_increasing": volume_increasing_count,
        "higher_low": higher_low_count,
        "non_climactic": non_climactic_count,
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
    positive = sum(item["positive"] for item in results)
    negative = sum(item["negative"] for item in results)
    flat = sum(item["flat"] for item in results)
    decisive = positive + negative
    mean_return = (
        sum(item["mean_return"] * item["events"] for item in results) / events
        if events else 0.0
    )
    volume_increasing = sum(item["volume_increasing"] for item in results)
    higher_low = sum(item["higher_low"] for item in results)
    non_climactic = sum(item["non_climactic"] for item in results)

    print("HIDDEN DEMAND SEMANTIC QUALITY AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": len(results),
        "events": events,
        "positive": positive,
        "negative": negative,
        "flat": flat,
        "decisive": decisive,
        "positive_decisive_rate": positive / decisive if decisive else 0.0,
        "mean_return": mean_return,
        "volume_increasing": volume_increasing,
        "higher_low": higher_low,
        "non_climactic": non_climactic,
        "failures": failures,
        "status": "PASS" if not failures else "FAIL",
    })
    print("HIDDEN DEMAND SEMANTIC QUALITY BY_SYMBOL")
    for item in sorted(results, key=lambda x: x["symbol"]):
        print(item)


if __name__ == "__main__":
    main()
