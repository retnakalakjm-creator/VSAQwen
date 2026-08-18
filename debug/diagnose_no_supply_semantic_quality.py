from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data import daily_to_weekly, download_data
from engine.columns import COL_AVG_SPREAD, COL_CLOSE, COL_LOW, COL_WEEK
from evidence.demand import _collect_no_supply
from evidence.engine import EvidenceEngine
from evidence.rules import (
    has_weak_spread,
    is_bearish_bar,
    is_low_volume,
    is_narrow_spread,
    is_weak_close,
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
        replay = metrics.iloc[: index + 1]
        trend = TrendAnalyzer().analyze(replay)
        swings = tuple(trend.structure.structural_swings)
        engine = EvidenceEngine()
        engine._reset(
            metrics=replay,
            trend=trend,
            structural_swings=swings,
            validation_metrics=replay,
        )
        assert engine._ctx is not None
        contexts[index] = engine._ctx
    return contexts


def diagnostics(ctx, metrics, bar_index: int):
    bar = ctx.current
    previous = ctx.previous
    requirements = {
        "bearish_environment": ctx.is_bearish_environment(),
        "bearish_bar": is_bearish_bar(bar),
        "low_volume": is_low_volume(bar),
        "narrow_spread": is_narrow_spread(bar),
    }
    confirmations = {
        "weak_spread": has_weak_spread(bar),
        "volume_decreasing": (
            volume_decreasing(bar, previous)
            if previous is not None
            else False
        ),
        "weak_selling_result": is_weak_close(bar),
    }

    avg_spread = float(metrics.iloc[bar_index][COL_AVG_SPREAD])
    spread_ratio_to_average = (
        float(bar.spread_ratio) if avg_spread > 0 else None
    )

    return {
        **requirements,
        **confirmations,
        "higher_low": (
            bar.low > previous.low if previous is not None else False
        ),
        "lower_low": (
            bar.low < previous.low if previous is not None else False
        ),
        "close_position": bar.close_position.name,
        "spread_class": bar.spread.name,
        "volume_class": bar.volume.name,
        "spread_ratio": spread_ratio_to_average,
        "trend_direction": ctx.trend.direction.value,
        "trend_state": ctx.trend.state.value,
    }


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
    for bar_index, ctx in contexts.items():
        emitted = tuple(
            event
            for event in _collect_no_supply(ctx)
            if event.code.value == "no_supply" and event.bar_index == bar_index
        )
        if not emitted:
            continue
        events.append(
            {
                "symbol": symbol,
                "bar_index": bar_index,
                "week": str(metrics.iloc[bar_index][COL_WEEK]),
                "outcome": classify_outcome(metrics, bar_index),
                **diagnostics(ctx, metrics, bar_index),
            }
        )
    return events


def main() -> None:
    all_events = []
    failures = []
    for symbol in SYMBOLS:
        try:
            all_events.extend(audit_symbol(symbol))
        except Exception as exc:
            failures.append({"symbol": symbol, "error": repr(exc)})

    counts = Counter(event["outcome"] for event in all_events)
    decisive = counts["POSITIVE_8_BAR"] + counts["NEGATIVE_8_BAR"]
    semantic_like = sum(
        event["volume_decreasing"]
        or event["weak_selling_result"]
        or event["higher_low"]
        for event in all_events
    )
    contradictory_downtrend = sum(
        event["trend_direction"] == "down"
        and event["trend_state"] == "healthy"
        and not event["higher_low"]
        for event in all_events
    )

    print("NO SUPPLY SEMANTIC QUALITY AUDIT SUMMARY")
    print(
        {
            "symbols_requested": len(SYMBOLS),
            "symbols_with_events": len({e["symbol"] for e in all_events}),
            "events": len(all_events),
            "low_effort_probe": sum(
                e["low_volume"] and e["narrow_spread"] for e in all_events
            ),
            "meaningful_selling_context": sum(
                e["bearish_environment"] and e["bearish_bar"] for e in all_events
            ),
            "higher_low": sum(e["higher_low"] for e in all_events),
            "volume_decreasing": sum(e["volume_decreasing"] for e in all_events),
            "weak_selling_result": sum(e["weak_selling_result"] for e in all_events),
            "semantic_quality_like": semantic_like,
            "semantic_quality_like_rate": semantic_like / len(all_events) if all_events else 0.0,
            "contradictory_downtrend": contradictory_downtrend,
            "contradiction_rate": contradictory_downtrend / len(all_events) if all_events else 0.0,
            "failures": failures,
        }
    )

    print("NO SUPPLY SEMANTIC QUALITY AUDIT BY_SYMBOL")
    for symbol in SYMBOLS:
        rows = [e for e in all_events if e["symbol"] == symbol]
        print(
            {
                "symbol": symbol,
                "events": len(rows),
                "semantic_quality_like": sum(
                    e["volume_decreasing"]
                    or e["weak_selling_result"]
                    or e["higher_low"]
                    for e in rows
                ),
                "contradictions": sum(
                    e["trend_direction"] == "down"
                    and e["trend_state"] == "healthy"
                    and not e["higher_low"]
                    for e in rows
                ),
            }
        )

    print("NO SUPPLY SEMANTIC QUALITY AUDIT EVENTS")
    for event in all_events:
        print(event)


if __name__ == "__main__":
    main()
