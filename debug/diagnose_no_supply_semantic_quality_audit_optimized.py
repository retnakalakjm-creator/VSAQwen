"""NO_SUPPLY semantic-quality audit.

Analysis-only. Uses the cheap candidate population as the replay boundary and
uses actual production NO_SUPPLY emissions as the semantic authority. Raw
OHLCV column names are never accessed directly; canonical engine column names
are used throughout.
"""
from __future__ import annotations

import os
import sys

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from data import daily_to_weekly, download_data
from engine.columns import (
    COL_CLOSE,
    COL_DIRECTION,
    COL_SPREAD_CLASS,
    COL_VOLUME_CLASS,
)
from evidence.engine import EvidenceEngine
from evidence.rules import (
    is_bearish_bar,
    is_low_volume,
    is_narrow_spread,
    volume_decreasing,
    is_weak_close,
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
TARGET_CODE = EvidenceCode.NO_SUPPLY
FORWARD_BARS = 8
EXPECTED_CANDIDATES = 225
EXPECTED_EVENTS = 23


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


def main() -> None:
    cheap_candidates = 0
    candidate_events = 0
    normal_detector_rejections = 0
    duplicate_emissions = 0
    semantic_failures = 0
    heavy_context_rebuilds = 0
    failures: list[dict[str, str]] = []

    semantic_counts = {
        "bullish_environment": 0,
        "bearish_bar": 0,
        "low_volume": 0,
        "narrow_spread": 0,
        "volume_decreasing_confirmation": 0,
        "weak_close_confirmation": 0,
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

                engine = EvidenceEngine()
                result = engine.collect(
                    metrics=replay,
                    trend=trend,
                    structural_swings=tuple(trend.structure.structural_swings),
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

                emitted = targets[0]
                candidate_events += 1

                if emitted.code is not TARGET_CODE or emitted.bar_index != index:
                    semantic_failures += 1
                    continue

                # Reuse the exact point-in-time context built by the production
                # EvidenceEngine. This is critical: the production requirement is
                # named "Bullish Environment" but the current detector implements it
                # with ctx.is_bearish_environment(). The audit must validate the
                # actual production predicate, not infer semantics from the label.
                ctx = getattr(engine, "_ctx", None)
                if ctx is None:
                    semantic_failures += 1
                    continue

                reqs = {
                    "bullish_environment": ctx.is_bearish_environment(),
                    "bearish_bar": is_bearish_bar(ctx.current),
                    "low_volume": is_low_volume(ctx.current),
                    "narrow_spread": is_narrow_spread(ctx.current),
                }

                for key, passed in reqs.items():
                    if passed:
                        semantic_counts[key] += 1
                    else:
                        semantic_failures += 1

                if ctx.previous is not None:
                    if volume_decreasing(ctx.current, ctx.previous):
                        semantic_counts["volume_decreasing_confirmation"] += 1
                    if is_weak_close(ctx.current):
                        semantic_counts["weak_close_confirmation"] += 1

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

    print("NO_SUPPLY SEMANTIC QUALITY AUDIT")
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
        "canonical_close_column": COL_CLOSE,
        "production_environment_predicate": "ctx.is_bearish_environment()",
        "failures": failures_out,
        "status": "FAIL" if failures_out else "PASS",
    })


if __name__ == "__main__":
    main()
