from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config
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
    is_weak_close,
    is_very_high_volume,
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


def inspect_symbol(symbol: str) -> list[dict]:
    daily = download_data(symbol)
    metrics = MetricsEngine().calculate(daily_to_weekly(daily))
    engine = EvidenceEngine()
    trend_analyzer = TrendAnalyzer()
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
        trend = trend_analyzer.analyze(replay)
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

        if not all(
            (
                has_selling_campaign(ctx),
                is_bearish_bar(bar),
                is_high_volume(bar),
                is_above_average_spread(bar),
                not is_weak_close(bar),
            )
        ):
            continue

        future_index = index + 8
        if future_index >= len(metrics):
            continue

        current = float(metrics.iloc[index][COL_CLOSE])
        future = float(metrics.iloc[future_index][COL_CLOSE])
        ret8 = (future - current) / current

        if ret8 > 0.02:
            outcome = "POSITIVE_8_BAR"
        elif ret8 < -0.02:
            outcome = "NEGATIVE_8_BAR"
        else:
            outcome = "FLAT_8_BAR"

        events.append(
            {
                "symbol": symbol,
                "bar_index": index,
                "week": str(metrics.iloc[index][COL_WEEK]),
                "outcome": outcome,
                "quality": 1.0,
                "confirmations": {
                    "very_high_volume": is_very_high_volume(bar),
                    "wide_spread": has_strong_spread(bar),
                    "volume_increasing": volume_increasing(bar, previous),
                    "higher_low": makes_higher_low(bar, previous),
                },
            }
        )

    return events


def main() -> None:
    symbols = tuple(sys.argv[1:]) or DEFAULT_SYMBOLS
    all_events: list[dict] = []
    failures: list[dict] = []

    with ThreadPoolExecutor(max_workers=min(4, len(symbols))) as executor:
        futures = {executor.submit(inspect_symbol, symbol): symbol for symbol in symbols}
        for future, symbol in futures.items():
            try:
                all_events.extend(future.result())
            except Exception as exc:
                failures.append({"symbol": symbol, "error": repr(exc)})

    configured_weight = float(config.STOPPING_VOLUME_WEIGHT)

    print("STOPPING VOLUME CONTRIBUTION SUMMARY")
    print({
        "symbols_requested": len(symbols),
        "symbols_with_events": len({x["symbol"] for x in all_events}),
        "events": len(all_events),
        "configured_weight": configured_weight,
        "production_path": "DISABLED",
        "actual_production_delta": 0.0,
        "failed_symbols": failures,
        "note": "Detector is not collected in production; contribution is therefore zero until explicitly enabled.",
    })

    by_outcome = {
        "POSITIVE_8_BAR": sum(x["outcome"] == "POSITIVE_8_BAR" for x in all_events),
        "NEGATIVE_8_BAR": sum(x["outcome"] == "NEGATIVE_8_BAR" for x in all_events),
        "FLAT_8_BAR": sum(x["outcome"] == "FLAT_8_BAR" for x in all_events),
    }

    print("\nSTOPPING VOLUME AUDIT CONTRIBUTION")
    print({
        "outcomes": by_outcome,
        "configured_weight": configured_weight,
        "candidate_demand_delta": configured_weight,
        "candidate_direction": "BULLISH",
        "candidate_quality": 1.0,
    })


if __name__ == "__main__":
    main()
