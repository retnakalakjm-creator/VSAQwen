"""Analysis-only conflict outcome audit for ABSORPTION."""
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


def _candidate(bar, previous) -> bool:
    return (
        Direction(int(bar[COL_DIRECTION])) == Direction.DOWN
        and VolumeClass(int(bar[COL_VOLUME_CLASS])) >= VolumeClass.HIGH
        and SpreadClass(int(bar[COL_SPREAD_CLASS])) >= SpreadClass.ABOVE_AVERAGE
        and ClosePosition(int(bar[COL_CLOSE_POSITION])) >= ClosePosition.UPPER
        and float(bar[COL_LOW]) < float(previous[COL_LOW])
    )


def _conflict(bar, previous) -> bool:
    return (
        Direction(int(bar[COL_DIRECTION])) == Direction.DOWN
        and VolumeClass(int(bar[COL_VOLUME_CLASS])) > VolumeClass(int(previous[COL_VOLUME_CLASS]))
        and SpreadClass(int(bar[COL_SPREAD_CLASS])) > SpreadClass(int(previous[COL_SPREAD_CLASS]))
    )


def _audit_symbol(symbol: str) -> dict:
    metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
    out = {
        "symbol": symbol,
        "conflict_events": 0,
        "conflict_positive": 0,
        "conflict_negative": 0,
        "conflict_flat": 0,
        "clean_events": 0,
        "clean_positive": 0,
        "clean_negative": 0,
        "clean_flat": 0,
        "conflict_returns": [],
        "clean_returns": [],
    }

    for index in range(21, len(metrics)):
        if index + FORWARD_BARS >= len(metrics):
            continue
        bar = metrics.iloc[index]
        previous = metrics.iloc[index - 1]
        if not _candidate(bar, previous):
            continue

        start = float(bar[COL_CLOSE])
        end = float(metrics.iloc[index + FORWARD_BARS][COL_CLOSE])
        if start == 0.0:
            continue
        forward = end / start - 1.0

        bucket = "conflict" if _conflict(bar, previous) else "clean"
        out[f"{bucket}_events"] += 1
        out[f"{bucket}_returns"].append(forward)
        if forward > 0:
            out[f"{bucket}_positive"] += 1
        elif forward < 0:
            out[f"{bucket}_negative"] += 1
        else:
            out[f"{bucket}_flat"] += 1

    return out


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


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

    conflict_events = sum(x["conflict_events"] for x in results)
    clean_events = sum(x["clean_events"] for x in results)
    conflict_positive = sum(x["conflict_positive"] for x in results)
    clean_positive = sum(x["clean_positive"] for x in results)
    conflict_negative = sum(x["conflict_negative"] for x in results)
    clean_negative = sum(x["clean_negative"] for x in results)
    conflict_flat = sum(x["conflict_flat"] for x in results)
    clean_flat = sum(x["clean_flat"] for x in results)
    conflict_returns = [r for x in results for r in x["conflict_returns"]]
    clean_returns = [r for x in results for r in x["clean_returns"]]

    conflict_decisive = conflict_positive + conflict_negative
    clean_decisive = clean_positive + clean_negative
    conflict_rate = conflict_events / (conflict_events + clean_events) if conflict_events + clean_events else 0.0
    conflict_positive_rate = conflict_positive / conflict_decisive if conflict_decisive else 0.0
    clean_positive_rate = clean_positive / clean_decisive if clean_decisive else 0.0
    conflict_mean = _mean(conflict_returns)
    clean_mean = _mean(clean_returns)

    print("ABSORPTION CONFLICT OUTCOME AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": len(results),
        "conflict_events": conflict_events,
        "clean_events": clean_events,
        "conflict_rate": conflict_rate,
        "conflict_positive_decisive_rate": conflict_positive_rate,
        "clean_positive_decisive_rate": clean_positive_rate,
        "conflict_mean_return": conflict_mean,
        "clean_mean_return": clean_mean,
        "mean_return_gap": conflict_mean - clean_mean,
        "positive_rate_gap": conflict_positive_rate - clean_positive_rate,
        "conflict_flat": conflict_flat,
        "clean_flat": clean_flat,
        "failures": failures,
        "status": "PASS" if not failures else "FAIL",
    })
    print("ABSORPTION CONFLICT OUTCOME BY_SYMBOL")
    for item in sorted(results, key=lambda x: x["symbol"]):
        item = dict(item)
        item.pop("conflict_returns", None)
        item.pop("clean_returns", None)
        item["conflict_positive_decisive_rate"] = (
            item["conflict_positive"] / (item["conflict_positive"] + item["conflict_negative"])
            if item["conflict_positive"] + item["conflict_negative"] else 0.0
        )
        item["clean_positive_decisive_rate"] = (
            item["clean_positive"] / (item["clean_positive"] + item["clean_negative"])
            if item["clean_positive"] + item["clean_negative"] else 0.0
        )
        item["conflict_mean_return"] = _mean(_audit_symbol(item["symbol"])["conflict_returns"])
        item["clean_mean_return"] = _mean(_audit_symbol(item["symbol"])["clean_returns"])
        print(item)


if __name__ == "__main__":
    main()
