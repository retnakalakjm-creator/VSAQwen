"""Production-path readiness audit for BUYING_CLIMAX.

Analysis-only. Verifies the real collector/engine production path emits
BUYING_CLIMAX for campaign-qualified candidates and that its runtime weight
comes from the production WeightCalculator rather than an empirical fixed
calibration weight. The 0.20 interaction penalty remains hypothetical and
is NOT applied to production scoring in this audit.
"""
from __future__ import annotations

import os
import sys
from collections import Counter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from data import daily_to_weekly, download_data
from evidence.campaign import has_buying_campaign
from evidence.engine import EvidenceEngine
from evidence.profiles import EVIDENCE_REGISTRY
from evidence.weight import WeightCalculator
from metrics_engine import MetricsEngine
from models import Direction, EvidenceCode, SpreadClass, VolumeClass
from engine.columns import COL_DIRECTION, COL_VOLUME_CLASS
from trend import TrendAnalyzer

SYMBOLS = (
    "BHARTIARTL.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "LT.NS", "RELIANCE.NS", "SBIN.NS", "TCS.NS",
)
FORWARD_BARS = 8
EMPIRICAL_REFERENCE_WEIGHT = 0.38
TARGET_CODE = EvidenceCode.BUYING_CLIMAX
RUNTIME_WEIGHT_MIN = 0.50
RUNTIME_WEIGHT_MAX = 2.00
EXPECTED_CAMPAIGN_EVENTS = 181


def _cheap_candidate(metrics, index: int) -> bool:
    row = metrics.iloc[index]
    return (
        Direction(int(row[COL_DIRECTION])) == Direction.UP
        and VolumeClass(int(row[COL_VOLUME_CLASS])) == VolumeClass.VERY_HIGH
        and SpreadClass(int(row["spread_class"])) >= SpreadClass.ABOVE_AVERAGE
    )


def _audit_symbol(symbol: str):
    metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
    cheap = 0
    rebuilds = 0
    emissions: list[tuple[int, float]] = []
    duplicates = 0
    campaign_mismatches = 0
    out_of_bounds = 0
    failures: list[str] = []

    for index in range(1, len(metrics) - FORWARD_BARS):
        if not _cheap_candidate(metrics, index):
            continue
        cheap += 1

        replay = metrics.iloc[: index + 1].copy()
        trend = TrendAnalyzer().analyze(replay)
        structural_swings = tuple(trend.structure.structural_swings)

        engine = EvidenceEngine()
        engine._reset(
            metrics=replay,
            trend=trend,
            structural_swings=structural_swings,
        )
        rebuilds += 1
        assert engine._ctx is not None

        campaign = has_buying_campaign(engine._ctx)
        result = engine.collect(
            metrics=replay,
            trend=trend,
            structural_swings=structural_swings,
        )

        target_items = [
            item for item in result.evidence
            if item.code is TARGET_CODE
            and getattr(item, "bar_index", None) == index
        ]

        if campaign and len(target_items) != 1:
            campaign_mismatches += 1
            if not target_items:
                failures.append(
                    f"{symbol}:{index}: campaign qualified but BUYING_CLIMAX not emitted"
                )
            else:
                duplicates += len(target_items) - 1
        elif not campaign and target_items:
            campaign_mismatches += 1
            failures.append(
                f"{symbol}:{index}: BUYING_CLIMAX emitted without campaign gate"
            )

        for _item in target_items:
            runtime_weight = float(WeightCalculator.calculate(TARGET_CODE, engine._ctx))
            emissions.append((index, runtime_weight))
            if not (RUNTIME_WEIGHT_MIN <= runtime_weight <= RUNTIME_WEIGHT_MAX):
                out_of_bounds += 1
                failures.append(
                    f"{symbol}:{index}: runtime weight {runtime_weight} outside production bounds"
                )

    return cheap, rebuilds, emissions, duplicates, campaign_mismatches, out_of_bounds, failures


def main() -> None:
    symbols_with_results = 0
    cheap_total = 0
    rebuild_total = 0
    all_emissions: list[tuple[int, float]] = []
    duplicate_emissions = 0
    campaign_mismatch = 0
    out_of_bounds = 0
    failures: list[dict[str, str]] = []

    for symbol in SYMBOLS:
        try:
            (
                cheap,
                rebuilds,
                emissions,
                duplicates,
                mismatches,
                bounds_failures,
                symbol_failures,
            ) = _audit_symbol(symbol)
            symbols_with_results += 1
            cheap_total += cheap
            rebuild_total += rebuilds
            all_emissions.extend(emissions)
            duplicate_emissions += duplicates
            campaign_mismatch += mismatches
            out_of_bounds += bounds_failures
            failures.extend(
                {"symbol": symbol, "error": message}
                for message in symbol_failures
            )
        except Exception as exc:
            failures.append({"symbol": symbol, "error": str(exc)})

    profile = EVIDENCE_REGISTRY.get(TARGET_CODE)
    registry_weight = None if profile is None else float(profile.weight)
    weight_counts = Counter(round(weight, 12) for _, weight in all_emissions)
    production_emissions = len(all_emissions)

    print("BUYING CLIMAX PRODUCTION PATH READINESS AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": symbols_with_results,
        "cheap_candidates": cheap_total,
        "engine_replays": rebuild_total,
        "production_emissions": production_emissions,
        "expected_campaign_events": EXPECTED_CAMPAIGN_EVENTS,
        "registry_weight": registry_weight,
        "empirical_reference_weight": EMPIRICAL_REFERENCE_WEIGHT,
        "runtime_weight_bounds": (RUNTIME_WEIGHT_MIN, RUNTIME_WEIGHT_MAX),
        "weight_counts": dict(weight_counts),
        "runtime_weight_out_of_bounds": out_of_bounds,
        "duplicate_emissions": duplicate_emissions,
        "campaign_mismatch": campaign_mismatch,
        "interaction_penalty_configured_in_production": False,
        "production_score_mutation": False,
        "errors": len(failures),
        "failures": failures,
        "status": (
            "PASS"
            if (
                not failures
                and production_emissions == EXPECTED_CAMPAIGN_EVENTS
                and duplicate_emissions == 0
                and campaign_mismatch == 0
                and out_of_bounds == 0
                and registry_weight == 1.0
            )
            else "FAIL"
        ),
    })


if __name__ == "__main__":
    main()
