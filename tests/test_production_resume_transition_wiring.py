from __future__ import annotations

import numpy as np
import pandas as pd

import production_scanner
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
from scanner import ScannerCandidate, ScannerEngine
from scanner_state import ScannerStateStore


def _metrics(size: int = 112) -> pd.DataFrame:
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
    ]
    bars_per_segment = max(6, size // (len(anchors) - 1))
    points: list[float] = []
    for start, end in zip(anchors[:-1], anchors[1:]):
        points.extend(np.linspace(start, end, bars_per_segment, endpoint=False))
    if len(points) < size:
        points.extend(np.linspace(anchors[-1], anchors[-1] + 3.0, size - len(points)))

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

    return MetricsEngine().calculate(
        pd.DataFrame(
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
    )


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


def test_valid_production_checkpoint_resume_uses_transition_adapter(
    monkeypatch,
    tmp_path,
) -> None:
    metrics = _metrics()
    symbol = "CONTRACT"
    timeframe = "1wk"
    checkpoint_index = 72
    target_index = len(metrics) - 1
    store = ScannerStateStore(tmp_path)
    checkpoint_state = IncrementalScannerEngine().snapshot(
        metrics,
        target_index=checkpoint_index,
        symbol=symbol,
        timeframe=timeframe,
    )
    store.save(checkpoint_state)

    expected = ScannerEngine().scan_to_index(metrics, target_index)
    calls = {"transition_resume": 0, "snapshot": 0}

    class FakeTransitionResumeAdapter:
        def resume_latest(self, received_metrics, state):
            calls["transition_resume"] += 1
            assert received_metrics is metrics
            assert state.last_closed_bar == checkpoint_state.last_closed_bar
            return expected

    class FakeIncrementalScannerEngine:
        def resume_latest(self, *_args, **_kwargs):
            raise AssertionError("production resume must use ScannerTransitionResumeAdapter")

        def snapshot(self, received_metrics, *, target_index, symbol, timeframe):
            calls["snapshot"] += 1
            return IncrementalScannerEngine().snapshot(
                received_metrics,
                target_index=target_index,
                symbol=symbol,
                timeframe=timeframe,
            )

    monkeypatch.setattr(
        production_scanner,
        "ScannerTransitionResumeAdapter",
        FakeTransitionResumeAdapter,
    )
    monkeypatch.setattr(
        production_scanner,
        "IncrementalScannerEngine",
        FakeIncrementalScannerEngine,
    )

    diagnostics: list[str] = []
    candidate = production_scanner.scan_latest_candidate_production(
        metrics,
        symbol=symbol,
        timeframe=timeframe,
        state_store=store,
        allow_full_replay_fallback=False,
        fallback_diagnostics=diagnostics,
    )

    assert candidate is expected
    assert calls == {"transition_resume": 1, "snapshot": 1}
    assert diagnostics == []
    refreshed = store.load(symbol, timeframe)
    assert refreshed.last_closed_bar == str(metrics.iloc[target_index][COL_WEEK])


def test_transition_resume_failure_still_uses_full_replay_fallback(
    monkeypatch,
    tmp_path,
) -> None:
    metrics = _metrics()
    symbol = "CONTRACT"
    timeframe = "1wk"
    checkpoint_index = 72
    target_index = len(metrics) - 1
    store = ScannerStateStore(tmp_path)
    store.save(
        IncrementalScannerEngine().snapshot(
            metrics,
            target_index=checkpoint_index,
            symbol=symbol,
            timeframe=timeframe,
        )
    )

    class RaisingTransitionResumeAdapter:
        def resume_latest(self, *_args, **_kwargs):
            raise RuntimeError("transition resume divergence")

    monkeypatch.setattr(
        production_scanner,
        "ScannerTransitionResumeAdapter",
        RaisingTransitionResumeAdapter,
    )

    diagnostics: list[str] = []
    candidate = production_scanner.scan_latest_candidate_production(
        metrics,
        symbol=symbol,
        timeframe=timeframe,
        state_store=store,
        allow_full_replay_fallback=True,
        fallback_diagnostics=diagnostics,
    )
    full = ScannerEngine().scan_to_index(metrics, target_index)

    assert candidate is not None
    assert _candidate_signature(candidate) == _candidate_signature(full)
    assert len(diagnostics) == 1
    assert production_scanner.ENGINE_DIVERGENCE in diagnostics[0]
    assert "full replay fallback used" in diagnostics[0]
