from __future__ import annotations

import sys
from pathlib import Path
from statistics import median
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evidence.engine import EvidenceEngine
from metrics_engine import MetricsEngine
from trend import TrendAnalyzer
from tests.test_incremental_trend import _bars

ROUNDS = 200


def _setup() -> tuple[EvidenceEngine, object]:
    metrics = MetricsEngine().calculate(_bars())
    trend = TrendAnalyzer().analyze(metrics)
    engine = EvidenceEngine()
    engine._reset(
        metrics=metrics,
        trend=trend,
        structural_swings=tuple(trend.structure.structural_swings),
    )
    return engine, trend


def _time_call(fn) -> float:
    start = perf_counter()
    fn()
    return perf_counter() - start


def main() -> None:
    engine, _ = _setup()

    # Warm-up and parity sanity: each isolated collector must succeed
    # and leave evidence attached to the engine.
    for fn in (engine._create_context, engine._collect_demand, engine._collect_spring):
        fn()

    stage_times: dict[str, list[float]] = {
        "context": [],
        "demand": [],
        "spring": [],
    }

    for _ in range(ROUNDS):
        stage_times["context"].append(_time_call(engine._create_context))
        stage_times["demand"].append(_time_call(engine._collect_demand))
        stage_times["spring"].append(_time_call(engine._collect_spring))

    medians = {name: median(times) for name, times in stage_times.items()}
    total = sum(medians.values())

    print(f"context median: {medians['context']:.9f}s")
    print(f"demand median:  {medians['demand']:.9f}s")
    print(f"spring median:  {medians['spring']:.9f}s")
    print(f"sum medians:    {total:.9f}s")

    for name, value in medians.items():
        share = (value / total * 100.0) if total else 0.0
        print(f"{name:16s}: {share:6.2f}%")


if __name__ == "__main__":
    main()
