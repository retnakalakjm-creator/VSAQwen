"""NO_SUPPLY decision-value audit.

Analysis-only. Compares the frozen production-emission population against the
eligible-market baseline using the project 8-bar forward-return methodology.
The event population is fixed by the production detector; this audit does not
change detector semantics, scoring, qualification, or actionability.
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
TARGET_CODE = EvidenceCode.NO_SUPPLY
EXPECTED_CHEAP_CANDIDATES = 225
EXPECTED_EVENTS = 23
FORWARD_BARS = 8


def cheap_candidate(metrics: pd.DataFrame, index: int) -> bool:
    row = metrics.iloc[index]
    return (
        Direction(int(row[COL_DIRECTION])) == Direction.DOWN
        and VolumeClass(int(row[COL_VOLUME_CLASS])) <= VolumeClass.LOW
        and SpreadClass(int(row[COL_SPREAD_CLASS])) <= SpreadClass.NARROW
    )


def candidate_indices(metrics: pd.DataFrame) -> list[int]:
    return [
        i
        for i in range(1, len(metrics) - FORWARD_BARS)
        if cheap_candidate(metrics, i)
    ]


def forward_return(metrics: pd.DataFrame, index: int) -> float:
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
    cheap_candidates = 0
    candidate_returns: list[float] = []
    eligible_market_returns: list[float] = []
    failures: list[dict[str, str]] = []
    heavy_context_rebuilds = 0
    duplicate_emissions = 0

    for symbol in SYMBOLS:
        try:
            metrics = MetricsEngine().calculate(
                daily_to_weekly(download_data(symbol))
            )

            # Full eligible-market baseline is cheap: no EvidenceEngine replay.
            eligible_market_returns.extend(
                forward_return(metrics, index)
                for index in range(0, len(metrics) - FORWARD_BARS)
            )

            indices = candidate_indices(metrics)
            cheap_candidates += len(indices)

            for index in indices:
                replay = metrics.iloc[: index + 1].copy()
                trend = TrendAnalyzer().analyze(replay)
                heavy_context_rebuilds += 1

                result = EvidenceEngine().collect(
                    metrics=replay,
                    trend=trend,
                    structural_swings=tuple(
                        trend.structure.structural_swings
                    ),
                )

                targets = [
                    item
                    for item in result.evidence
                    if item.code is TARGET_CODE
                    and item.bar_index == index
                ]

                if len(targets) > 1:
                    duplicate_emissions += len(targets) - 1
                    continue

                if not targets:
                    continue

                candidate_returns.append(
                    forward_return(metrics, index)
                )

        except Exception as exc:
            failures.append({"symbol": symbol, "error": str(exc)})

    candidate_summary = summarize(candidate_returns)
    eligible_summary = summarize(eligible_market_returns)

    failures_out = list(failures)

    if cheap_candidates != EXPECTED_CHEAP_CANDIDATES:
        failures_out.append({
            "scope": "candidate_population",
            "error": (
                f"expected {EXPECTED_CHEAP_CANDIDATES} cheap candidates, "
                f"got {cheap_candidates}"
            ),
        })

    if len(candidate_returns) != EXPECTED_EVENTS:
        failures_out.append({
            "scope": "candidate_events",
            "error": (
                f"expected {EXPECTED_EVENTS} emitted events, "
                f"got {len(candidate_returns)}"
            ),
        })

    if duplicate_emissions:
        failures_out.append({
            "scope": "duplicates",
            "error": (
                f"duplicate target emissions: {duplicate_emissions}"
            ),
        })

    positive_rate_lift = (
        candidate_summary["positive_decisive_rate"]
        - eligible_summary["positive_decisive_rate"]
    )
    mean_return_lift = (
        candidate_summary["mean_return"]
        - eligible_summary["mean_return"]
    )

    print("NO_SUPPLY DECISION-VALUE AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": len(SYMBOLS) - len(failures),
        "cheap_candidates": cheap_candidates,
        "candidate_events": len(candidate_returns),
        "eligible_market_events": len(eligible_market_returns),
        "candidate_summary": candidate_summary,
        "eligible_market_summary": eligible_summary,
        "positive_decisive_rate_lift_vs_market": positive_rate_lift,
        "mean_return_lift_vs_market": mean_return_lift,
        "candidate_share_of_eligible": (
            len(candidate_returns) / len(eligible_market_returns)
            if eligible_market_returns else 0.0
        ),
        "frozen_candidate_population": True,
        "target_bar_only": True,
        "point_in_time": True,
        "production_path_mutation": False,
        "heavy_context_rebuilds": heavy_context_rebuilds,
        "duplicate_emissions": duplicate_emissions,
        "failures": failures_out,
        "status": "FAIL" if failures_out else "PASS",
    })


if __name__ == "__main__":
    main()
