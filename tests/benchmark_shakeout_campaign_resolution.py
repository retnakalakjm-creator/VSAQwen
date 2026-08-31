from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from statistics import median
from time import perf_counter

from evidence.campaign import has_selling_campaign
from evidence.demand import _candidate_campaign_snapshot
from evidence.engine import EvidenceEngine
from metrics_engine import MetricsEngine
from trend import TrendAnalyzer

from tests.test_incremental_trend import _bars

ROUNDS = 100


def _candidate_indices(size: int) -> list[int]:
    lookback = 21
    return list(range(max(1, size - lookback), size))


def _legacy_campaign(ctx, validation_metrics, candidate_index: int) -> bool:
    """Frozen representation of the pre-optimization SHAKEOUT campaign path."""
    candidate_replay = validation_metrics.iloc[: candidate_index + 1].copy()
    candidate_trend = TrendAnalyzer().analyze(candidate_replay)

    candidate_engine = EvidenceEngine()
    candidate_engine._reset(
        metrics=candidate_replay,
        trend=candidate_trend,
        structural_swings=tuple(candidate_trend.structure.structural_swings),
        validation_metrics=candidate_replay,
    )
    candidate_ctx = candidate_engine._ctx
    if candidate_ctx is None or candidate_ctx.previous is None:
        return False

    return has_selling_campaign(candidate_ctx)


def main() -> None:
    metrics = MetricsEngine().calculate(_bars())
    full_trend = TrendAnalyzer().analyze(metrics)

    engine = EvidenceEngine()
    engine._reset(
        metrics=metrics,
        trend=full_trend,
        structural_swings=tuple(full_trend.structure.structural_swings),
        validation_metrics=metrics,
    )
    ctx = engine._ctx
    assert ctx is not None

    classified_structural = TrendAnalyzer()._classify_swings(
        list(ctx.structural_swings)
    )
    candidates = _candidate_indices(len(metrics))

    legacy_expected = [
        _legacy_campaign(ctx, metrics, index)
        for index in candidates
    ]
    snapshot_expected = [
        _candidate_campaign_snapshot(
            ctx,
            metrics,
            index,
            classified_structural,
        ).has_selling_campaign()
        for index in candidates
    ]
    assert legacy_expected == snapshot_expected, (
        "legacy and snapshot campaign decisions differ",
        list(zip(candidates, legacy_expected, snapshot_expected)),
    )

    legacy_times = []
    for _ in range(ROUNDS):
        start = perf_counter()
        for index in candidates:
            _legacy_campaign(ctx, metrics, index)
        legacy_times.append(perf_counter() - start)

    snapshot_times = []
    for _ in range(ROUNDS):
        start = perf_counter()
        for index in candidates:
            _candidate_campaign_snapshot(
                ctx,
                metrics,
                index,
                classified_structural,
            ).has_selling_campaign()
        snapshot_times.append(perf_counter() - start)

    legacy_median = median(legacy_times)
    snapshot_median = median(snapshot_times)
    speedup = legacy_median / snapshot_median if snapshot_median else float("inf")

    print(f"legacy median:   {legacy_median:.9f}s")
    print(f"snapshot median: {snapshot_median:.9f}s")
    print(f"speedup:         {speedup:.2f}x")


if __name__ == "__main__":
    main()
