"""Audit threshold sensitivity for the current Stopping Volume rule.

Read-only diagnostic. Production code, detector logic, and configured weight
are not modified. The audit replays each weekly bar point-in-time and applies
candidate thresholds directly to the current rule's three measurable inputs.
"""
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from itertools import product
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from engine.columns import COL_CLOSE, COL_WEEK, COL_SPREAD_PERCENTILE, COL_VOLUME_PERCENTILE, COL_CLOSE_RATIO
from metrics_engine import MetricsEngine

DEFAULT_SYMBOLS = (
    "BHARTIARTL.NS",
    "RELIANCE.NS",
    "HDFCBANK.NS",
    "ICICIBANK.NS",
    "INFY.NS",
    "TCS.NS",
    "SBIN.NS",
    "LT.NS",
)
MIN_REPLAY_BARS = 20
FORWARD_HORIZON = 8
OUTCOME_THRESHOLD = 0.02

VOLUME_THRESHOLDS = (80.0, 85.0, 90.0)
SPREAD_THRESHOLDS = (60.0, 70.0, 80.0)
CLOSE_THRESHOLDS = (0.55, 0.60, 0.65)


def _classify(forward_return: float) -> str:
    if forward_return > OUTCOME_THRESHOLD:
        return "POSITIVE_8_BAR"
    if forward_return < -OUTCOME_THRESHOLD:
        return "NEGATIVE_8_BAR"
    return "FLAT_8_BAR"


def _empty_stats() -> dict:
    return {
        "events": 0,
        "positive": 0,
        "negative": 0,
        "flat": 0,
        "symbols": set(),
    }


def inspect_symbol(symbol: str) -> list[dict]:
    daily = download_data(symbol)
    metrics = MetricsEngine().calculate(daily_to_weekly(daily))
    events: list[dict] = []

    for index in range(MIN_REPLAY_BARS, len(metrics)):
        future_index = index + FORWARD_HORIZON
        if future_index >= len(metrics):
            break

        row = metrics.iloc[index]
        volume = float(row[COL_VOLUME_PERCENTILE])
        spread = float(row[COL_SPREAD_PERCENTILE])
        close_ratio = float(row[COL_CLOSE_RATIO])

        current = float(row[COL_CLOSE])
        future = float(metrics.iloc[future_index][COL_CLOSE])
        if current != current or future != future or current == 0.0:
            continue

        forward_return = (future - current) / current
        events.append(
            {
                "symbol": symbol,
                "bar_index": index,
                "week": str(row[COL_WEEK]),
                "volume_percentile": volume,
                "spread_percentile": spread,
                "close_ratio": close_ratio,
                "forward_return": forward_return,
                "outcome": _classify(forward_return),
            }
        )

    return events


def _summarize(events: list[dict], volume_min: float, spread_min: float, close_min: float) -> dict:
    matched = [
        e for e in events
        if e["volume_percentile"] >= volume_min
        and e["spread_percentile"] >= spread_min
        and e["close_ratio"] >= close_min
    ]

    positive = sum(e["outcome"] == "POSITIVE_8_BAR" for e in matched)
    negative = sum(e["outcome"] == "NEGATIVE_8_BAR" for e in matched)
    flat = sum(e["outcome"] == "FLAT_8_BAR" for e in matched)
    decisive = positive + negative

    return {
        "volume_min": volume_min,
        "spread_min": spread_min,
        "close_min": close_min,
        "events": len(matched),
        "symbols": len({e["symbol"] for e in matched}),
        "positive": positive,
        "negative": negative,
        "flat": flat,
        "decisive": decisive,
        "positive_decisive_rate": positive / decisive if decisive else None,
    }


def main() -> None:
    symbols = tuple(sys.argv[1:]) or DEFAULT_SYMBOLS
    all_events: list[dict] = []
    failures: list[dict] = []

    with ThreadPoolExecutor(max_workers=min(4, len(symbols))) as executor:
        futures = {executor.submit(inspect_symbol, symbol): symbol for symbol in symbols}
        for future, symbol in futures.items():
            try:
                events = future.result()
                all_events.extend(events)
                print({"symbol": symbol, "bars_audited": len(events)})
            except Exception as exc:
                failures.append({"symbol": symbol, "error": repr(exc)})
                print(f"FAILED {symbol}: {exc!r}")

    rows = [
        _summarize(all_events, volume_min, spread_min, close_min)
        for volume_min, spread_min, close_min in product(
            VOLUME_THRESHOLDS,
            SPREAD_THRESHOLDS,
            CLOSE_THRESHOLDS,
        )
    ]

    baseline = next(
        row for row in rows
        if row["volume_min"] == 85.0
        and row["spread_min"] == 70.0
        and row["close_min"] == 0.60
    )

    robust = [
        row for row in rows
        if row["events"] >= 30
        and row["symbols"] >= max(4, len(symbols) // 2)
        and row["positive_decisive_rate"] is not None
    ]
    robust.sort(
        key=lambda row: (
            row["positive_decisive_rate"],
            row["symbols"],
            -abs(row["events"] - baseline["events"]),
        ),
        reverse=True,
    )

    print("STOPPING VOLUME THRESHOLD SENSITIVITY SUMMARY")
    print({
        "symbols_requested": len(symbols),
        "bars_audited": len(all_events),
        "failures": failures,
        "candidate_combinations": len(rows),
        "baseline": baseline,
    })

    print("STOPPING VOLUME THRESHOLD SENSITIVITY TOP ROBUST CANDIDATES")
    for row in robust[:10]:
        print(row)

    print("STOPPING VOLUME THRESHOLD SENSITIVITY ALL COMBINATIONS")
    for row in rows:
        print(row)


if __name__ == "__main__":
    main()
