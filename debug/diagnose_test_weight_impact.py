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


SYMBOL = "BHARTIARTL.NS"
CANDIDATE_WEIGHTS = (0.25, 0.40, 0.60, 0.75, 0.85, 1.00)
OUTCOME_BY_BAR = {
    149: "PARTIAL_HOLD",
    152: "PARTIAL_HOLD",
    248: "STRONG_HOLD",
    942: "EARLY_AREA_FAILURE",
    1084: "EARLY_AREA_FAILURE",
}


def score_with_test_weight(trend, evidence, weight: float):
    without_test = tuple(
        item for item in evidence.evidence
        if str(item.code).lower() != "test"
    )
    test_items = tuple(
        item for item in evidence.evidence
        if str(item.code).lower() == "test"
    )

    scorer = ProfessionalScoringEngine()
    base = scorer.calculate(
        trend,
        EvidenceResult(context=evidence.context, evidence=without_test),
    )

    demand = min(
        base.scores.demand + (weight * len(test_items)),
        1.0,
    )
    supply = base.scores.supply
    effort = base.scores.effort
    trend_score = base.scores.trend

    strength = scorer._score_strength(trend_score, demand, supply, effort)
    weakness = scorer._score_weakness(trend_score, demand, supply, effort)
    confidence = scorer._measure_confidence(
        type(base.scores)(
            trend=trend_score,
            supply=supply,
            demand=demand,
            effort=effort,
            strength=strength,
            weakness=weakness,
            confidence=0.0,
        )
    )

    net_pressure = demand - supply
    net_strength = strength - weakness

    return {
        "demand": demand,
        "strength": strength,
        "weakness": weakness,
        "confidence": confidence,
        "net_pressure": net_pressure,
        "net_strength": net_strength,
    }


def main() -> None:
    daily = download_data(SYMBOL)
    metrics = MetricsEngine().calculate(daily_to_weekly(daily))

    cases = []
    for index, outcome in OUTCOME_BY_BAR.items():
        replay = metrics.iloc[: index + 1].copy()
        trend = TrendAnalyzer().analyze(replay)
        structural_swings = tuple(trend.structure.structural_swings)
        evidence = EvidenceEngine().collect(
            metrics=replay,
            trend=trend,
            structural_swings=structural_swings,
            validation_metrics=metrics,
        )
        if any(str(item.code).lower() == "test" for item in evidence.evidence):
            cases.append((index, outcome, trend, evidence))

    print("=" * 72)
    print("TEST WEIGHT IMPACT / OUTCOME ALIGNMENT AUDIT")
    print("=" * 72)
    print({"symbol": SYMBOL, "events": len(cases), "bars": [x[0] for x in cases]})

    for weight in CANDIDATE_WEIGHTS:
        rows = []
        for index, outcome, trend, evidence in cases:
            score = score_with_test_weight(trend, evidence, weight)
            rows.append({
                "bar_index": index,
                "outcome": outcome,
                "net_pressure": score["net_pressure"],
                "net_strength": score["net_strength"],
                "confidence": score["confidence"],
                "bullish_pressure": score["net_pressure"] > 0.0,
                "positive_strength": score["net_strength"] > 0.0,
            })

        partial = [r for r in rows if r["outcome"] == "PARTIAL_HOLD"]
        strong = [r for r in rows if r["outcome"] == "STRONG_HOLD"]
        failure = [r for r in rows if r["outcome"] == "EARLY_AREA_FAILURE"]

        def avg(items, key):
            return sum(r[key] for r in items) / len(items) if items else 0.0

        hold = partial + strong
        print({
            "candidate_weight": weight,
            "hold_avg_net_pressure": avg(hold, "net_pressure"),
            "failure_avg_net_pressure": avg(failure, "net_pressure"),
            "hold_positive_pressure": sum(r["bullish_pressure"] for r in hold),
            "failure_positive_pressure": sum(r["bullish_pressure"] for r in failure),
            "hold_positive_strength": sum(r["positive_strength"] for r in hold),
            "failure_positive_strength": sum(r["positive_strength"] for r in failure),
            "bars_positive_pressure": [r["bar_index"] for r in rows if r["bullish_pressure"]],
        })

    print("\nTEST WEIGHT IMPACT DETAIL")
    for weight in CANDIDATE_WEIGHTS:
        print(f"weight={weight}")
        for index, outcome, trend, evidence in cases:
            score = score_with_test_weight(trend, evidence, weight)
            print({
                "bar_index": index,
                "outcome": outcome,
                "net_pressure": score["net_pressure"],
                "net_strength": score["net_strength"],
                "confidence": score["confidence"],
            })


if __name__ == "__main__":
    main()
