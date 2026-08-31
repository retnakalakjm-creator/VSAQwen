from __future__ import annotations

import sys
from pathlib import Path
from statistics import median
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evidence.engine import EvidenceEngine
from evidence.fast_context import create_context_fast
from market_structure.progression import determine_structural_pattern
from market_structure.vsa_context import build_vsa_context
from metrics_engine import MetricsEngine
from trend import TrendAnalyzer
from tests.test_incremental_trend import _bars

ROUNDS = 200


def _legacy_context(engine: EvidenceEngine):
    recent = engine._recent
    bars = tuple(
        engine._create_bar_context(
            recent.iloc[i],
            int(recent.index[i]),
        )
        for i in range(len(recent))
    )
    current = bars[-1]
    previous = bars[-2] if len(bars) >= 2 else None
    return bars, current, previous


def main() -> None:
    metrics = MetricsEngine().calculate(_bars())
    trend = TrendAnalyzer().analyze(metrics)

    engine = EvidenceEngine()
    engine._reset(
        metrics=metrics,
        trend=trend,
        structural_swings=tuple(trend.structure.structural_swings),
        validation_metrics=metrics,
    )

    baseline = _legacy_context(engine)
    fast = create_context_fast(engine)
    assert tuple(_legacy_context(engine)[0]) == tuple(fast.bars)
    assert baseline[1] == fast.current
    assert baseline[2] == fast.previous

    legacy_times = []
    for _ in range(ROUNDS):
        start = perf_counter()
        _legacy_context(engine)
        legacy_times.append(perf_counter() - start)

    fast_times = []
    for _ in range(ROUNDS):
        start = perf_counter()
        create_context_fast(engine)
        fast_times.append(perf_counter() - start)

    legacy_median = median(legacy_times)
    fast_median = median(fast_times)
    speedup = legacy_median / fast_median if fast_median else float("inf")

    print(f"legacy median: {legacy_median:.9f}s")
    print(f"fast median:   {fast_median:.9f}s")
    print(f"speedup:       {speedup:.2f}x")


if __name__ == "__main__":
    main()
