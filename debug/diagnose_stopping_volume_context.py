from __future__ import annotations

import sys
from collections import defaultdict
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


def inspect_symbol(symbol: str) -> list[dict]:
    daily = download_data(symbol)
    metrics = MetricsEngine().calculate(daily_to_weekly(daily))
    engine = EvidenceEngine()
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

        replay = metrics.iloc[: index + 1]
        trend = engine._build_trend(replay)
        structural_swings = tuple(trend.structure.structural_swings)
        engine.collect(
            metrics=replay,
            trend=trend,
            structural_swings=structural_swings,
            validation_metrics=metrics,
        )
        assert engine._ctx is not None
        ctx = engine._ctx
        bar = ctx.current
        previous = ctx.previous

        requirements = {
            "selling_campaign": has_selling_campaign(ctx),
            "bearish_bar": is_bearish_bar(bar),
            "high_volume": is_high_volume(bar),
            "above_average_spread": is_above_average_spread(bar),
            "close_off_low": not is_weak_close(bar),
        }
        if not all(requirements.values()):
            continue

        confirmations = {
            "very_high_volume": is_very_high_volume(bar),
            "wide_spread": has_strong_spread(bar),
            "volume_increasing": volume_increasing(bar, previous),
            "higher_low": makes_higher_low(bar, previous),
        }

        current = float(metrics.iloc[index][COL_CLOSE])
        future_index = index + 8
        if future_index >= len(metrics):
            continue
        future = float(metrics.iloc[future_index][COL_CLOSE])
        ret8 = (future - current) / current
        if ret8 > 0.02:
            outcome = "POSITIVE_8_BAR"
        elif ret8 < -0.02:
            outcome = "NEGATIVE_8_BAR"
        else:
            outcome = "FLAT_8_BAR"

        context_codes = tuple(sorted(str(item.code) for item in engine._evidence if item.bar_index == index))
        campaign_codes = tuple(sorted(str(item.code) for item in engine._evidence))

        events.append({
            "symbol": symbol,
            "bar_index": index,
            "week": str(metrics.iloc[index][COL_WEEK]),
            "outcome": outcome,
            "confirmations": tuple(k for k, v in confirmations.items() if v),
            "cooccurring_current_bar": context_codes,
            "cooccurring_campaign": campaign_codes,
            "forward_return_8": ret8,
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

    confirmation_groups: dict[tuple[str, ...], list[dict]] = defaultdict(list)
    context_groups: dict[tuple[str, ...], list[dict]] = defaultdict(list)
    for item in all_events:
        confirmation_groups[item["confirmations"]].append(item)
        context_groups[item["cooccurring_campaign"]].append(item)

    print("STOPPING VOLUME CONFIRMATION GROUP SUMMARY")
    for key, items in sorted(confirmation_groups.items(), key=lambda x: (-len(x[1]), x[0])):
        print({
            "confirmations": key,
            "events": len(items),
            "positive": sum(x["outcome"] == "POSITIVE_8_BAR" for x in items),
            "negative": sum(x["outcome"] == "NEGATIVE_8_BAR" for x in items),
            "flat": sum(x["outcome"] == "FLAT_8_BAR" for x in items),
            "bars": [x["bar_index"] for x in items],
        })

    print("STOPPING VOLUME CONTEXT GROUP SUMMARY")
    for key, items in sorted(context_groups.items(), key=lambda x: (-len(x[1]), x[0])):
        print({
            "cooccurring_evidence": key,
            "events": len(items),
            "positive": sum(x["outcome"] == "POSITIVE_8_BAR" for x in items),
            "negative": sum(x["outcome"] == "NEGATIVE_8_BAR" for x in items),
            "flat": sum(x["outcome"] == "FLAT_8_BAR" for x in items),
            "bars": [x["bar_index"] for x in items],
        })

    print("STOPPING VOLUME CONTEXT AUDIT SUMMARY")
    print({
        "symbols": len(symbols),
        "events": len(all_events),
        "failures": failures,
    })


if __name__ == "__main__":
    main()
