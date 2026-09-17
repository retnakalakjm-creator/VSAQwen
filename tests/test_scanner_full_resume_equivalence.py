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
from scanner import ScannerCandidate, ScannerEngine
from scanner_transition import BarEvaluation, ScanState, ScannerTransitionEngine
from scanner_transition_resume import ScannerTransitionResumeAdapter
from scanner_transition_snapshot import ScannerTransitionSnapshotAdapter


SYMBOL = "TEST"
TIMEFRAME = "1wk"


def _metrics(size: int = 120) -> pd.DataFrame:
    """Deterministic history with enough reversals to exercise swing state."""

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


def _evidence_signature(items) -> tuple[tuple[object, ...], ...]:
    return tuple(
        (
            item.code,
            item.category,
            item.direction,
            item.bar_index,
            str(item.week_beginning),
            item.strength,
            item.weight,
            item.quality,
        )
        for item in items
    )


def _candidate_signature(candidate: ScannerCandidate) -> tuple[object, ...]:
    return (
        candidate.qualification,
        candidate.qualification_result.is_actionable_evidence,
        candidate.reason,
        candidate.actionable,
        candidate.professional.confidence,
        candidate.professional.scores.net_strength,
        candidate.professional.scores.net_pressure,
        _evidence_signature(candidate.target_bar_evidence),
        _evidence_signature(candidate.campaign_evidence),
        _evidence_signature(candidate.qualifying_evidence),
        _evidence_signature(candidate.scoring_evidence),
        candidate.scoring_bar_index,
        candidate.scoring_evidence_age,
        candidate.used_fallback_evidence,
        candidate.bar_index,
        candidate.week,
        candidate.execution_bar_index,
        candidate.execution_week,
        candidate.execution_available,
        candidate.execution_pending,
        candidate.signal_bar_anomaly,
        candidate.signal_bar_anomaly_reason,
        candidate.ranking_score,
    )


def _trend_signature(evaluation: BarEvaluation) -> tuple[object, ...]:
    structure = evaluation.trend.structure
    return (
        structure.direction,
        structure.state,
        structure.strength,
        structure.confidence,
        structure.swing_count,
        tuple(repr(item) for item in structure.structural_swings),
    )


def _structural_state_signature(state: ScanState) -> tuple[tuple[object, ...], ...]:
    return tuple(
        (
            item.bar_key,
            item.code,
            item.category,
            item.direction,
            item.strength,
            item.weight,
            item.quality,
        )
        for item in state.structural_events
    )


def _checkpoint_indices(
    full_state: ScanState,
    metrics: pd.DataFrame,
    target_index: int,
) -> tuple[int, ...]:
    """Cover early/middle/late checkpoints and a structural boundary when present."""

    minimum = ScannerEngine.MIN_REPLAY_BARS
    checkpoints = {
        minimum,
        minimum + (target_index - minimum) // 2,
        target_index - 1,
    }
    index_by_week = {
        str(value): index for index, value in enumerate(metrics[COL_WEEK])
    }
    structural_indices = sorted(
        {
            index_by_week[item.bar_key]
            for item in full_state.structural_events
            if item.bar_key in index_by_week
            and minimum + 1 < index_by_week[item.bar_key] < target_index - 1
        }
    )
    if structural_indices:
        boundary = structural_indices[len(structural_indices) // 2]
        checkpoints.update({boundary - 1, boundary, boundary + 1})

    return tuple(sorted(index for index in checkpoints if minimum <= index < target_index))


def test_full_and_resumed_transition_paths_are_semantically_equivalent() -> None:
    metrics = _metrics()
    target_index = len(metrics) - 1
    transition = ScannerTransitionEngine()
    snapshot = ScannerTransitionSnapshotAdapter(transition)
    resume = ScannerTransitionResumeAdapter(transition)

    full_state, full_evaluation = transition.run_to_index(metrics, target_index)
    full_snapshot = snapshot.snapshot_from_transition_state(
        metrics,
        target_index=target_index,
        symbol=SYMBOL,
        timeframe=TIMEFRAME,
        transition_state=full_state,
    )

    for checkpoint_index in _checkpoint_indices(full_state, metrics, target_index):
        checkpoint_transition_state, _ = transition.run_to_index(
            metrics,
            checkpoint_index,
        )
        checkpoint_state = snapshot.snapshot_from_transition_state(
            metrics,
            target_index=checkpoint_index,
            symbol=SYMBOL,
            timeframe=TIMEFRAME,
            transition_state=checkpoint_transition_state,
        )
        resumed_start = resume.transition_state_from_scanner_state(
            metrics,
            checkpoint_state,
        )
        resumed_state, resumed_evaluation = transition.run_to_index(
            metrics,
            target_index,
            state=resumed_start,
        )
        resumed_snapshot = snapshot.snapshot_from_transition_state(
            metrics,
            target_index=target_index,
            symbol=SYMBOL,
            timeframe=TIMEFRAME,
            transition_state=resumed_state,
        )

        message = f"checkpoint_index={checkpoint_index}"
        assert _candidate_signature(resumed_evaluation.candidate) == _candidate_signature(
            full_evaluation.candidate
        ), message
        assert _trend_signature(resumed_evaluation) == _trend_signature(
            full_evaluation
        ), message
        assert _evidence_signature(resumed_evaluation.evidence.evidence) == _evidence_signature(
            full_evaluation.evidence.evidence
        ), message
        assert _structural_state_signature(resumed_state) == _structural_state_signature(
            full_state
        ), message
        assert resumed_state.qualification == full_state.qualification, message
        assert resumed_state.last_bar_index == full_state.last_bar_index, message
        assert resumed_snapshot.to_dict() == full_snapshot.to_dict(), message
