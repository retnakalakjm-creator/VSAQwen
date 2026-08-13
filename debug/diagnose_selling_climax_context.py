from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from engine.columns import COL_CLOSE, COL_WEEK
from evidence.campaign import has_recent_weakness, has_selling_campaign
from evidence.engine import EvidenceEngine
from evidence.rules import (
    is_bearish_bar,
    is_strong_close,
    is_very_high_volume,
    is_above_average_spread,
    has_strong_spread,
    volume_increasing,
)
from evidence.demand import _collect_selling_climax
from metrics_engine import MetricsEngine
from trend import TrendAnalyzer

DEFAULT_SYMBOLS = (
    "BHARTIARTL.NS", "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "INFY.NS", "TCS.NS", "SBIN.NS", "LT.NS",
)


def classify(value: float) -> str:
    if value >= 0.05:
        return "POSITIVE_8_BAR"
    if value <= -0.05:
        return "NEGATIVE_8_BAR"
    return "FLAT_8_BAR"


def inspect(symbol: str) -> list[dict]:
    metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
    events: list[dict] = []

    for index in range(20, len(metrics) - 8):
        replay = metrics.iloc[: index + 1].copy()
        trend = TrendAnalyzer().analyze(replay)
        engine = EvidenceEngine()
        result = engine.collect(
            metrics=replay,
            trend=trend,
            structural_swings=tuple(trend.structure.structural_swings),
        )
        ctx = engine._ctx
        if ctx is None:
            continue

        items = _collect_selling_climax(ctx)
        if not items:
            continue

        bar = ctx.current
        previous = ctx.previous
        confirmations = {
            "wide_spread": has_strong_spread(bar),
            "strong_close": is_strong_close(bar),
            "volume_increasing": volume_increasing(bar, previous),
        }

        current = float(metrics.iloc[index][COL_CLOSE])
        forward = {
            h: float(metrics.iloc[index + h][COL_CLOSE]) / current - 1.0
            for h in (1, 2, 4, 8)
            if current != 0.0
        }

        exact = [str(item.code) for item in result.evidence if str(item.code).lower() != "selling_climax"]
        events.append({
            "symbol": symbol,
            "bar_index": index,
            "week": str(metrics.iloc[index][COL_WEEK]),
            "confirmations": confirmations,
            "cooccurring_evidence": sorted(set(exact)),
            "forward_returns": forward,
            "8_bar_class": classify(forward[8]),
        })

    return events


def main() -> None:
    symbols = tuple(sys.argv[1:]) or DEFAULT_SYMBOLS
    all_events: list[dict] = []
    for symbol in symbols:
        events = inspect(symbol)
        all_events.extend(events)
        print({"symbol": symbol, "events": len(events)})

    groups: dict[tuple, dict[str, int | list[int]]] = defaultdict(lambda: {"events": 0, "positive": 0, "negative": 0, "flat": 0, "bars": []})
    for item in all_events:
        key = tuple(sorted(name for name, passed in item["confirmations"].items() if passed))
        g = groups[key]
        g["events"] += 1
        g["bars"].append(item["bar_index"])
        g[{"POSITIVE_8_BAR": "positive", "NEGATIVE_8_BAR": "negative", "FLAT_8_BAR": "flat"}[item["8_bar_class"]]] += 1

    print("SELLING CLIMAX CONFIRMATION GROUP SUMMARY")
    for key, value in sorted(groups.items(), key=lambda x: (-int(x[1]["events"]), x[0])):
        print({"confirmations": key, **value})

    context: dict[tuple, dict[str, int | list[int]]] = defaultdict(lambda: {"events": 0, "positive": 0, "negative": 0, "flat": 0, "bars": []})
    for item in all_events:
        key = tuple(item["cooccurring_evidence"])
        g = context[key]
        g["events"] += 1
        g["bars"].append(item["bar_index"])
        g[{"POSITIVE_8_BAR": "positive", "NEGATIVE_8_BAR": "negative", "FLAT_8_BAR": "flat"}[item["8_bar_class"]]] += 1

    print("SELLING CLIMAX CONTEXT GROUP SUMMARY")
    for key, value in sorted(context.items(), key=lambda x: (-int(x[1]["events"]), x[0])):
        print({"cooccurring_evidence": key, **value})


if __name__ == "__main__":
    main()
