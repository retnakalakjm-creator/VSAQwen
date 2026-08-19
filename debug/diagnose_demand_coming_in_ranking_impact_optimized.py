"""Optimized ranking-impact audit for DEMAND_COMING_IN.

Analysis-only. Compares scanner ranking with and without the target event
contribution while preserving all other evidence and scoring behavior.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from evidence.engine import EvidenceEngine
from evidence.scoring import _score_bias
from metrics_engine import MetricsEngine
from models import EvidenceCode
from trend import TrendAnalyzer

SYMBOLS = (
    "BHARTIARTL.NS", "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "INFY.NS", "TCS.NS", "SBIN.NS", "LT.NS",
)
TARGET = EvidenceCode.DEMAND_COMING_IN
WEIGHT = 0.38


def collect(symbol: str):
    metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
    trend = TrendAnalyzer().analyze(metrics)
    engine = EvidenceEngine()
    result = engine.collect(
        metrics=metrics,
        trend=trend,
        structural_swings=tuple(trend.structure.structural_swings),
        validation_metrics=metrics,
    )
    return result


def main() -> None:
    results = []
    failures = []
    for symbol in SYMBOLS:
        try:
            results.append((symbol, collect(symbol)))
        except Exception as exc:
            failures.append((symbol, str(exc)))

    changed = 0
    target_events = 0
    before_scores = []
    after_scores = []
    by_symbol = {}

    for symbol, result in results:
        evidence = list(result.evidence)
        target = [item for item in evidence if item.code == TARGET]
        target_events += len(target)

        base_bias = _score_bias(evidence)
        stripped = [item for item in evidence if item.code != TARGET]
        counterfactual_bias = _score_bias(stripped)

        if base_bias != counterfactual_bias:
            changed += 1
        before_scores.append(counterfactual_bias.name)
        after_scores.append(base_bias.name)
        by_symbol[symbol] = {
            "target_events": len(target),
            "bias_without_target": counterfactual_bias.name,
            "bias_with_target": base_bias.name,
            "bias_changed": base_bias != counterfactual_bias,
            "target_weights": sorted({item.weight for item in target}),
            "ranking_safe_weight": all(item.weight == WEIGHT for item in target),
        }

    print("DEMAND COMING IN RANKING IMPACT OPTIMIZED AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": len(results),
        "target_events": target_events,
        "bias_changes": changed,
        "bias_change_rate": changed / target_events if target_events else 0.0,
        "all_target_weights_038": all(
            info["ranking_safe_weight"] for info in by_symbol.values()
        ),
        "failures": failures,
        "status": "PASS" if not failures else "FAIL",
    })
    print("DEMAND COMING IN RANKING IMPACT BY_SYMBOL")
    for symbol, info in by_symbol.items():
        print({"symbol": symbol, **info})


if __name__ == "__main__":
    main()
