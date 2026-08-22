"""Decision-value audit for INCREASING_SUPPLY.

Compares the frozen 528-event point-in-time candidate population against
an eligible-market baseline using the same 8-bar forward outcome convention.
"""
from __future__ import annotations

import os
import sys

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from data import daily_to_weekly, download_data
from engine.columns import COL_CLOSE
from evidence.engine import EvidenceEngine
from metrics_engine import MetricsEngine
from models import EvidenceCode
from trend import TrendAnalyzer

SYMBOLS = (
    "BHARTIARTL.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "LT.NS", "RELIANCE.NS", "SBIN.NS", "TCS.NS",
)
TARGET_CODE = EvidenceCode.INCREASING_SUPPLY
EXPECTED_EVENTS = 528
FORWARD_BARS = 8


def _candidate_indices(symbol: str, metrics) -> list[int]:
    indices: list[int] = []
    for index in range(1, len(metrics)):
        replay = metrics.iloc[: index + 1].copy()
        trend = TrendAnalyzer().analyze(replay)
        engine = EvidenceEngine()
        result = engine.collect(
            metrics=replay,
            trend=trend,
            structural_swings=tuple(trend.structure.structural_swings),
        )
        target = [
            e for e in result.evidence
            if e.code is TARGET_CODE
            and getattr(e, "bar_index", None) == index
        ]
        if target:
            indices.append(index)
    return indices


def _outcomes(metrics, indices: list[int]) -> tuple[int, int, int, list[float]]:
    positive = negative = flat = 0
    returns: list[float] = []
    for index in indices:
        if index + FORWARD_BARS >= len(metrics):
            continue
        start = float(metrics.iloc[index][COL_CLOSE])
        end = float(metrics.iloc[index + FORWARD_BARS][COL_CLOSE])
        if start == 0.0:
            continue
        ret = (end - start) / start
        returns.append(ret)
        if ret > 0:
            positive += 1
        elif ret < 0:
            negative += 1
        else:
            flat += 1
    return positive, negative, flat, returns


def main() -> None:
    candidate_events = 0
    candidate_positive = candidate_negative = candidate_flat = 0
    candidate_returns: list[float] = []
    eligible_positive = eligible_negative = eligible_flat = 0
    eligible_returns: list[float] = []
    failures: list[dict[str, str]] = []
    symbols_with_results = 0
    heavy_rebuilds = 0

    for symbol in SYMBOLS:
        try:
            metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
            indices = _candidate_indices(symbol, metrics)
            heavy_rebuilds += len(metrics) - 1
            symbols_with_results += 1

            p, n, f, rets = _outcomes(metrics, indices)
            candidate_events += p + n + f
            candidate_positive += p
            candidate_negative += n
            candidate_flat += f
            candidate_returns.extend(rets)

            eligible_indices = list(range(1, len(metrics) - FORWARD_BARS))
            cp, cn, cf, crets = _outcomes(metrics, eligible_indices)
            eligible_positive += cp
            eligible_negative += cn
            eligible_flat += cf
            eligible_returns.extend(crets)
        except Exception as exc:
            failures.append({"symbol": symbol, "error": str(exc)})

    candidate_decisive = candidate_positive + candidate_negative
    eligible_decisive = eligible_positive + eligible_negative
    candidate_rate = candidate_positive / candidate_decisive if candidate_decisive else 0.0
    eligible_rate = eligible_positive / eligible_decisive if eligible_decisive else 0.0
    candidate_mean = float(np.mean(candidate_returns)) if candidate_returns else 0.0
    eligible_mean = float(np.mean(eligible_returns)) if eligible_returns else 0.0

    print("INCREASING SUPPLY DECISION-VALUE AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": symbols_with_results,
        "candidate_events": candidate_events,
        "expected_events": EXPECTED_EVENTS,
        "candidate_summary": {
            "events": candidate_events,
            "positive": candidate_positive,
            "negative": candidate_negative,
            "flat": candidate_flat,
            "decisive": candidate_decisive,
            "positive_decisive_rate": candidate_rate,
            "mean_return": candidate_mean,
        },
        "eligible_market_summary": {
            "events": eligible_decisive + eligible_flat,
            "positive": eligible_positive,
            "negative": eligible_negative,
            "flat": eligible_flat,
            "decisive": eligible_decisive,
            "positive_decisive_rate": eligible_rate,
            "mean_return": eligible_mean,
        },
        "positive_decisive_rate_lift_vs_market": candidate_rate - eligible_rate,
        "mean_return_lift_vs_market": candidate_mean - eligible_mean,
        "candidate_share_of_eligible": candidate_events / (eligible_decisive + eligible_flat)
        if (eligible_decisive + eligible_flat) else 0.0,
        "heavy_context_rebuilds": heavy_rebuilds,
        "production_path_mutation": False,
        "failures": failures,
        "status": "PASS" if not failures and candidate_events == EXPECTED_EVENTS else "FAIL",
    })


if __name__ == "__main__":
    main()
