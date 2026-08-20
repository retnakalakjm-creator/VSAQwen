"""Analysis-only candidate audit for DEMAND_DRYING_UP.

No production detector or scoring path is modified.

Candidate semantics under test:
- bullish/up bar
- volume decreasing versus previous bar
- spread decreasing versus previous bar

This deliberately differs from NO_DEMAND, which already uses low volume
and narrow spread. The audit asks whether diminishing buying effort itself
adds measurable value.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from engine.columns import COL_CLOSE, COL_DIRECTION, COL_SPREAD_CLASS, COL_VOLUME_CLASS
from metrics_engine import MetricsEngine
from models import Direction, SpreadClass, VolumeClass

SYMBOLS = (
    "BHARTIARTL.NS", "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "INFY.NS", "TCS.NS", "SBIN.NS", "LT.NS",
)
FORWARD_BARS = 8


def _audit_symbol(symbol: str) -> dict:
    metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
    events = positive = negative = flat = 0
    returns: list[float] = []

    for index in range(21, len(metrics)):
        bar = metrics.iloc[index]
        previous = metrics.iloc[index - 1]

        direction = Direction(int(bar[COL_DIRECTION]))
        volume = VolumeClass(int(bar[COL_VOLUME_CLASS]))
        previous_volume = VolumeClass(int(previous[COL_VOLUME_CLASS]))
        spread = SpreadClass(int(bar[COL_SPREAD_CLASS]))
        previous_spread = SpreadClass(int(previous[COL_SPREAD_CLASS]))

        candidate = (
            direction == Direction.UP
            and volume < previous_volume
            and spread < previous_spread
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

        forward = end / start - 1.0
        events += 1
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

    print("DEMAND DRYING UP CANDIDATE AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": len(results),
        "candidate_events": events,
        "positive": positive,
        "negative": negative,
        "flat": flat,
        "decisive": decisive,
        "positive_decisive_rate": positive / decisive if decisive else 0.0,
        "mean_return": mean_return,
        "failures": failures,
        "status": "PASS" if not failures else "FAIL",
    })
    print("DEMAND DRYING UP CANDIDATE BY_SYMBOL")
    for item in sorted(results, key=lambda x: x["symbol"]):
        print(item)


if __name__ == "__main__":
    main()
