"""UPTHRUST semantic-quality audit.

Analysis-only. Reuses the exact cheap-candidate population from the validated
UPTHRUST candidate audit and treats actual production UPTHRUST emission at the
target bar as the semantic authority.
"""
from __future__ import annotations

import os
import sys

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from data import daily_to_weekly, download_data
from engine.columns import COL_DIRECTION, COL_SPREAD_CLASS, COL_VOLUME_CLASS
from evidence.campaign import has_buying_campaign
from evidence.engine import EvidenceEngine
from evidence.rules import (
    closes_lower_than_previous,
    has_strong_spread,
    is_above_average_spread,
    is_bullish_bar,
    is_very_high_volume,
    is_weak_close,
    is_wide_spread,
)
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
TARGET_CODE = EvidenceCode.UPTHRUST
EXPECTED_CANDIDATES = 1319
EXPECTED_EVENTS = 289
FORWARD_BARS = 8


def cheap_candidate(metrics: pd.DataFrame, index: int) -> bool:
    row = metrics.iloc[index]
    return (
        Direction(int(row[COL_DIRECTION])) == Direction.UP
        and VolumeClass(int(row[COL_VOLUME_CLASS])) >= VolumeClass.HIGH
        and SpreadClass(int(row[COL_SPREAD_CLASS])) >= SpreadClass.ABOVE_AVERAGE
    )


def candidate_indices(metrics: pd.DataFrame) -> list[int]:
    return [
        i
        for i in range(1, len(metrics) - FORWARD_BARS)
        if cheap_candidate(metrics, i)
    ]


def main() -> None:
    cheap_candidates = 0
    candidate_events = 0
    normal_detector_rejections = 0
    semantic_failures = 0
    duplicate_emissions = 0
    heavy_context_rebuilds = 0
    failures: list[dict[str, str]] = []

    semantic_counts = {
        "buying_campaign": 0,
        "bullish_bar": 0,
        "very_high_volume": 0,
        "above_average_spread": 0,
        "wide_spread_confirmation": 0,
        "weak_close_confirmation": 0,
        "lower_close_confirmation": 0,
    }

    for symbol in SYMBOLS:
        try:
            metrics = MetricsEngine().calculate(
                daily_to_weekly(download_data(symbol))
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
                    structural_swings=list(trend.structure.structural_swings),
                )

                targets = [
                    item
                    for item in result.evidence
                    if item.code is TARGET_CODE and item.bar_index == index
                ]

                if len(targets) > 1:
                    duplicate_emissions += len(targets) - 1
                    continue

                if not targets:
                    normal_detector_rejections += 1
                    continue

                candidate_events += 1
                emitted = targets[0]

                if emitted.code is not TARGET_CODE or emitted.bar_index != index:
                    semantic_failures += 1
                    continue

                # Rebuild only the point-in-time production context for the
                # target bar. Do not infer semantics from the cheap prefilter.
                semantic_engine = EvidenceEngine()
                semantic_engine._reset(
                    metrics=replay,
                    trend=trend,
                    structural_swings=tuple(trend.structure.structural_swings),
                    validation_metrics=replay,
                )
                ctx = semantic_engine._ctx
                if ctx is None or ctx.current is None:
                    semantic_failures += 1
                    continue

                bar = ctx.current
                previous = ctx.previous

                mandatory = {
                    "buying_campaign": has_buying_campaign(ctx),
                    "bullish_bar": is_bullish_bar(bar),
                    "very_high_volume": is_very_high_volume(bar),
                    "above_average_spread": is_above_average_spread(bar),
                }

                for key, passed in mandatory.items():
                    if passed:
                        semantic_counts[key] += 1
                    else:
                        semantic_failures += 1

                if has_strong_spread(bar) or is_wide_spread(bar):
                    semantic_counts["wide_spread_confirmation"] += 1
                if is_weak_close(bar):
                    semantic_counts["weak_close_confirmation"] += 1
                if previous is not None and closes_lower_than_previous(bar, previous):
                    semantic_counts["lower_close_confirmation"] += 1

        except Exception as exc:
            failures.append({"symbol": symbol, "error": str(exc)})

    failures_out = list(failures)

    if cheap_candidates != EXPECTED_CANDIDATES:
        failures_out.append({
            "scope": "candidate_population",
            "error": f"expected {EXPECTED_CANDIDATES}, got {cheap_candidates}",
        })

    if candidate_events != EXPECTED_EVENTS:
        failures_out.append({
            "scope": "production_emissions",
            "error": f"expected {EXPECTED_EVENTS}, got {candidate_events}",
        })

    if duplicate_emissions:
        failures_out.append({
            "scope": "duplicates",
            "error": f"duplicate emissions: {duplicate_emissions}",
        })

    if semantic_failures:
        failures_out.append({
            "scope": "semantics",
            "error": f"mandatory semantic failures: {semantic_failures}",
        })

    print("UPTHRUST SEMANTIC QUALITY AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": len(SYMBOLS) - len(failures),
        "cheap_candidates": cheap_candidates,
        "candidate_events": candidate_events,
        "expected_candidate_events": EXPECTED_EVENTS,
        "semantic_counts": semantic_counts,
        "semantic_failures": semantic_failures,
        "normal_detector_rejections": normal_detector_rejections,
        "duplicate_emissions": duplicate_emissions,
        "heavy_context_rebuilds": heavy_context_rebuilds,
        "target_bar_only": True,
        "point_in_time": True,
        "production_context_used": True,
        "production_emission_authority": True,
        "confirmations_are_non_mandatory": True,
        "failures": failures_out,
        "status": "FAIL" if failures_out else "PASS",
    })


if __name__ == "__main__":
    main()
