from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path
from pprint import pprint

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data import daily_to_weekly, download_data
from engine.columns import COL_CLOSE
from evidence.demand import _collect_no_supply
from evidence.engine import EvidenceEngine
from evidence.rules import (
    has_weak_spread,
    is_low_volume,
    is_narrow_spread,
    is_weak_close,
    volume_decreasing,
)
from metrics_engine import MetricsEngine
from trend import TrendAnalyzer
from models import TrendDirection, TrendState

SYMBOLS = (
    "BHARTIARTL.NS", "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "INFY.NS", "TCS.NS", "SBIN.NS", "LT.NS",
)
MIN_REPLAY_BARS = 20
FORWARD_HORIZON = 8


def build_contexts(metrics):
    contexts = {}
    for index in range(MIN_REPLAY_BARS, len(metrics)):
        replay = metrics.iloc[: index + 1]
        trend = TrendAnalyzer().analyze(replay)
        engine = EvidenceEngine()
        engine._reset(
            metrics=replay,
            trend=trend,
            structural_swings=tuple(trend.structure.structural_swings),
            validation_metrics=replay,
        )
        assert engine._ctx is not None
        contexts[index] = engine._ctx
    return contexts


def outcome(metrics, bar_index: int) -> str:
    future = bar_index + FORWARD_HORIZON
    if future >= len(metrics):
        return "INSUFFICIENT_FORWARD_DATA"
    c0 = float(metrics.iloc[bar_index][COL_CLOSE])
    c1 = float(metrics.iloc[future][COL_CLOSE])
    if c1 > c0:
        return "POSITIVE_8_BAR"
    if c1 < c0:
        return "NEGATIVE_8_BAR"
    return "FLAT_8_BAR"


def collect_events(symbol: str):
    daily = download_data(symbol)
    weekly = daily_to_weekly(daily)
    metrics = MetricsEngine().calculate(weekly)
    contexts = build_contexts(metrics)

    events = []
    for bar_index, ctx in contexts.items():
        emitted = tuple(
            e for e in _collect_no_supply(ctx)
            if e.code.value == "no_supply" and e.bar_index == bar_index
        )
        if not emitted:
            continue
        bar = ctx.current
        previous = ctx.previous
        events.append({
            "symbol": symbol,
            "bar_index": bar_index,
            "direction": ctx.trend.direction,
            "state": ctx.trend.state,
            "outcome": outcome(metrics, bar_index),
            "higher_low": previous is not None and bar.low > previous.low,
            "volume_decreasing": previous is not None and volume_decreasing(bar, previous),
            "weak_close": is_weak_close(bar),
            "low_volume": is_low_volume(bar),
            "narrow_spread": is_narrow_spread(bar),
            "weak_spread": has_weak_spread(bar),
        })
    return events


def summarize(events, label):
    counts = Counter(e["outcome"] for e in events)
    decisive = counts["POSITIVE_8_BAR"] + counts["NEGATIVE_8_BAR"]
    return {
        "filter": label,
        "events": len(events),
        "positive": counts["POSITIVE_8_BAR"],
        "negative": counts["NEGATIVE_8_BAR"],
        "flat": counts["FLAT_8_BAR"],
        "insufficient_forward_data": counts["INSUFFICIENT_FORWARD_DATA"],
        "decisive": decisive,
        "positive_decisive_rate": counts["POSITIVE_8_BAR"] / decisive if decisive else 0.0,
        "symbols_with_events": len({e["symbol"] for e in events}),
    }


def main() -> None:
    all_events = []
    failures = []
    for symbol in SYMBOLS:
        try:
            all_events.extend(collect_events(symbol))
        except Exception as exc:
            failures.append({"symbol": symbol, "error": repr(exc)})

    filters = {
        "baseline": lambda e: True,
        "exclude_healthy_downtrend": lambda e: not (
            e["direction"] == TrendDirection.DOWN and e["state"] == TrendState.HEALTHY
        ),
        "exclude_confirmed_downtrend": lambda e: not (
            e["direction"] == TrendDirection.DOWN
            and e["state"] in {TrendState.DEVELOPING, TrendState.HEALTHY, TrendState.EXHAUSTED}
        ),
        "require_higher_low": lambda e: e["higher_low"],
        "require_volume_decreasing": lambda e: e["volume_decreasing"],
        "require_weak_close": lambda e: e["weak_close"],
        "higher_low_or_volume_decreasing": lambda e: e["higher_low"] or e["volume_decreasing"],
        "higher_low_or_weak_close": lambda e: e["higher_low"] or e["weak_close"],
        "all_three_supports": lambda e: e["higher_low"] and e["volume_decreasing"] and e["weak_close"],
    }

    print("NO SUPPLY CONTEXT REFINEMENT AUDIT SUMMARY")
    print({"events": len(all_events), "failures": failures})

    print("NO SUPPLY CONTEXT REFINEMENT COMPARISON")
    for label, predicate in filters.items():
        selected = [e for e in all_events if predicate(e)]
        pprint(summarize(selected, label))

    print("NO SUPPLY CONTEXT REFINEMENT BY_SYMBOL")
    for label, predicate in filters.items():
        selected = [e for e in all_events if predicate(e)]
        print(label)
        for symbol in SYMBOLS:
            rows = [e for e in selected if e["symbol"] == symbol]
            pprint({"symbol": symbol, **summarize(rows, label)})

    print("NO SUPPLY CONTEXT REFINEMENT EVENTS")
    for event in all_events:
        pprint(event)


if __name__ == "__main__":
    main()
