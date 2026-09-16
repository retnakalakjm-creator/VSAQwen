from __future__ import annotations

from dataclasses import replace

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
from scanner_transition import ScannerTransitionEngine
from scanner_transition_resume import ScannerTransitionResumeAdapter
from scanner_transition_snapshot import ScannerTransitionSnapshotAdapter


SYMBOL = "TEST"
TIMEFRAME = "1wk"


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


def _event_signature(events) -> tuple[tuple[object, ...], ...]:
    return tuple(
        (
            item.bar_key,
            item.code,
            item.direction,
            item.strength,
            item.weight,
            item.quality,
        )
        for item in events
    )


def test_transition_state_carries_same_structural_events_as_durable_snapshot() -> None:
    metrics = _metrics()
    target = len(metrics) - 1
    transition = ScannerTransitionEngine()
    snapshot = ScannerTransitionSnapshotAdapter(transition)

    state, _ = transition.run_to_index(metrics, target)
    durable = snapshot.snapshot_from_transition_state(
        metrics,
        target_index=target,
        symbol=SYMBOL,
        timeframe=TIMEFRAME,
        transition_state=state,
    )

    assert _event_signature(state.structural_events) == _event_signature(
        durable.structural_events
    )


def test_snapshot_structural_events_do_not_depend_on_legacy_history() -> None:
    metrics = _metrics()
    target = len(metrics) - 1
    transition = ScannerTransitionEngine()
    snapshot = ScannerTransitionSnapshotAdapter(transition)

    state, _ = transition.run_to_index(metrics, target)
    expected = snapshot.snapshot_from_transition_state(
        metrics,
        target_index=target,
        symbol=SYMBOL,
        timeframe=TIMEFRAME,
        transition_state=state,
    )
    without_history = snapshot.snapshot_from_transition_state(
        metrics,
        target_index=target,
        symbol=SYMBOL,
        timeframe=TIMEFRAME,
        transition_state=replace(state, history=()),
    )

    assert _event_signature(without_history.structural_events) == _event_signature(
        expected.structural_events
    )


def test_resume_restores_first_class_structural_events_from_checkpoint() -> None:
    metrics = _metrics()
    checkpoint = 72
    transition = ScannerTransitionEngine()
    snapshot = ScannerTransitionSnapshotAdapter(transition)
    resume = ScannerTransitionResumeAdapter(transition)

    checkpoint_state, _ = transition.run_to_index(metrics, checkpoint)
    durable = snapshot.snapshot_from_transition_state(
        metrics,
        target_index=checkpoint,
        symbol=SYMBOL,
        timeframe=TIMEFRAME,
        transition_state=checkpoint_state,
    )
    restored = resume.transition_state_from_scanner_state(metrics, durable)

    assert _event_signature(restored.structural_events) == _event_signature(
        durable.structural_events
    )
    assert restored.qualification == checkpoint_state.qualification
