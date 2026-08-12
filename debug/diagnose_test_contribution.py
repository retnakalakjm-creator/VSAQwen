from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from evidence.engine import EvidenceEngine
from metrics_engine import MetricsEngine
from model import EvidenceResult
from professional.scoring_engine import ProfessionalScoringEngine
from trend import TrendAnalyzer
import config


SYMBOL = "BHARTIARTL.NS"


def contribution_at(metrics, index: int) -> dict:
    replay = metrics.iloc[: index + 1].copy()
    trend = TrendAnalyzer().analyze(replay)
    structural_swings = tuple(trend.structure.structural_swings)
    evidence = EvidenceEngine().collect(
        metrics=replay,
        trend=trend,
        structural_swings=structural_swings,
        validation_metrics=metrics,
    )

    test_items = tuple(
        item for item in evidence.evidence
        if str(item.code).lower() == "test"
    )
    without_test = tuple(
        item for item in evidence.evidence
        if str(item.code).lower() != "test"
    )

    scorer = ProfessionalScoringEngine()
    full = scorer.calculate(trend, evidence)
    reduced = scorer.calculate(
        trend,
        EvidenceResult(
            context=evidence.context,
            evidence=without_test,
        ),
    )

    return {
        "bar_index": index,
        "test_count": len(test_items),
        "test": [
            {
                "code": str(item.code),
                "strength": item.strength,
                "weight": item.weight,
                "quality": item.quality,
                "configured_weight": (
                    config.SUPPLY_EVIDENCE_WEIGHTS.get(item.code, 0.0)
                    if "SUPPLY" in item.category.name
                    else config.DEMAND_EVIDENCE_WEIGHTS.get(item.code, 0.0)
                ),
                "direction": str(item.direction),
            }
            for item in test_items
        ],
        "full": {
            "trend": full.scores.trend,
            "supply": full.scores.supply,
            "demand": full.scores.demand,
            "effort": full.scores.effort,
            "strength": full.scores.strength,
            "weakness": full.scores.weakness,
            "net_pressure": full.scores.net_pressure,
            "net_strength": full.scores.net_strength,
            "confidence": full.scores.confidence,
        },
        "without_test": {
            "trend": reduced.scores.trend,
            "supply": reduced.scores.supply,
            "demand": reduced.scores.demand,
            "effort": reduced.scores.effort,
            "strength": reduced.scores.strength,
            "weakness": reduced.scores.weakness,
            "net_pressure": reduced.scores.net_pressure,
            "net_strength": reduced.scores.net_strength,
            "confidence": reduced.scores.confidence,
        },
        "delta": {
            "demand": full.scores.demand - reduced.scores.demand,
            "strength": full.scores.strength - reduced.scores.strength,
            "weakness": full.scores.weakness - reduced.scores.weakness,
            "net_pressure": full.scores.net_pressure - reduced.scores.net_pressure,
            "net_strength": full.scores.net_strength - reduced.scores.net_strength,
            "confidence": full.scores.confidence - reduced.scores.confidence,
        },
        "all_evidence": [str(item.code) for item in evidence.evidence],
    }


def main() -> None:
    daily = download_data(SYMBOL)
    metrics = MetricsEngine().calculate(daily_to_weekly(daily))

    replay = []
    for index in range(20, len(metrics)):
        result = contribution_at(metrics, index)
        if result["test_count"]:
            replay.append(result)

    print("=" * 72)
    print("TEST PROFESSIONAL-SCORE CONTRIBUTION AUDIT")
    print("=" * 72)
    print({"symbol": SYMBOL, "test_events": len(replay), "bars": [x["bar_index"] for x in replay]})

    for item in replay:
        print(item)

    print("\nTEST CONTRIBUTION SUMMARY")
    print({
        "events": len(replay),
        "avg_demand_delta": sum(x["delta"]["demand"] for x in replay) / len(replay) if replay else 0.0,
        "avg_strength_delta": sum(x["delta"]["strength"] for x in replay) / len(replay) if replay else 0.0,
        "avg_net_pressure_delta": sum(x["delta"]["net_pressure"] for x in replay) / len(replay) if replay else 0.0,
        "avg_net_strength_delta": sum(x["delta"]["net_strength"] for x in replay) / len(replay) if replay else 0.0,
        "avg_confidence_delta": sum(x["delta"]["confidence"] for x in replay) / len(replay) if replay else 0.0,
    })


if __name__ == "__main__":
    main()
