"""Interaction / contradiction audit for campaign-qualified BUYING_CLIMAX.

Analysis-only. Replays only cheap BUYING_CLIMAX candidates, applies the real
buying-campaign gate, then inspects the actual EvidenceEngine supply/demand
emissions on the target bar. BUYING_CLIMAX is excluded from its own conflict
set so self-conflict can never be reported.
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

SUPPLY_CONFLICT_CODES = (
    EvidenceCode.SUPPLY_COMING_IN,
    EvidenceCode.INCREASING_SUPPLY,
    EvidenceCode.HIDDEN_SUPPLY,
    EvidenceCode.UPTHRUST,
    EvidenceCode.NO_DEMAND,
    EvidenceCode.BUYING_CLIMAX,
)

DEMAND_INTERACTION_CODES = (
    EvidenceCode.STOPPING_VOLUME,
    EvidenceCode.NO_SUPPLY,
    EvidenceCode.SHAKEOUT,
    EvidenceCode.SPRING,
    EvidenceCode.TEST,
    EvidenceCode.DEMAND_COMING_IN,
    EvidenceCode.INCREASING_DEMAND,
    EvidenceCode.HIDDEN_DEMAND,
)


def _cheap_candidate(metrics, index: int) -> bool:
    row = metrics.iloc[index]
    return (
        Direction(int(row[COL_DIRECTION])) == Direction.UP
        and VolumeClass(int(row[COL_VOLUME_CLASS])) == VolumeClass.VERY_HIGH
        and SpreadClass(int(row["spread_class"])) >= SpreadClass.ABOVE_AVERAGE
    )


def _point_in_time(metrics, index: int):
    replay = metrics.iloc[: index + 1].copy()
    trend = TrendAnalyzer().analyze(replay)
    structural_swings = tuple(trend.structure.structural_swings)

    ctx_engine = EvidenceEngine()
    ctx_engine._reset(
        metrics=replay,
        trend=trend,
        structural_swings=structural_swings,
    )
    assert ctx_engine._ctx is not None

    evidence = ctx_engine.collect(
        metrics=replay,
        trend=trend,
        structural_swings=structural_swings,
    )
    return ctx_engine._ctx, evidence


def main() -> None:
    failures: list[dict[str, str]] = []
    symbols_with_results = 0
    cheap_candidates = 0
    campaign_qualified = 0
    heavy_rebuilds = 0
    conflict_events = 0
    demand_interaction_events = 0
    aggregate_supply = Counter()
    aggregate_demand = Counter()

    for symbol in SYMBOLS:
        try:
            metrics = MetricsEngine().calculate(
                daily_to_weekly(download_data(symbol))
            )
            symbols_with_results += 1

            for index in range(1, len(metrics) - FORWARD_BARS):
                if not _cheap_candidate(metrics, index):
                    continue

                cheap_candidates += 1
                ctx, result = _point_in_time(metrics, index)
                heavy_rebuilds += 1

                if not has_buying_campaign(ctx):
                    continue

                campaign_qualified += 1

                target_codes = {
                    item.code
                    for item in result.evidence
                    if item.bar_index == index
                }

                supply_codes = [
                    code for code in SUPPLY_CONFLICT_CODES
                    if code is not EvidenceCode.BUYING_CLIMAX
                    and code in target_codes
                ]
                demand_codes = [
                    code
                    for code in DEMAND_INTERACTION_CODES
                    if code in target_codes
                ]

                if supply_codes:
                    conflict_events += 1
                    for code in supply_codes:
                        aggregate_supply[str(code)] += 1

                if demand_codes:
                    demand_interaction_events += 1
                    for code in demand_codes:
                        aggregate_demand[str(code)] += 1

        except Exception as exc:
            failures.append({"symbol": symbol, "error": str(exc)})

    print("BUYING CLIMAX INTERACTION / CONTRADICTION AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": symbols_with_results,
        "cheap_candidates": cheap_candidates,
        "campaign_qualified_events": campaign_qualified,
        "events_with_supply_conflict": conflict_events,
        "supply_conflict_rate": (
            conflict_events / campaign_qualified
            if campaign_qualified else 0.0
        ),
        "aggregate_supply_conflicts": dict(aggregate_supply),
        "demand_interaction_events": demand_interaction_events,
        "aggregate_demand_interactions": dict(aggregate_demand),
        "self_conflict_excluded": True,
        "heavy_context_rebuilds": heavy_rebuilds,
        "failures": failures,
        "status": "PASS" if not failures else "FAIL",
    })


if __name__ == "__main__":
    main()
