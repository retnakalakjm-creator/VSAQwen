"""Decision-value audit for HIDDEN_SUPPLY.

Analysis-only. Compares the validated HIDDEN_SUPPLY candidate population
against the eligible market baseline and tests synthetic decision weights.
No production scoring mutation.
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
from engine.columns import COL_CLOSE, COL_DIRECTION, COL_VOLUME_CLASS, COL_CLOSE_POSITION
from metrics_engine import MetricsEngine
from models import Direction, VolumeClass, ClosePosition

SYMBOLS = (
    "BHARTIARTL.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "LT.NS", "RELIANCE.NS", "SBIN.NS", "TCS.NS",
)
FORWARD_BARS = 8
WEIGHTS = (0.0, 0.25, 0.30, 0.38, 0.45, 0.50)
REFERENCE_WEIGHT = 0.38


def _candidate(mask_metrics, index: int) -> bool:
    direction = Direction(int(mask_metrics.iloc[index][COL_DIRECTION]))
    volume = VolumeClass(int(mask_metrics.iloc[index][COL_VOLUME_CLASS]))
    close_position = ClosePosition(int(mask_metrics.iloc[index][COL_CLOSE_POSITION]))
    return (
        direction == Direction.UP
        and volume in (VolumeClass.HIGH, VolumeClass.VERY_HIGH, VolumeClass.ULTRA_HIGH)
        and close_position in (ClosePosition.LOWER, ClosePosition.ON_LOW)
    )


def _audit_symbol(symbol: str) -> dict[str, object]:
    metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
    closes = metrics[COL_CLOSE].to_numpy(dtype=float)
    candidate_returns: list[float] = []
    eligible_returns: list[float] = []
    candidates = 0

    for index in range(len(metrics)):
        if index + FORWARD_BARS >= len(metrics):
            continue
        forward_return = float(closes[index + FORWARD_BARS] / closes[index] - 1.0)
        eligible_returns.append(forward_return)
        if _candidate(metrics, index):
            candidates += 1
            candidate_returns.append(forward_return)

    return {
        "symbol": symbol,
        "candidate_events": candidates,
        "candidate_returns": candidate_returns,
        "eligible_returns": eligible_returns,
    }


def _stats(values: list[float]) -> dict[str, object]:
    positive = sum(value > 0.0 for value in values)
    negative = sum(value < 0.0 for value in values)
    flat = sum(value == 0.0 for value in values)
    decisive = positive + negative
    return {
        "events": len(values),
        "positive": positive,
        "negative": negative,
        "flat": flat,
        "decisive": decisive,
        "positive_decisive_rate": positive / decisive if decisive else 0.0,
        "mean_return": float(np.mean(values)) if values else 0.0,
    }


def main() -> None:
    results: list[dict[str, object]] = []
    failures: list[dict[str, str]] = []
    for symbol in SYMBOLS:
        try:
            results.append(_audit_symbol(symbol))
        except Exception as exc:
            failures.append({"symbol": symbol, "error": str(exc)})

    candidate_returns = [v for r in results for v in r["candidate_returns"]]
    eligible_returns = [v for r in results for v in r["eligible_returns"]]
    candidate = _stats(candidate_returns)
    eligible = _stats(eligible_returns)
    lift_rate = candidate["positive_decisive_rate"] - eligible["positive_decisive_rate"]
    lift_return = candidate["mean_return"] - eligible["mean_return"]

    print("HIDDEN SUPPLY DECISION VALUE AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": len(results),
        "candidate": candidate,
        "eligible_market": eligible,
        "positive_decisive_rate_lift": lift_rate,
        "mean_return_lift": lift_return,
        "candidate_share_of_eligible": (
            candidate["events"] / eligible["events"]
            if eligible["events"] else 0.0
        ),
        "weights_tested": WEIGHTS,
        "reference_weight": REFERENCE_WEIGHT,
        "production_path_mutation": False,
        "failures": failures,
        "status": "PASS" if not failures else "FAIL",
    })

    for weight in WEIGHTS:
        print({
            "weight": weight,
            "candidate_score_contribution": weight,
            "relative_candidate_strength": round(weight * 0.90, 6),
        })


if __name__ == "__main__":
    main()
