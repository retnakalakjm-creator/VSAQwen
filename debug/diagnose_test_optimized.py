from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data import daily_to_weekly, download_data
from engine.columns import COL_DIRECTION, COL_SPREAD_CLASS, COL_VOLUME_CLASS, COL_WEEK
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


def candidate_indices(metrics) -> list[int]:
    """Superset prefilter for TEST using only current-bar data."""
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
    candidates = candidate_indices(metrics)

    for index in candidates:
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

        for event in _collect_test(ctx):
            if event.bar_index != index:
                continue
            rows.append(
                {
                    "symbol": symbol,
                    "bar_index": index,
                    "week": str(metrics.iloc[index][COL_WEEK]),
                    "test_events": 1,
                    "strength": float(event.strength),
                    "weight": float(event.weight),
                }
            )

    return rows


def main() -> None:
    symbols = tuple(sys.argv[1:]) or DEFAULT_SYMBOLS
    events: list[dict] = []
    failures: list[dict] = []

    with ThreadPoolExecutor(max_workers=min(4, len(symbols))) as executor:
        futures = {executor.submit(inspect_symbol, symbol): symbol for symbol in symbols}
        for future, symbol in futures.items():
            try:
                symbol_events = future.result()
                events.extend(symbol_events)
                print({"symbol": symbol, "events": len(symbol_events)})
            except Exception as exc:
                failures.append({"symbol": symbol, "error": repr(exc)})

    print("TEST OPTIMIZED AUDIT SUMMARY")
    print(
        {
            "symbols_requested": len(symbols),
            "symbols_with_events": len({row["symbol"] for row in events}),
            "test_events": len(events),
            "failures": failures,
        }
    )

    print("TEST OPTIMIZED AUDIT EVENTS")
    for row in events:
        print(row)


if __name__ == "__main__":
    main()
