from __future__ import annotations

import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from engine.columns import (
    COL_CLOSE,
    COL_SPREAD_CLASS,
    COL_VOLUME_CLASS,
    COL_WEEK,
)
from evidence.campaign import has_selling_campaign
from evidence.demand import _collect_selling_climax
from evidence.engine import EvidenceEngine
from evidence.rules import (
    has_strong_spread,
    is_above_average_spread,
    is_bearish_bar,
    is_strong_close,
    is_very_high_volume,
    volume_increasing,
)
from metrics_engine import MetricsEngine
from models import SpreadClass, VolumeClass
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

FORWARD_HORIZONS = (1, 2, 4, 8)
MIN_REPLAY_BARS = 20


def classify_forward_return(value: float) -> str:
    if value >= 0.05:
        return "POSITIVE_8_BAR"
    if value <= -0.05:
        return "NEGATIVE_8_BAR"
    return "FLAT_8_BAR"


def inspect_symbol(symbol: str) -> list[dict]:
    daily = download_data(symbol)
    metrics = MetricsEngine().calculate(daily_to_weekly(daily))
    events: list[dict] = []

    for index in range(MIN_REPLAY_BARS, len(metrics)):
        row = metrics.iloc[index]

        # Safe atomic pre-filter only. Detector semantics are still
        # evaluated from the full point-in-time replay context.
        if not (
            int(row["direction"]) == -1
            and VolumeClass(row[COL_VOLUME_CLASS]) >= VolumeClass.VERY_HIGH
            and SpreadClass(row[COL_SPREAD_CLASS]) >= SpreadClass.ABOVE_AVERAGE
        ):
            continue

        replay = metrics.iloc[: index + 1].copy()
        trend = TrendAnalyzer().analyze(replay)
        engine = EvidenceEngine()
        engine.collect(
            metrics=replay,
            trend=trend,
            structural_swings=tuple(trend.structure.structural_swings),
        )

        assert engine._ctx is not None
        ctx = engine._ctx
        detected = _collect_selling_climax(ctx)
        if not detected:
            continue

        bar = ctx.current
        previous = ctx.previous
        requirements = {
            "selling_campaign": has_selling_campaign(ctx),
            "bearish_bar": is_bearish_bar(bar),
            "very_high_volume": is_very_high_volume(bar),
            "above_average_spread": is_above_average_spread(bar),
        }
        confirmations = {
            "wide_spread": has_strong_spread(bar),
            "strong_close": is_strong_close(bar),
            "volume_increasing": (
                volume_increasing(bar, previous)
                if previous is not None else False
            ),
        }

        current = float(metrics.iloc[index][COL_CLOSE])
        returns: dict[int, float] = {}
        if current != 0.0:
            for horizon in FORWARD_HORIZONS:
                future_index = index + horizon
                if future_index < len(metrics):
                    future_close = float(metrics.iloc[future_index][COL_CLOSE])
                    returns[horizon] = future_close / current - 1.0

        events.append({
            "symbol": symbol,
            "bar_index": index,
            "week": str(metrics.iloc[index][COL_WEEK]),
            "strength": [item.strength for item in detected],
            "quality": [item.quality for item in detected],
            "requirements": requirements,
            "confirmations": confirmations,
            "forward_returns": returns,
            "8_bar_class": (
                classify_forward_return(returns[8])
                if 8 in returns else "INSUFFICIENT_FORWARD_DATA"
            ),
        })

    return events


def main() -> None:
    symbols = tuple(sys.argv[1:]) or DEFAULT_SYMBOLS
    all_events: list[dict] = []
    failures: list[dict] = []

    print("=" * 72)
    print("SELLING CLIMAX HISTORICAL VALIDATION AUDIT")
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
                print({
                    "symbol": symbol,
                    "selling_climax_events": len(events),
                    "bars": [item["bar_index"] for item in events],
                })
            except Exception as exc:
                failures.append({"symbol": symbol, "error": repr(exc)})
                print({"symbol": symbol, "error": repr(exc)})

    classes: dict[str, int] = {}
    for item in all_events:
        outcome = item["8_bar_class"]
        classes[outcome] = classes.get(outcome, 0) + 1

    confirmation_counts = {
        key: sum(item["confirmations"][key] for item in all_events)
        for key in ("wide_spread", "strong_close", "volume_increasing")
    }

    print("\nSELLING CLIMAX SUMMARY")
    print({
        "symbols_requested": len(symbols),
        "symbols_with_events": len({item["symbol"] for item in all_events}),
        "total_events": len(all_events),
        "outcome_classes": classes,
        "confirmation_true_counts": confirmation_counts,
        "failed_symbols": failures,
    })

    print("\nSELLING CLIMAX EVENTS")
    for item in all_events:
        print(item)


if __name__ == "__main__":
    main()
