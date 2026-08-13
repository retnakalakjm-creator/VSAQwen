from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from engine.columns import COL_CLOSE, COL_DIRECTION, COL_SPREAD_CLASS, COL_VOLUME_CLASS, COL_WEEK
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
    "BHARTIARTL.NS", "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "INFY.NS", "TCS.NS", "SBIN.NS", "LT.NS",
)
MIN_REPLAY_BARS = 20
HORIZON = 8


def inspect_symbol(symbol: str) -> list[dict]:
    daily = download_data(symbol)
    metrics = MetricsEngine().calculate(daily_to_weekly(daily))
    events: list[dict] = []

    for index in range(MIN_REPLAY_BARS, len(metrics) - HORIZON):
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
        ctx = engine._ctx
        bar = ctx.current
        previous = ctx.previous

        # Exact validated 902-event INCREASING_DEMAND definition.
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
        future = float(metrics.iloc[index + HORIZON][COL_CLOSE])
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
            "trend_direction": getattr(trend.structure.direction, "name", str(trend.structure.direction)),
            "trend_state": getattr(trend.structure.state, "name", str(trend.structure.state)),
        })

    return events


def main() -> None:
    symbols = tuple(sys.argv[1:]) or DEFAULT_SYMBOLS
    all_events: list[dict] = []
    failures: list[dict] = []

    with ThreadPoolExecutor(max_workers=min(4, len(symbols))) as executor:
        futures = {executor.submit(inspect_symbol, s): s for s in symbols}
        for future, symbol in futures.items():
            try:
                all_events.extend(future.result())
            except Exception as exc:
                failures.append({"symbol": symbol, "error": repr(exc)})

    def update(group: dict, outcome: str, bar_index: int) -> None:
        group["events"] += 1
        group[{"POSITIVE_8_BAR": "positive", "NEGATIVE_8_BAR": "negative", "FLAT_8_BAR": "flat"}[outcome]] += 1
        group["bars"].append(bar_index)

    confirmation_groups: dict[tuple[str, ...], dict[str, object]] = {}
    trend_groups: dict[tuple[str, ...], dict[str, object]] = {}
    for item in all_events:
        ckey = tuple(k for k, v in item["confirmations"].items() if v)
        cgroup = confirmation_groups.setdefault(ckey, {"events": 0, "positive": 0, "negative": 0, "flat": 0, "bars": []})
        update(cgroup, item["outcome"], item["bar_index"])

        tkey = (item["trend_direction"], item["trend_state"])
        tgroup = trend_groups.setdefault(tkey, {"events": 0, "positive": 0, "negative": 0, "flat": 0, "bars": []})
        update(tgroup, item["outcome"], item["bar_index"])

    print("INCREASING DEMAND CONFIRMATION GROUP SUMMARY")
    for key, value in sorted(confirmation_groups.items(), key=lambda x: (-x[1]["events"], x[0])):
        print({"confirmations": key, **value})

    print("INCREASING DEMAND CONTEXT GROUP SUMMARY")
    for key, value in sorted(trend_groups.items(), key=lambda x: (-x[1]["events"], x[0])):
        print({"context": key, **value})

    print("INCREASING DEMAND CONTEXT AUDIT SUMMARY")
    print({
        "symbols": len(symbols),
        "symbols_with_events": len({x["symbol"] for x in all_events}),
        "events": len(all_events),
        "failures": failures,
    })


if __name__ == "__main__":
    main()
