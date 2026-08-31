from __future__ import annotations

import pandas as pd

from scanner_state import ScannerState
from trend import TrendAnalyzer, TrendResult
from market_structure.structure_filter import StructureFilter


class IncrementalTrendAnalyzer(TrendAnalyzer):
    """Trend analysis adapter that resumes from persisted swing state."""

    def analyze_from_state(
        self,
        df: pd.DataFrame,
        state: ScannerState,
    ) -> TrendResult:
        """Resume swing detection and rebuild the current trend structure."""
        self._reset(df)

        swings = list(self._swing_engine.calculate_from_state(df, state))
        structural_swings = StructureFilter().filter(swings, df)

        self._classified_swings = self._classify_swings(structural_swings)
        self._structural_swings = structural_swings
        self._create_structure()

        return self._build_result()
