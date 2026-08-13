from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from engine.columns import COL_DIRECTION, COL_SPREAD_CLASS, COL_VOLUME_CLASS, COL_WEEK
from evidence.demand import _collect_selling_climax
from evidence.engine import EvidenceEngine
from metrics_engine import MetricsEngine
from model import EvidenceResult
from models import Direction, SpreadClass, VolumeClass
from professional.scoring_engine import ProfessionalScoringEngine
from trend import TrendAnalyzer
import config

DEFAULT_SYMBOLS = (
    "BHARTIARTL.NS", "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "INFY.NS", "TCS.NS", "SBIN.NS", "LT.NS",
)
MIN_REPLAY_BARS = 20


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

    scorer = ProfessionalScoringEngine()
    full = scorer.calculate(
        trend,
        EvidenceResult(
            context=production.context,
            evidence=tuple(production.evidence) + selling_climax,
        ),
    )
    reduced = scorer.calculate(trend, production)

    return {
        "bar_index": index,
        "week": str(metrics.iloc[index][COL_WEEK]),
        "selling_climax": [
            {
                "code": str(item.code),
                "strength": item.strength,
                "weight": item.weight,
                "quality": item.quality,
                "configured_weight": config.SUPPLY_EVIDENCE_WEIGHTS.get(item.code, 0.0)
                if "SUPPLY" in item.category.name
                else config.DEMAND_EVIDENCE_WEIGHTS.get(item.code, 0.0),
            }
            for item in selling_climax
        ],
        "delta": {
            "supply": full.scores.supply - reduced.scores.supply,
            "demand": full.scores.demand - reduced.scores.demand,
            "strength": full.scores.strength - reduced.scores.strength,
            "weakness": full.scores.weakness - reduced.scores.weakness,
            "net_pressure": full.scores.net_pressure - reduced.scores.net_pressure,
            "net_strength": full.scores.net_strength - reduced.scores.net_strength,
            "confidence": full.scores.confidence - reduced.scores.confidence,
        },
    }


def inspect_symbol(symbol: str) -> list[dict]:
    daily = download_data(symbol)
    metrics = MetricsEngine().calculate(daily_to_weekly(daily))
    events: list[dict] = []

    for index in range(MIN_REPLAY_BARS, len(metrics)):
        row = metrics.iloc[index]

        # Safe semantic pre-filter matching SELLING_CLIMAX atomic requirements.
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
    print("SELLING CLIMAX PROFESSIONAL-SCORE CONTRIBUTION AUDIT (OPTIMIZED)")
    print("=" * 72)
    print({"symbols": symbols})

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

    print("\nSELLING CLIMAX CONTRIBUTION SUMMARY")
    print({
        "symbols_requested": len(symbols),
        "symbols_with_events": len({item["symbol"] for item in all_events}),
        "events": len(all_events),
        "failed_symbols": failures,
        "avg_supply_delta": sum(x["delta"]["supply"] for x in all_events) / len(all_events) if all_events else 0.0,
        "avg_demand_delta": sum(x["delta"]["demand"] for x in all_events) / len(all_events) if all_events else 0.0,
        "avg_strength_delta": sum(x["delta"]["strength"] for x in all_events) / len(all_events) if all_events else 0.0,
        "avg_weakness_delta": sum(x["delta"]["weakness"] for x in all_events) / len(all_events) if all_events else 0.0,
        "avg_net_pressure_delta": sum(x["delta"]["net_pressure"] for x in all_events) / len(all_events) if all_events else 0.0,
        "avg_net_strength_delta": sum(x["delta"]["net_strength"] for x in all_events) / len(all_events) if all_events else 0.0,
        "avg_confidence_delta": sum(x["delta"]["confidence"] for x in all_events) / len(all_events) if all_events else 0.0,
    })

    print("\nSELLING CLIMAX CONTRIBUTION EVENTS")
    for item in all_events:
        print(item)


if __name__ == "__main__":
    main()
