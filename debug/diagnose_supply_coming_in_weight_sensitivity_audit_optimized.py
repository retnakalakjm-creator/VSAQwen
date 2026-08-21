"""Weight-sensitivity audit for SUPPLY_COMING_IN.

Analysis-only. Uses the frozen 189-event target population and evaluates
counterfactual weights without mutating production configuration.
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
TARGET_CODE = EvidenceCode.SUPPLY_COMING_IN
FORWARD_BARS = 8
EXPECTED_EVENTS = 189
WEIGHTS = (0.0, 0.25, 0.30, 0.38, 0.45, 0.50)
REFERENCE_WEIGHT = 0.38


def _cheap_candidate(metrics, index: int) -> bool:
    row = metrics.iloc[index]
    return (
        Direction(int(row[COL_DIRECTION])) == Direction.DOWN
        and VolumeClass(int(row[COL_VOLUME_CLASS])) >= VolumeClass.HIGH
        and SpreadClass(int(row[COL_SPREAD_CLASS])) >= SpreadClass.ABOVE_AVERAGE
    )


def _audit_symbol(symbol: str) -> tuple[int, int, list[float], int, list[dict[str, str]]]:
    metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
    closes = metrics[COL_CLOSE].to_numpy(dtype=float)
    cheap = 0
    campaign = 0
    outcomes: list[float] = []
    rebuilds = 0
    failures: list[dict[str, str]] = []

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
        rebuilds += 1
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
        outcomes.append(float(closes[index + FORWARD_BARS] / closes[index] - 1.0))

    return cheap, campaign, outcomes, rebuilds, failures


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
    symbols_with_results = 0
    cheap = campaign = rebuilds = 0
    outcomes: list[float] = []
    failures: list[dict[str, str]] = []

    for symbol in SYMBOLS:
        try:
            c, q, r, h, f = _audit_symbol(symbol)
            symbols_with_results += 1
            cheap += c
            campaign += q
            outcomes.extend(r)
            rebuilds += h
            failures.extend(f)
        except Exception as exc:
            failures.append({"symbol": symbol, "error": str(exc)})

    summary = _summary(outcomes)
    candidate_score_mass = {w: len(outcomes) * w for w in WEIGHTS}
    relative_strength = {
        w: (w / REFERENCE_WEIGHT) if REFERENCE_WEIGHT else 0.0
        for w in WEIGHTS
    }

    print("SUPPLY COMING IN WEIGHT SENSITIVITY AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": symbols_with_results,
        "cheap_candidates": cheap,
        "campaign_qualified_events": campaign,
        "candidate_events": len(outcomes),
        "candidate_summary": summary,
        "weights_tested": WEIGHTS,
        "reference_weight": REFERENCE_WEIGHT,
        "candidate_score_mass": candidate_score_mass,
        "relative_candidate_strength": relative_strength,
        "expected_candidate_events": EXPECTED_EVENTS,
        "production_path_mutation": False,
        "heavy_context_rebuilds": rebuilds,
        "failures": failures,
        "status": "PASS" if not failures and len(outcomes) == EXPECTED_EVENTS else "FAIL",
    })
    for weight in WEIGHTS:
        print({
            "weight": weight,
            "candidate_score_contribution": weight,
            "relative_candidate_strength": relative_strength[weight],
        })


if __name__ == "__main__":
    main()
