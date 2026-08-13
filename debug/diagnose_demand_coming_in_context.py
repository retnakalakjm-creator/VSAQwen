from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from engine.columns import COL_CLOSE, COL_DIRECTION, COL_SPREAD_CLASS, COL_VOLUME_CLASS, COL_WEEK
from evidence.campaign import has_recent_weakness
from evidence.engine import EvidenceEngine
from evidence.rules import has_strong_spread, is_above_average_spread, is_bullish_bar, is_high_volume, is_very_high_volume, volume_increasing
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
        engine.collect(metrics=replay, trend=trend, structural_swings=tuple(trend.structure.structural_swings), validation_metrics=metrics)
        assert engine._ctx is not None
        ctx = engine._ctx
        bar, prev = ctx.current, ctx.previous
        required = (
            is_bullish_bar(bar)
            and is_high_volume(bar)
            and is_above_average_spread(bar)
        )
        if not required:
            continue
        confirmations = {
            "very_high_volume": is_very_high_volume(bar),
            "wide_spread": has_strong_spread(bar),
            "volume_increasing": volume_increasing(bar, prev),
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
            "recent_weakness": bool(has_recent_weakness(ctx)),
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

    confirmation_groups: dict[tuple[str, ...], dict[str, object]] = {}
    for item in all_events:
        key = tuple(k for k, v in item["confirmations"].items() if v)
        group = confirmation_groups.setdefault(key, {"events": 0, "positive": 0, "negative": 0, "flat": 0, "bars": []})
        group["events"] += 1
        group[{"POSITIVE_8_BAR": "positive", "NEGATIVE_8_BAR": "negative", "FLAT_8_BAR": "flat"}[item["outcome"]]] += 1
        group["bars"].append(item["bar_index"])

    context_groups: dict[tuple[object, ...], dict[str, object]] = {}
    for item in all_events:
        key = ("recent_weakness",) if item["recent_weakness"] else ()
        group = context_groups.setdefault(key, {"events": 0, "positive": 0, "negative": 0, "flat": 0, "bars": []})
        group["events"] += 1
        group[{"POSITIVE_8_BAR": "positive", "NEGATIVE_8_BAR": "negative", "FLAT_8_BAR": "flat"}[item["outcome"]]] += 1
        group["bars"].append(item["bar_index"])

    print("DEMAND COMING IN CONFIRMATION GROUP SUMMARY")
    for key, value in sorted(confirmation_groups.items(), key=lambda x: (-x[1]["events"], x[0])):
        print({"confirmations": key, **value})
    print("DEMAND COMING IN CONTEXT GROUP SUMMARY")
    for key, value in sorted(context_groups.items(), key=lambda x: (-x[1]["events"], str(x[0]))):
        print({"context": key, **value})
    print("DEMAND COMING IN CONTEXT AUDIT SUMMARY")
    print({"symbols": len(symbols), "symbols_with_events": len({x["symbol"] for x in all_events}), "events": len(all_events), "failures": failures})


if __name__ == "__main__":
    main()
