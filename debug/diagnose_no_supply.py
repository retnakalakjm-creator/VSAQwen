from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from data import daily_to_weekly, download_data
from engine.columns import COL_CLOSE, COL_LOW, COL_WEEK
from evidence.campaign import has_selling_campaign
from evidence.engine import EvidenceEngine
from evidence.demand import _collect_no_supply
from evidence.rules import (
    has_weak_spread,
    is_bearish_bar,
    is_low_volume,
    is_weak_close,
    is_narrow_spread,
    volume_decreasing,
)
from metrics_engine import MetricsEngine
from trend import TrendAnalyzer


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


def build_point_in_time_contexts(metrics):
    contexts = {}
    for index in range(MIN_REPLAY_BARS, len(metrics)):
        replay = metrics.iloc[: index + 1].copy()
        trend = TrendAnalyzer().analyze(replay)
        swings = tuple(trend.structure.structural_swings)
        engine = EvidenceEngine()
        result = engine.collect(
            metrics=replay,
            trend=trend,
            structural_swings=swings,
        )
        assert engine._ctx is not None
        contexts[index] = (engine._ctx, result)
    return contexts


def exact_no_supply_events(result, bar_index: int):
    return tuple(
        item
        for item in result.evidence
        if item.code.value == "no_supply" and item.bar_index == bar_index
    )


def diagnostics(ctx):
    bar = ctx.current
    previous = ctx.previous

    confirmations = {
        "weak_spread": has_weak_spread(bar),
        "volume_decreasing": (
            volume_decreasing(bar, previous)
            if previous is not None
            else False
        ),
        "weak_selling_result": is_weak_close(bar),
    }

    requirements = {
        "bullish_environment": ctx.is_bearish_environment(),
        "bearish_bar": is_bearish_bar(bar),
        "low_volume": is_low_volume(bar),
        "narrow_spread": is_narrow_spread(bar),
    }

    return requirements, confirmations


def classify_outcome(metrics, bar_index: int):
    future_index = bar_index + FORWARD_HORIZON
    if future_index >= len(metrics):
        return "INSUFFICIENT_FORWARD_DATA"

    current_close = float(metrics.iloc[bar_index][COL_CLOSE])
    future_close = float(metrics.iloc[future_index][COL_CLOSE])

    if future_close > current_close:
        return "POSITIVE_8_BAR"
    if future_close < current_close:
        return "NEGATIVE_8_BAR"
    return "FLAT_8_BAR"


def audit_symbol(symbol: str):
    daily = download_data(symbol)
    weekly = daily_to_weekly(daily)
    metrics = MetricsEngine().calculate(weekly)
    contexts = build_point_in_time_contexts(metrics)

    events = []
    for bar_index, (ctx, result) in contexts.items():
        emitted = exact_no_supply_events(result, bar_index)
        if not emitted:
            continue

        requirements, confirmations = diagnostics(ctx)
        outcome = classify_outcome(metrics, bar_index)
        events.append(
            {
                "symbol": symbol,
                "bar_index": bar_index,
                "week": str(metrics.iloc[bar_index][COL_WEEK]),
                "outcome": outcome,
                **requirements,
                **confirmations,
            }
        )

    return events


def main() -> None:
    all_events = []
    failures = []

    for symbol in SYMBOLS:
        try:
            events = audit_symbol(symbol)
            all_events.extend(events)
        except Exception as exc:  # diagnostic boundary
            failures.append({"symbol": symbol, "error": repr(exc)})

    counts = Counter(event["outcome"] for event in all_events)
    decisive = counts["POSITIVE_8_BAR"] + counts["NEGATIVE_8_BAR"]
    positive_rate = (
        counts["POSITIVE_8_BAR"] / decisive
        if decisive
        else 0.0
    )

    print("NO SUPPLY SEMANTIC AUDIT SUMMARY")
    print(
        {
            "symbols_requested": len(SYMBOLS),
            "symbols_with_events": len({e["symbol"] for e in all_events}),
            "events": len(all_events),
            "positive": counts["POSITIVE_8_BAR"],
            "negative": counts["NEGATIVE_8_BAR"],
            "flat": counts["FLAT_8_BAR"],
            "insufficient_forward_data": counts["INSUFFICIENT_FORWARD_DATA"],
            "decisive": decisive,
            "positive_decisive_rate": positive_rate,
            "failures": failures,
        }
    )

    print("NO SUPPLY SEMANTIC AUDIT BY_SYMBOL")
    for symbol in SYMBOLS:
        rows = [e for e in all_events if e["symbol"] == symbol]
        decisive_symbol = sum(
            e["outcome"] in {"POSITIVE_8_BAR", "NEGATIVE_8_BAR"}
            for e in rows
        )
        positives = sum(e["outcome"] == "POSITIVE_8_BAR" for e in rows)
        negatives = sum(e["outcome"] == "NEGATIVE_8_BAR" for e in rows)
        flats = sum(e["outcome"] == "FLAT_8_BAR" for e in rows)
        rate = positives / decisive_symbol if decisive_symbol else 0.0
        print(
            {
                "symbol": symbol,
                "events": len(rows),
                "positive": positives,
                "negative": negatives,
                "flat": flats,
                "decisive": decisive_symbol,
                "positive_decisive_rate": rate,
            }
        )

    print("NO SUPPLY REQUIREMENT SUMMARY")
    if all_events:
        keys = (
            "bullish_environment",
            "bearish_bar",
            "low_volume",
            "narrow_spread",
            "weak_spread",
            "volume_decreasing",
            "weak_selling_result",
        )
        print(
            {
                key: sum(event[key] for event in all_events)
                for key in keys
            }
        )
    else:
        print({})

    print("NO SUPPLY EVENTS")
    for event in all_events:
        print(event)


if __name__ == "__main__":
    main()
