from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from engine.columns import (
    COL_CLOSE,
    COL_DIRECTION,
    COL_SPREAD_CLASS,
    COL_VOLUME_CLASS,
    COL_WEEK,
)
from evidence.demand import _collect_selling_climax
from evidence.engine import EvidenceEngine
from metrics_engine import MetricsEngine
from model import EvidenceResult
from models import Direction, SpreadClass, VolumeClass
from professional.scoring_engine import ProfessionalScoringEngine
from trend import TrendAnalyzer
import config

DEFAULT_SYMBOLS = (
    "BHARTIARTL.NS",
    "RELIANCE.NS",
    "HDFCBANK.NS",
    "ICICIBANK.NS",
    "INFY.NS",
    "TCS.NS",
    "SBIN.NS",
    "LT.NS",
)

MIN_REPLAY_BARS = 20
FORWARD_HORIZON = 8
CANDIDATE_WEIGHTS = (0.25, 0.4, 0.6, 0.75, 0.85, 1.0, 1.2, 1.4)


def forward_return(metrics, index: int) -> float | None:
    future = index + FORWARD_HORIZON
    if future >= len(metrics):
        return None
    current = float(metrics.iloc[index][COL_CLOSE])
    future_close = float(metrics.iloc[future][COL_CLOSE])
    if current == 0.0:
        return None
    return (future_close / current) - 1.0


def classify_return(value: float | None) -> str:
    if value is None:
        return "UNAVAILABLE"
    if value > 0.02:
        return "POSITIVE_8_BAR"
    if value < -0.02:
        return "NEGATIVE_8_BAR"
    return "FLAT_8_BAR"


def contribution_at(metrics, index: int) -> dict | None:
    replay = metrics.iloc[: index + 1]
    trend = TrendAnalyzer().analyze(replay)
    structural_swings = tuple(trend.structure.structural_swings)

    engine = EvidenceEngine()
    production = engine.collect(
        metrics=replay,
        trend=trend,
        structural_swings=structural_swings,
        validation_metrics=metrics,
    )

    assert engine._ctx is not None
    selling_climax = tuple(_collect_selling_climax(engine._ctx))
    if not selling_climax:
        return None

    baseline = EvidenceResult(
        context=production.context,
        evidence=production.evidence,
    )
    scorer = ProfessionalScoringEngine()
    scored = scorer.calculate(trend, baseline)

    ret8 = forward_return(metrics, index)

    return {
        "bar_index": index,
        "week": str(metrics.iloc[index][COL_WEEK]),
        "forward_return_8": ret8,
        "outcome": classify_return(ret8),
        "runtime_weights": [item.weight for item in selling_climax],
        "strength": [item.strength for item in selling_climax],
        "quality": [item.quality for item in selling_climax],
        "baseline": {
            "trend": scored.scores.trend,
            "supply": scored.scores.supply,
            "demand": scored.scores.demand,
            "effort": scored.scores.effort,
            "strength": scored.scores.strength,
            "weakness": scored.scores.weakness,
            "net_pressure": scored.scores.net_pressure,
            "net_strength": scored.scores.net_strength,
            "confidence": scored.scores.confidence,
        },
        "symbol": None,
    }


def apply_candidate(base: dict, candidate_weight: float) -> dict:
    demand = min(1.0, base["demand"] + candidate_weight)
    supply = base["supply"]
    trend = base["trend"]
    effort = base["effort"]

    demand_advantage = max(demand - supply, 0.0)
    strength = min(
        1.0,
        max(
            0.0,
            config.STRENGTH_TREND_WEIGHT * trend
            + config.STRENGTH_DEMAND_WEIGHT * demand_advantage
            + config.STRENGTH_EFFORT_WEIGHT * effort,
        ),
    )

    supply_advantage = max(supply - demand, 0.0)
    weakness = min(
        1.0,
        max(
            0.0,
            config.WEAKNESS_TREND_WEIGHT * (1.0 - trend)
            + config.WEAKNESS_SUPPLY_WEIGHT * supply_advantage
            + config.WEAKNESS_EFFORT_WEIGHT * (1.0 - effort),
        ),
    )

    confidence = min(
        1.0,
        max(
            0.0,
            trend * config.PROFESSIONAL_CONFIDENCE_TREND_WEIGHT
            + abs(demand - supply)
            * config.PROFESSIONAL_CONFIDENCE_AGREEMENT_WEIGHT
            + effort * config.PROFESSIONAL_CONFIDENCE_EFFORT_WEIGHT,
        ),
    )

    return {
        "demand": demand,
        "strength": strength,
        "weakness": weakness,
        "net_pressure": demand - supply,
        "net_strength": strength - weakness,
        "confidence": confidence,
    }


