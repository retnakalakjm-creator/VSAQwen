"""Analysis-only semantic-quality audit for ABSORPTION."""
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
    COL_HIGH,
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
    events = upper_close = lower_low = high_volume = wide_spread = 0
    failures = []

    for index in range(21, len(metrics)):
        bar = metrics.iloc[index]
        previous = metrics.iloc[index - 1]
        if not _candidate(bar, previous):
            continue

        events += 1
        upper = ClosePosition(int(bar[COL_CLOSE_POSITION])) >= ClosePosition.UPPER
        lower_low_ok = float(bar[COL_LOW]) < float(previous[COL_LOW])
        high_volume = VolumeClass(int(bar[COL_VOLUME_CLASS])) >= VolumeClass.HIGH
        wide_spread = SpreadClass(int(bar[COL_SPREAD_CLASS])) >= SpreadClass.ABOVE_AVERAGE
        upper_close += int(upper)
        lower_low += int(lower_low_ok)
        high_volume += int(high_volume)
        wide_spread += int(wide_spread)

        if not (upper and lower_low_ok and high_volume and wide_spread):
            failures.append(index)

    return {
        "symbol": symbol,
        "events": events,
        "upper_close": upper_close,
        "lower_low": lower_low,
        "high_volume": high_volume,
        "wide_spread": wide_spread,
        "failures": failures,
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
    upper_close = sum(item["upper_close"] for item in results)
    lower_low = sum(item["lower_low"] for item in results)
    high_volume = sum(item["high_volume"] for item in results)
    wide_spread = sum(item["wide_spread"] for item in results)
    semantic_failures = sum(len(item["failures"]) for item in results)

    print("ABSORPTION SEMANTIC QUALITY AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": len(results),
        "events": events,
        "upper_close": upper_close,
        "lower_low": lower_low,
        "high_volume": high_volume,
        "wide_spread": wide_spread,
        "semantic_failures": semantic_failures,
        "failures": failures,
        "status": "PASS" if not failures and semantic_failures == 0 else "FAIL",
    })
    print("ABSORPTION SEMANTIC QUALITY BY_SYMBOL")
    for item in sorted(results, key=lambda x: x["symbol"]):
        print(item)


if __name__ == "__main__":
    main()
