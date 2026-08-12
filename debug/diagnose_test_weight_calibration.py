from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config
from data import daily_to_weekly, download_data
from evidence.engine import EvidenceEngine
from metrics_engine import MetricsEngine
from model import EvidenceResult, ProfessionalScore
from professional.scoring_engine import ProfessionalScoringEngine
from trend import TrendAnalyzer


SYMBOL = "BHARTIARTL.NS"
TEST_BARS = (149, 152, 248, 942, 1084)
CANDIDATE_WEIGHTS = (0.25, 0.40, 0.60, 0.75, 0.85, 1.00)


def score_with_test_weight(
    trend,
    evidence,
    test_weight: float,
):
    scorer = ProfessionalScoringEngine()
    test_items = tuple(
        item for item in evidence.evidence
        if str(item.code).lower() == "test"
    )
    other_items = tuple(
        item for item in evidence.evidence
        if str(item.code).lower() != "test"
    )

    base = scorer.calculate(
        trend,
        EvidenceResult(context=evidence.context, evidence=other_items),
    )
    base_score = base.scores

    if not test_items:
        return base_score

    demand = min(base_score.demand + test_weight, 1.0)
    strength = scorer._score_strength(
        base_score.trend,
        demand,
        base_score.supply,
        base_score.effort,
    )
    weakness = scorer._score_weakness(
        base_score.trend,
        demand,
        base_score.supply,
        base_score.effort,
    )
    confidence = scorer._measure_confidence(
        ProfessionalScore(
            trend=base_score.trend,
            supply=base_score.supply,
            demand=demand,
            effort=base_score.effort,
            strength=strength,
            weakness=weakness,
            confidence=0.0,
        )
    )

    return ProfessionalScore(
        trend=base_score.trend,
        supply=base_score.supply,
        demand=demand,
        effort=base_score.effort,
        strength=strength,
        weakness=weakness,
        confidence=confidence,
    )


def main() -> None:
    daily = download_data(SYMBOL)
    metrics = MetricsEngine().calculate(daily_to_weekly(daily))

    rows: list[dict] = []
    for index in TEST_BARS:
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
        if not test_items:
            continue

        zero = score_with_test_weight(trend, evidence, 0.0)
        for weight in CANDIDATE_WEIGHTS:
            score = score_with_test_weight(trend, evidence, weight)
            rows.append(
                {
                    "bar_index": index,
                    "week": str(metrics.iloc[index].name),
                    "candidate_weight": weight,
                    "base_demand_without_test": zero.demand,
                    "demand_with_test": score.demand,
                    "demand_delta": score.demand - zero.demand,
                    "strength_delta": score.strength - zero.strength,
                    "weakness_delta": score.weakness - zero.weakness,
                    "net_pressure": score.net_pressure,
                    "net_strength": score.net_strength,
                    "confidence_delta": score.confidence - zero.confidence,
                }
            )

    print("=" * 72)
    print("TEST WEIGHT CALIBRATION AUDIT")
    print("=" * 72)
    print({"symbol": SYMBOL, "events": len(TEST_BARS), "candidate_weights": CANDIDATE_WEIGHTS})

    for row in rows:
        print(row)

    print("\nTEST WEIGHT CALIBRATION SUMMARY")
    for weight in CANDIDATE_WEIGHTS:
        subset = [r for r in rows if r["candidate_weight"] == weight]
        print(
            {
                "candidate_weight": weight,
                "avg_demand_delta": sum(r["demand_delta"] for r in subset) / len(subset),
                "avg_strength_delta": sum(r["strength_delta"] for r in subset) / len(subset),
                "avg_weakness_delta": sum(r["weakness_delta"] for r in subset) / len(subset),
                "avg_confidence_delta": sum(r["confidence_delta"] for r in subset) / len(subset),
                "min_net_strength": min(r["net_strength"] for r in subset),
                "max_net_strength": max(r["net_strength"] for r in subset),
            }
        )


if __name__ == "__main__":
    main()
