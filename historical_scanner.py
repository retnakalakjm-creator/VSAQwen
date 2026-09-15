from __future__ import annotations

from collections.abc import Sequence

import pandas as pd

from scanner import ScannerCandidate, ScannerEngine
from scanner_transition import ScannerTransitionEngine


class HistoricalScannerRunner:
    """Historical and production full-replay runner backed by the transition engine.

    This adapter gives historical, audit, replay, bootstrap, and production
    fallback callers a named transition boundary. It delegates to
    ``ScannerTransitionEngine`` and preserves the scanner semantics proven by
    the transition-runner parity tests.
    """

    def __init__(self, transition: ScannerTransitionEngine | None = None) -> None:
        self._transition = transition or ScannerTransitionEngine()

    def scan_to_index(self, metrics: pd.DataFrame, target_index: int) -> ScannerCandidate:
        """Return the candidate at ``target_index`` through the transition path."""

        return self._transition.scan_to_index(metrics, target_index)

    def scan_to_indices(
        self,
        metrics: pd.DataFrame,
        target_indices: Sequence[int],
    ) -> dict[int, ScannerCandidate]:
        """Return requested candidates through one suffix-reuse transition path."""

        return self._transition.scan_to_indices(metrics, target_indices)

    def scan(self, metrics: pd.DataFrame) -> list[ScannerCandidate]:
        """Return historical candidates through the suffix-reuse transition path."""

        if len(metrics) <= ScannerEngine.MIN_REPLAY_BARS:
            return []
        candidates = self._transition.scan_to_indices(
            metrics,
            range(ScannerEngine.MIN_REPLAY_BARS, len(metrics)),
        )
        return list(candidates.values())

    def scan_actionable(self, metrics: pd.DataFrame) -> list[ScannerCandidate]:
        """Return the latest actionable historical candidate through the transition path."""

        return self._transition.scan_actionable(metrics)


__all__ = ["HistoricalScannerRunner"]
