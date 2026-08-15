from __future__ import annotations

import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from engine.columns import COL_CLOSE, COL_DIRECTION, COL_SPREAD_CLASS, COL_VOLUME_CLASS, COL_WEEK
from evidence.demand import _collect_test
from evidence.engine import EvidenceEngine
from metrics_engine import MetricsEngine
from models import Direction, SpreadClass, VolumeClass
from trend import TrendAnalyzer

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


def forward_outcome(weekly, index: int) -> str:
    future_index = index + 8
    if future_index >= len(weekly):
        return "INSUFFICIENT_FORWARD_DATA"
    current = float(weekly.iloc[index][COL_CLOSE])
    future = float(weekly.iloc[future_index][COL_CLOSE])
    forward_return = (future - current) / current
    if forward_return > 0.02:
        return "POSITIVE_8_BAR"
    if forward_return < -0.02:
        return "NEGATIVE_8_BAR"
    return "FLAT_8_BAR"


def candidate_indices(metrics) -> list[int]:
    indices: list[int] = []
    for index in range(MIN_REPLAY_BARS, len(metrics)):
        row = metrics.iloc[index]
        direction = Direction(int(row[COL_DIRECTION]))
        volume = VolumeClass(int(row[COL_VOLUME_CLASS]))
        spread = SpreadClass(int(row[COL_SPREAD_CLASS]))
        if (
            direction == Direction.DOWN
            and volume <= VolumeClass.LOW
            and spread <= SpreadClass.NARROW
        ):
            indices.append(index)
    return indices


def inspect_symbol(symbol: str) -> list[dict]:
    daily = download_data(symbol)
    weekly = daily_to_weekly(daily)
    metrics = MetricsEngine().calculate(weekly)
    rows: list[dict] = []

    for index in candidate_indices(metrics):
        replay = metrics.iloc[: index + 1].copy()
        trend = TrendAnalyzer().analyze(replay)
        structural_swings = tuple(trend.structure.structural_swings)

        engine = EvidenceEngine()
        engine.collect(
            metrics=replay,
            trend=trend,
            structural_swings=structural_swings,
        )

        ctx = engine._ctx
        if ctx is None:
            continue

        events = tuple(event for event in _collect_test(ctx) if event.bar_index == index)
        if not events:
            continue

        rows.append(
            {
                "symbol": symbol,
                "bar_index": index,
                "week": str(metrics.iloc[index][COL_WEEK]),
                "outcome": forward_outcome(weekly, index),
            }
        )

    return rows


def stats(events: list[dict]) -> dict:
    counts = Counter(row["outcome"] for row in events)
    decisive = counts["POSITIVE_8_BAR"] + counts["NEGATIVE_8_BAR"]
    return {
        "events": len(events),
        "positive": counts["POSITIVE_8_BAR"],
        "negative": counts["NEGATIVE_8_BAR"],
        "flat": counts["FLAT_8_BAR"],
        "insufficient_forward_data": counts["INSUFFICIENT_FORWARD_DATA"],
        "decisive": decisive,
        "positive_decisive_rate": (
            counts["POSITIVE_8_BAR"] / decisive if decisive else 0.0
        ),
    }


def main() -> None:
    symbols = tuple(sys.argv[1:]) or DEFAULT_SYMBOLS
    all_events: list[dict] = []
    failures: list[dict] = []

    with ThreadPoolExecutor(max_workers=min(4, len(symbols))) as executor:
        futures = {executor.submit(inspect_symbol, symbol): symbol for symbol in symbols}
        for future, symbol in futures.items():
            try:
                symbol_events = future.result()
                all_events.extend(symbol_events)
                print({"symbol": symbol, "events": len(symbol_events)})
            except Exception as exc:
                failures.append({"symbol": symbol, "error": repr(exc)})

    print("TEST ROBUSTNESS SUMMARY")
    print(
        {
            "symbols_requested": len(symbols),
            "symbols_with_events": len({row["symbol"] for row in all_events}),
            **stats(all_events),
            "failures": failures,
        }
    )

    print("TEST ROBUSTNESS BY_SYMBOL")
    for symbol in symbols:
        symbol_events = [row for row in all_events if row["symbol"] == symbol]
        print({"symbol": symbol, **stats(symbol_events)})

    print("TEST ROBUSTNESS LEAVE_ONE_OUT")
    for excluded in symbols:
        remaining = [row for row in all_events if row["symbol"] != excluded]
        print({"excluded_symbol": excluded, **stats(remaining)})


if __name__ == "__main__":
    main()
