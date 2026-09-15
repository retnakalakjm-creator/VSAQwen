from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import vsa_event_audit
from historical_scanner import HistoricalScannerRunner
from scanner import ScannerEngine
from vsa_event_audit import build_vsa_event_audit


def _weekly_frame(size: int = 72) -> pd.DataFrame:
    """Build a generic weekly OHLCV fixture with enough structure for scanner replay."""

    anchors = [100.0, 111.0, 103.0, 116.0, 106.0, 121.0, 112.0, 126.0]
    segment_size = max(4, size // (len(anchors) - 1))
    close_values: list[float] = []
    for start, end in zip(anchors[:-1], anchors[1:]):
        close_values.extend(np.linspace(start, end, segment_size, endpoint=False))
    if len(close_values) < size:
        close_values.extend(np.linspace(anchors[-1], anchors[-1] + 3.0, size - len(close_values)))

    close = np.asarray(close_values[:size], dtype=float)
    open_ = close - np.where(np.arange(size) % 4 == 0, -0.75, 0.5)
    high = np.maximum(open_, close) + 1.4
    low = np.minimum(open_, close) - 1.4
    volume = 1_000_000.0 + np.sin(np.linspace(0.0, 6.0, size)) * 120_000.0
    volume[24] *= 1.8
    volume[35] *= 2.0
    volume[48] *= 1.6

    return pd.DataFrame(
        {
            "week_beginning": pd.date_range("2025-01-06", periods=size, freq="W-MON"),
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )


def _row_signature(row) -> tuple[object, ...]:
    return (
        row.replay_bar_index,
        row.replay_week,
        row.target_event_codes,
        row.scoring_event_codes,
        row.qualifying_event_codes,
        row.campaign_event_codes,
        row.structural_event_codes,
        row.vsa_event_codes,
        row.qualification,
        row.actionable,
        row.used_fallback_evidence,
        row.scoring_evidence_age,
        round(row.net_pressure, 12),
        round(row.confidence, 12),
        row.audit_flags,
        row.detector_diagnostics,
        row.notes,
    )


def _audit_signature(audit) -> tuple[object, ...]:
    return (
        audit.symbol,
        audit.timeframe,
        audit.start_week,
        audit.end_week,
        audit.replay_weeks,
        audit.audit_only,
        tuple(_row_signature(row) for row in audit.rows),
    )


def test_default_vsa_audit_matches_explicit_scanner_engine_output() -> None:
    weekly = _weekly_frame()
    start_week = str(weekly.iloc[24]["week_beginning"])

    transition_audit = build_vsa_event_audit(
        symbol="GENERIC.NS",
        weekly=weekly,
        start_week=start_week,
        horizon_weeks=12,
    )
    legacy_audit = build_vsa_event_audit(
        symbol="GENERIC.NS",
        weekly=weekly,
        start_week=start_week,
        horizon_weeks=12,
        scanner=ScannerEngine(),
    )

    assert _audit_signature(transition_audit) == _audit_signature(legacy_audit)
    assert len(transition_audit.rows) == 12


@pytest.mark.parametrize(
    ("start_index", "horizon_weeks"),
    [
        (20, 3),
        (31, 8),
        (45, 15),
    ],
)
def test_default_vsa_audit_transition_runner_matches_scanner_engine_across_windows(
    start_index: int,
    horizon_weeks: int,
) -> None:
    weekly = _weekly_frame()
    start_week = str(weekly.iloc[start_index]["week_beginning"])

    transition_audit = build_vsa_event_audit(
        symbol="GENERIC.NS",
        weekly=weekly,
        start_week=start_week,
        horizon_weeks=horizon_weeks,
    )
    legacy_audit = build_vsa_event_audit(
        symbol="GENERIC.NS",
        weekly=weekly,
        start_week=start_week,
        horizon_weeks=horizon_weeks,
        scanner=ScannerEngine(),
    )

    assert _audit_signature(transition_audit) == _audit_signature(legacy_audit)
    assert [row.replay_bar_index for row in transition_audit.rows] == list(
        range(start_index, start_index + horizon_weeks)
    )


def test_vsa_audit_default_uses_historical_transition_runner(monkeypatch: pytest.MonkeyPatch) -> None:
    weekly = _weekly_frame()
    scan_lengths: list[int] = []
    batch_lengths: list[int] = []
    batch_targets: list[tuple[int, ...]] = []

    class RecordingHistoricalRunner(HistoricalScannerRunner):
        def scan(self, metrics: pd.DataFrame):
            scan_lengths.append(len(metrics))
            return super().scan(metrics)

        def scan_to_indices(self, metrics: pd.DataFrame, target_indices):
            targets = tuple(target_indices)
            batch_lengths.append(len(metrics))
            batch_targets.append(targets)
            return super().scan_to_indices(metrics, targets)

    monkeypatch.setattr(vsa_event_audit, "HistoricalScannerRunner", RecordingHistoricalRunner)

    audit = build_vsa_event_audit(
        symbol="GENERIC.NS",
        weekly=weekly,
        start_week=str(weekly.iloc[26]["week_beginning"]),
        horizon_weeks=4,
    )

    assert scan_lengths == []
    assert batch_lengths == [30]
    assert batch_targets == [(26, 27, 28, 29)]
    assert [row.replay_bar_index for row in audit.rows] == [26, 27, 28, 29]


def test_vsa_audit_explicit_scanner_injection_still_bypasses_default_runner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    weekly = _weekly_frame()

    class ExplodingHistoricalRunner:
        def scan(self, metrics: pd.DataFrame):  # pragma: no cover - should not run
            raise AssertionError("default runner should not be used when scanner is injected")

    class EmptyScanner:
        def __init__(self) -> None:
            self.scan_lengths: list[int] = []

        def scan(self, metrics: pd.DataFrame):
            self.scan_lengths.append(len(metrics))
            return []

    monkeypatch.setattr(vsa_event_audit, "HistoricalScannerRunner", ExplodingHistoricalRunner)
    scanner = EmptyScanner()

    audit = build_vsa_event_audit(
        symbol="GENERIC.NS",
        weekly=weekly,
        start_week=str(weekly.iloc[26]["week_beginning"]),
        horizon_weeks=4,
        scanner=scanner,
    )

    assert scanner.scan_lengths == [30]
    assert audit.rows == ()
