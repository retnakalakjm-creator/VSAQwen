from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config
from data import daily_to_weekly, download_data
from engine.columns import (
    COL_CLOSE,
    COL_CLOSE_POSITION,
    COL_DIRECTION,
    COL_SPREAD_CLASS,
    COL_VOLUME_CLASS,
    COL_WEEK,
)
from evidence.campaign import has_selling_campaign
from evidence.engine import EvidenceEngine
from evidence.rules import (
    has_strong_spread,
    is_above_average_spread,
    is_high_volume,
    is_weak_close,
    is_very_high_volume,
    makes_higher_low,
    volume_increasing,
)
from metrics_engine import MetricsEngine
from models import ClosePosition, Direction, SpreadClass, VolumeClass
from trend import TrendAnalyzer
from professional.scoring_engine import ProfessionalScoringEngine

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


def event_baseline(metrics, index: int) -> dict | None:
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
    ctx = engine._ctx
    bar = ctx.current

    required = (
        has_selling_campaign(ctx),
        bar.direction == Direction.DOWN,
        is_high_volume(bar),
        is_above_average_spread(bar),
        not is_weak_close(bar),
    )
    if not all(required):
        return None

    ret8 = forward_return(metrics, index)
    if ret8 is None:
        return None

    scored = ProfessionalScoringEngine().calculate(
        trend,
        production,
    )

    return {
        "bar_index": index,
        "week": str(metrics.iloc[index][COL_WEEK]),
        "forward_return_8": ret8,
        "outcome": classify_return(ret8),
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
            and VolumeClass(row[COL_VOLUME_CLASS]) >= VolumeClass.HIGH
            and SpreadClass(row[COL_SPREAD_CLASS]) >= SpreadClass.ABOVE_AVERAGE
            and ClosePosition(row[COL_CLOSE_POSITION]) >= ClosePosition.MIDDLE
        ):
            continue

        result = event_baseline(metrics, index)
        if result is not None:
            result["symbol"] = symbol
            events.append(result)

    return events


def main() -> None:
    symbols = tuple(sys.argv[1:]) or DEFAULT_SYMBOLS
    all_events: list[dict] = []
    failures: list[dict] = []

    print("=" * 72)
    print("STOPPING VOLUME WEIGHT CALIBRATION AUDIT (OPTIMIZED)")
    print("=" * 72)
    print({"symbols": symbols, "candidate_weights": CANDIDATE_WEIGHTS})

    with ThreadPoolExecutor(max_workers=min(4, len(symbols))) as executor:
        futures = {executor.submit(inspect_symbol, symbol): symbol for symbol in symbols}
        for future, symbol in futures.items():
            try:
                events = future.result()
                all_events.extend(events)
                print({"symbol": symbol, "events": len(events)})
            except Exception as exc:
                failures.append({"symbol": symbol, "error": repr(exc)})
                print({"symbol": symbol, "error": repr(exc)})

    print("\nSTOPPING VOLUME WEIGHT CALIBRATION SUMMARY")
    for candidate in CANDIDATE_WEIGHTS:
        rows = []
        for event in all_events:
            scored = apply_candidate(event["baseline"], candidate)
            rows.append((event["outcome"], scored, event))

        positive = [r for r in rows if r[0] == "POSITIVE_8_BAR"]
        negative = [r for r in rows if r[0] == "NEGATIVE_8_BAR"]
        flat = [r for r in rows if r[0] == "FLAT_8_BAR"]

        def avg(group, field):
            return (
                sum(item[1][field] - item[2]["baseline"][field] for item in group) / len(group)
                if group else 0.0
            )

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

    print("\nSTOPPING VOLUME WEIGHT IMPACT BY OUTCOME")
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

    print("\nSTOPPING VOLUME CALIBRATION META")
    print({
        "symbols_requested": len(symbols),
        "symbols_with_events": len({item["symbol"] for item in all_events}),
        "events": len(all_events),
        "failed_symbols": failures,
        "configured_registry_weight": float(config.STOPPING_VOLUME_WEIGHT),
        "production_collection": "DISABLED",
    })


if __name__ == "__main__":
    main()
