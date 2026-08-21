"""Decision-value audit for SUPPLY_COMING_IN.

Compares the frozen 189-event candidate population against eligible market
and tests counterfactual evidence weights without mutating production.
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
from evidence.rules import is_above_average_spread, is_down_bar, is_high_volume, is_weak_close, volume_increasing
from metrics_engine import MetricsEngine
from models import Direction, EvidenceCode, SpreadClass, VolumeClass
from trend import TrendAnalyzer

SYMBOLS = (
    "BHARTIARTL.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "LT.NS", "RELIANCE.NS", "SBIN.NS", "TCS.NS",
)
FORWARD_BARS = 8
TARGET_CODE = EvidenceCode.SUPPLY_COMING_IN
REFERENCE_WEIGHT = 0.38
WEIGHTS_TESTED = (0.0, 0.25, 0.30, 0.38, 0.45, 0.50)
EXPECTED_EVENTS = 189


def _cheap_candidate(metrics, index: int) -> bool:
    row = metrics.iloc[index]
    return (
        Direction(int(row[COL_DIRECTION])) == Direction.DOWN
        and VolumeClass(int(row[COL_VOLUME_CLASS])) >= VolumeClass.HIGH
        and SpreadClass(int(row[COL_SPREAD_CLASS])) >= SpreadClass.ABOVE_AVERAGE
    )


def _find_bar(ctx, bar_index: int):
    for bar in ctx.bars:
        if bar.bar_index == bar_index:
            return bar
    return None


def _collect_frozen_population() -> tuple[list[float], int, int, int, list[dict[str, str]]]:
    candidate_returns: list[float] = []
    eligible_returns: list[float] = []
    cheap_candidates = campaign_qualified = engine_replays = 0
    failures: list[dict[str, str]] = []

    for symbol in SYMBOLS:
        try:
            metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
            closes = metrics[COL_CLOSE].to_numpy(dtype=float)

            for index in range(1, len(metrics) - FORWARD_BARS):
                forward_return = float(closes[index + FORWARD_BARS] / closes[index] - 1.0)
                eligible_returns.append(forward_return)

                if not _cheap_candidate(metrics, index):
                    continue
                cheap_candidates += 1

                replay = metrics.iloc[: index + 1].copy()
                trend = TrendAnalyzer().analyze(replay)
                structural_swings = tuple(trend.structure.structural_swings)
                engine = EvidenceEngine()
                result = engine.collect(
                    metrics=replay,
                    trend=trend,
                    structural_swings=structural_swings,
                )
                engine_replays += 1
                ctx = engine._ctx
                assert ctx is not None

                if not has_buying_campaign(ctx):
                    continue
                campaign_qualified += 1

                target = [
                    e for e in result.evidence
                    if e.code is TARGET_CODE
                    and getattr(e, "bar_index", None) == index
                ]
                if len(target) == 1:
                    candidate_returns.append(forward_return)
        except Exception as exc:
            failures.append({"symbol": symbol, "error": str(exc)})

    return candidate_returns, eligible_returns, cheap_candidates, campaign_qualified, engine_replays, failures


def _summary(values: list[float]) -> dict[str, float | int]:
    positive = sum(v > 0.0 for v in values)
    negative = sum(v < 0.0 for v in values)
    flat = sum(v == 0.0 for v in values)
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
    candidate, eligible, cheap, campaign, replays, failures = _collect_frozen_population()
    eligible_summary = _summary(eligible)
    candidate_summary = _summary(candidate)
    market_rate = float(eligible_summary["positive_decisive_rate"])
    market_mean = float(eligible_summary["mean_return"])

    print("SUPPLY COMING IN DECISION VALUE AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "cheap_candidates": cheap,
        "campaign_qualified_events": campaign,
        "candidate_events": len(candidate),
        "eligible_market_events": len(eligible),
        "candidate_summary": candidate_summary,
        "eligible_market_summary": eligible_summary,
        "positive_decisive_rate_lift_vs_market": float(candidate_summary["positive_decisive_rate"] - market_rate),
        "mean_return_lift_vs_market": float(candidate_summary["mean_return"] - market_mean),
        "weights_tested": WEIGHTS_TESTED,
        "reference_weight": REFERENCE_WEIGHT,
        "expected_candidate_events": EXPECTED_EVENTS,
        "production_path_mutation": False,
        "heavy_context_rebuilds": replays,
        "failures": failures,
        "status": "PASS" if not failures and len(candidate) == EXPECTED_EVENTS else "FAIL",
    })

    for weight in WEIGHTS_TESTED:
        # Counterfactual event weighting is intentionally analysis-only.
        # We use event-mass weighting against the eligible market baseline.
        candidate_mass = len(candidate) * weight
        market_mass = max(0.0, len(eligible) - len(candidate))
        total_mass = candidate_mass + market_mass
        weighted_rate = (
            ((sum(v > 0.0 for v in candidate) * weight) +
             (sum(v > 0.0 for v in eligible) - sum(v > 0.0 for v in candidate))) /
            total_mass
            if total_mass else 0.0
        )
        weighted_mean = (
            ((float(np.mean(candidate)) * candidate_mass) +
             ((float(np.mean(eligible)) * market_mass))) / total_mass
            if total_mass else 0.0
        )
        print({
            "weight": weight,
            "candidate_score_mass": candidate_mass,
            "weighted_positive_decisive_rate": weighted_rate,
            "weighted_mean_return": weighted_mean,
            "positive_decisive_rate_lift_vs_market": weighted_rate - market_rate,
            "mean_return_lift_vs_market": weighted_mean - market_mean,
        })


if __name__ == "__main__":
    main()
