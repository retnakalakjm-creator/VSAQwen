from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from engine.columns import (
    COL_CLOSE,
    COL_HIGH,
    COL_LOW,
    COL_OPEN,
    COL_VOLUME,
    COL_WEEK,
)
from historical_scanner import HistoricalScannerRunner
from metrics_engine import MetricsEngine
from scanner import ScannerCandidate, ScannerEngine


def _metrics(size: int = 64) -> pd.DataFrame:
    anchors = [100.0, 109.0, 101.5, 112.0, 104.0, 116.0, 108.0, 119.0]
    points: list[float] = []
    segment_size = max(4, size // (len(anchors) - 1))
    for start, end in zip(anchors[:-1], anchors[1:]):
        points.extend(np.linspace(start, end, segment_size, endpoint=False))
    if len(points) < size:
        points.extend(np.linspace(anchors[-1], anchors[-1] + 2.0, size - len(points)))

    close = np.asarray(points[:size], dtype=float)
    spread = np.full(size, 1.25)
    return MetricsEngine().calculate(
        pd.DataFrame(
            {
                COL_WEEK: [
                    value.strftime("%Y-%m-%d")
                    for value in pd.date_range("2025-01-06", periods=size, freq="W-MON")
                ],
                COL_OPEN: close - 0.25,
                COL_HIGH: close + spread / 2,
                COL_LOW: close - spread / 2,
                COL_CLOSE: close,
                COL_VOLUME: np.full(size, 1_000.0),
            }
        )
    )


def _evidence_signature(items) -> tuple[tuple[object, int, str], ...]:
    return tuple(
        (item.code, item.bar_index, item.week_beginning)
        for item in items
    )


def _candidate_signature(candidate: ScannerCandidate) -> tuple[object, ...]:
    return (
        candidate.qualification,
        candidate.actionable,
        candidate.reason,
        candidate.scoring_bar_index,
        candidate.scoring_evidence_age,
        candidate.used_fallback_evidence,
        candidate.signal_bar_index,
        candidate.signal_week,
        candidate.execution_bar_index,
        candidate.execution_week,
        candidate.execution_available,
        round(candidate.ranking_score, 10),
        round(candidate.net_strength, 10),
        round(candidate.net_pressure, 10),
        round(candidate.confidence, 10),
        _evidence_signature(candidate.target_bar_evidence),
        _evidence_signature(candidate.qualifying_evidence),
        _evidence_signature(candidate.scoring_evidence),
        candidate.effort_result_evidence_codes,
        candidate.absorption_evidence_codes,
    )


def _candidate_list_signature(candidates: list[ScannerCandidate]) -> tuple[tuple[object, ...], ...]:
    return tuple(_candidate_signature(candidate) for candidate in candidates)


def test_historical_runner_scan_to_index_matches_current_scanner() -> None:
    metrics = _metrics()
    target_index = len(metrics) - 1

    candidate = HistoricalScannerRunner().scan_to_index(metrics, target_index)
    expected = ScannerEngine().scan_to_index(metrics, target_index)

    assert _candidate_signature(candidate) == _candidate_signature(expected)


def test_historical_runner_scan_matches_current_scanner_sequence() -> None:
    metrics = _metrics()

    candidates = HistoricalScannerRunner().scan(metrics)
    expected = ScannerEngine().scan(metrics)

    assert _candidate_list_signature(candidates) == _candidate_list_signature(expected)
    assert len(candidates) == len(metrics) - ScannerEngine.MIN_REPLAY_BARS


def test_historical_runner_scan_actionable_matches_current_scanner() -> None:
    metrics = _metrics()

    candidates = HistoricalScannerRunner().scan_actionable(metrics)
    expected = ScannerEngine().scan_actionable(metrics)

    assert _candidate_list_signature(candidates) == _candidate_list_signature(expected)


def test_historical_runner_returns_empty_before_minimum_replay_bars() -> None:
    metrics = _metrics().iloc[: ScannerEngine.MIN_REPLAY_BARS].copy()

    assert HistoricalScannerRunner().scan(metrics) == []
    assert HistoricalScannerRunner().scan_actionable(metrics) == []


def test_historical_runner_is_only_wired_to_production_full_replay_boundary() -> None:
    production_source = Path("production_scanner.py").read_text(encoding="utf-8")

    assert "from historical_scanner import HistoricalScannerRunner" in production_source
    assert "def _full_replay_candidate" in production_source
    assert "HistoricalScannerRunner().scan_to_index(metrics, target_index)" in production_source
    assert "from scanner_transition import" not in production_source
    assert "ScannerTransitionEngine(" not in production_source
