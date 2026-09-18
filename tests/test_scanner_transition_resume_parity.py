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
from incremental_scanner import IncrementalScannerEngine
from metrics_engine import MetricsEngine
from production_transition_shadow import default_candidate_signature
from scanner import ScannerEngine
from scanner_transition_resume import ScannerTransitionResumeAdapter


def _resume_metrics(size: int = 132) -> pd.DataFrame:
    """Generic synthetic OHLCV fixture with enough swings for resume parity."""

    anchors = [
        100.0,
        113.0,
        104.0,
        119.0,
        108.0,
        125.0,
        112.0,
        130.0,
        116.0,
        136.0,
        121.0,
        141.0,
        124.0,
        134.0,
    ]
    bars_per_segment = max(6, size // (len(anchors) - 1))
    points: list[float] = []
    for start, end in zip(anchors[:-1], anchors[1:]):
        points.extend(np.linspace(start, end, bars_per_segment, endpoint=False))
    if len(points) < size:
        points.extend(np.linspace(anchors[-1], anchors[-1] + 4.0, size - len(points)))

    close = np.asarray(points[:size], dtype=float)
    delta = np.diff(close, prepend=close[0])
    open_ = close - np.where(delta >= 0.0, 0.35, -0.35)
    spread = 1.2 + (np.arange(size, dtype=float) % 6.0) * 0.12
    high = np.maximum(open_, close) + spread / 2.0
    low = np.minimum(open_, close) - spread / 2.0
    volume = (
        1_000.0
        + (np.arange(size, dtype=float) % 11.0) * 55.0
        + np.where((np.arange(size) % 17) == 0, 350.0, 0.0)
    )

    raw = pd.DataFrame(
        {
            COL_WEEK: [
                value.strftime("%Y-%m-%d")
                for value in pd.date_range("2024-01-01", periods=size, freq="W-MON")
            ],
            COL_OPEN: open_,
            COL_HIGH: high,
            COL_LOW: low,
            COL_CLOSE: close,
            COL_VOLUME: volume,
        }
    )
    return MetricsEngine().calculate(raw)


@pytest.mark.parametrize("checkpoint_index", (36, 72, 108))
def test_transition_resume_matches_incremental_resume(
    checkpoint_index: int,
) -> None:
    metrics = _resume_metrics()
    checkpoint_state = IncrementalScannerEngine().snapshot(
        metrics,
        target_index=checkpoint_index,
        symbol="RESUME-PARITY",
        timeframe="1wk",
    )

    incremental = IncrementalScannerEngine().resume_latest(metrics, checkpoint_state)
    transition = ScannerTransitionResumeAdapter().resume_latest(metrics, checkpoint_state)
    full_transition = ScannerTransitionResumeAdapter().resume_latest_with_metadata(
        metrics,
        checkpoint_state,
    )

    assert default_candidate_signature(transition) == default_candidate_signature(
        incremental
    )
    assert full_transition.checkpoint_index == checkpoint_index
    assert full_transition.target_index == len(metrics) - 1
    assert full_transition.resumed_bar_count == len(metrics) - 1 - checkpoint_index


@pytest.mark.parametrize("checkpoint_index", (36, 72, 108))
def test_transition_resume_matches_full_scanner_contract(
    checkpoint_index: int,
) -> None:
    metrics = _resume_metrics()
    target_index = len(metrics) - 1
    checkpoint_state = IncrementalScannerEngine().snapshot(
        metrics,
        target_index=checkpoint_index,
        symbol="RESUME-FULL-PARITY",
        timeframe="1wk",
    )

    transition = ScannerTransitionResumeAdapter().resume_latest(metrics, checkpoint_state)
    full = ScannerEngine().scan_to_index(metrics, target_index)

    assert default_candidate_signature(transition) == default_candidate_signature(full)


def test_transition_resume_can_translate_checkpoint_state_without_production_wiring() -> None:
    metrics = _resume_metrics()
    checkpoint_index = 72
    checkpoint_state = IncrementalScannerEngine().snapshot(
        metrics,
        target_index=checkpoint_index,
        symbol="RESUME-STATE",
        timeframe="1wk",
    )

    transition_state = ScannerTransitionResumeAdapter().transition_state_from_scanner_state(
        metrics,
        checkpoint_state,
    )

    assert transition_state.last_bar_index == checkpoint_index
    assert transition_state.structural_events == checkpoint_state.structural_events
    assert transition_state.swing_state == checkpoint_state

    index_by_week = {str(week): index for index, week in enumerate(metrics[COL_WEEK])}
    restored_indices = tuple(
        index_by_week[event.bar_key]
        for event in transition_state.structural_events
    )
    checkpoint_indices = tuple(
        index_by_week[event.bar_key]
        for event in checkpoint_state.structural_events
    )
    assert restored_indices == checkpoint_indices
    assert tuple(
        (item.bar_index, item.code)
        for item in transition_state.qualification.active_events
    ) == tuple(
        (index_by_week[event.bar_key], event.code)
        for event in checkpoint_state.structural_events
        if event.bar_key in index_by_week
    )[-len(transition_state.qualification.active_events):]


def test_transition_resume_rejects_duplicate_bar_identities() -> None:
    metrics = _resume_metrics()
    checkpoint_state = IncrementalScannerEngine().snapshot(
        metrics,
        target_index=72,
        symbol="RESUME-DUPLICATE",
        timeframe="1wk",
    )
    duplicated = metrics.copy()
    duplicated.loc[12, COL_WEEK] = duplicated.loc[11, COL_WEEK]

    with pytest.raises(
        ValueError,
        match="duplicate checkpoint bar identities",
    ):
        ScannerTransitionResumeAdapter().resume_latest(duplicated, checkpoint_state)


def test_transition_resume_rejects_missing_checkpoint_identity() -> None:
    metrics = _resume_metrics()
    checkpoint_state = IncrementalScannerEngine().snapshot(
        metrics,
        target_index=72,
        symbol="RESUME-MISSING",
        timeframe="1wk",
    )
    missing_checkpoint = metrics[metrics[COL_WEEK] != checkpoint_state.last_closed_bar].copy()

    with pytest.raises(
        ValueError,
        match="checkpoint bar is not present",
    ):
        ScannerTransitionResumeAdapter().resume_latest(
            missing_checkpoint,
            checkpoint_state,
        )


def test_transition_resume_adapter_is_wired_only_to_valid_production_resume_boundary() -> None:
    production_source = Path("production_scanner.py").read_text(encoding="utf-8")

    assert "from scanner_transition_resume import ScannerTransitionResumeAdapter" in production_source
    assert "transition_resume = ScannerTransitionResumeAdapter()" in production_source
    assert "candidate = transition_resume.resume_latest(metrics, state)" in production_source
    assert "from scanner_transition import" not in production_source
    assert "ScannerTransitionEngine(" not in production_source
