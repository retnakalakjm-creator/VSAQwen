"""Point-in-time replay of the original Stopping Volume audit semantics.

Reconstructs the original audit-only requirements while removing its historical
look-ahead by truncating validation metrics at the target bar.

Original required semantics:
- selling campaign
- bearish bar
- high volume
- above-average spread
- close off the low

Confirmations are reported but are not required.
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
FORWARD_HORIZON = 8
OUTCOME_THRESHOLD = 0.02


def qualify(ctx) -> dict:
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


def outcome(forward_return: float | None) -> str:
    if forward_return is None:
        return "INSUFFICIENT_FORWARD_DATA"
    if forward_return > OUTCOME_THRESHOLD:
        return "POSITIVE_8_BAR"
    if forward_return < -OUTCOME_THRESHOLD:
        return "NEGATIVE_8_BAR"
    return "FLAT_8_BAR"


def inspect_symbol(symbol: str) -> list[dict]:
    daily = download_data(symbol)
    metrics = MetricsEngine().calculate(daily_to_weekly(daily))
    events: list[dict] = []

    for index in range(MIN_REPLAY_BARS, len(metrics)):
        row = metrics.iloc[index]
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

        if engine._ctx is None:
            continue
        result = qualify(engine._ctx)
        if not result["required"]:
            continue

        current = float(row[COL_CLOSE])
        future_index = index + FORWARD_HORIZON
        future = (
            None if future_index >= len(metrics)
            else float(metrics.iloc[future_index][COL_CLOSE])
        )
        forward_return = None if future is None else (future - current) / current

        events.append({
            "symbol": symbol,
            "bar_index": index,
            "week": str(row[COL_WEEK]),
            "requirements": result["requirements"],
            "confirmations": result["confirmations"],
            "forward_return": forward_return,
            "outcome": outcome(forward_return),
        })

    return events


def summarize(events: list[dict]) -> dict:
    positive = sum(e["outcome"] == "POSITIVE_8_BAR" for e in events)
    negative = sum(e["outcome"] == "NEGATIVE_8_BAR" for e in events)
    flat = sum(e["outcome"] == "FLAT_8_BAR" for e in events)
    insufficient = sum(e["outcome"] == "INSUFFICIENT_FORWARD_DATA" for e in events)
    decisive = positive + negative
    return {
        "events": len(events),
        "positive": positive,
        "negative": negative,
        "flat": flat,
        "insufficient_forward_data": insufficient,
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
                print({"symbol": symbol, "events": len(events)})
            except Exception as exc:
                failures.append({"symbol": symbol, "error": repr(exc)})

    print("STOPPING VOLUME ORIGINAL SEMANTICS P.I.T. SUMMARY")
    print({
        "symbols_requested": len(symbols),
        "symbols_with_events": len({e["symbol"] for e in all_events}),
        "summary": summarize(all_events),
        "failures": failures,
    })

    print("STOPPING VOLUME ORIGINAL SEMANTICS P.I.T. CONFIRMATIONS")
    for key in ("very_high_volume", "wide_spread", "volume_increasing", "higher_low"):
        print({"confirmation": key, "true": sum(e["confirmations"][key] for e in all_events)})


if __name__ == "__main__":
    main()
