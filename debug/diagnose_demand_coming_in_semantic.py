from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data import daily_to_weekly, download_data
from engine.columns import (
    COL_CLOSE,
    COL_CLOSE_POSITION,
    COL_DIRECTION,
    COL_HIGH,
    COL_LOW,
    COL_SPREAD_CLASS,
    COL_VOLUME_CLASS,
    COL_WEEK,
)
from evidence.rules import is_high_volume, is_very_high_volume, has_strong_spread, volume_increasing, makes_higher_low
from metrics_engine import MetricsEngine
from models import Direction, SpreadClass, VolumeClass


SYMBOLS = (
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


def is_candidate(row) -> bool:
    return (
        Direction(int(row[COL_DIRECTION])) == Direction.DOWN
        and VolumeClass(int(row[COL_VOLUME_CLASS])) >= VolumeClass.HIGH
        and SpreadClass(int(row[COL_SPREAD_CLASS])) >= SpreadClass.ABOVE_AVERAGE
        and int(row[COL_CLOSE_POSITION]) >= 2
    )


def outcome(metrics, bar_index: int) -> str:
    future = bar_index + FORWARD_HORIZON
    if future >= len(metrics):
        return "INSUFFICIENT_FORWARD_DATA"
    current = float(metrics.iloc[bar_index][COL_CLOSE])
    future_close = float(metrics.iloc[future][COL_CLOSE])
    if future_close > current:
        return "POSITIVE_8_BAR"
    if future_close < current:
        return "NEGATIVE_8_BAR"
    return "FLAT_8_BAR"


def collect_symbol(symbol: str) -> list[dict]:
    metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
    rows: list[dict] = []

    for bar_index in range(MIN_REPLAY_BARS, len(metrics)):
        row = metrics.iloc[bar_index]
        if not is_candidate(row):
            continue

        previous = metrics.iloc[bar_index - 1]
        rows.append(
            {
                "symbol": symbol,
                "bar_index": bar_index,
                "week": str(row[COL_WEEK]),
                "outcome": outcome(metrics, bar_index),
                "very_high_volume": is_very_high_volume(row),
                "wide_spread": has_strong_spread(row),
                "volume_increasing": volume_increasing(row, previous),
                "higher_low": makes_higher_low(row, previous),
                "volume_class": int(row[COL_VOLUME_CLASS]),
                "spread_class": int(row[COL_SPREAD_CLASS]),
                "close_position": int(row[COL_CLOSE_POSITION]),
            }
        )

    return rows


def summarize(rows: list[dict]) -> dict:
    counts = Counter(row["outcome"] for row in rows)
    decisive = counts["POSITIVE_8_BAR"] + counts["NEGATIVE_8_BAR"]
    return {
        "events": len(rows),
        "positive": counts["POSITIVE_8_BAR"],
        "negative": counts["NEGATIVE_8_BAR"],
        "flat": counts["FLAT_8_BAR"],
        "insufficient_forward_data": counts["INSUFFICIENT_FORWARD_DATA"],
        "decisive": decisive,
        "positive_decisive_rate": counts["POSITIVE_8_BAR"] / decisive if decisive else 0.0,
    }


def main() -> None:
    all_rows: list[dict] = []
    failures: list[dict] = []
    by_symbol: dict[str, list[dict]] = {symbol: [] for symbol in SYMBOLS}

    for symbol in SYMBOLS:
        try:
            rows = collect_symbol(symbol)
            all_rows.extend(rows)
            by_symbol[symbol].extend(rows)
        except Exception as exc:
            failures.append({"symbol": symbol, "error": repr(exc)})

    print("DEMAND COMING IN SEMANTIC AUDIT SUMMARY")
    print(
        {
            "symbols_requested": len(SYMBOLS),
            "symbols_with_candidates": len({row["symbol"] for row in all_rows}),
            "candidate_events": len(all_rows),
            "positive": summarize(all_rows)["positive"],
            "negative": summarize(all_rows)["negative"],
            "flat": summarize(all_rows)["flat"],
            "insufficient_forward_data": summarize(all_rows)["insufficient_forward_data"],
            "decisive": summarize(all_rows)["decisive"],
            "positive_decisive_rate": summarize(all_rows)["positive_decisive_rate"],
            "very_high_volume": sum(row["very_high_volume"] for row in all_rows),
            "wide_spread": sum(row["wide_spread"] for row in all_rows),
            "volume_increasing": sum(row["volume_increasing"] for row in all_rows),
            "higher_low": sum(row["higher_low"] for row in all_rows),
            "failures": failures,
        }
    )

    print("DEMAND COMING IN SEMANTIC AUDIT BY_SYMBOL")
    for symbol in SYMBOLS:
        print(symbol, summarize(by_symbol[symbol]))

    print("DEMAND COMING IN SEMANTIC AUDIT EVENTS")
    for row in all_rows:
        print(row)


if __name__ == "__main__":
    main()
