from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from engine.columns import COL_DIRECTION, COL_SPREAD_CLASS, COL_VOLUME_CLASS
from evidence.engine import EvidenceEngine
from evidence.rules import is_above_average_spread, is_bullish_bar, is_high_volume, volume_increasing
from metrics_engine import MetricsEngine
from models import Direction, SpreadClass, VolumeClass
from trend import TrendAnalyzer

SYMBOLS = ("BHARTIARTL.NS", "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS", "TCS.NS", "SBIN.NS", "LT.NS")
HORIZON = 8
MIN_REPLAY_BARS = 20


def inspect(symbol: str) -> int:
    metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
    count = 0
    for i in range(MIN_REPLAY_BARS, len(metrics) - HORIZON):
        row = metrics.iloc[i]
        if not (Direction(row[COL_DIRECTION]) == Direction.UP and VolumeClass(row[COL_VOLUME_CLASS]) >= VolumeClass.HIGH and SpreadClass(row[COL_SPREAD_CLASS]) >= SpreadClass.ABOVE_AVERAGE):
            continue
        replay = metrics.iloc[: i + 1]
        trend = TrendAnalyzer().analyze(replay)
        engine = EvidenceEngine()
        engine.collect(metrics=replay, trend=trend, structural_swings=tuple(trend.structure.structural_swings), validation_metrics=metrics)
        assert engine._ctx is not None
        bar = engine._ctx.current
        previous = engine._ctx.previous
        if previous is not None and all((is_bullish_bar(bar), is_high_volume(bar), is_above_average_spread(bar), volume_increasing(bar, previous))):
            count += 1
    return count


def main() -> None:
    failures = []
    counts = {}
    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = {ex.submit(inspect, s): s for s in SYMBOLS}
        for future, symbol in futures.items():
            try:
                counts[symbol] = future.result()
            except Exception as exc:
                failures.append({"symbol": symbol, "error": repr(exc)})
    print("INCREASING DEMAND CONTRIBUTION SUMMARY")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_events": len(counts),
        "events": sum(counts.values()),
        "configured_weight": "NOT REGISTERED",
        "production_path": "DISABLED",
        "actual_production_hits": 0,
        "actual_production_delta": 0.0,
        "failed_symbols": failures,
        "note": "Exact 902-event detector definition is replayed point-in-time; production contribution remains zero until explicitly enabled and registered.",
    })


if __name__ == "__main__":
    main()
