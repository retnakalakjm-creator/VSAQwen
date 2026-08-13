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
from evidence.rules import (
    has_strong_spread,
    is_above_average_spread,
    is_bullish_bar,
    is_high_volume,
    is_very_high_volume,
    is_strong_close,
    volume_increasing,
)
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
FORWARD_HORIZON = 8


def inspect_symbol(symbol: str) -> list[dict]:
    daily = download_data(symbol)
    metrics = MetricsEngine().calculate(daily_to_weekly(daily))
    events: list[dict] = []

    for index in range(MIN_REPLAY_BARS, len(metrics) - FORWARD_HORIZON):
        row = metrics.iloc[index]
        if not (
            Direction(row[COL_DIRECTION]) == Direction.UP
            and VolumeClass(row[COL_VOLUME_CLASS]) >= VolumeClass.HIGH
            and SpreadClass(row[COL_SPREAD_CLASS]) >= SpreadClass.ABOVE_AVERAGE
        ):
            continue

        replay = metrics.iloc[: index + 1]
        trend = TrendAnalyzer().analyze(replay)
        engine = EvidenceEngine()
        engine.collect(
            metrics=replay,
            trend=trend,
            structural_swings=tuple(trend.structure.structural_swings),
            validation_metrics=metrics,
        )
        assert engine._ctx is not None
        bar = engine._ctx.current
        previous = engine._ctx.previous

        # Candidate INCREASING_DEMAND definition:
        # bullish bar + high volume + above-average spread + increasing volume.
        requirements = (
            is_bullish_bar(bar),
            is_high_volume(bar),
            is_above_average_spread(bar),
            volume_increasing(bar, previous),
        )
        if previous is None or not all(requirements):
            continue

        confirmations = {
            "very_high_volume": is_very_high_volume(bar),
            "wide_spread": has_strong_spread(bar),
            "strong_close": is_strong_close(bar),
        }

        current = float(metrics.iloc[index][COL_CLOSE])
        future = float(metrics.iloc[index + FORWARD_HORIZON][COL_CLOSE])
        ret8 = (future - current) / current
        if ret8 > 0.02:
            outcome = "POSITIVE_8_BAR"
        elif ret8 < -0.02:
            outcome = "NEGATIVE_8_BAR"
        else:
            outcome = "FLAT_8_BAR"

        events.append({
            "symbol": symbol,
            "bar_index": index,
            "week": str(metrics.iloc[index][COL_WEEK]),
            "outcome": outcome,
            "confirmations": confirmations,
            "forward_return_8": ret8,
        })

    return events


def main() -> None:
    symbols = tuple(sys.argv[1:]) or DEFAULT_SYMBOLS
    all_events: list[dict] = []
    failures: list[dict] = []

    with ThreadPoolExecutor(max_workers=min(4, len(symbols))) as executor:
        futures = {executor.submit(inspect_symbol, symbol): symbol for symbol in symbols}
        for future, symbol in futures.items():
            try:
                all_events.extend(future.result())
                print({"symbol": symbol, "events": len(all_events)})
            except Exception as exc:
                failures.append({"symbol": symbol, "error": repr(exc)})

    print("INCREASING DEMAND SUMMARY")
    print({
        "symbols_requested": len(symbols),
        "symbols_with_events": len({x["symbol"] for x in all_events}),
        "events": len(all_events),
        "outcome_classes": {
            "POSITIVE_8_BAR": sum(x["outcome"] == "POSITIVE_8_BAR" for x in all_events),
            "NEGATIVE_8_BAR": sum(x["outcome"] == "NEGATIVE_8_BAR" for x in all_events),
            "FLAT_8_BAR": sum(x["outcome"] == "FLAT_8_BAR" for x in all_events),
            "INSUFFICIENT_FORWARD_DATA": 0,
        },
        "failures": failures,
        "confirmation_true_counts": {
            key: sum(item["confirmations"][key] for item in all_events)
            for key in ("very_high_volume", "wide_spread", "strong_close")
        },
    })


if __name__ == "__main__":
    main()
