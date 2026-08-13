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
    has_strong_spread,
    is_above_average_spread,
    is_bearish_bar,
    is_high_volume,
    is_very_high_volume,
    is_weak_close,
    makes_higher_low,
    volume_increasing,
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


def _qualifies(ctx) -> dict:
    bar = ctx.current
    previous = ctx.previous

    requirements = {
        "selling_campaign": has_selling_campaign(ctx),
        "bearish_bar": bar.direction == Direction.DOWN,
        "high_volume": is_high_volume(bar),
        "above_average_spread": is_above_average_spread(bar),
        "close_off_low": not is_weak_close(bar),
    }

    confirmations = {
        "very_high_volume": is_very_high_volume(bar),
        "wide_spread": has_strong_spread(bar),
        "volume_increasing": volume_increasing(bar, previous),
        "higher_low": makes_higher_low(bar, previous),
    }

    return {
        "requirements": requirements,
        "confirmations": confirmations,
        "required": all(requirements.values()),
    }


def inspect_symbol(symbol: str) -> list[dict]:
    daily = download_data(symbol)
    metrics = MetricsEngine().calculate(daily_to_weekly(daily))
    events: list[dict] = []

    for index in range(MIN_REPLAY_BARS, len(metrics)):
        row = metrics.iloc[index]

        # Safe semantic pre-filter matching only atomic candidate conditions.
        if not (
            Direction(row[COL_DIRECTION]) == Direction.DOWN
            and VolumeClass(row[COL_VOLUME_CLASS]) >= VolumeClass.HIGH
            and SpreadClass(row[COL_SPREAD_CLASS]) >= SpreadClass.ABOVE_AVERAGE
            and ClosePosition(row[COL_CLOSE_POSITION]) >= ClosePosition.MIDDLE
        ):
            continue

        replay = metrics.iloc[: index + 1]
        trend = TrendAnalyzer().analyze(replay)
        structural_swings = tuple(trend.structure.structural_swings)

        engine = EvidenceEngine()
        engine.collect(
            metrics=replay,
            trend=trend,
            structural_swings=structural_swings,
            validation_metrics=metrics,
        )

        assert engine._ctx is not None
        result = _qualifies(engine._ctx)
        if not result["required"]:
            continue

        current = float(metrics.iloc[index][COL_CLOSE])
        forward_returns: dict[int, float | None] = {}
        for horizon in (1, 2, 4, 8):
            future_index = index + horizon
            if future_index >= len(metrics):
                forward_returns[horizon] = None
                continue
            future = float(metrics.iloc[future_index][COL_CLOSE])
            forward_returns[horizon] = (future - current) / current

        if forward_returns[8] is None:
            outcome = "INSUFFICIENT_FORWARD_DATA"
        elif forward_returns[8] > 0.02:
            outcome = "POSITIVE_8_BAR"
        elif forward_returns[8] < -0.02:
            outcome = "NEGATIVE_8_BAR"
        else:
            outcome = "FLAT_8_BAR"

        events.append(
            {
                "symbol": symbol,
                "bar_index": index,
                "week": str(metrics.iloc[index][COL_WEEK]),
                "requirements": result["requirements"],
                "confirmations": result["confirmations"],
                "forward_returns": forward_returns,
                "8_bar_class": outcome,
            }
        )

    return events


def main() -> None:
    symbols = tuple(sys.argv[1:]) or DEFAULT_SYMBOLS
    all_events: list[dict] = []
    failures: list[dict] = []

    print("=" * 72)
    print("STOPPING VOLUME HISTORICAL AUDIT (AUDIT ONLY)")
    print("=" * 72)
    print({"symbols": symbols})

    with ThreadPoolExecutor(max_workers=min(4, len(symbols))) as executor:
        futures = {
            executor.submit(inspect_symbol, symbol): symbol
            for symbol in symbols
        }
        for future, symbol in futures.items():
            try:
                events = future.result()
                all_events.extend(events)
                print({"symbol": symbol, "events": len(events)})
            except Exception as exc:
                failures.append({"symbol": symbol, "error": repr(exc)})
                print({"symbol": symbol, "error": repr(exc)})

    counts = {
        "POSITIVE_8_BAR": sum(x["8_bar_class"] == "POSITIVE_8_BAR" for x in all_events),
        "NEGATIVE_8_BAR": sum(x["8_bar_class"] == "NEGATIVE_8_BAR" for x in all_events),
        "FLAT_8_BAR": sum(x["8_bar_class"] == "FLAT_8_BAR" for x in all_events),
        "INSUFFICIENT_FORWARD_DATA": sum(x["8_bar_class"] == "INSUFFICIENT_FORWARD_DATA" for x in all_events),
    }

    print("\nSTOPPING VOLUME SUMMARY")
    print({
        "symbols_requested": len(symbols),
        "symbols_with_events": len({x["symbol"] for x in all_events}),
        "events": len(all_events),
        "outcome_classes": counts,
        "failures": failures,
        "confirmation_true_counts": {
            key: sum(item["confirmations"][key] for item in all_events)
            for key in ("very_high_volume", "wide_spread", "volume_increasing", "higher_low")
        },
    })

    print("\nSTOPPING VOLUME EVENTS")
    for item in all_events:
        print(item)


if __name__ == "__main__":
    main()
