"""Weight-sensitivity audit for INCREASING_SUPPLY.

Uses the frozen 528-event candidate population and tests fixed counterfactual
weights without mutating production configuration. The production registry
weight (0.85) and the runtime calculator behavior (currently fallback 1.00)
are reported separately.
"""
from __future__ import annotations

import os
import sys

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from data import daily_to_weekly, download_data
from engine.columns import COL_DIRECTION, COL_SPREAD_CLASS, COL_VOLUME_CLASS
from evidence.engine import EvidenceEngine
from evidence.profiles import EVIDENCE_REGISTRY
from evidence.weight import WeightCalculator
from metrics_engine import MetricsEngine
from models import Direction, EvidenceCode, SpreadClass, VolumeClass
from trend import TrendAnalyzer

SYMBOLS = (
    "BHARTIARTL.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "LT.NS", "RELIANCE.NS", "SBIN.NS", "TCS.NS",
)
TARGET_CODE = EvidenceCode.INCREASING_SUPPLY
EXPECTED_EVENTS = 528
WEIGHTS_TESTED = (0.70, 0.75, 0.80, 0.85, 0.90, 1.00)
FORWARD_BARS = 8


def _cheap_candidate(metrics, index: int) -> bool:
    row = metrics.iloc[index]
    return (
        Direction(int(row[COL_DIRECTION])) == Direction.DOWN
        and VolumeClass(int(row[COL_VOLUME_CLASS])) >= VolumeClass.HIGH
        and SpreadClass(int(row[COL_SPREAD_CLASS])) >= SpreadClass.ABOVE_AVERAGE
    )


def _collect_target_events(metrics) -> tuple[list[tuple[int, float, float]], int]:
    events: list[tuple[int, float, float]] = []
    heavy_rebuilds = 0

    for index in range(1, len(metrics)):
        if not _cheap_candidate(metrics, index):
            continue

        replay = metrics.iloc[: index + 1].copy()
        trend = TrendAnalyzer().analyze(replay)
        engine = EvidenceEngine()
        result = engine.collect(
            metrics=replay,
            trend=trend,
            structural_swings=tuple(trend.structure.structural_swings),
        )
        heavy_rebuilds += 1

        target = [
            e for e in result.evidence
            if e.code is TARGET_CODE
            and getattr(e, "bar_index", None) == index
        ]
        if len(target) != 1:
            continue

        emitted_weight = float(getattr(target[0], "weight", np.nan))
        ctx = engine._ctx
        if ctx is None:
            continue
        runtime_weight = WeightCalculator.calculate(TARGET_CODE, ctx)
        events.append((index, emitted_weight, runtime_weight))

    return events, heavy_rebuilds


def main() -> None:
    registry_weight = float(EVIDENCE_REGISTRY[TARGET_CODE].weight)
    all_events: list[tuple[str, int, float, float]] = []
    cheap_candidates = 0
    heavy_rebuilds = 0
    failures: list[dict[str, str]] = []

    for symbol in SYMBOLS:
        try:
            metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
            cheap_candidates += sum(
                _cheap_candidate(metrics, i)
                for i in range(1, len(metrics))
            )
            events, rebuilds = _collect_target_events(metrics)
            heavy_rebuilds += rebuilds
            all_events.extend((symbol, i, emitted, runtime) for i, emitted, runtime in events)
        except Exception as exc:
            failures.append({"symbol": symbol, "error": str(exc)})

    print("INCREASING SUPPLY WEIGHT SENSITIVITY AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": len(SYMBOLS) - len(failures),
        "cheap_candidates": cheap_candidates,
        "candidate_events": len(all_events),
        "expected_events": EXPECTED_EVENTS,
        "registry_weight": registry_weight,
        "runtime_weight_observed": {
            "min": min((x[3] for x in all_events), default=0.0),
            "max": max((x[3] for x in all_events), default=0.0),
            "mean": float(np.mean([x[3] for x in all_events])) if all_events else 0.0,
        },
        "emitted_weight_observed": {
            "min": min((x[2] for x in all_events), default=0.0),
            "max": max((x[2] for x in all_events), default=0.0),
            "mean": float(np.mean([x[2] for x in all_events])) if all_events else 0.0,
        },
        "weights_tested": WEIGHTS_TESTED,
        "production_path_mutation": False,
        "heavy_context_rebuilds": heavy_rebuilds,
        "failures": failures,
        "status": "PASS" if not failures and len(all_events) == EXPECTED_EVENTS else "FAIL",
    })

    for weight in WEIGHTS_TESTED:
        score_mass = len(all_events) * weight
        relative = weight / registry_weight if registry_weight else 0.0
        print({
            "weight": weight,
            "candidate_score_mass": score_mass,
            "relative_to_registry_weight": relative,
            "events_affected": len(all_events),
        })


if __name__ == "__main__":
    main()
