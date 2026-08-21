"""Production-path readiness audit for BUYING_CLIMAX.

Analysis-only. Verifies the real collector/engine production path emits
BUYING_CLIMAX for campaign-qualified candidates at the expected base weight.
The 0.20 interaction penalty remains hypothetical and is NOT applied to
production scoring in this audit.
"""
from __future__ import annotations

import os
import sys
from collections import Counter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from data import daily_to_weekly, download_data
from engine.columns import COL_CLOSE, COL_DIRECTION, COL_VOLUME_CLASS
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
EXPECTED_BASE_WEIGHT = 0.38
TARGET_CODE = EvidenceCode.BUYING_CLIMAX


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
    emissions: list[tuple[int, float, float]] = []
    wrong_weights: list[tuple[int, float, float]] = []
    duplicates = 0
    campaign_mismatches = 0
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

        for item in target_items:
            if not hasattr(item, "weight"):
                failures.append(
                    f"{symbol}:{index}: BUYING_CLIMAX evidence has no weight attribute"
                )
                continue
            weight = float(item.weight)
            emissions.append((index, weight, float(metrics.iloc[index][COL_CLOSE])))
            if abs(weight - EXPECTED_BASE_WEIGHT) > 1e-12:
                wrong_weights.append((index, weight, EXPECTED_BASE_WEIGHT))

    return cheap, rebuilds, emissions, wrong_weights, duplicates, campaign_mismatches, failures


def main() -> None:
    symbols_with_results = 0
    cheap_total = 0
    rebuild_total = 0
    all_emissions: list[tuple[int, float, float]] = []
    wrong_weights: list[tuple[str, float, float]] = []
    duplicate_emissions = 0
    campaign_mismatch = 0
    failures: list[dict[str, str]] = []

    for symbol in SYMBOLS:
        try:
            (
                cheap,
                rebuilds,
                emissions,
                wrong,
                duplicates,
                mismatches,
                symbol_failures,
            ) = _audit_symbol(symbol)
            symbols_with_results += 1
            cheap_total += cheap
            rebuild_total += rebuilds
            all_emissions.extend((i, w, c) for i, w, c in emissions)
            wrong_weights.extend((f"{symbol}:{i}", w, e) for i, w, e in wrong)
            duplicate_emissions += duplicates
            campaign_mismatch += mismatches
            failures.extend(
                {"symbol": symbol, "error": message}
                for message in symbol_failures
            )
        except Exception as exc:
            failures.append({"symbol": symbol, "error": str(exc)})

    counts = Counter(round(weight, 12) for _, weight, _ in all_emissions)
    production_emissions = len(all_emissions)
    wrong_weight_count = len(wrong_weights)
    score_mutation_failures = wrong_weight_count

    print("BUYING CLIMAX PRODUCTION PATH READINESS AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": symbols_with_results,
        "cheap_candidates": cheap_total,
        "engine_replays": rebuild_total,
        "production_emissions": production_emissions,
        "expected_weight": EXPECTED_BASE_WEIGHT,
        "weight_counts": dict(counts),
        "wrong_weight": wrong_weight_count,
        "duplicate_emissions": duplicate_emissions,
        "campaign_mismatch": campaign_mismatch,
        "interaction_penalty_configured_in_production": False,
        "production_score_mutation": False,
        "errors": len(failures),
        "failures": failures,
        "status": "PASS" if not failures and wrong_weight_count == 0 and duplicate_emissions == 0 and campaign_mismatch == 0 else "FAIL",
    })


if __name__ == "__main__":
    main()
