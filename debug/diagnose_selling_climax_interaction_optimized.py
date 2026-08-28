"""Analysis-only interaction/contradiction audit for SELLING_CLIMAX."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from engine.columns import (
    COL_CLOSE,
    COL_CLOSE_POSITION,
    COL_DIRECTION,
    COL_PREV_CLOSE,
    COL_SPREAD_CLASS,
    COL_VOLUME_CLASS,
)
from evidence.campaign import has_selling_campaign
from evidence.engine import EvidenceEngine
from evidence.evidence_registry import build_evidence
from evidence.rules import has_strong_spread, is_strong_close, volume_increasing
from metrics_engine import MetricsEngine
from models import EvidenceCode, SpreadClass, VolumeClass
import config

SYMBOLS = (
    "BHARTIARTL.NS", "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "INFY.NS", "TCS.NS", "SBIN.NS", "LT.NS",
)
FORWARD_BARS = 8
BACKGROUND_WINDOW = config.BACKGROUND_LOOKBACK
SUPPLY_CONFLICT_CODES = {
    EvidenceCode.SUPPLY_COMING_IN: "SUPPLY_COMING_IN_LIKE",
    EvidenceCode.INCREASING_SUPPLY: "INCREASING_SUPPLY_LIKE",
    EvidenceCode.HIDDEN_SUPPLY: "HIDDEN_SUPPLY_LIKE",
    EvidenceCode.UPTHRUST: "UPTHRUST_LIKE",
    EvidenceCode.NO_DEMAND: "NO_DEMAND_LIKE",
    EvidenceCode.BUYING_CLIMAX: "BUYING_CLIMAX_LIKE",
}
DEMAND_INTERACTION_CODES = {
    EvidenceCode.STOPPING_VOLUME: "STOPPING_VOLUME_LIKE",
    EvidenceCode.SHAKEOUT: "SHAKEOUT_LIKE",
    EvidenceCode.SPRING: "SPRING_LIKE",
    EvidenceCode.TEST: "TEST_LIKE",
    EvidenceCode.DEMAND_COMING_IN: "DEMAND_COMING_IN_LIKE",
    EvidenceCode.INCREASING_DEMAND: "INCREASING_DEMAND_LIKE",
}


def _cheap_campaign_score(metrics, index: int) -> int:
    start = max(0, index - BACKGROUND_WINDOW + 1)
    window = metrics.iloc[start:index + 1]

    down_ok = int(
        (window[COL_DIRECTION].to_numpy(dtype=int) == -1).sum()
    ) >= config.CAMPAIGN_MIN_DOWN_BARS

    lower_ok = int(
        (
            window[COL_CLOSE].to_numpy(dtype=float)
            < window[COL_PREV_CLOSE].to_numpy(dtype=float)
        ).sum()
    ) >= config.CAMPAIGN_MIN_LOWER_CLOSES

    weak_ok = int(
        (window[COL_CLOSE_POSITION].to_numpy(dtype=int) <= 1).sum()
    ) >= config.CAMPAIGN_MIN_WEAK_CLOSES

    return int(down_ok) + int(lower_ok) + int(weak_ok)


def _selling_climax_cheap_gate(bar) -> bool:
    return (
        int(bar[COL_DIRECTION]) == -1
        and VolumeClass(int(bar[COL_VOLUME_CLASS])) >= VolumeClass.VERY_HIGH
        and SpreadClass(int(bar[COL_SPREAD_CLASS])) >= SpreadClass.ABOVE_AVERAGE
    )


def _same_bar_code_names(engine: EvidenceEngine, index: int) -> tuple[set[str], set[str]]:
    assert engine._ctx is not None

    engine._evidence.clear()
    engine._collect_supply()
    engine._collect_demand()
    engine._collect_spring()

    supply_names: set[str] = set()
    demand_names: set[str] = set()

    for item in engine._evidence:
        if item.bar_index != index:
            continue
        code = item.code
        if code in SUPPLY_CONFLICT_CODES:
            supply_names.add(SUPPLY_CONFLICT_CODES[code])
        if code in DEMAND_INTERACTION_CODES:
            demand_names.add(DEMAND_INTERACTION_CODES[code])

    return supply_names, demand_names


def _audit_symbol(symbol: str) -> dict:
    metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))

    out = {
        "symbol": symbol,
        "cheap_candidates": 0,
        "heavy_context_rebuilds": 0,
        "events": 0,
        "events_with_supply_conflict": 0,
        "supply_conflicts": {},
        "demand_interactions": {},
        "supply_union_events": 0,
        "demand_union_events": 0,
    }

    for index in range(21, len(metrics) - FORWARD_BARS):
        bar = metrics.iloc[index]
        if not _selling_climax_cheap_gate(bar):
            continue

        out["cheap_candidates"] += 1
        if _cheap_campaign_score(metrics, index) < 2:
            continue

        replay = metrics.iloc[:index + 1]
        from trend import TrendAnalyzer
        trend = TrendAnalyzer().analyze(replay)
        engine = EvidenceEngine()
        engine._reset(
            metrics=replay,
            trend=trend,
            structural_swings=tuple(trend.structure.structural_swings),
            validation_metrics=replay,
        )
        out["heavy_context_rebuilds"] += 1

        ctx = engine._ctx
        if ctx is None or ctx.previous is None or not has_selling_campaign(ctx):
            continue

        out["events"] += 1
        supply_names, demand_names = _same_bar_code_names(engine, index)

        if supply_names:
            out["events_with_supply_conflict"] += 1
            out["supply_union_events"] += 1
        if demand_names:
            out["demand_union_events"] += 1

        for name in supply_names:
            out["supply_conflicts"][name] = out["supply_conflicts"].get(name, 0) + 1
        for name in demand_names:
            out["demand_interactions"][name] = out["demand_interactions"].get(name, 0) + 1

    return out


def main() -> None:
    failures = []
    results = []
    with ThreadPoolExecutor(max_workers=min(4, len(SYMBOLS))) as executor:
        futures = {executor.submit(_audit_symbol, symbol): symbol for symbol in SYMBOLS}
        for future, symbol in futures.items():
            try:
                results.append(future.result())
            except Exception as exc:
                failures.append({"symbol": symbol, "error": repr(exc)})

    events = sum(x["events"] for x in results)
    conflict_events = sum(x["supply_union_events"] for x in results)
    demand_events = sum(x["demand_union_events"] for x in results)
    supply = {}
    demand = {}
    for item in results:
        for key, value in item["supply_conflicts"].items():
            supply[key] = supply.get(key, 0) + value
        for key, value in item["demand_interactions"].items():
            demand[key] = demand.get(key, 0) + value

    print("SELLING CLIMAX INTERACTION / CONTRADICTION AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": len(results),
        "events": events,
        "events_with_supply_conflict": conflict_events,
        "supply_conflict_rate": conflict_events / events if events else 0.0,
        "aggregate_supply_conflicts": supply,
        "demand_interaction_events": demand_events,
        "aggregate_demand_interactions": demand,
        "heavy_context_rebuilds": sum(x["heavy_context_rebuilds"] for x in results),
        "failures": failures,
        "status": "PASS" if not failures else "FAIL",
    })

    print("SELLING CLIMAX INTERACTION / CONTRADICTION BY_SYMBOL")
    for item in sorted(results, key=lambda x: x["symbol"]):
        print({
            "symbol": item["symbol"],
            "events": item["events"],
            "events_with_supply_conflict": item["events_with_supply_conflict"],
            "conflicts": item["supply_conflicts"],
            "demand_interactions": item["demand_interactions"],
        })


if __name__ == "__main__":
    main()
