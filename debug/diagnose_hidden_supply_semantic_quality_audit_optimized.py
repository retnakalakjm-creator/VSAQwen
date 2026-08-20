"""Semantic-quality audit for HIDDEN_SUPPLY.

Analysis-only. Uses the exact production candidate semantics without invoking
EvidenceEngine, because HIDDEN_SUPPLY depends only on current-bar direction,
volume class, and close position.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from engine.columns import COL_CLOSE_POSITION, COL_DIRECTION, COL_VOLUME_CLASS
from metrics_engine import MetricsEngine
from models import ClosePosition, Direction, VolumeClass

SYMBOLS = (
    "BHARTIARTL.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "LT.NS", "RELIANCE.NS", "SBIN.NS", "TCS.NS",
)


def _candidate(row) -> bool:
    return (
        Direction(int(row[COL_DIRECTION])) == Direction.UP
        and VolumeClass(int(row[COL_VOLUME_CLASS])) in (
            VolumeClass.HIGH, VolumeClass.VERY_HIGH, VolumeClass.ULTRA_HIGH,
        )
        and ClosePosition(int(row[COL_CLOSE_POSITION])) in (
            ClosePosition.LOWER, ClosePosition.ON_LOW,
        )
    )


def main() -> None:
    results = []
    failures = []

    for symbol in SYMBOLS:
        try:
            metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
            total = 0
            high_volume = 0
            very_high_volume = 0
            lower_close = 0
            on_low = 0
            semantic_failures = 0

            for _, row in metrics.iterrows():
                if not _candidate(row):
                    continue
                total += 1
                volume = VolumeClass(int(row[COL_VOLUME_CLASS]))
                close_position = ClosePosition(int(row[COL_CLOSE_POSITION]))
                high_volume += volume >= VolumeClass.HIGH
                very_high_volume += volume >= VolumeClass.VERY_HIGH
                lower_close += close_position == ClosePosition.LOWER
                on_low += close_position == ClosePosition.ON_LOW
                if not (
                    Direction(int(row[COL_DIRECTION])) == Direction.UP
                    and volume >= VolumeClass.HIGH
                    and close_position in (ClosePosition.LOWER, ClosePosition.ON_LOW)
                ):
                    semantic_failures += 1

            results.append({
                "symbol": symbol,
                "candidate_events": total,
                "high_volume": high_volume,
                "very_high_volume": very_high_volume,
                "lower_close": lower_close,
                "on_low": on_low,
                "semantic_failures": semantic_failures,
            })
        except Exception as exc:
            failures.append({"symbol": symbol, "error": str(exc)})

    aggregate = {
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": len(results),
        "candidate_events": sum(r["candidate_events"] for r in results),
        "high_volume": sum(r["high_volume"] for r in results),
        "very_high_volume": sum(r["very_high_volume"] for r in results),
        "lower_close": sum(r["lower_close"] for r in results),
        "on_low": sum(r["on_low"] for r in results),
        "semantic_failures": sum(r["semantic_failures"] for r in results),
        "failures": failures,
        "status": "PASS" if not failures and not sum(r["semantic_failures"] for r in results) else "FAIL",
    }

    print("HIDDEN SUPPLY SEMANTIC-QUALITY AUDIT")
    print(aggregate)
    for result in results:
        print(result)


if __name__ == "__main__":
    main()