def inspect_symbol(symbol: str) -> list[dict]:
    daily = download_data(symbol)
    metrics = MetricsEngine().calculate(daily_to_weekly(daily))
    events: list[dict] = []

    for index in range(MIN_REPLAY_BARS, len(metrics) - FORWARD_HORIZON):
        row = metrics.iloc[index]
        if not (
            Direction(row[COL_DIRECTION]) == Direction.DOWN
            and VolumeClass(row[COL_VOLUME_CLASS]) >= VolumeClass.VERY_HIGH
            and SpreadClass(row[COL_SPREAD_CLASS]) >= SpreadClass.ABOVE_AVERAGE
        ):
            continue

        result = contribution_at(metrics, index)
        if result is not None:
            result["symbol"] = symbol
            events.append(result)

    return events


def main() -> None:
    symbols = tuple(sys.argv[1:]) or DEFAULT_SYMBOLS
    all_events: list[dict] = []
    failures: list[dict] = []

    print("=" * 72)
    print("SELLING CLIMAX WEIGHT CALIBRATION AUDIT (OPTIMIZED)")
    print("=" * 72)
    print({"symbols": symbols, "candidate_weights": CANDIDATE_WEIGHTS})

    with ThreadPoolExecutor(max_workers=min(4, len(symbols))) as executor:
        futures = {executor.submit(inspect_symbol, symbol): symbol for symbol in symbols}
        for future, symbol in futures.items():
            try:
                events = future.result()
                all_events.extend(events)
                print({
                    "symbol": symbol,
                    "events": len(events),
                    "bars": [item["bar_index"] for item in events],
                })
            except Exception as exc:
                failures.append({"symbol": symbol, "error": repr(exc)})
                print({"symbol": symbol, "error": repr(exc)})

    print("\nSELLING CLIMAX WEIGHT CALIBRATION SUMMARY")
    for candidate in CANDIDATE_WEIGHTS:
        rows = []
        for event in all_events:
            scored = apply_candidate(event["baseline"], candidate)
            rows.append((event["outcome"], scored, event))

        positive = [r for r in rows if r[0] == "POSITIVE_8_BAR"]
        negative = [r for r in rows if r[0] == "NEGATIVE_8_BAR"]
        flat = [r for r in rows if r[0] == "FLAT_8_BAR"]

        def avg(group, field):
            return sum(item[1][field] - item[2]["baseline"][field] for item in group) / len(group) if group else 0.0

        def avg_score(group, field):
            return sum(item[1][field] for item in group) / len(group) if group else 0.0

        print({
            "candidate_weight": candidate,
            "events": len(rows),
            "positive_events": len(positive),
            "negative_events": len(negative),
            "flat_events": len(flat),
            "avg_demand_delta": avg(rows, "demand"),
            "avg_strength_delta": avg(rows, "strength"),
            "avg_weakness_delta": avg(rows, "weakness"),
            "avg_net_pressure_delta": avg(rows, "net_pressure"),
            "avg_net_strength_delta": avg(rows, "net_strength"),
            "avg_confidence_delta": avg(rows, "confidence"),
            "positive_avg_net_strength": avg_score(positive, "net_strength"),
            "negative_avg_net_strength": avg_score(negative, "net_strength"),
            "positive_avg_net_pressure": avg_score(positive, "net_pressure"),
            "negative_avg_net_pressure": avg_score(negative, "net_pressure"),
        })

    print("\nSELLING CLIMAX WEIGHT IMPACT BY OUTCOME")
    for candidate in CANDIDATE_WEIGHTS:
        by_outcome = {}
        for outcome in ("POSITIVE_8_BAR", "NEGATIVE_8_BAR", "FLAT_8_BAR"):
            group = [event for event in all_events if event["outcome"] == outcome]
            if not group:
                continue
            scored = [apply_candidate(event["baseline"], candidate) for event in group]
            by_outcome[outcome] = {
                "events": len(group),
                "avg_demand": sum(x["demand"] for x in scored) / len(scored),
                "avg_net_pressure": sum(x["net_pressure"] for x in scored) / len(scored),
                "avg_net_strength": sum(x["net_strength"] for x in scored) / len(scored),
                "positive_net_strength_events": sum(x["net_strength"] > 0 for x in scored),
            }
        print({"candidate_weight": candidate, "by_outcome": by_outcome})

    print("\nSELLING CLIMAX CALIBRATION META")
    print({
        "symbols_requested": len(symbols),
        "symbols_with_events": len({item["symbol"] for item in all_events}),
        "events": len(all_events),
        "failed_symbols": failures,
        "configured_production_weight": 0.0,
    })


if __name__ == "__main__":
    main()
