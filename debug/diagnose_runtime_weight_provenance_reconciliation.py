"""Reconcile empirical weights with the actual runtime weighting architecture.

Analysis-only. Reports registry/profile weights separately from runtime
WeightCalculator outputs for calibrated evidence codes. No production mutation.
"""
from __future__ import annotations

import os
import sys
from collections import Counter

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from data import daily_to_weekly, download_data
from evidence.engine import EvidenceEngine
from evidence.profiles import EVIDENCE_REGISTRY
from evidence.weight import WeightCalculator
from metrics_engine import MetricsEngine
from models import EvidenceCode
from trend import TrendAnalyzer

SYMBOLS = (
    "BHARTIARTL.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "LT.NS", "RELIANCE.NS", "SBIN.NS", "TCS.NS",
)
FORWARD_BARS = 8
TARGETS = tuple(EvidenceCode)


def main() -> None:
    stats: dict[EvidenceCode, dict[str, object]] = {
        code: {
            "registry_weight": (
                None
                if EVIDENCE_REGISTRY.get(code) is None
                else float(EVIDENCE_REGISTRY[code].weight)
            ),
            "runtime": [],
        }
        for code in TARGETS
    }

    failures: list[dict[str, str]] = []
    symbols_with_results = 0
    rebuilds = 0

    for symbol in SYMBOLS:
        try:
            metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))

            for index in range(1, len(metrics) - FORWARD_BARS):
                replay = metrics.iloc[: index + 1].copy()
                trend = TrendAnalyzer().analyze(replay)
                structural_swings = tuple(trend.structure.structural_swings)

                engine = EvidenceEngine()
                engine._reset(
                    metrics=replay,
                    trend=trend,
                    structural_swings=structural_swings,
                )
                rebuilds += 1
                assert engine._ctx is not None

                result = engine.collect(
                    metrics=replay,
                    trend=trend,
                    structural_swings=structural_swings,
                )

                for item in result.evidence:
                    code = item.code
                    if code not in stats or getattr(item, "bar_index", None) != index:
                        continue

                    runtime = float(WeightCalculator.calculate(code, engine._ctx))
                    stats[code]["runtime"].append(runtime)

            symbols_with_results += 1

        except Exception as exc:
            failures.append({"symbol": symbol, "error": str(exc)})

    print("RUNTIME WEIGHT PROVENANCE RECONCILIATION AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": symbols_with_results,
        "engine_replays": rebuilds,
        "production_mutation": False,
        "failures": failures,
        "status": "PASS" if not failures else "FAIL",
    })

    for code in TARGETS:
        registry_weight = stats[code]["registry_weight"]
        values = stats[code]["runtime"]

        if not values:
            continue

        counts = Counter(round(float(v), 12) for v in values)
        print({
            "code": code.name,
            "registry_weight": registry_weight,
            "runtime_emissions": len(values),
            "runtime_min": float(np.min(values)),
            "runtime_max": float(np.max(values)),
            "runtime_mean": float(np.mean(values)),
            "runtime_unique": tuple(sorted(counts)),
            "runtime_weight_counts": dict(counts),
            "runtime_dynamic": len(counts) > 1,
            "registry_matches_runtime_always": (
                registry_weight is not None
                and all(
                    abs(float(v) - float(registry_weight)) < 1e-12
                    for v in values
                )
            ),
        })


if __name__ == "__main__":
    main()
