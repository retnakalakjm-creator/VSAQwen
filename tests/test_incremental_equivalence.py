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
from market_structure.swing_engine import SwingEngine
from models import SwingSearchState
from scanner_state import ScannerState
from trend import TrendAnalyzer


def _metrics(size: int = 120) -> pd.DataFrame:
    """Create deterministic weekly bars with repeated directional reversals."""
    points: list[float] = []
    anchors = [100.0, 108.0, 101.0, 111.0, 103.0, 115.0, 106.0]
    for start, end in zip(anchors[:-1], anchors[1:]):
        points.extend(np.linspace(start, end, 18, endpoint=False))
    points.extend(np.linspace(anchors[-1], 118.0, size - len(points)))
    close = np.asarray(points[:size], dtype=float)
    spread = np.full(size, 1.0)
    high = close + 0.5
    low = close - 0.5
    open_ = close - 0.2
    volume = np.full(size, 1_000.0)

    return pd.DataFrame(
        {
            COL_WEEK: [f"2025-01-{i + 1:02d}" for i in range(size)],
            COL_OPEN: open_,
            COL_HIGH: high,
            COL_LOW: low,
            COL_CLOSE: close,
            COL_VOLUME: volume,
            COL_SPREAD: spread,
            COL_AVG_VOLUME: volume,
            COL_AVG_SPREAD: spread,
        }
    )


def _swing_signature(swings) -> tuple[tuple[object, int, int, float, str], ...]:
    return tuple(
        (
            swing.type,
            swing.bar_index,
            swing.confirmation_index,
            swing.price,
            swing.week_beginning,
        )
        for swing in swings
    )


def _structural_signature(structural_swings) -> tuple[tuple[object, int, int, object, float], ...]:
    return tuple(
        (
            item.swing.type,
            item.swing.bar_index,
            item.swing.confirmation_index,
            item.grade,
            item.evaluation.professional.overall,
        )
        for item in structural_swings
    )


def _classified_signature(classified_swings) -> tuple[tuple[object, int, int, object], ...]:
    return tuple(
        (
            item.swing.type,
            item.swing.bar_index,
            item.swing.confirmation_index,
            item.label,
        )
        for item in classified_swings
    )


def _advance(engine: SwingEngine, start_index: int, end_index: int) -> None:
    """Advance a prepared SwingEngine through an inclusive bar range."""
    for bar_index in range(start_index, end_index + 1):
        if engine._state in (
            SwingSearchState.TRACKING_HIGH,
            SwingSearchState.TRACKING_LOW,
        ):
            engine._update_candidate(bar_index)
            if engine._is_reversal_confirmed(bar_index):
                if engine._state == SwingSearchState.TRACKING_HIGH:
                    engine._state = SwingSearchState.WAITING_HIGH_CONFIRMATION
                else:
                    engine._state = SwingSearchState.WAITING_LOW_CONFIRMATION
                continue

        if engine._state == SwingSearchState.WAITING_HIGH_CONFIRMATION:
            if bar_index - engine._candidate.bar_index >= 2:
                engine._confirm_candidate(bar_index)
        elif engine._state == SwingSearchState.WAITING_LOW_CONFIRMATION:
            if bar_index - engine._candidate.bar_index >= 2:
                engine._confirm_candidate(bar_index)


def test_full_history_matches_every_prefix_for_confirmed_swings() -> None:
    metrics = _metrics()
    full = SwingEngine().calculate(metrics)

    for end_index in range(10, len(metrics)):
        prefix = metrics.iloc[: end_index + 1].copy()
        prefix_swings = SwingEngine().calculate(prefix)
        expected = tuple(
            swing for swing in full if swing.confirmation_index <= end_index
        )

        assert _swing_signature(prefix_swings) == _swing_signature(expected)


def test_prefix_never_loses_a_previously_confirmed_swing() -> None:
    metrics = _metrics()
    previous: tuple[tuple[object, int, int, float, str], ...] = ()

    for end_index in range(10, len(metrics)):
        prefix = metrics.iloc[: end_index + 1].copy()
        current = _swing_signature(SwingEngine().calculate(prefix))

        assert current[: len(previous)] == previous
        previous = current


def test_full_history_matches_prefix_structural_state() -> None:
    metrics = _metrics()
    full = TrendAnalyzer().analyze(metrics).structure

    for end_index in range(30, len(metrics)):
        prefix = metrics.iloc[: end_index + 1].copy()
        structure = TrendAnalyzer().analyze(prefix).structure
        expected_swings = tuple(
            item for item in full.structural_swings
            if item.swing.confirmation_index <= end_index
        )
        expected_classified = tuple(
            item for item in full.swings
            if item.swing.confirmation_index <= end_index
        )

        assert _classified_signature(structure.swings) == _classified_signature(expected_classified)
        assert _structural_signature(structure.structural_swings) == _structural_signature(expected_swings)
        assert structure.direction == TrendAnalyzer().analyze(
            metrics.iloc[: end_index + 1].copy()
        ).structure.direction


def test_in_memory_swing_continuation_matches_full_history() -> None:
    metrics = _metrics()
    split = 72

    full_swings = SwingEngine().calculate(metrics)

    prefix_engine = SwingEngine()
    prefix_engine.calculate(metrics.iloc[: split + 1].copy())
    state = prefix_engine.snapshot_state("TEST", "1wk")

    continuation = SwingEngine()
    resumed_swings = continuation.calculate_from_state(metrics, state)

    assert _swing_signature(resumed_swings) == _swing_signature(full_swings)


def test_serialized_scanner_state_resumes_swing_engine() -> None:
    metrics = _metrics()
    split = 72

    full_swings = SwingEngine().calculate(metrics)

    prefix_engine = SwingEngine()
    prefix_engine.calculate(metrics.iloc[: split + 1].copy())
    state = prefix_engine.snapshot_state("TEST", "1wk")
    restored_state = ScannerState.from_dict(state.to_dict())

    resumed_swings = SwingEngine().calculate_from_state(metrics, restored_state)

    assert _swing_signature(resumed_swings) == _swing_signature(full_swings)
