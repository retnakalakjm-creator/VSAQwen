from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd
import pytest

import config

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
from market_structure.structure_filter import StructureFilter
from market_structure.swing_engine import SwingEngine
from scanner import ScannerCandidate, ScannerEngine
from scanner_transition import BarFeatures, ScannerTransitionEngine


def _metrics(size: int = 96) -> pd.DataFrame:
    """Generic synthetic OHLCV fixture for transition-runner measurement tests."""

    anchors = [
        100.0,
        112.0,
        105.0,
        118.0,
        109.0,
        126.0,
        114.0,
        132.0,
        121.0,
        138.0,
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
    spread = 1.1 + (np.arange(size, dtype=float) % 5.0) * 0.12
    high = np.maximum(open_, close) + spread / 2.0
    low = np.minimum(open_, close) - spread / 2.0
    volume = (
        1_000.0
        + (np.arange(size, dtype=float) % 9.0) * 60.0
        + np.where((np.arange(size) % 13) == 0, 275.0, 0.0)
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


def _value(item: object) -> object:
    return getattr(item, "value", item)


def _rounded(item: float | None) -> float | None:
    if item is None:
        return None
    return round(float(item), 10)


def _candidate_signature(candidate: ScannerCandidate) -> tuple[object, ...]:
    qualification = candidate.qualification_result
    return (
        _value(candidate.qualification),
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
        _rounded(candidate.ranking_score),
        _rounded(candidate.net_strength),
        _rounded(candidate.net_pressure),
        _rounded(candidate.confidence),
        _value(qualification.qualification),
        qualification.is_actionable_evidence,
        qualification.reason,
        tuple(_value(code) for code in qualification.evidence_codes),
        tuple(qualification.evidence_bar_indices),
        candidate.effort_result_evidence_codes,
        candidate.absorption_evidence_codes,
        candidate.high_volume_reversal_evidence_codes,
    )


class MeasuringTransitionEngine(ScannerTransitionEngine):
    """Transition engine test double that records prefix construction."""

    def __init__(self) -> None:
        super().__init__()
        self.feature_indices: list[int] = []
        self.prefix_lengths: list[int] = []

    def features_for(self, metrics: pd.DataFrame, index: int) -> BarFeatures:
        features = ScannerTransitionEngine.features_for(metrics, index)
        self.feature_indices.append(index)
        self.prefix_lengths.append(len(features.metrics_prefix))
        return features


class RecordingBatchTransition(MeasuringTransitionEngine):
    """Measuring transition double that records batch suffix-reuse calls."""

    def __init__(self) -> None:
        super().__init__()
        self.scan_called = False
        self.scan_to_indices_targets: list[tuple[int, ...]] = []

    def scan(self, metrics: pd.DataFrame) -> list[ScannerCandidate]:
        self.scan_called = True
        raise AssertionError("HistoricalScannerRunner.scan should use scan_to_indices")

    def scan_to_indices(
        self,
        metrics: pd.DataFrame,
        target_indices: Sequence[int],
    ) -> dict[int, ScannerCandidate]:
        targets = tuple(target_indices)
        self.scan_to_indices_targets.append(targets)
        return super().scan_to_indices(metrics, targets)


def _expected_indices(start: int, target: int) -> list[int]:
    return list(range(start, target + 1))


def test_features_for_uses_shallow_prefix_without_copying_column_buffers() -> None:
    metrics = _metrics()
    index = ScannerEngine.MIN_REPLAY_BARS + 5

    features = ScannerTransitionEngine.features_for(metrics, index)

    assert features.metrics_prefix is not metrics
    assert len(features.metrics_prefix) == index + 1
    assert np.shares_memory(
        features.metrics_prefix[COL_CLOSE].to_numpy(copy=False),
        metrics[COL_CLOSE].to_numpy(copy=False),
    )


def test_transition_reuses_swing_state_after_first_replay_bar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    metrics = _metrics()
    start = ScannerEngine.MIN_REPLAY_BARS
    targets = tuple(range(start, len(metrics)))
    calls = {"full": 0, "resumed": 0}

    original_calculate = SwingEngine.calculate
    original_calculate_from_state = SwingEngine.calculate_from_state

    def counting_calculate(self, frame):
        calls["full"] += 1
        return original_calculate(self, frame)

    def counting_calculate_from_state(self, frame, state):
        calls["resumed"] += 1
        return original_calculate_from_state(self, frame, state)

    monkeypatch.setattr(SwingEngine, "calculate", counting_calculate)
    monkeypatch.setattr(
        SwingEngine,
        "calculate_from_state",
        counting_calculate_from_state,
    )

    candidates = ScannerTransitionEngine().scan_to_indices(metrics, targets)

    assert list(candidates) == list(targets)
    assert calls["full"] == 1
    assert calls["resumed"] == len(targets) - 1


def test_transition_rescores_structure_only_when_new_swings_arrive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    metrics = _metrics()
    start = ScannerEngine.MIN_REPLAY_BARS
    targets = tuple(range(start, len(metrics)))
    scored_lengths: list[int] = []

    original_filter = StructureFilter.filter

    def counting_filter(self, swings, frame):
        scored_lengths.append(len(swings))
        return original_filter(self, swings, frame)

    monkeypatch.setattr(StructureFilter, "filter", counting_filter)

    ScannerTransitionEngine().scan_to_indices(metrics, targets)

    full_swings = SwingEngine().calculate(metrics)
    later_confirmations = sum(
        swing.confirmation_index > start
        for swing in full_swings
    )

    assert len(scored_lengths) == 1 + later_confirmations
    assert all(
        length <= config.STRUCTURE_LOOKBACK + 1
        for length in scored_lengths[1:]
    )


def test_repeated_scan_to_index_rebuilds_prefixes_from_replay_start() -> None:
    metrics = _metrics()
    transition = MeasuringTransitionEngine()
    baseline = ScannerEngine()
    start = baseline.MIN_REPLAY_BARS
    targets = (start + 3, start + 5, start + 7)

    for target_index in targets:
        candidate = transition.scan_to_index(metrics, target_index)
        expected = baseline.scan_to_index(metrics, target_index)
        assert _candidate_signature(candidate) == _candidate_signature(expected)

    expected_indices = [
        index
        for target_index in targets
        for index in _expected_indices(start, target_index)
    ]
    assert transition.feature_indices == expected_indices
    assert transition.prefix_lengths == [index + 1 for index in expected_indices]
    assert len(transition.feature_indices) > len(_expected_indices(start, targets[-1]))


def test_stateful_run_to_index_extends_only_the_new_suffix() -> None:
    metrics = _metrics()
    transition = MeasuringTransitionEngine()
    baseline = ScannerEngine()
    start = baseline.MIN_REPLAY_BARS
    checkpoint_index = start + 4
    target_index = checkpoint_index + 5

    state, _ = transition.run_to_index(metrics, checkpoint_index)
    assert state.last_bar_index == checkpoint_index
    assert transition.feature_indices == _expected_indices(start, checkpoint_index)

    transition.feature_indices.clear()
    transition.prefix_lengths.clear()
    state, evaluation = transition.run_to_index(
        metrics,
        target_index,
        state=state,
    )

    expected_suffix = _expected_indices(checkpoint_index + 1, target_index)
    assert state.last_bar_index == target_index
    assert transition.feature_indices == expected_suffix
    assert transition.prefix_lengths == [index + 1 for index in expected_suffix]
    assert _candidate_signature(evaluation.candidate) == _candidate_signature(
        baseline.scan_to_index(metrics, target_index)
    )


def test_scan_to_indices_reuses_one_transition_state_for_increasing_targets() -> None:
    metrics = _metrics()
    transition = MeasuringTransitionEngine()
    baseline = ScannerEngine()
    start = baseline.MIN_REPLAY_BARS
    targets = (start + 3, start + 5, start + 7)

    candidates = transition.scan_to_indices(metrics, targets)

    assert list(candidates) == list(targets)
    for target_index in targets:
        assert _candidate_signature(candidates[target_index]) == _candidate_signature(
            baseline.scan_to_index(metrics, target_index)
        )

    expected_indices = _expected_indices(start, targets[-1])
    assert transition.feature_indices == expected_indices
    assert transition.prefix_lengths == [index + 1 for index in expected_indices]


def test_scan_to_indices_rejects_empty_and_invalid_target_sequences() -> None:
    metrics = _metrics()
    transition = ScannerTransitionEngine()
    start = ScannerEngine.MIN_REPLAY_BARS

    assert transition.scan_to_indices(metrics, ()) == {}

    with pytest.raises(ValueError, match="strictly increasing"):
        transition.scan_to_indices(metrics, (start + 2, start + 2))

    with pytest.raises(ValueError, match="strictly increasing"):
        transition.scan_to_indices(metrics, (start + 3, start + 1))

    with pytest.raises(ValueError, match="target_index must be"):
        transition.scan_to_indices(metrics, (start - 1,))

    with pytest.raises(IndexError, match="outside metrics"):
        transition.scan_to_indices(metrics, (len(metrics),))


def test_historical_runner_scan_consumes_suffix_reuse_api() -> None:
    metrics = _metrics()
    transition = RecordingBatchTransition()
    baseline = ScannerEngine()
    runner = HistoricalScannerRunner(transition=transition)
    start = baseline.MIN_REPLAY_BARS

    candidates = runner.scan(metrics)

    expected_targets = tuple(range(start, len(metrics)))
    assert transition.scan_called is False
    assert transition.scan_to_indices_targets == [expected_targets]
    assert transition.feature_indices == list(expected_targets)
    assert [_candidate_signature(candidate) for candidate in candidates] == [
        _candidate_signature(candidate) for candidate in baseline.scan(metrics)
    ]


def test_historical_runner_scan_short_metrics_skips_suffix_reuse_call() -> None:
    metrics = _metrics(ScannerEngine.MIN_REPLAY_BARS)
    transition = RecordingBatchTransition()
    runner = HistoricalScannerRunner(transition=transition)

    assert runner.scan(metrics) == []
    assert transition.scan_called is False
    assert transition.scan_to_indices_targets == []
    assert transition.feature_indices == []
