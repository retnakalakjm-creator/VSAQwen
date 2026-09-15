from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from engine.columns import (
    COL_CLOSE,
    COL_HIGH,
    COL_LOW,
    COL_OPEN,
    COL_VOLUME,
    COL_WEEK,
)
from metrics_engine import MetricsEngine
from scanner import ScannerCandidate, ScannerEngine
from scanner_transition import ScanState, ScannerTransitionEngine


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


def test_transition_run_to_index_matches_full_scanner_candidate() -> None:
    metrics = _metrics()
    target_index = len(metrics) - 1

    _, evaluation = ScannerTransitionEngine().run_to_index(metrics, target_index)
    expected = ScannerEngine().scan_to_index(metrics, target_index)

    assert _candidate_signature(evaluation.candidate) == _candidate_signature(expected)
    assert evaluation.bar.index == target_index
    assert evaluation.bar.week == expected.week


def test_transition_sequence_matches_full_scanner_at_checkpoints() -> None:
    metrics = _metrics()
    transition = ScannerTransitionEngine()
    state = ScanState()
    checkpoints = {
        ScannerEngine.MIN_REPLAY_BARS,
        ScannerEngine.MIN_REPLAY_BARS + 7,
        len(metrics) - 1,
    }

    for index in range(ScannerEngine.MIN_REPLAY_BARS, len(metrics)):
        state, evaluation = transition.step(
            state,
            transition.bar_for(metrics, index),
            transition.features_for(metrics, index),
            metrics=metrics,
        )
        if index in checkpoints:
            expected = ScannerEngine().scan_to_index(metrics, index)
            assert _candidate_signature(evaluation.candidate) == _candidate_signature(expected)

    assert state.last_bar_index == len(metrics) - 1
    assert len(state.history) == len(metrics) - ScannerEngine.MIN_REPLAY_BARS


def test_transition_rejects_non_sequential_steps() -> None:
    metrics = _metrics()
    transition = ScannerTransitionEngine()
    first_index = ScannerEngine.MIN_REPLAY_BARS
    state, _ = transition.step(
        ScanState(),
        transition.bar_for(metrics, first_index),
        transition.features_for(metrics, first_index),
        metrics=metrics,
    )

    with pytest.raises(ValueError, match="sequential"):
        transition.step(
            state,
            transition.bar_for(metrics, first_index + 2),
            transition.features_for(metrics, first_index + 2),
            metrics=metrics,
        )


def test_transition_history_keeps_only_structural_evidence() -> None:
    metrics = _metrics()
    state, _ = ScannerTransitionEngine().run_to_index(metrics, len(metrics) - 1)

    for historical_result in state.history:
        assert all(
            item.code in ScannerEngine._STRUCTURAL_CODES
            for item in historical_result.evidence
        )


def test_transition_contract_is_not_wired_into_production_scanner_yet() -> None:
    production_source = Path("production_scanner.py").read_text(encoding="utf-8")

    assert "scanner_transition" not in production_source
    assert "ScannerTransitionEngine" not in production_source
