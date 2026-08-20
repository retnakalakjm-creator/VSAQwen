"""Point-in-time candidate audit for HIDDEN_SUPPLY.

This is an analysis-only audit. It intentionally bypasses the EvidenceEngine
because the production HIDDEN_SUPPLY detector depends only on the current
bar's semantic direction, volume class, and close position.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

# Allow the script to be launched directly from the repository root or from
# the debug directory without making imports depend on the caller's cwd.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np

from data import daily_to_weekly, download_data
from engine.columns import (
    COL_CLOSE,
    COL_CLOSE_POSITION,
    COL_DIRECTION,
    COL_VOLUME_CLASS,
)
from metrics_engine import MetricsEngine
from models import ClosePosition, Direction, VolumeClass


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


def _is_candidate(metrics, index: int) -> bool:
    direction = Direction(int(metrics.iloc[index][COL_DIRECTION]))
    volume = VolumeClass(int(metrics.iloc[index][COL_VOLUME_CLASS]))
    close_position = ClosePosition(int(metrics.iloc[index][COL_CLOSE_POSITION]))

    return (
        direction == Direction.UP
        and volume in (
            VolumeClass.HIGH,
            VolumeClass.VERY_HIGH,
            VolumeClass.ULTRA_HIGH,
        )
        and close_position in (
            ClosePosition.LOWER,
            ClosePosition.ON_LOW,
        )
    )


def _audit_symbol(symbol: str) -> dict[str, object]:
    daily = download_data(symbol)
    weekly = daily_to_weekly(daily)
    metrics = MetricsEngine().calculate(weekly)

    candidates = 0
    outcome = Outcome()

    closes = metrics[COL_CLOSE].to_numpy(dtype=float)

    for index in range(len(metrics)):
        if not _is_candidate(metrics, index):
            continue

        candidates += 1

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
    }


def main() -> None:
    print("HIDDEN SUPPLY CANDIDATE AUDIT")

    results: list[dict[str, object]] = []
    failures: list[dict[str, str]] = []

    for symbol in SYMBOLS:
        try:
            results.append(_audit_symbol(symbol))
        except Exception as exc:  # pragma: no cover - diagnostic guard
            failures.append({"symbol": symbol, "error": str(exc)})

    all_returns = [
        value
        for result in results
        for value in result["returns"]  # type: ignore[union-attr]
    ]

    total_candidates = sum(int(r["candidate_events"]) for r in results)
    positive = sum(int(r["positive"]) for r in results)
    negative = sum(int(r["negative"]) for r in results)
    flat = sum(int(r["flat"]) for r in results)
    decisive = positive + negative

    positive_decisive_rate = (
        positive / decisive
        if decisive
        else 0.0
    )
    mean_return = float(np.mean(all_returns)) if all_returns else 0.0

    print(
        {
            "symbols_requested": len(SYMBOLS),
            "symbols_with_results": len(results),
            "candidate_events": total_candidates,
            "positive": positive,
            "negative": negative,
            "flat": flat,
            "decisive": decisive,
            "positive_decisive_rate": positive_decisive_rate,
            "mean_return": mean_return,
            "failures": failures,
            "status": "PASS" if not failures else "FAIL",
        }
    )

    for result in results:
        returns = result["returns"]
        decisive_symbol = int(result["positive"]) + int(result["negative"])
        positive_symbol_rate = (
            int(result["positive"]) / decisive_symbol
            if decisive_symbol
            else 0.0
        )
        mean_symbol_return = (
            float(np.mean(returns))
            if returns
            else 0.0
        )
        print(
            {
                "symbol": result["symbol"],
                "candidate_events": result["candidate_events"],
                "positive": result["positive"],
                "negative": result["negative"],
                "flat": result["flat"],
                "positive_decisive_rate": positive_symbol_rate,
                "mean_return": mean_symbol_return,
            }
        )


if __name__ == "__main__":
    main()
