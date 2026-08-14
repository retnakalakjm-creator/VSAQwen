"""Replay Spring through the production EvidenceEngine path.

Unlike diagnose_spring.py, this diagnostic does not call the Spring detector
or validator directly. Each point-in-time replay is passed through
EvidenceEngine.collect(), so the reported Spring events represent the actual
production evidence path.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from evidence.engine import EvidenceEngine
from engine.columns import COL_CLOSE, COL_WEEK
from market_structure.swing_engine import SwingEngine
from metrics_engine import MetricsEngine
from trend import TrendAnalyzer

DEFAULT_SYMBOLS = (
    "BHARTIARTL.NS", "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "INFY.NS", "TCS.NS", "SBIN.NS", "LT.NS",
)
MIN_REPLAY_BARS = 20
FORWARD_HORIZON = 8


def _code(item) -> str:
    return str(item.code).split(".")[-1].upper()


def inspect_symbol(symbol: str) -> list[dict]:
    daily = download_data(symbol)
    metrics = MetricsEngine().calculate(daily_to_weekly(daily))
    events: list[dict] = []

    for index in range(MIN_REPLAY_BARS, len(metrics)):
        future_index = index + FORWARD_HORIZON
        if future_index >= len(metrics):
            break

        replay = metrics.iloc[: index + 1].copy()
        trend = TrendAnalyzer().analyze(replay)
        structural_swings = tuple(trend.structure.structural_swings)
        result = EvidenceEngine().collect(
            metrics=replay,
            trend=trend,
            structural_swings=structural_swings,
            validation_metrics=replay,
        )

        spring_events = [item for item in result.evidence if _code(item) == "SPRING"]
        if not spring_events:
            continue

        current = float(metrics.iloc[index][COL_CLOSE])
        future = float(metrics.iloc[future_index][COL_CLOSE])
        if current != current or future != future or current == 0.0:
            continue

        forward_return = (future - current) / current
        outcome = (
            "POSITIVE_8_BAR" if forward_return > 0.02
            else "NEGATIVE_8_BAR" if forward_return < -0.02
            else "FLAT_8_BAR"
        )
        events.append({
            "symbol": symbol,
            "bar_index": index,
            "week": str(metrics.iloc[index][COL_WEEK]),
            "spring_events": len(spring_events),
            "outcome": outcome,
            "forward_return": forward_return,
            "weights": [item.weight for item in spring_events],
        })

    return events


def main() -> None:
    all_events: list[dict] = []
    failures: list[dict] = []

    for symbol in DEFAULT_SYMBOLS:
        try:
            events = inspect_symbol(symbol)
            all_events.extend(events)
            print({"symbol": symbol, "production_spring_events": len(events)})
        except Exception as exc:
            failures.append({"symbol": symbol, "error": repr(exc)})
            print(f"FAILED {symbol}: {exc!r}")

    by_outcome = {
        "POSITIVE_8_BAR": sum(e["outcome"] == "POSITIVE_8_BAR" for e in all_events),
        "NEGATIVE_8_BAR": sum(e["outcome"] == "NEGATIVE_8_BAR" for e in all_events),
        "FLAT_8_BAR": sum(e["outcome"] == "FLAT_8_BAR" for e in all_events),
    }

    print("SPRING PRODUCTION REPLAY SUMMARY")
    print({
        "symbols_requested": len(DEFAULT_SYMBOLS),
        "symbols_with_events": len({e["symbol"] for e in all_events}),
        "production_spring_events": len(all_events),
        "outcome_classes": by_outcome,
        "failures": failures,
    })

    print("SPRING PRODUCTION REPLAY EVENTS")
    for event in all_events:
        print(event)


if __name__ == "__main__":
    main()
