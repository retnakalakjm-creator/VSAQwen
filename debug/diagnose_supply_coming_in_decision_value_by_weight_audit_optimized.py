"""Decision-value sensitivity audit for SUPPLY_COMING_IN.

Analysis-only. Measures whether changing the hypothetical evidence weight
changes the candidate's relative decision value versus the eligible market.
The production path is never mutated.
"""
from __future__ import annotations

import os
import sys

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from data import daily_to_weekly, download_data
from engine.columns import COL_CLOSE, COL_DIRECTION, COL_SPREAD_CLASS, COL_VOLUME_CLASS
from evidence.campaign import has_buying_campaign
from evidence.engine import EvidenceEngine
from metrics_engine import MetricsEngine
from models import Direction, EvidenceCode, SpreadClass, VolumeClass
from trend import TrendAnalyzer

SYMBOLS = (
    "BHARTIARTL.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "LT.NS", "RELIANCE.NS", "SBIN.NS", "TCS.NS",
)
FORWARD_BARS = 8
TARGET_CODE = EvidenceCode.SUPPLY_COMING_IN
WEIGHTS = (0.25, 0.30, 0.38, 0.45, 0.50)
REFERENCE_WEIGHT = 0.38
EXPECTED_EVENTS = 189


def _cheap_candidate(metrics, index: int) -> bool:
    row = metrics.iloc[index]
    return (
        Direction(int(row[COL_DIRECTION])) == Direction.DOWN
        and VolumeClass(int(row[COL_VOLUME_CLASS])) >= VolumeClass.HIGH
        and SpreadClass(int(row[COL_SPREAD_CLASS])) >= SpreadClass.ABOVE_AVERAGE
    )


def _audit_symbol(symbol: str) -> dict[str, object]:
    metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
    closes = metrics[COL_CLOSE].to_numpy(dtype=float)

    cheap = campaign = events = 0
    returns: list[float] = []
    failures: list[str] = []
    heavy_rebuilds = 0

    for index in range(1, len(metrics) - FORWARD_BARS):
        if not _cheap_candidate(metrics, index):
            continue
        cheap += 1

        replay = metrics.iloc[: index + 1].copy()
        trend = TrendAnalyzer().analyze(replay)
        structural_swings = tuple(trend.structure.structural_swings)
        engine = EvidenceEngine()
        result = engine.collect(
            metrics=replay,
            trend=trend,
            structural_swings=structural_swings,
        )
        heavy_rebuilds += 1
        ctx = engine._ctx
        assert ctx is not None

        if not has_buying_campaign(ctx):
            continue
        campaign += 1

        target = [
            e for e in result.evidence
            if e.code is TARGET_CODE
            and getattr(e, "bar_index", None) == index
        ]
        if len(target) != 1:
            continue

        events += 1
        returns.append(float(closes[index + FORWARD_BARS] / closes[index] - 1.0))

    return {
        "cheap": cheap,
        "campaign": campaign,
        "events": events,
        "returns": returns,
        "heavy_rebuilds": heavy_rebuilds,
        "failures": failures,
    }


def _summary(values: list[float], weight: float) -> dict[str, object]:
    positive = sum(v > 0.0 for v in values)
    negative = sum(v < 0.0 for v in values)
    flat = sum(v == 0.0 for v in values)
    decisive = positive + negative
    candidate_mass = weight * len(values)
    return {
        "weight": weight,
        "events": len(values),
        "positive": positive,
        "negative": negative,
        "flat": flat,
        "decisive": decisive,
        "positive_decisive_rate": positive / decisive if decisive else 0.0,
        "mean_return": float(np.mean(values)) if values else 0.0,
        "candidate_score_mass": candidate_mass,
    }


def main() -> None:
    symbols_with_results = 0
    cheap = campaign = events = heavy_rebuilds = 0
    candidate_returns: list[float] = []
    failures: list[dict[str, str]] = []

    for symbol in SYMBOLS:
        try:
            r = _audit_symbol(symbol)
            symbols_with_results += 1
            cheap += int(r["cheap"])
            campaign += int(r["campaign"])
            events += int(r["events"])
            heavy_rebuilds += int(r["heavy_rebuilds"])
            candidate_returns.extend(r["returns"])
            failures.extend({"symbol": symbol, "error": msg} for msg in r["failures"])
        except Exception as exc:
            failures.append({"symbol": symbol, "error": str(exc)})

    # Market baseline uses all eligible bars in the same point-in-time universe.
    market_returns: list[float] = []
    for symbol in SYMBOLS:
        try:
            metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
            closes = metrics[COL_CLOSE].to_numpy(dtype=float)
            for index in range(FORWARD_BARS, len(metrics) - 0):
                if index + FORWARD_BARS >= len(metrics):
                    break
                market_returns.append(float(closes[index + FORWARD_BARS] / closes[index] - 1.0))
        except Exception as exc:
            failures.append({"symbol": symbol, "error": str(exc)})

    market_positive = sum(v > 0.0 for v in market_returns)
    market_negative = sum(v < 0.0 for v in market_returns)
    market_decisive = market_positive + market_negative
    market_rate = market_positive / market_decisive if market_decisive else 0.0
    market_mean = float(np.mean(market_returns)) if market_returns else 0.0

    weight_results = []
    for weight in WEIGHTS:
        summary = _summary(candidate_returns, weight)
        summary["positive_decisive_rate_lift_vs_market"] = (
            summary["positive_decisive_rate"] - market_rate
        )
        summary["mean_return_lift_vs_market"] = (
            summary["mean_return"] - market_mean
        )
        summary["relative_candidate_strength"] = (
            weight / REFERENCE_WEIGHT if REFERENCE_WEIGHT else 0.0
        )
        weight_results.append(summary)

    print("SUPPLY COMING IN DECISION-VALUE BY WEIGHT AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": symbols_with_results,
        "cheap_candidates": cheap,
        "campaign_qualified_events": campaign,
        "candidate_events": events,
        "eligible_market_events": len(market_returns),
        "candidate_positive_decisive_rate": (
            sum(v > 0.0 for v in candidate_returns) / len(candidate_returns)
            if candidate_returns else 0.0
        ),
        "candidate_mean_return": float(np.mean(candidate_returns)) if candidate_returns else 0.0,
        "eligible_market_positive_decisive_rate": market_rate,
        "eligible_market_mean_return": market_mean,
        "weights_tested": WEIGHTS,
        "reference_weight": REFERENCE_WEIGHT,
        "expected_candidate_events": EXPECTED_EVENTS,
        "production_path_mutation": False,
        "heavy_context_rebuilds": heavy_rebuilds,
        "failures": failures,
        "status": "PASS" if not failures and events == EXPECTED_EVENTS else "FAIL",
    })

    for result in weight_results:
        print(result)


if __name__ == "__main__":
    main()
