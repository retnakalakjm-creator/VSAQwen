"""Analysis-only candidate audit for BUYING_CLIMAX.

The audit first measures the cheap point-in-time mandatory bar population and
then reports confirmation characteristics. The buying-campaign gate is kept
separate because it depends on historical campaign/trend context and should
not be approximated or silently replaced with textbook pattern matching.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from data import daily_to_weekly, download_data
from engine.columns import (
    COL_AVG_SPREAD,
    COL_CLOSE,
    COL_CLOSE_POSITION,
    COL_DIRECTION,
    COL_VOLUME_CLASS,
)
from metrics_engine import MetricsEngine
from models import ClosePosition, Direction, SpreadClass, VolumeClass

SYMBOLS = (
    "BHARTIARTL.NS",
    "HDFCBANK.NS",
    "ICICIBANK.NS",
    "INFY.NS",
    "LT.NS",
    "RELIANCE.NS",
    "SBIN.NS",
    "TCS.NS",
)
FORWARD_BARS = 8


@dataclass(slots=True)
class Outcome:
    positive: int = 0
    negative: int = 0
    flat: int = 0
    returns: list[float] | None = None

    def __post_init__(self) -> None:
        if self.returns is None:
            self.returns = []


def _cheap_candidate(metrics, index: int) -> bool:
    direction = Direction(int(metrics.iloc[index][COL_DIRECTION]))
    volume = VolumeClass(int(metrics.iloc[index][COL_VOLUME_CLASS]))
    spread = SpreadClass(int(metrics.iloc[index]["spread_class"]))
    return (
        direction == Direction.UP
        and volume == VolumeClass.VERY_HIGH
        and spread >= SpreadClass.ABOVE_AVERAGE
    )


def _audit_symbol(symbol: str) -> dict[str, object]:
    daily = download_data(symbol)
    weekly = daily_to_weekly(daily)
    metrics = MetricsEngine().calculate(weekly)

    outcome = Outcome()
    candidates = 0
    confirmations = {
        "wide_spread": 0,
        "weak_close": 0,
        "volume_increasing": 0,
    }

    closes = metrics[COL_CLOSE].to_numpy(dtype=float)

    for index in range(1, len(metrics)):
        if not _cheap_candidate(metrics, index):
            continue

        candidates += 1
        bar = metrics.iloc[index]
        previous = metrics.iloc[index - 1]

        close_position = ClosePosition(int(bar[COL_CLOSE_POSITION]))
        current_volume = VolumeClass(int(bar[COL_VOLUME_CLASS]))
        previous_volume = VolumeClass(int(previous[COL_VOLUME_CLASS]))
        spread = SpreadClass(int(bar["spread_class"]))

        if spread >= SpreadClass.WIDE:
            confirmations["wide_spread"] += 1
        if close_position in (ClosePosition.LOWER, ClosePosition.ON_LOW):
            confirmations["weak_close"] += 1
        if current_volume > previous_volume:
            confirmations["volume_increasing"] += 1

        if index + FORWARD_BARS >= len(closes):
            continue

        forward_return = float(closes[index + FORWARD_BARS] / closes[index] - 1.0)
        assert outcome.returns is not None
        outcome.returns.append(forward_return)
        if forward_return > 0.0:
            outcome.positive += 1
        elif forward_return < 0.0:
            outcome.negative += 1
        else:
            outcome.flat += 1

    return {
        "symbol": symbol,
        "bars": len(metrics),
        "candidate_events": candidates,
        "positive": outcome.positive,
        "negative": outcome.negative,
        "flat": outcome.flat,
        "returns": outcome.returns or [],
        **confirmations,
    }


def main() -> None:
    results: list[dict[str, object]] = []
    failures: list[dict[str, str]] = []

    for symbol in SYMBOLS:
        try:
            results.append(_audit_symbol(symbol))
        except Exception as exc:
            failures.append({"symbol": symbol, "error": str(exc)})

    all_returns = [v for result in results for v in result["returns"]]
    candidates = sum(int(r["candidate_events"]) for r in results)
    positive = sum(int(r["positive"]) for r in results)
    negative = sum(int(r["negative"]) for r in results)
    flat = sum(int(r["flat"]) for r in results)
    decisive = positive + negative

    print("BUYING CLIMAX CANDIDATE AUDIT")
    print(
        {
            "symbols_requested": len(SYMBOLS),
            "symbols_with_results": len(results),
            "candidate_events": candidates,
            "positive": positive,
            "negative": negative,
            "flat": flat,
            "decisive": decisive,
            "positive_decisive_rate": positive / decisive if decisive else 0.0,
            "mean_return": float(np.mean(all_returns)) if all_returns else 0.0,
            "wide_spread": sum(int(r["wide_spread"]) for r in results),
            "weak_close": sum(int(r["weak_close"]) for r in results),
            "volume_increasing": sum(int(r["volume_increasing"]) for r in results),
            "campaign_gate_included": False,
            "failures": failures,
            "status": "PASS" if not failures else "FAIL",
        }
    )

    for result in results:
        symbol_decisive = int(result["positive"]) + int(result["negative"])
        returns = result["returns"]
        print(
            {
                "symbol": result["symbol"],
                "candidate_events": result["candidate_events"],
                "positive": result["positive"],
                "negative": result["negative"],
                "flat": result["flat"],
                "positive_decisive_rate": (
                    int(result["positive"]) / symbol_decisive
                    if symbol_decisive
                    else 0.0
                ),
                "mean_return": float(np.mean(returns)) if returns else 0.0,
            }
        )


if __name__ == "__main__":
    main()
