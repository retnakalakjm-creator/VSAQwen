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
    COL_CLOSE_POSITION,
    COL_DIRECTION,
    COL_SPREAD_CLASS,
    COL_VOLUME_CLASS,
    COL_WEEK,
)
from evidence.campaign import has_selling_campaign
from evidence.engine import EvidenceEngine
from evidence.rules import (
    is_above_average_spread,
    is_high_volume,
    is_weak_close,
)
from metrics_engine import MetricsEngine
from models import ClosePosition, Direction, SpreadClass, VolumeClass
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


def _candidate_count(symbol: str) -> list[dict]:
    daily = download_data(symbol)
    metrics = MetricsEngine().calculate(daily_to_weekly(daily))
    events: list[dict] = []

    for index in range(MIN_REPLAY_BARS, len(metrics)):
        row = metrics.iloc[index]

        # Atomic, point-in-time-safe pre-filter.
        if not (
            Direction(row[COL_DIRECTION]) == Direction.DOWN
            and VolumeClass(row[COL_VOLUME_CLASS]) >= VolumeClass.HIGH
            and SpreadClass(row[COL_SPREAD_CLASS]) >= SpreadClass.ABOVE_AVERAGE
            and ClosePosition(row[COL_CLOSE_POSITION]) >= ClosePosition.MIDDLE
        ):
            continue

        replay = metrics.iloc[: index + 1].copy()
        trend = TrendAnalyzer().analyze(replay)
        structural_swings = tuple(trend.structure.structural_swings)

        engine = EvidenceEngine()
        engine.collect(
            metrics=replay,
            trend=trend,
            structural_swings=structural_swings,
            validation_metrics=replay,
        )

        assert engine._ctx is not None
        ctx = engine._ctx
        bar = ctx.current

        required = {
            "selling_campaign": has_selling_campaign(ctx),
            "bearish_bar": Direction(row[COL_DIRECTION]) == Direction.DOWN,
            "high_volume": is_high_volume(bar),
            "above_average_spread": is_above_average_spread(bar),
            "close_off_low": not is_weak_close(bar),
        }

        if not all(required.values()):
            continue

        current = float(metrics.iloc[index][COL_CLOSE])
        future_index = index + 8
        if future_index >= len(metrics):
            continue
        future = float(metrics.iloc[future_index][COL_CLOSE])
        forward_return = (future / current) - 1.0

        if forward_return > 0.02:
            outcome = "POSITIVE_8_BAR"
        elif forward_return < -0.02:
            outcome = "NEGATIVE_8_BAR"
        else:
            outcome = "FLAT_8_BAR"

        events.append(
            {
                "symbol": symbol,
                "bar_index": index,
                "week": str(metrics.iloc[index][COL_WEEK]),
                "outcome": outcome,
            }
        )

    return events


def summarize(events: list[dict]) -> dict:
    positive = sum(item["outcome"] == "POSITIVE_8_BAR" for item in events)
    negative = sum(item["outcome"] == "NEGATIVE_8_BAR" for item in events)
    flat = sum(item["outcome"] == "FLAT_8_BAR" for item in events)
    decisive = positive + negative
    return {
        "events": len(events),
        "positive": positive,
        "negative": negative,
        "flat": flat,
        "decisive": decisive,
        "positive_decisive_rate": positive / decisive if decisive else 0.0,
    }


def main() -> None:
    symbols = tuple(sys.argv[1:]) or DEFAULT_SYMBOLS
    all_events: list[dict] = []
    failures: list[dict] = []

    with ThreadPoolExecutor(max_workers=min(4, len(symbols))) as executor:
        futures = {executor.submit(_candidate_count, symbol): symbol for symbol in symbols}
        for future, symbol in futures.items():
            try:
                events = future.result()
                all_events.extend(events)
            except Exception as exc:
                failures.append({"symbol": symbol, "error": repr(exc)})

    print("=" * 78)
    print("STOPPING VOLUME ORIGINAL SEMANTICS ROBUSTNESS")
    print("=" * 78)
    print("\nSUMMARY")
    print({
        "symbols_requested": len(symbols),
        "symbols_with_events": len({x["symbol"] for x in all_events}),
        **summarize(all_events),
        "failures": failures,
    })

    print("\nBY_SYMBOL")
    for symbol in symbols:
        subset = [x for x in all_events if x["symbol"] == symbol]
        print({"symbol": symbol, **summarize(subset)})

    print("\nLEAVE_ONE_OUT")
    for excluded in symbols:
        subset = [x for x in all_events if x["symbol"] != excluded]
        print({"excluded_symbol": excluded, **summarize(subset)})


if __name__ == "__main__":
    main()
