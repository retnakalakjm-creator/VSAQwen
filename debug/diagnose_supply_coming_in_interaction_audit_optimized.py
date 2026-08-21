"""Interaction / contradiction audit for SUPPLY_COMING_IN.

Analysis-only. Reconstructs point-in-time production evidence for the exact
SUPPLY_COMING_IN candidate population and examines same-bar interactions.
Self-conflict is excluded.
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from data import daily_to_weekly, download_data
from engine.columns import COL_DIRECTION, COL_SPREAD_CLASS, COL_VOLUME_CLASS
from evidence.campaign import has_buying_campaign
from evidence.engine import EvidenceEngine
from metrics_engine import MetricsEngine
from models import Direction, EvidenceCode, SpreadClass, VolumeClass
from trend import TrendAnalyzer

SYMBOLS = (
    "BHARTIARTL.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "LT.NS", "RELIANCE.NS", "SBIN.NS", "TCS.NS",
)
TARGET = EvidenceCode.SUPPLY_COMING_IN
SUPPLY_CODES = {
    EvidenceCode.SUPPLY_COMING_IN,
    EvidenceCode.INCREASING_SUPPLY,
    EvidenceCode.HIDDEN_SUPPLY,
    EvidenceCode.SUPPLY_DRYING_UP,
    EvidenceCode.UPTHRUST,
    EvidenceCode.NO_DEMAND,
    EvidenceCode.BUYING_CLIMAX,
}
DEMAND_CODES = {
    EvidenceCode.STOPPING_VOLUME,
    EvidenceCode.SHAKEOUT,
    EvidenceCode.NO_SUPPLY,
    EvidenceCode.TEST,
    EvidenceCode.DEMAND_COMING_IN,
    EvidenceCode.INCREASING_DEMAND,
    EvidenceCode.HIDDEN_DEMAND,
    EvidenceCode.DEMAND_DRYING_UP,
}
EXPECTED_EVENTS = 189


def _cheap_candidate(metrics, index: int) -> bool:
    row = metrics.iloc[index]
    return (
        Direction(int(row[COL_DIRECTION])) == Direction.DOWN
        and VolumeClass(int(row[COL_VOLUME_CLASS])) >= VolumeClass.HIGH
        and SpreadClass(int(row[COL_SPREAD_CLASS])) >= SpreadClass.ABOVE_AVERAGE
    )


def main() -> None:
    symbols_with_results = 0
    cheap_candidates = 0
    campaign_qualified = 0
    events = 0
    supply_conflict_events = 0
    demand_interaction_events = 0
    aggregate_supply = {code.name: 0 for code in SUPPLY_CODES if code is not TARGET}
    aggregate_demand = {code.name: 0 for code in DEMAND_CODES}
    self_conflict_excluded = True
    heavy_rebuilds = 0
    failures: list[dict[str, str]] = []

    for symbol in SYMBOLS:
        try:
            metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
            for index in range(1, len(metrics)):
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
                ctx = engine._ctx
                assert ctx is not None
                heavy_rebuilds += 1

                if not has_buying_campaign(ctx):
                    continue
                campaign_qualified += 1

                target_items = [
                    e for e in result.evidence
                    if e.code is TARGET
                    and getattr(e, "bar_index", None) == index
                ]
                if len(target_items) != 1:
                    continue
                events += 1

                same_bar = [
                    e for e in result.evidence
                    if getattr(e, "bar_index", None) == index
                ]
                supply_hits = [
                    e for e in same_bar
                    if e.code in SUPPLY_CODES and e.code is not TARGET
                ]
                demand_hits = [e for e in same_bar if e.code in DEMAND_CODES]

                if supply_hits:
                    supply_conflict_events += 1
                    for e in supply_hits:
                        aggregate_supply[e.code.name] = aggregate_supply.get(e.code.name, 0) + 1
                if demand_hits:
                    demand_interaction_events += 1
                    for e in demand_hits:
                        aggregate_demand[e.code.name] = aggregate_demand.get(e.code.name, 0) + 1
        except Exception as exc:
            failures.append({"symbol": symbol, "error": str(exc)})
        else:
            symbols_with_results += 1

    print("SUPPLY COMING IN INTERACTION / CONTRADICTION AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": symbols_with_results,
        "cheap_candidates": cheap_candidates,
        "campaign_qualified_events": campaign_qualified,
        "events": events,
        "events_with_supply_conflict": supply_conflict_events,
        "supply_conflict_rate": supply_conflict_events / events if events else 0.0,
        "aggregate_supply_conflicts": aggregate_supply,
        "demand_interaction_events": demand_interaction_events,
        "aggregate_demand_interactions": aggregate_demand,
        "self_conflict_excluded": self_conflict_excluded,
        "target_bar_only": True,
        "heavy_context_rebuilds": heavy_rebuilds,
        "expected_events": EXPECTED_EVENTS,
        "failures": failures,
        "status": "PASS" if not failures and events == EXPECTED_EVENTS else "FAIL",
    })


if __name__ == "__main__":
    main()
