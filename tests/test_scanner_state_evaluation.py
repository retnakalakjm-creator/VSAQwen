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
from scanner import ScannerEngine
from scanner_transition import ScannerTransitionEngine


def _metrics(size: int = 120) -> pd.DataFrame:
    points: list[float] = []
    anchors = [100.0, 108.0, 101.0, 111.0, 103.0, 115.0, 106.0]
    for start, end in zip(anchors[:-1], anchors[1:]):
        points.extend(np.linspace(start, end, 18, endpoint=False))
    points.extend(np.linspace(anchors[-1], 118.0, size - len(points)))
    close = np.asarray(points[:size], dtype=float)
    spread = np.full(size, 1.0)
    volume = np.full(size, 1_000.0)
    raw = pd.DataFrame(
        {
            COL_WEEK: [f"2025-01-{i + 1:03d}" for i in range(size)],
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


def _signature(candidate) -> tuple[object, ...]:
    return (
        candidate.qualification,
        candidate.qualification_result.is_actionable_evidence,
        candidate.reason,
        candidate.actionable,
        candidate.professional.confidence,
        candidate.professional.scores.net_strength,
        candidate.professional.scores.net_pressure,
        tuple((item.bar_index, item.code) for item in candidate.qualifying_evidence),
        tuple((item.bar_index, item.code) for item in candidate.scoring_evidence),
        candidate.scoring_bar_index,
        candidate.scoring_evidence_age,
        candidate.used_fallback_evidence,
        candidate.bar_index,
        candidate.week,
        candidate.execution_bar_index,
        candidate.execution_week,
        candidate.signal_bar_anomaly,
        candidate.ranking_score,
    )


def test_state_driven_transition_matches_legacy_scanner_at_multiple_targets() -> None:
    metrics = _metrics()
    legacy = ScannerEngine()
    transition = ScannerTransitionEngine()

    for target in (40, 60, 80, len(metrics) - 1):
        legacy_candidate = legacy.scan_to_index(metrics, target)
        state_candidate = transition.scan_to_index(metrics, target)
        assert _signature(state_candidate) == _signature(legacy_candidate), f"target={target}"
