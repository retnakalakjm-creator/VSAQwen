from __future__ import annotations

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
from market_structure.incremental_trend import IncrementalTrendAnalyzer
from market_structure.swing_engine import SwingEngine
from metrics_engine import MetricsEngine
from production_scanner import scan_latest_candidate_production
from scanner import (
    ABSORPTION_READ_ONLY_CODES,
    EFFORT_RESULT_READ_ONLY_CODES,
    HIGH_VOLUME_REVERSAL_READ_ONLY_CODES,
    ScannerCandidate,
    ScannerEngine,
)
from scanner_state import ScannerState, ScannerStateStore
from trend import TrendAnalyzer


READ_ONLY_CODE_VALUES = frozenset(
    str(getattr(code, "value", code))
    for code in (
        EFFORT_RESULT_READ_ONLY_CODES
        | ABSORPTION_READ_ONLY_CODES
        | HIGH_VOLUME_REVERSAL_READ_ONLY_CODES
    )
)


def _contract_metrics(size: int = 132) -> pd.DataFrame:
    """Generic synthetic OHLCV history with enough swings for resume tests."""

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

    weeks = pd.date_range("2024-01-01", periods=size, freq="W-MON")
    raw = pd.DataFrame(
        {
            COL_WEEK: weeks.strftime("%Y-%m-%d").tolist(),
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


def _evidence_signature(item) -> tuple[object, ...]:
    return (
        _value(item.code),
        _value(item.category),
        _value(item.direction),
        _rounded(item.strength),
        _rounded(item.weight),
        _rounded(item.quality),
        item.bar_index,
        str(item.week_beginning),
        item.test_index,
        item.recovery_index,
        item.observation,
        item.description,
    )


def _evidence_signatures(items) -> tuple[tuple[object, ...], ...]:
    return tuple(_evidence_signature(item) for item in items)


def _candidate_contract_signature(candidate: ScannerCandidate) -> tuple[object, ...]:
    """Semantic scanner output covered by the full-vs-resume contract."""

    qualification = candidate.qualification_result
    scores = candidate.professional.scores
    return (
        _value(candidate.qualification),
        candidate.actionable,
        _rounded(candidate.base_score),
        _rounded(candidate.ranking_score),
        _rounded(candidate.net_strength),
        _rounded(candidate.net_pressure),
        _rounded(candidate.confidence),
        _value(qualification.qualification),
        qualification.is_actionable_evidence,
        qualification.reason,
        tuple(_value(code) for code in qualification.evidence_codes),
        tuple(qualification.evidence_bar_indices),
        _rounded(scores.trend),
        _rounded(scores.supply),
        _rounded(scores.demand),
        _rounded(scores.effort),
        _rounded(scores.strength),
        _rounded(scores.weakness),
        _rounded(scores.confidence),
        _evidence_signatures(candidate.target_bar_evidence),
        _evidence_signatures(candidate.campaign_evidence),
        _evidence_signatures(candidate.qualifying_evidence),
        _evidence_signatures(candidate.scoring_evidence),
        candidate.scoring_bar_index,
        candidate.scoring_evidence_age,
        candidate.used_fallback_evidence,
        candidate.bar_index,
        candidate.week,
        candidate.signal_bar_index,
        candidate.signal_week,
        candidate.execution_bar_index,
        candidate.execution_week,
        candidate.execution_available,
        candidate.execution_pending,
        candidate.signal_bar_anomaly,
        candidate.signal_bar_anomaly_reason,
        candidate.reason,
        candidate.effort_result_evidence_codes,
        candidate.absorption_evidence_codes,
        candidate.high_volume_reversal_evidence_codes,
    )


def _assert_read_only_neutrality(candidate: ScannerCandidate) -> None:
    scoring_codes = {str(_value(item.code)) for item in candidate.scoring_evidence}
    qualifying_codes = {str(_value(item.code)) for item in candidate.qualifying_evidence}

    assert scoring_codes.isdisjoint(READ_ONLY_CODE_VALUES)
    assert qualifying_codes.isdisjoint(READ_ONLY_CODE_VALUES)


def _candidate_state_signature(state: ScannerState) -> tuple[object, ...] | None:
    if state.candidate is None:
        return None
    return (
        state.candidate.bar_key,
        _value(state.candidate.type),
        _rounded(state.candidate.price),
    )


def _swing_state_signature(state: ScannerState) -> tuple[object, ...]:
    return (
        state.last_closed_bar,
        _value(state.search_state),
        _candidate_state_signature(state),
        tuple(
            (
                swing.pivot_bar_key,
                swing.confirmation_bar_key,
                _value(swing.type),
                _rounded(swing.price),
            )
            for swing in state.confirmed_swings
        ),
    )


def _classified_swing_signature(item) -> tuple[object, ...]:
    swing = item.swing
    return (
        str(swing.week_beginning),
        swing.bar_index,
        swing.confirmation_index,
        _value(swing.type),
        _value(item.label),
        _rounded(swing.price),
    )


def _structural_swing_signature(item) -> tuple[object, ...]:
    swing = item.swing
    return (
        str(swing.week_beginning),
        swing.bar_index,
        swing.confirmation_index,
        _value(swing.type),
        _rounded(swing.price),
        _value(item.grade),
        item.is_failed,
    )


def _trend_contract_signature(result) -> tuple[object, ...]:
    structure = result.structure
    return (
        _value(structure.direction),
        _value(structure.state),
        _rounded(structure.strength),
        _rounded(structure.confidence),
        structure.swing_count,
        structure.hh_count,
        structure.hl_count,
        structure.lh_count,
        structure.ll_count,
        tuple(_classified_swing_signature(item) for item in structure.swings),
        tuple(
            _structural_swing_signature(item)
            for item in structure.structural_swings
        ),
    )


@pytest.mark.parametrize("checkpoint_index", (36, 72, 108))
def test_resume_rebuilds_same_swing_and_trend_state_as_full_scan(
    checkpoint_index: int,
) -> None:
    metrics = _contract_metrics()
    target_index = len(metrics) - 1
    incremental = IncrementalScannerEngine()
    checkpoint_state = incremental.snapshot(
        metrics,
        target_index=checkpoint_index,
        symbol="CONTRACT",
        timeframe="1wk",
    )

    resumed_trend = IncrementalTrendAnalyzer().analyze_from_state(
        metrics,
        checkpoint_state,
    )
    full_trend = TrendAnalyzer().analyze(metrics)

    assert _trend_contract_signature(resumed_trend) == _trend_contract_signature(
        full_trend
    )

    resumed_swing_engine = SwingEngine()
    resumed_swing_engine.calculate_from_state(metrics, checkpoint_state)
    resumed_state = resumed_swing_engine.snapshot_state(
        symbol="CONTRACT",
        timeframe="1wk",
    )
    full_state = incremental.snapshot(
        metrics,
        target_index=target_index,
        symbol="CONTRACT",
        timeframe="1wk",
    )

    assert _swing_state_signature(resumed_state) == _swing_state_signature(
        full_state
    )


@pytest.mark.parametrize("checkpoint_index", (36, 72, 108))
def test_snapshot_resume_candidate_matches_full_scan_contract(
    checkpoint_index: int,
) -> None:
    metrics = _contract_metrics()
    target_index = len(metrics) - 1
    incremental = IncrementalScannerEngine()
    checkpoint_state = incremental.snapshot(
        metrics,
        target_index=checkpoint_index,
        symbol="CONTRACT",
        timeframe="1wk",
    )

    resumed = incremental.resume_latest(metrics, checkpoint_state)
    full = ScannerEngine().scan_to_index(metrics, target_index)

    assert _candidate_contract_signature(resumed) == _candidate_contract_signature(
        full
    )
    _assert_read_only_neutrality(resumed)
    _assert_read_only_neutrality(full)


def test_production_resume_path_matches_full_scan_contract_without_fallback(
    tmp_path,
) -> None:
    metrics = _contract_metrics()
    checkpoint_index = 72
    target_index = len(metrics) - 1
    store = ScannerStateStore(tmp_path)
    checkpoint_state = IncrementalScannerEngine().snapshot(
        metrics,
        target_index=checkpoint_index,
        symbol="CONTRACT",
        timeframe="1wk",
    )
    store.save(checkpoint_state)

    resumed = scan_latest_candidate_production(
        metrics,
        symbol="CONTRACT",
        timeframe="1wk",
        state_store=store,
        allow_full_replay_fallback=False,
    )
    full = ScannerEngine().scan_to_index(metrics, target_index)

    assert resumed is not None
    assert _candidate_contract_signature(resumed) == _candidate_contract_signature(
        full
    )
    _assert_read_only_neutrality(resumed)

    refreshed = store.load("CONTRACT", "1wk")
    assert refreshed.last_closed_bar == str(metrics.iloc[target_index][COL_WEEK])
