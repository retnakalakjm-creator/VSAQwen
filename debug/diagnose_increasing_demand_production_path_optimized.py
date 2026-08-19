"""Optimized production-path audit for INCREASING_DEMAND."""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from evidence.demand import collect_demand
from evidence.engine import EvidenceEngine
from evidence.evidence_registry import EVIDENCE_LIBRARY
from metrics_engine import MetricsEngine
from models import EvidenceCode
from trend import TrendAnalyzer

SYMBOLS = (
    "BHARTIARTL.NS", "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "INFY.NS", "TCS.NS", "SBIN.NS", "LT.NS",
)
TARGET = EvidenceCode.INCREASING_DEMAND
EXPECTED_WEIGHT = 0.85


def _collect_at(metrics, index: int):
    replay = metrics.iloc[: index + 1]
    trend = TrendAnalyzer().analyze(replay)
    engine = EvidenceEngine()
    return engine.collect(
        metrics=replay,
        trend=trend,
        structural_swings=tuple(trend.structure.structural_swings),
        validation_metrics=metrics,
    )


def main() -> None:
    demand_source = inspect.getsource(collect_demand)
    registry = EVIDENCE_LIBRARY.get(TARGET)
    failures = []
    production_hits = 0
    weights = []
    by_symbol = {}

    for symbol in SYMBOLS:
        try:
            metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
            hits = 0
            symbol_weights = []
            for index in range(20, len(metrics)):
                result = _collect_at(metrics, index)
                target = [item for item in result.evidence if item.code == TARGET]
                hits += len(target)
                symbol_weights.extend(item.weight for item in target)
            production_hits += hits
            weights.extend(symbol_weights)
            by_symbol[symbol] = {
                "production_hits": hits,
                "weights": sorted(set(symbol_weights)),
            }
        except Exception as exc:
            failures.append({"symbol": symbol, "error": repr(exc)})

    collector_contains_target = "INCREASING_DEMAND" in demand_source
    observed_weights = sorted(set(weights))
    status = (
        "PASS"
        if not failures
        and collector_contains_target
        and production_hits > 0
        and observed_weights == [EXPECTED_WEIGHT]
        else "FAIL"
    )

    print("INCREASING DEMAND PRODUCTION PATH OPTIMIZED AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": len(by_symbol),
        "production_hits": production_hits,
        "collector_contains_target": collector_contains_target,
        "registry_present": registry is not None,
        "registry_weight": None if registry is None else registry.weight,
        "registry_strength": None if registry is None else registry.strength,
        "observed_weights": observed_weights,
        "failures": failures,
        "status": status,
    })
    print("INCREASING DEMAND PRODUCTION PATH BY_SYMBOL")
    for symbol, info in by_symbol.items():
        print({"symbol": symbol, **info})


if __name__ == "__main__":
    main()
