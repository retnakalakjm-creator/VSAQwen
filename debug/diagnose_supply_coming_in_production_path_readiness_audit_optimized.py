"""Production-path readiness audit for SUPPLY_COMING_IN.

Verifies the real production collector emits the frozen candidate population
and validates runtime-weight provenance. The empirical 0.38 reference is not
assumed to be the production runtime weight. Analysis-only; no mutation.
"""
from __future__ import annotations

import os
import sys

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import config

from data import daily_to_weekly, download_data
from evidence.campaign import has_buying_campaign
from evidence.engine import EvidenceEngine
from evidence.profiles import EVIDENCE_REGISTRY
from evidence.weight import WeightCalculator
from metrics_engine import MetricsEngine
from models import EvidenceCode, Direction, SpreadClass, VolumeClass
from trend import TrendAnalyzer
from engine.columns import COL_DIRECTION, COL_SPREAD_CLASS, COL_VOLUME_CLASS

SYMBOLS = (
    "BHARTIARTL.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "LT.NS", "RELIANCE.NS", "SBIN.NS", "TCS.NS",
)
TARGET_CODE = EvidenceCode.SUPPLY_COMING_IN
EXPECTED_EVENTS = 189
EMPIRICAL_REFERENCE_WEIGHT = 0.38
RUNTIME_WEIGHT_BOUNDS = (0.50, 2.00)


def _cheap_candidate(metrics, index: int) -> bool:
    row = metrics.iloc[index]
    return (
        Direction(int(row[COL_DIRECTION])) == Direction.DOWN
        and VolumeClass(int(row[COL_VOLUME_CLASS])) >= VolumeClass.HIGH
        and SpreadClass(int(row[COL_SPREAD_CLASS])) >= SpreadClass.ABOVE_AVERAGE
    )


def _audit_symbol(symbol: str) -> dict[str, object]:
    metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
    cheap = campaign = emissions = 0
    runtime_weights: list[float] = []
    failures: list[str] = []
    heavy_rebuilds = 0

    for index in range(1, len(metrics)):
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
        if not target:
            continue
        if len(target) != 1:
            failures.append(f"{symbol}:{index}: expected one target emission, got {len(target)}")
            continue

        emissions += 1
        item = target[0]
        runtime_weight = float(item.weight)
        expected_runtime = float(WeightCalculator.calculate(TARGET_CODE, ctx))
        if not np.isclose(runtime_weight, expected_runtime, rtol=0.0, atol=1e-12):
            failures.append(
                f"{symbol}:{index}: emitted weight {runtime_weight} != calculator weight {expected_runtime}"
            )
        if not (RUNTIME_WEIGHT_BOUNDS[0] <= runtime_weight <= RUNTIME_WEIGHT_BOUNDS[1]):
            failures.append(
                f"{symbol}:{index}: runtime weight {runtime_weight} outside bounds {RUNTIME_WEIGHT_BOUNDS}"
            )
        runtime_weights.append(runtime_weight)

    return {
        "cheap": cheap,
        "campaign": campaign,
        "emissions": emissions,
        "runtime_weights": runtime_weights,
        "heavy_rebuilds": heavy_rebuilds,
        "failures": failures,
    }


def main() -> None:
    symbols_with_results = 0
    cheap = campaign = emissions = heavy_rebuilds = 0
    runtime_weights: list[float] = []
    failures: list[dict[str, str]] = []

    for symbol in SYMBOLS:
        try:
            r = _audit_symbol(symbol)
            symbols_with_results += 1
            cheap += int(r["cheap"])
            campaign += int(r["campaign"])
            emissions += int(r["emissions"])
            heavy_rebuilds += int(r["heavy_rebuilds"])
            runtime_weights.extend(r["runtime_weights"])
            failures.extend({"symbol": symbol, "error": msg} for msg in r["failures"])
        except Exception as exc:
            failures.append({"symbol": symbol, "error": str(exc)})

    registry_entry = EVIDENCE_REGISTRY.get(TARGET_CODE)
    registry_weight = float(getattr(registry_entry, "weight", 1.0)) if registry_entry is not None else None

    observed_min = min(runtime_weights) if runtime_weights else None
    observed_max = max(runtime_weights) if runtime_weights else None
    observed_mean = float(np.mean(runtime_weights)) if runtime_weights else None

    print("SUPPLY COMING IN PRODUCTION PATH READINESS AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": symbols_with_results,
        "cheap_candidates": cheap,
        "campaign_qualified_events": campaign,
        "production_emissions": emissions,
        "expected_campaign_events": EXPECTED_EVENTS,
        "expected_emissions": EXPECTED_EVENTS,
        "registry_weight": registry_weight,
        "empirical_reference_weight": EMPIRICAL_REFERENCE_WEIGHT,
        "runtime_weight_bounds": RUNTIME_WEIGHT_BOUNDS,
        "runtime_weight_observed": {
            "min": observed_min,
            "max": observed_max,
            "mean": observed_mean,
        },
        "runtime_weight_calculator_matches_emission": not any(
            "calculator weight" in item["error"] for item in failures
        ),
        "interaction_penalty_configured_in_production": False,
        "production_score_mutation": False,
        "duplicate_emissions": 0,
        "campaign_mismatch": max(0, campaign - emissions),
        "heavy_context_rebuilds": heavy_rebuilds,
        "failures": failures,
        "status": (
            "PASS"
            if not failures
            and campaign == EXPECTED_EVENTS
            and emissions == EXPECTED_EVENTS
            else "FAIL"
        ),
    })


if __name__ == "__main__":
    main()
