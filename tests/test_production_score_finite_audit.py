from __future__ import annotations

import numpy as np
import pandas as pd

from engine.columns import (
    COL_AVG_SPREAD,
    COL_AVG_VOLUME,
    COL_CLOSE,
    COL_HIGH,
    COL_LOW,
    COL_OPEN,
    COL_SPREAD,
    COL_VOLUME,
    COL_WEEK,
)
from metrics_engine import MetricsEngine
from scanner import ScannerEngine, rank_candidates


def _metrics(size: int = 120) -> pd.DataFrame:
    anchors = [100.0, 108.0, 101.0, 111.0, 103.0, 115.0, 106.0]
    points: list[float] = []
    for start, end in zip(anchors[:-1], anchors[1:]):
        points.extend(np.linspace(start, end, 18, endpoint=False))
    points.extend(np.linspace(anchors[-1], 118.0, size - len(points)))

    close = np.asarray(points[:size], dtype=float)
    spread = np.full(size, 1.0)
    volume = np.full(size, 1_000.0)

    raw = pd.DataFrame(
        {
            COL_WEEK: [f"2025-01-{i + 1:02d}" for i in range(size)],
            COL_OPEN: close - 0.2,
            COL_HIGH: close + 0.5,
            COL_LOW: close - 0.5,
            COL_CLOSE: close,
            COL_VOLUME: volume,
            COL_SPREAD: spread,
            COL_AVG_VOLUME: volume,
            COL_AVG_SPREAD: spread,
        }
    )
    return MetricsEngine().calculate(raw)


def _production_candidates() -> tuple:
    metrics = _metrics()
    scanner = ScannerEngine()
    return tuple(
        scanner.scan_to_index(metrics, index)
        for index in range(scanner.MIN_REPLAY_BARS, len(metrics))
    )


def test_production_candidates_have_finite_scores() -> None:
    for candidate in _production_candidates():
        scores = candidate.professional.scores
        values = (
            scores.trend,
            scores.supply,
            scores.demand,
            scores.effort,
            scores.strength,
            scores.weakness,
            scores.confidence,
            scores.net_pressure,
            scores.net_strength,
        )
        assert all(np.isfinite(value) for value in values)


def test_production_ranking_is_monotonic_within_each_actionability_tier() -> None:
    ranked = rank_candidates(_production_candidates())

    for left, right in zip(ranked, ranked[1:]):
        if left.actionable == right.actionable:
            assert left.ranking_score >= right.ranking_score


def test_production_ranking_has_actionable_prefix() -> None:
    ranked = rank_candidates(_production_candidates())

    first_non_actionable = next(
        (index for index, candidate in enumerate(ranked) if not candidate.actionable),
        len(ranked),
    )
    assert all(candidate.actionable for candidate in ranked[:first_non_actionable])
