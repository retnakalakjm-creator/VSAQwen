"""Decision-value audit for NO_DEMAND.

Analysis-only. Compares the validated point-in-time NO_DEMAND candidate
population with the eligible market population using identical forward-return
logic. No production scoring/configuration is mutated.
"""
from __future__ import annotations

import os
import sys

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from data import daily_to_weekly, download_data
from engine.columns import COL_CLOSE, COL_DIRECTION, COL_SPREAD_CLASS, COL_VOLUME_CLASS
from evidence.engine import EvidenceEngine
from metrics_engine import MetricsEngine
from models import Direction, EvidenceCode, SpreadClass, VolumeClass
from trend import TrendAnalyzer

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
TARGET_CODE = EvidenceCode.NO_DEMAND
FORWARD_BARS = 8
EXPECTED_CANDIDATES = 202
EXPECTED_EVENTS = 109


def cheap_candidate(metrics: pd.DataFrame, index: int) -> bool:
    row = metrics.iloc[index]
    return (
        Direction(int(row[COL_DIRECTION])) == Direction.UP
        and VolumeClass(int(row[COL_VOLUME_CLASS])) <= VolumeClass.LOW
        and SpreadClass(int(row[COL_SPREAD_CLASS])) <= SpreadClass.NARROW
    )


def eligible_market(metrics: pd.DataFrame, index: int) -> bool:
    return 0 < index < len(metrics) - FORWARD_BARS


def outcome(metrics: pd.DataFrame, index: int) -> float:
    start = float(metrics.iloc[index][COL_CLOSE])
    end = float(metrics.iloc[index + FORWARD_BARS][COL_CLOSE])
    return 0.0 if start == 0.0 else end / start - 1.0


def summarize(returns: list[float]) -> dict[str, float | int]:
    positive = sum(value > 0.0 for value in returns)
    negative = sum(value < 0.0 for value in returns)
    flat = sum(value == 0.0 for value in returns)
    decisive = positive + negative
    return {
        "events": len(returns),
        "positive": positive,
        "negative": negative,
        "flat": flat,
        "decisive": decisive,
        "positive_decisive_rate": positive / decisive if decisive else 0.0,
        "mean_return": sum(returns) / len(returns) if returns else 0.0,
    }


def main() -> None:
    candidate_returns: list[float] = []
    eligible_returns: list[float] = []
    cheap_candidates = 0
    candidate_events = 0
    heavy_context_rebuilds = 0
    failures: list[dict[str, str]] = []

    for symbol in SYMBOLS:
        try:
            metrics = MetricsEngine().calculate(
                daily_to_weekly(download_data(symbol))
            )

            for index in range(1, len(metrics) - FORWARD_BARS):
                ret = outcome(metrics, index)
                eligible_returns.append(ret)

                if not cheap_candidate(metrics, index):
                    continue

                cheap_candidates += 1

                replay = metrics.iloc[: index + 1].copy()
                trend = TrendAnalyzer().analyze(replay)
                heavy_context_rebuilds += 1
                result = EvidenceEngine().collect(
                    metrics=replay,
                    trend=trend,
                    structural_swings=tuple(trend.structure.structural_swings),
                )
                targets = [
                    item
                    for item in result.evidence
                    if item.code is TARGET_CODE and item.bar_index == index
                ]

                if len(targets) != 1:
                    continue

                candidate_events += 1
                candidate_returns.append(ret)

        except Exception as exc:
            failures.append({"symbol": symbol, "error": str(exc)})

    candidate_summary = summarize(candidate_returns)
    eligible_summary = summarize(eligible_returns)

    rate_lift = (
        candidate_summary["positive_decisive_rate"]
        - eligible_summary["positive_decisive_rate"]
    )
    return_lift = candidate_summary["mean_return"] - eligible_summary["mean_return"]

    failures_out = list(failures)
    if cheap_candidates != EXPECTED_CANDIDATES:
        failures_out.append({
            "scope": "candidate_population",
            "error": f"expected {EXPECTED_CANDIDATES}, got {cheap_candidates}",
        })
    if candidate_events != EXPECTED_EVENTS:
        failures_out.append({
            "scope": "candidate_events",
            "error": f"expected {EXPECTED_EVENTS}, got {candidate_events}",
        })

    print("NO_DEMAND DECISION-VALUE AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": len(SYMBOLS) - len(failures),
        "cheap_candidates": cheap_candidates,
        "candidate_events": candidate_events,
        "eligible_market_events": len(eligible_returns),
        "candidate_summary": candidate_summary,
        "eligible_market_summary": eligible_summary,
        "positive_decisive_rate_lift_vs_market": rate_lift,
        "mean_return_lift_vs_market": return_lift,
        "candidate_share_of_eligible": (
            candidate_events / len(eligible_returns) if eligible_returns else 0.0
        ),
        "frozen_candidate_population": True,
        "target_bar_only": True,
        "point_in_time": True,
        "production_path_mutation": False,
        "heavy_context_rebuilds": heavy_context_rebuilds,
        "failures": failures_out,
        "status": "FAIL" if failures_out else "PASS",
    })


if __name__ == "__main__":
    main()
