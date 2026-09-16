from __future__ import annotations

from enum import Enum

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
from metrics_engine import MetricsEngine
from production_scanner import (
    CHECKPOINT_CORRUPT,
    scan_actionable_production,
    scan_latest_candidate_production,
)
from scanner import ScannerCandidate, ScannerEngine
from scanner_state import ScannerStateStore
from scanner_transition_snapshot import ScannerTransitionSnapshotAdapter


def _metrics(size: int = 132) -> pd.DataFrame:
    """Generic production-parity OHLCV fixture with mixed swings and volume."""

    anchors = [
        100.0,
        112.0,
        104.0,
        119.0,
        108.0,
        126.0,
        113.0,
        132.0,
        121.0,
        136.0,
    ]
    bars_per_segment = max(8, size // (len(anchors) - 1))
    points: list[float] = []
    for start, end in zip(anchors[:-1], anchors[1:]):
        points.extend(np.linspace(start, end, bars_per_segment, endpoint=False))
    if len(points) < size:
        points.extend(np.linspace(anchors[-1], anchors[-1] + 3.0, size - len(points)))

    close = np.asarray(points[:size], dtype=float)
    delta = np.diff(close, prepend=close[0])
    open_ = close - np.where(delta >= 0.0, 0.4, -0.4)
    spread = 1.0 + (np.arange(size, dtype=float) % 6.0) * 0.15
    high = np.maximum(open_, close) + spread / 2.0
    low = np.minimum(open_, close) - spread / 2.0
    volume = (
        1_000.0
        + (np.arange(size, dtype=float) % 10.0) * 55.0
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


def _value(item: object) -> object:
    return item.value if isinstance(item, Enum) else item


def _rounded(item: float | None) -> float | None:
    if item is None:
        return None
    return round(float(item), 10)


def _codes(items: object) -> tuple[object, ...]:
    return tuple(_value(getattr(item, "code", item)) for item in items or ())


def _candidate_signature(candidate: ScannerCandidate | None) -> tuple[object, ...] | None:
    if candidate is None:
        return None

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
        _codes(getattr(candidate, "target_bar_evidence", ())),
        _codes(getattr(candidate, "scoring_evidence", ())),
        _codes(getattr(candidate, "qualifying_evidence", ())),
        _codes(getattr(candidate, "campaign_evidence", ())),
        candidate.effort_result_evidence_codes,
        candidate.absorption_evidence_codes,
        candidate.high_volume_reversal_evidence_codes,
        candidate.signal_bar_anomaly,
        candidate.signal_bar_anomaly_reason,
    )


def _full_replay_latest(metrics: pd.DataFrame) -> ScannerCandidate:
    return ScannerEngine().scan_to_index(metrics, len(metrics) - 1)


def test_production_bootstrap_freezes_full_candidate_signature(tmp_path) -> None:
    metrics = _metrics()
    store = ScannerStateStore(tmp_path)
    diagnostics: list[str] = []

    candidate = scan_latest_candidate_production(
        metrics,
        symbol="TEST",
        timeframe="1wk",
        state_store=store,
        fallback_diagnostics=diagnostics,
    )

    assert _candidate_signature(candidate) == _candidate_signature(
        _full_replay_latest(metrics)
    )
    assert diagnostics == []
    assert store.path_for("TEST", "1wk").exists()


def test_production_resume_freezes_full_candidate_signature(tmp_path) -> None:
    metrics = _metrics()
    store = ScannerStateStore(tmp_path)
    split_index = ScannerEngine.MIN_REPLAY_BARS + 18
    state = ScannerTransitionSnapshotAdapter().snapshot(
        metrics,
        target_index=split_index,
        symbol="TEST",
        timeframe="1wk",
    )
    store.save(state)

    candidate = scan_latest_candidate_production(
        metrics,
        symbol="TEST",
        timeframe="1wk",
        state_store=store,
    )

    assert _candidate_signature(candidate) == _candidate_signature(
        _full_replay_latest(metrics)
    )
    refreshed = store.load("TEST", "1wk")
    assert refreshed.last_closed_bar == str(metrics.iloc[-1][COL_WEEK])


def test_production_corrupt_checkpoint_fallback_freezes_candidate_signature(tmp_path) -> None:
    metrics = _metrics()
    store = ScannerStateStore(tmp_path)
    state_path = store.path_for("TEST", "1wk")
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text("{not valid json", encoding="utf-8")
    diagnostics: list[str] = []

    candidate = scan_latest_candidate_production(
        metrics,
        symbol="TEST",
        timeframe="1wk",
        state_store=store,
        fallback_diagnostics=diagnostics,
    )

    assert _candidate_signature(candidate) == _candidate_signature(
        _full_replay_latest(metrics)
    )
    assert len(diagnostics) == 1
    assert CHECKPOINT_CORRUPT in diagnostics[0]
    assert "full replay fallback used" in diagnostics[0]


def test_production_actionable_wrapper_freezes_full_replay_shape(tmp_path) -> None:
    metrics = _metrics()
    store = ScannerStateStore(tmp_path)

    candidates = scan_actionable_production(
        metrics,
        symbol="TEST",
        timeframe="1wk",
        state_store=store,
    )
    full = ScannerEngine().scan_actionable(metrics)

    assert [_candidate_signature(candidate) for candidate in candidates] == [
        _candidate_signature(candidate) for candidate in full
    ]
