from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from engine.columns import COL_CLOSE, COL_DIRECTION, COL_SPREAD_CLASS, COL_VOLUME_CLASS
from evidence.campaign import has_buying_campaign
from evidence.engine import EvidenceEngine
from evidence.rules import (
    is_above_average_spread,
    is_bullish_bar,
    is_high_volume,
    is_strong_close,
)
from metrics_engine import MetricsEngine
from models import Direction, EvidenceCode, SpreadClass, VolumeClass
from trend import TrendAnalyzer

DEFAULT_SYMBOLS = (
    "BHARTIARTL.NS", "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "INFY.NS", "TCS.NS", "SBIN.NS", "LT.NS",
)
MIN_REPLAY_BARS = 20
HORIZON = 8


def inspect_symbol(symbol: str) -> dict:
    daily = download_data(symbol)
    metrics = MetricsEngine().calculate(daily_to_weekly(daily))
    events = 0
    production_hits = 0

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
        result = engine.collect(
            metrics=replay,
            trend=trend,
            structural_swings=tuple(trend.structure.structural_swings),
            validation_metrics=metrics,
        )

        assert engine._ctx is not None
        bar = engine._ctx.current
        if not all(
            (
                has_buying_campaign(engine._ctx),
                is_bullish_bar(bar),
                is_high_volume(bar),
                is_above_average_spread(bar),
                is_strong_close(bar),
            )
        ):
            continue

        events += 1
        production_hits += sum(
            item.code == EvidenceCode.DEMAND_COMING_IN
            for item in result.evidence
        )

    return {"symbol": symbol, "events": events, "production_hits": production_hits}


def main() -> None:
    symbols = tuple(sys.argv[1:]) or DEFAULT_SYMBOLS
    rows: list[dict] = []
    failures: list[dict] = []

    with ThreadPoolExecutor(max_workers=min(4, len(symbols))) as executor:
        futures = {executor.submit(inspect_symbol, symbol): symbol for symbol in symbols}
        for future, symbol in futures.items():
            try:
                rows.append(future.result())
            except Exception as exc:
                failures.append({"symbol": symbol, "error": repr(exc)})

    events = sum(row["events"] for row in rows)
    production_hits = sum(row["production_hits"] for row in rows)

    print("DEMAND COMING IN CONTRIBUTION SUMMARY")
    print({
        "symbols_requested": len(symbols),
        "symbols_with_events": len(rows),
        "events": events,
        "configured_weight": "NOT REGISTERED",
        "production_path": "DISABLED",
        "actual_production_hits": production_hits,
        "actual_production_delta": 0.0,
        "failed_symbols": failures,
        "note": "Exact detector definition is replayed point-in-time; production contribution remains zero until explicitly enabled and registered.",
    })


if __name__ == "__main__":
    main()
