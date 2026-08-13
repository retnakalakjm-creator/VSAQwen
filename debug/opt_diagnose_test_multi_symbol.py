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
    COL_DIRECTION,
    COL_SPREAD_CLASS,
    COL_VOLUME_CLASS,
    COL_WEEK,
)
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

# Preserve the original full-history replay semantics.
MIN_REPLAY_BARS = 20


def classify_forward_return(value: float) -> str:
    if value >= 0.05:
        return "POSITIVE_8_BAR"
    if value <= -0.05:
        return "NEGATIVE_8_BAR"
    return "FLAT_8_BAR"


def inspect_symbol(symbol: str) -> list[dict]:
    daily = download_data(symbol)
    metrics = MetricsEngine().calculate(daily_to_weekly(daily))

    events: list[dict] = []

    for index in range(MIN_REPLAY_BARS, len(metrics)):
        row = metrics.iloc[index]

        # Safe pre-filter using semantic classification columns.
        # This only skips bars that cannot satisfy TEST's atomic
        # down-bar / low-volume / narrow-spread requirements.
        if not (
            Direction(row[COL_DIRECTION]) == Direction.DOWN
            and VolumeClass(row[COL_VOLUME_CLASS]) <= VolumeClass.LOW
            and SpreadClass(row[COL_SPREAD_CLASS]) <= SpreadClass.NARROW
        ):
            continue

        # Full point-in-time replay is retained so campaign and
        # structural context are identical to the validated audit.
        replay = metrics.iloc[: index + 1]

        trend = TrendAnalyzer().analyze(replay)
        evidence = EvidenceEngine().collect(
            metrics=replay,
            trend=trend,
            structural_swings=tuple(trend.structure.structural_swings),
            validation_metrics=metrics,
        )

        test_items = tuple(
            item
            for item in evidence.evidence
            if str(item.code).lower() == "test"
        )
        if not test_items:
            continue

        current = float(metrics.iloc[index][COL_CLOSE])
        returns: dict[int, float] = {}

        if current != 0.0:
            for horizon in (1, 2, 4, 8):
                future_index = index + horizon
                if future_index < len(metrics):
                    future_close = float(metrics.iloc[future_index][COL_CLOSE])
                    returns[horizon] = future_close / current - 1.0

        events.append(
            {
                "symbol": symbol,
                "bar_index": index,
                "week": str(metrics.iloc[index][COL_WEEK]),
                "test_count": len(test_items),
                "test_strength": [item.strength for item in test_items],
                "test_quality": [item.quality for item in test_items],
                "evidence": [str(item.code) for item in evidence.evidence],
                "forward_returns": returns,
                "8_bar_class": (
                    classify_forward_return(returns[8])
                    if 8 in returns
                    else "INSUFFICIENT_FORWARD_DATA"
                ),
            }
        )

    return events


def main() -> None:
    symbols = tuple(sys.argv[1:]) or DEFAULT_SYMBOLS
    all_events: list[dict] = []
    failures: list[dict] = []

    print("=" * 72)
    print("MULTI-SYMBOL TEST HISTORICAL VALIDATION AUDIT (OPTIMIZED)")
    print("=" * 72)
    print({"symbols": symbols})

    # Parallelize independent symbols. Each worker keeps its own
    # download, metrics, trend, and evidence state.
    with ThreadPoolExecutor(max_workers=min(4, len(symbols))) as executor:
        futures = {
            executor.submit(inspect_symbol, symbol): symbol
            for symbol in symbols
        }

        for future, symbol in futures.items():
            try:
                events = future.result()
                all_events.extend(events)
                print(
                    {
                        "symbol": symbol,
                        "test_events": len(events),
                        "bars": [item["bar_index"] for item in events],
                    }
                )
            except Exception as exc:
                failures.append({"symbol": symbol, "error": repr(exc)})
                print({"symbol": symbol, "error": repr(exc)})

    classes: dict[str, int] = {}
    for item in all_events:
        outcome = item["8_bar_class"]
        classes[outcome] = classes.get(outcome, 0) + 1

    print("\nTEST MULTI-SYMBOL SUMMARY")
    print(
        {
            "symbols_requested": len(symbols),
            "symbols_with_events": len({item["symbol"] for item in all_events}),
            "total_test_events": len(all_events),
            "outcome_classes": classes,
            "failed_symbols": failures,
        }
    )

    print("\nTEST MULTI-SYMBOL EVENTS")
    for item in all_events:
        print(item)


if __name__ == "__main__":
    main()
