"""Drill-down audit for DEMAND_COMING_IN + supply conflict events.

Analysis-only. Focuses on the 13-event subset where nearby INCREASING_SUPPLY
and a BUYING_CLIMAX/UPTHRUST trap both occurred. No production behavior changes.
"""
from __future__ import annotations

import sys
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
    COL_HIGH,
    COL_LOW,
    COL_OPEN,
    COL_SPREAD_CLASS,
    COL_VOLUME_CLASS,
    COL_WEEK,
)
from evidence.engine import EvidenceEngine
from evidence.supply import collect_supply
from evidence.rules import has_strong_spread, is_strong_close, is_very_high_volume, volume_increasing
from metrics_engine import MetricsEngine
from models import Direction, EvidenceCode, SpreadClass, VolumeClass
from trend import TrendAnalyzer

SYMBOLS = (
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
HORIZON = 8
WINDOW = 5
TARGET_CODES = {
    EvidenceCode.INCREASING_SUPPLY,
    EvidenceCode.BUYING_CLIMAX,
    EvidenceCode.UPTHRUST,
}


def is_candidate(row) -> bool:
    return (
        Direction(int(row[COL_DIRECTION])) == Direction.DOWN
        and VolumeClass(int(row[COL_VOLUME_CLASS])) >= VolumeClass.HIGH
        and SpreadClass(int(row[COL_SPREAD_CLASS])) >= SpreadClass.ABOVE_AVERAGE
        and int(row[COL_CLOSE_POSITION]) >= 2
    )


def outcome(metrics, index: int) -> str | None:
    future = index + HORIZON
    if future >= len(metrics):
        return None
    entry = float(metrics.iloc[index][COL_CLOSE])
    end = float(metrics.iloc[future][COL_CLOSE])
    if end > entry:
        return "POSITIVE_8_BAR"
    if end < entry:
        return "NEGATIVE_8_BAR"
    return "FLAT_8_BAR"


def inspect_symbol(symbol: str) -> list[dict]:
    metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
    events: list[dict] = []

    for index in range(MIN_REPLAY_BARS, len(metrics) - HORIZON):
        row = metrics.iloc[index]
        if not is_candidate(row):
            continue

        replay = metrics.iloc[: index + 1]
        trend = TrendAnalyzer().analyze(replay)
        engine = EvidenceEngine()
        engine.collect(
            metrics=replay,
            trend=trend,
            structural_swings=tuple(trend.structure.structural_swings),
            validation_metrics=replay,
        )
        assert engine._ctx is not None

        supply = collect_supply(engine._ctx)
        interactions: dict[int, set[EvidenceCode]] = {}
        for item in supply:
            if item.code in TARGET_CODES:
                distance = item.bar_index - index
                if -WINDOW <= distance <= WINDOW and distance != 0:
                    interactions.setdefault(item.bar_index, set()).add(item.code)

        codes = {code for values in interactions.values() for code in values}
        required = {
            EvidenceCode.INCREASING_SUPPLY,
            EvidenceCode.BUYING_CLIMAX,
            EvidenceCode.UPTHRUST,
        }
        if not required.issubset(codes):
            continue

        current = metrics.iloc[index]
        prev = metrics.iloc[index - 1]
        future_close = float(metrics.iloc[index + HORIZON][COL_CLOSE])
        current_close = float(current[COL_CLOSE])

        events.append({
            "symbol": symbol,
            "bar_index": index,
            "week": str(current[COL_WEEK]),
            "outcome": outcome(metrics, index),
            "close": current_close,
            "future_close": future_close,
            "return_8_bar": (future_close - current_close) / current_close,
            "direction": Direction(int(current[COL_DIRECTION])).name,
            "volume_class": VolumeClass(int(current[COL_VOLUME_CLASS])).name,
            "spread_class": SpreadClass(int(current[COL_SPREAD_CLASS])).name,
            "close_position": int(current[COL_CLOSE_POSITION]),
            "very_high_volume": bool(is_very_high_volume(current)),
            "wide_spread": bool(has_strong_spread(current)),
            "strong_close": bool(is_strong_close(current)),
            "volume_increasing": bool(volume_increasing(current, prev)),
            "interaction_bars": {
                str(bar_index): sorted(code.name for code in bar_codes)
                for bar_index, bar_codes in sorted(interactions.items())
            },
        })

    return events


def main() -> None:
    symbols = tuple(sys.argv[1:]) or SYMBOLS
    rows: list[dict] = []
    failures: list[dict[str, str]] = []

    with ThreadPoolExecutor(max_workers=min(4, len(symbols))) as executor:
        futures = {executor.submit(inspect_symbol, symbol): symbol for symbol in symbols}
        for future, symbol in futures.items():
            try:
                rows.extend(future.result())
            except Exception as exc:  # noqa: BLE001
                failures.append({"symbol": symbol, "error": repr(exc)})

    print("DEMAND COMING IN CONFLICT EVENT DRILLDOWN")
    print({"events": len(rows), "symbols": len({r['symbol'] for r in rows}), "failures": failures})
    for row in sorted(rows, key=lambda r: (r["symbol"], r["bar_index"])):
        print(row)


if __name__ == "__main__":
    main()
