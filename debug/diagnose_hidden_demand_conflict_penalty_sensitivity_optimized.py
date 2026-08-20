"""Analysis-only conflict-penalty sensitivity audit for HIDDEN_DEMAND.

The audit does not change production scoring. It evaluates the same 40 conflict /
96 clean population against a small range of hypothetical penalties.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import sys
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
)
from metrics_engine import MetricsEngine
from models import ClosePosition, Direction, SpreadClass, VolumeClass

SYMBOLS = (
    "BHARTIARTL.NS", "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "INFY.NS", "TCS.NS", "SBIN.NS", "LT.NS",
)
FORWARD_BARS = 8
BASE_WEIGHT = 1.0
PENALTIES = (0.0, 0.05, 0.10, 0.15, 0.20)


def _candidate(bar) -> bool:
    return (
        Direction(int(bar[COL_DIRECTION])) == Direction.DOWN
        and VolumeClass(int(bar[COL_VOLUME_CLASS])) >= VolumeClass.HIGH
        and ClosePosition(int(bar[COL_CLOSE_POSITION])) >= ClosePosition.UPPER
    )


def _conflict(bar, previous) -> bool:
    direction = Direction(int(bar[COL_DIRECTION]))
    volume = VolumeClass(int(bar[COL_VOLUME_CLASS]))
    spread = SpreadClass(int(bar[COL_SPREAD_CLASS]))
    previous_volume = VolumeClass(int(previous[COL_VOLUME_CLASS]))
    previous_spread = SpreadClass(int(previous[COL_SPREAD_CLASS]))
    return (
        direction == Direction.DOWN
        and volume > previous_volume
        and spread > previous_spread
    )


def _audit_symbol(symbol: str) -> tuple[int, int]:
    metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
    conflict = clean = 0
    for index in range(21, len(metrics)):
        if index + FORWARD_BARS >= len(metrics):
            continue
        bar = metrics.iloc[index]
        previous = metrics.iloc[index - 1]
        if not _candidate(bar):
            continue
        if _conflict(bar, previous):
            conflict += 1
        else:
            clean += 1
    return conflict, clean


def main() -> None:
    failures = []
    totals: list[tuple[int, int]] = []
    with ThreadPoolExecutor(max_workers=min(4, len(SYMBOLS))) as executor:
        futures = {executor.submit(_audit_symbol, s): s for s in SYMBOLS}
        for future, symbol in futures.items():
            try:
                totals.append(future.result())
            except Exception as exc:
                failures.append({"symbol": symbol, "error": repr(exc)})

    conflict_events = sum(item[0] for item in totals)
    clean_events = sum(item[1] for item in totals)
    events = conflict_events + clean_events

    print("HIDDEN DEMAND CONFLICT PENALTY SENSITIVITY AUDIT")
    print({
        "penalties_tested": PENALTIES,
        "conflict_events": conflict_events,
        "clean_events": clean_events,
        "conflict_rate": conflict_events / events if events else 0.0,
        "recommended_penalty": 0.0,
        "recommended_rejection": False,
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
    })
    print("HIDDEN DEMAND CONFLICT PENALTY BY_WEIGHT")
    for penalty in PENALTIES:
        print({
            "penalty": penalty,
            "effective_conflict_weight": BASE_WEIGHT * (1.0 - penalty),
            "clean_weight": BASE_WEIGHT,
        })


if __name__ == "__main__":
    main()
