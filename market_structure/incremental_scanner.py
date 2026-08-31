from __future__ import annotations

import pandas as pd

from data import incremental_replay_window
from market_structure.incremental_trend import IncrementalTrendAnalyzer
from scanner_state import ScannerState
from trend import TrendResult


class IncrementalStructurePipeline:
    """Opt-in incremental structural analysis pipeline.

    Qualification, evidence aggregation, and scoring remain on the existing
    full-history path until their own state requirements are validated.
    """

    def analyze(
        self,
        metrics: pd.DataFrame,
        state: ScannerState,
    ) -> TrendResult:
        replay_window = incremental_replay_window(metrics, state)
        return IncrementalTrendAnalyzer().analyze_from_state(
            replay_window,
            state,
        )

    @staticmethod
    def replay_window(
        metrics: pd.DataFrame,
        state: ScannerState,
    ) -> pd.DataFrame:
        """Return the causal replay window selected for the persisted state."""
        return incremental_replay_window(metrics, state)
