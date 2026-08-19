"""Fast production-path audit for INCREASING_DEMAND."""
from __future__ import annotations

import inspect
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from evidence.demand import _collect_increasing_demand, collect_demand
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


def _semantic_sweep(metrics):
    probe_engine = EvidenceEngine()
    hits = 0
    weights = []

    for index in range(20, len(metrics)):
        current = probe_engine._create_bar_context(metrics.iloc[index], index)
        previous = probe_engine._create_bar_context(metrics.iloc[index - 1], index - 1)
        ctx = SimpleNamespace(current=current, previous=previous)
        evidence = []
        _collect_increasing_demand(ctx, evidence)
        target = [item for item in evidence if item.code == TARGET]
        hits += len(target)
        weights.extend(item.weight for item in target)

    return hits, sorted(set(weights))


def _production_probe(metrics, indices):
    hits = 0
    weights = []
    for index in indices:
        replay = metrics.iloc[: index + 1]
        trend = TrendAnalyzer().analyze(replay)
        engine = EvidenceEngine()
        result = engine.collect(
            metrics=replay,
            trend=trend,
            structural_swings=tuple(trend.structure.structural_swings),
            validation_metrics=replay,
        )
        target = [item for item in result.evidence if item.code == TARGET]
        hits += len(target)
        weights.extend(item.weight for item in target)
    return hits, sorted(set(weights))


def main() -> None:
    demand_source = inspect.getsource(collect_demand)
    registry = EVIDENCE_LIBRARY.get(TARGET)
    failures = []
    production_hits = 0
    weights = []
    probe_hits = 0
    probe_weights = []
    by_symbol = {}

    for symbol in SYMBOLS:
        try:
            metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
            hits, symbol_weights = _semantic_sweep(metrics)
            length = len(metrics)
            probe_indices = sorted(set((max(20, length // 3), max(20, (2 * length) // 3), length - 1)))
            symbol_probe_hits, symbol_probe_weights = _production_probe(metrics, probe_indices)
            production_hits += hits
            weights.extend(symbol_weights)
            probe_hits += symbol_probe_hits
            probe_weights.extend(symbol_probe_weights)
            by_symbol[symbol] = {
                "production_hits": hits,
                "weights": symbol_weights,
                "engine_probe_hits": symbol_probe_hits,
                "engine_probe_weights": symbol_probe_weights,
            }
        except Exception as exc:
            failures.append({"symbol": symbol, "error": repr(exc)})

    collector_contains_target = (
        "_collect_increasing_demand" in demand_source
        and "EvidenceCode.INCREASING_DEMAND" in demand_source
    )
    observed_weights = sorted(set(weights))
    observed_probe_weights = sorted(set(probe_weights))
    status = (
        "PASS"
        if not failures
        and collector_contains_target
        and production_hits > 0
        and observed_weights == [EXPECTED_WEIGHT]
        and observed_probe_weights in ([], [EXPECTED_WEIGHT])
        else "FAIL"
    )

    print("INCREASING DEMAND PRODUCTION PATH FAST OPTIMIZED AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": len(by_symbol),
        "production_hits": production_hits,
        "collector_contains_target": collector_contains_target,
        "registry_present": registry is not None,
        "registry_weight": None if registry is None else registry.weight,
        "registry_strength": None if registry is None else registry.strength,
        "observed_weights": observed_weights,
        "engine_probe_hits": probe_hits,
        "engine_probe_weights": observed_probe_weights,
        "failures": failures,
        "status": status,
    })
    print("INCREASING DEMAND PRODUCTION PATH BY_SYMBOL")
    for symbol, info in by_symbol.items():
        print({"symbol": symbol, **info})


if __name__ == "__main__":
    main()
