"""Optimized robustness audit for DEMAND_COMING_IN candidate semantics.

Analysis-only. Does not modify production detector logic, weights, or scanner behavior.

The script deliberately reuses the same cheap O(N) candidate definition as the
semantic audit and computes full-sample + leave-one-symbol-out outcome stability.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

# Allow direct execution from the repository root, e.g.
# `python debug/diagnose_demand_coming_in_robustness.py`.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from data import download_data, daily_to_weekly
from metrics_engine import MetricsEngine
from engine.columns import (
    COL_CLOSE,
    COL_CLOSE_POSITION,
    COL_DIRECTION,
    COL_SPREAD_CLASS,
    COL_VOLUME_CLASS,
)
from models import Direction, SpreadClass, VolumeClass

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
FORWARD_BARS = 8


@dataclass(frozen=True, slots=True)
class Event:
    symbol: str
    bar_index: int
    outcome: str


def _metrics(symbol: str) -> pd.DataFrame:
    daily = download_data(symbol)
    weekly = daily_to_weekly(daily)
    return MetricsEngine().calculate(weekly)


def _candidates(metrics: pd.DataFrame) -> list[int]:
    """Same cheap necessary-condition scan used by the semantic audit."""
    direction = metrics[COL_DIRECTION].to_numpy()
    volume = metrics[COL_VOLUME_CLASS].to_numpy()
    spread = metrics[COL_SPREAD_CLASS].to_numpy()
    close_pos = metrics[COL_CLOSE_POSITION].to_numpy()

    candidates: list[int] = []
    for index in range(MIN_REPLAY_BARS, len(metrics)):
        if Direction(int(direction[index])) != Direction.DOWN:
            continue
        if VolumeClass(int(volume[index])) < VolumeClass.HIGH:
            continue
        # Must match the semantic audit exactly.
        if SpreadClass(int(spread[index])) < SpreadClass.ABOVE_AVERAGE:
            continue
        if int(close_pos[index]) < 2:
            continue
        candidates.append(index)
    return candidates


def _outcome(metrics: pd.DataFrame, index: int) -> str | None:
    future = metrics.iloc[index + 1 : index + 1 + FORWARD_BARS]
    if len(future) < FORWARD_BARS:
        return None

    entry = float(metrics.iloc[index][COL_CLOSE])
    end = float(future.iloc[-1][COL_CLOSE])
    if end > entry:
        return "POSITIVE_8_BAR"
    if end < entry:
        return "NEGATIVE_8_BAR"
    return "FLAT_8_BAR"


def _collect_symbol(symbol: str) -> list[Event]:
    metrics = _metrics(symbol)
    events: list[Event] = []
    for index in _candidates(metrics):
        outcome = _outcome(metrics, index)
        if outcome is not None:
            events.append(Event(symbol=symbol, bar_index=index, outcome=outcome))
    return events


def _summary(events: list[Event]) -> dict:
    positive = sum(event.outcome == "POSITIVE_8_BAR" for event in events)
    negative = sum(event.outcome == "NEGATIVE_8_BAR" for event in events)
    flat = sum(event.outcome == "FLAT_8_BAR" for event in events)
    decisive = positive + negative

    return {
        "events": len(events),
        "positive": positive,
        "negative": negative,
        "flat": flat,
        "insufficient_forward_data": 0,
        "decisive": decisive,
        "positive_decisive_rate": positive / decisive if decisive else 0.0,
    }


def main() -> None:
    by_symbol: dict[str, list[Event]] = {}
    failures: list[dict[str, str]] = []

    for symbol in SYMBOLS:
        try:
            by_symbol[symbol] = _collect_symbol(symbol)
        except Exception as exc:  # noqa: BLE001
            failures.append({"symbol": symbol, "error": repr(exc)})
            by_symbol[symbol] = []

    all_events = [event for events in by_symbol.values() for event in events]

    print("DEMAND COMING IN ROBUSTNESS SUMMARY")
    print(
        {
            "symbols_requested": len(SYMBOLS),
            "symbols_with_candidates": sum(
                bool(events) for events in by_symbol.values()
            ),
            "failures": failures,
            **_summary(all_events),
        }
    )

    print("DEMAND COMING IN ROBUSTNESS BY_SYMBOL")
    for symbol in SYMBOLS:
        print(symbol, _summary(by_symbol[symbol]))

    print("DEMAND COMING IN ROBUSTNESS LEAVE_ONE_OUT")
    for excluded in SYMBOLS:
        remaining = [
            event
            for symbol, events in by_symbol.items()
            if symbol != excluded
            for event in events
        ]
        print({"excluded_symbol": excluded, **_summary(remaining)})


if __name__ == "__main__":
    main()
