from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd

from audit.runner import run_symbol_candidate_audit
from engine.columns import (
    COL_CLOSE,
    COL_HIGH,
    COL_LOW,
    COL_OPEN,
    COL_VOLUME,
    COL_WEEK,
)
from historical_scanner import HistoricalScannerRunner
from scanner import ScannerEngine
from vsa_event_audit import build_vsa_event_audit


def _weekly(size: int) -> pd.DataFrame:
    close = np.linspace(100.0, 130.0, size)
    return pd.DataFrame(
        {
            COL_WEEK: [
                value.strftime("%Y-%m-%d")
                for value in pd.date_range("2024-01-01", periods=size, freq="W-MON")
            ],
            COL_OPEN: close - 0.5,
            COL_HIGH: close + 1.0,
            COL_LOW: close - 1.0,
            COL_CLOSE: close,
            COL_VOLUME: 1_000.0 + np.arange(size, dtype=float) * 10.0,
        }
    )


def _independent_replay_work(targets: Sequence[int]) -> int:
    start = ScannerEngine.MIN_REPLAY_BARS
    return sum(target - start + 1 for target in targets)


@dataclass(frozen=True)
class _AuditCandidate:
    bar_index: int
    week: str
    qualification: str = "none"
    actionable: bool = False
    used_fallback_evidence: bool = False
    scoring_evidence_age: int | None = None
    net_pressure: float = 0.0
    confidence: float = 0.0


class _RecordingTransition:
    def __init__(self, *, return_candidates: bool = False) -> None:
        self.return_candidates = return_candidates
        self.calls: list[tuple[int, tuple[int, ...]]] = []

    def scan_to_indices(
        self,
        metrics: pd.DataFrame,
        target_indices: Sequence[int],
    ) -> dict[int, _AuditCandidate]:
        targets = tuple(target_indices)
        self.calls.append((len(metrics), targets))
        if not self.return_candidates:
            return {}
        return {
            target: _AuditCandidate(
                bar_index=target,
                week=str(metrics.iloc[target][COL_WEEK]),
            )
            for target in targets
        }


class _RecordingSelectedTargetScanner:
    def __init__(self) -> None:
        self.calls: list[tuple[int, tuple[int, ...]]] = []

    def scan_to_indices(
        self,
        metrics: pd.DataFrame,
        target_indices: Sequence[int],
    ) -> dict[int, _AuditCandidate]:
        targets = tuple(target_indices)
        self.calls.append((len(metrics), targets))
        return {
            target: _AuditCandidate(
                bar_index=target,
                week=str(metrics.iloc[target][COL_WEEK]),
            )
            for target in targets
        }


def test_historical_runner_full_scan_records_single_suffix_reuse_span() -> None:
    size = ScannerEngine.MIN_REPLAY_BARS + 12
    metrics = _weekly(size)
    transition = _RecordingTransition(return_candidates=True)
    runner = HistoricalScannerRunner(transition=transition)  # type: ignore[arg-type]

    candidates = runner.scan(metrics)

    targets = tuple(range(ScannerEngine.MIN_REPLAY_BARS, size))
    assert transition.calls == [(size, targets)]
    assert [candidate.bar_index for candidate in candidates] == list(targets)
    assert len(targets) < _independent_replay_work(targets)


def test_candidate_audit_reaches_historical_suffix_reuse_boundary() -> None:
    size = ScannerEngine.MIN_REPLAY_BARS + 8
    transition = _RecordingTransition()
    runner = HistoricalScannerRunner(transition=transition)  # type: ignore[arg-type]

    result = run_symbol_candidate_audit(
        "AAA.NS",
        horizons=[1],
        daily_loader=lambda _symbol: _weekly(size),
        weekly_transformer=lambda daily: daily,
        metrics_calculator=lambda weekly: weekly,
        scanner_factory=lambda: runner,
    )

    targets = tuple(range(ScannerEngine.MIN_REPLAY_BARS, size))
    assert transition.calls == [(size, targets)]
    assert result.candidate_count == 0
    assert result.outcome_rows == 0
    assert len(targets) < _independent_replay_work(targets)


def test_vsa_event_audit_uses_selected_targets_instead_of_full_bounded_history() -> None:
    size = ScannerEngine.MIN_REPLAY_BARS + 12
    weekly = _weekly(size)
    start_index = ScannerEngine.MIN_REPLAY_BARS + 4
    end_index = ScannerEngine.MIN_REPLAY_BARS + 7
    scanner = _RecordingSelectedTargetScanner()

    result = build_vsa_event_audit(
        symbol="AAA.NS",
        weekly=weekly,
        start_week=str(weekly.iloc[start_index][COL_WEEK]),
        end_week=str(weekly.iloc[end_index][COL_WEEK]),
        scanner=scanner,
    )

    selected_targets = tuple(range(start_index, end_index + 1))
    full_bounded_history = tuple(range(ScannerEngine.MIN_REPLAY_BARS, end_index + 1))
    assert scanner.calls == [(end_index + 1, selected_targets)]
    assert [row.replay_bar_index for row in result.rows] == list(selected_targets)
    assert len(selected_targets) < len(full_bounded_history)
