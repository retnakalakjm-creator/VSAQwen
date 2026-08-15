"""Audit bearish Stopping Volume candidates for absorption geometry.

Read-only diagnostic. No production detector or weight changes.
"""
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from engine.columns import (
    COL_CLOSE,
    COL_CLOSE_RATIO,
    COL_HIGH,
    COL_LOW,
    COL_OPEN,
    COL_WEEK,
    COL_DIRECTION,
    COL_VOLUME_PERCENTILE,
    COL_SPREAD_PERCENTILE,
    COL_SPREAD,
)
from metrics_engine import MetricsEngine
from models import Direction

DEFAULT_SYMBOLS = (
    "BHARTIARTL.NS", "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "INFY.NS", "TCS.NS", "SBIN.NS", "LT.NS",
)
MIN_REPLAY_BARS = 20
FORWARD_HORIZON = 8
OUTCOME_THRESHOLD = 0.02

CANDIDATES = (
    ("BEARISH", 0.00, 0.00, 0),
    ("BEARISH_TAIL25_CLOSE60", 0.25, 0.60, 0),
    ("BEARISH_TAIL35_CLOSE60", 0.35, 0.60, 0),
    ("BEARISH_TAIL25_CLOSE70", 0.25, 0.70, 0),
    ("BEARISH_TAIL35_CLOSE70", 0.35, 0.70, 0),
    ("BEARISH_TAIL25_CLOSE60_DECLINE3", 0.25, 0.60, 3),
    ("BEARISH_TAIL35_CLOSE60_DECLINE3", 0.35, 0.60, 3),
    ("BEARISH_TAIL25_CLOSE70_DECLINE3", 0.25, 0.70, 3),
    ("BEARISH_TAIL35_CLOSE70_DECLINE3", 0.35, 0.70, 3),
    ("BEARISH_TAIL25_CLOSE60_DECLINE5", 0.25, 0.60, 5),
    ("BEARISH_TAIL35_CLOSE60_DECLINE5", 0.35, 0.60, 5),
)


def outcome(forward_return: float) -> str:
    if forward_return > OUTCOME_THRESHOLD:
        return "POSITIVE_8_BAR"
    if forward_return < -OUTCOME_THRESHOLD:
        return "NEGATIVE_8_BAR"
    return "FLAT_8_BAR"


def summarize(events: list[dict]) -> dict:
    pos = sum(e["outcome"] == "POSITIVE_8_BAR" for e in events)
    neg = sum(e["outcome"] == "NEGATIVE_8_BAR" for e in events)
    flat = sum(e["outcome"] == "FLAT_8_BAR" for e in events)
    decisive = pos + neg
    return {
        "events": len(events),
        "positive": pos,
        "negative": neg,
        "flat": flat,
        "decisive": decisive,
        "positive_decisive_rate": pos / decisive if decisive else None,
    }


def inspect_symbol(symbol: str) -> dict[str, list[dict]]:
    daily = download_data(symbol)
    metrics = MetricsEngine().calculate(daily_to_weekly(daily))
    results = {name: [] for name, *_ in CANDIDATES}

    for index in range(MIN_REPLAY_BARS + 5, len(metrics)):
        future_index = index + FORWARD_HORIZON
        if future_index >= len(metrics):
            break

        row = metrics.iloc[index]
        if Direction(row[COL_DIRECTION]) is not Direction.DOWN:
            continue

        spread = float(row[COL_SPREAD])
        if spread <= 0.0:
            continue

        lower_tail = float(row[COL_OPEN] if row[COL_OPEN] < row[COL_CLOSE] else row[COL_CLOSE]) - float(row[COL_LOW])
        tail_ratio = lower_tail / spread
        close_ratio = float(row[COL_CLOSE_RATIO])
        current = float(row[COL_CLOSE])
        future = float(metrics.iloc[future_index][COL_CLOSE])
        forward_return = (future - current) / current

        for name, min_tail_ratio, min_close_ratio, decline_bars in CANDIDATES:
            if tail_ratio < min_tail_ratio or close_ratio < min_close_ratio:
                continue

            if decline_bars:
                if index < decline_bars:
                    continue
                start_close = float(metrics.iloc[index - decline_bars][COL_CLOSE])
                if not start_close > current:
                    continue

            results[name].append({
                "symbol": symbol,
                "bar_index": index,
                "week": str(row[COL_WEEK]),
                "tail_ratio": tail_ratio,
                "close_ratio": close_ratio,
                "volume_percentile": float(row[COL_VOLUME_PERCENTILE]),
                "spread_percentile": float(row[COL_SPREAD_PERCENTILE]),
                "forward_return": forward_return,
                "outcome": outcome(forward_return),
            })

    return results


def main() -> None:
    symbols = tuple(sys.argv[1:]) or DEFAULT_SYMBOLS
    by_candidate = {name: [] for name, *_ in CANDIDATES}
    failures: list[dict] = []

    with ThreadPoolExecutor(max_workers=min(4, len(symbols))) as executor:
        futures = {executor.submit(inspect_symbol, symbol): symbol for symbol in symbols}
        for future, symbol in futures.items():
            try:
                result = future.result()
                for name, events in result.items():
                    by_candidate[name].extend(events)
            except Exception as exc:
                failures.append({"symbol": symbol, "error": repr(exc)})

    print("STOPPING VOLUME ABSORPTION AUDIT SUMMARY")
    print({
        "symbols_requested": len(symbols),
        "failures": failures,
        "candidates": {name: summarize(events) for name, events in by_candidate.items()},
    })

    print("STOPPING VOLUME ABSORPTION AUDIT BY_SYMBOL")
    for name, events in by_candidate.items():
        by_symbol = {}
        for symbol in symbols:
            by_symbol[symbol] = summarize([e for e in events if e["symbol"] == symbol])
        print({"candidate": name, "by_symbol": by_symbol})


if __name__ == "__main__":
    main()
