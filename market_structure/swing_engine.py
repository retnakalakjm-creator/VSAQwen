from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from engine.columns import COL_AVG_SPREAD, COL_CLOSE, COL_HIGH, COL_LOW, COL_OPEN, COL_VOLUME, COL_WEEK
import config
from logger import Log
from models import (
    ClassifiedSwing,
    Swing,
    SwingLabel,
    SwingSearchState,
    SwingType,
)
from scanner_state import (
    CandidateState,
    ConfirmedSwingState,
    SCANNER_STATE_SCHEMA_VERSION,
    ScannerState,
)


# =============================================================================
# Internal Models
# =============================================================================
@dataclass(slots=True)
class CandidateSwing:
    """Internal representation of a potential swing."""

    bar_index: int
    week_beginning: str
    type: SwingType
    price: float

class SwingEngine:

    def __init__(self) -> None:
        self._df = None
        self._high = None
        self._low = None
        self._open = None
        self._close = None
        self._volume = None
        self._weeks = None
        self._avg_spread = None
        self._state = SwingSearchState.TRACKING_HIGH
        self._candidate = None
        self._swings: list[Swing] = []
        self._classified_swings: list[ClassifiedSwing] = []

    def calculate(
        self,
        metrics: pd.DataFrame,
    ) -> tuple[Swing, ...]:
        """Detect and classify all confirmed swings."""
        self._reset(metrics)
        self._find_potential_swings()
        # self._classify_swings()
        return tuple(self._swings)

    def snapshot_state(
        self,
        symbol: str,
        timeframe: str,
    ) -> ScannerState:
        """Capture causal swing state using stable bar identities."""
        if self._df is None or self._df.empty:
            raise ValueError("Cannot snapshot an uninitialized SwingEngine.")
        if self._candidate is None:
            raise RuntimeError("Cannot snapshot SwingEngine without a candidate.")

        retained_swings = self._swings

        return ScannerState(
            schema_version=SCANNER_STATE_SCHEMA_VERSION,
            symbol=symbol,
            timeframe=timeframe,
            last_closed_bar=str(self._weeks[-1]),
            search_state=self._state,
            candidate=CandidateState(
                bar_key=str(self._candidate.week_beginning),
                type=self._candidate.type,
                price=self._candidate.price,
            ),
            confirmed_swings=tuple(
                ConfirmedSwingState(
                    pivot_bar_key=str(swing.week_beginning),
                    confirmation_bar_key=str(self._weeks[swing.confirmation_index]),
                    type=swing.type,
                    price=swing.price,
                )
                for swing in retained_swings
            ),
        )

    def calculate_from_state(
        self,
        metrics: pd.DataFrame,
        state: ScannerState,
    ) -> tuple[Swing, ...]:
        """Resume swing detection from stable state identities."""
        self._reset(metrics)

        if state.candidate is None:
            raise ValueError("ScannerState must contain an active swing candidate.")

        last_closed_index = self._bar_index_for_key(
            state.last_closed_bar,
            "last_closed_bar",
        )
        candidate_index = self._bar_index_for_key(
            state.candidate.bar_key,
            "candidate.bar_key",
        )

        self._state = state.search_state
        self._candidate = CandidateSwing(
            bar_index=candidate_index,
            week_beginning=state.candidate.bar_key,
            type=state.candidate.type,
            price=state.candidate.price,
        )
        self._swings = [
            self._restore_swing(metrics, swing_state)
            for swing_state in state.confirmed_swings
        ]
        self._classified_swings.clear()

        self._find_potential_swings(
            start_index=last_closed_index + 1,
            initialize=False,
        )

        return tuple(self._swings)

    def _bar_index_for_key(
        self,
        bar_key: str,
        field_name: str,
    ) -> int:
        assert self._weeks is not None
        matches = [index for index, week in enumerate(self._weeks) if str(week) == bar_key]
        if not matches:
            raise ValueError(f"ScannerState {field_name} is not present in metrics.")
        if len(matches) > 1:
            raise ValueError(f"Metrics contain duplicate bar identity: {bar_key!r}.")
        return matches[0]

    def _restore_swing(
        self,
        metrics: pd.DataFrame,
        swing_state: ConfirmedSwingState,
    ) -> Swing:
        pivot_index = self._bar_index_for_key(
            swing_state.pivot_bar_key,
            "confirmed_swings.pivot_bar_key",
        )
        confirmation_index = self._bar_index_for_key(
            swing_state.confirmation_bar_key,
            "confirmed_swings.confirmation_bar_key",
        )
        return Swing(
            type=swing_state.type,
            price=swing_state.price,
            bar_index=pivot_index,
            confirmation_index=confirmation_index,
            week_beginning=swing_state.pivot_bar_key,
            metrics_index=pivot_index,
        )

    def _reset(
        self,
        df: pd.DataFrame,
    ) -> None:
        """Reset analyzer state."""
        if df.empty:
            raise ValueError("TrendAnalyzer received an empty DataFrame.")

        self._df = df
        self._high = df[COL_HIGH].to_numpy()
        self._low = df[COL_LOW].to_numpy()
        self._open = df[COL_OPEN].to_numpy()
        self._close = df[COL_CLOSE].to_numpy()
        self._volume = df[COL_VOLUME].to_numpy()
        self._weeks = df[COL_WEEK].tolist()
        self._avg_spread = df[COL_AVG_SPREAD].to_numpy()
        self._state = SwingSearchState.TRACKING_HIGH
        self._candidate = None
        self._swings.clear()
        self._classified_swings.clear()

    # -------------------------------------------------------------------------
    # Swing Detection
    # -------------------------------------------------------------------------
    def _find_potential_swings(
        self,
        start_index: int = 1,
        initialize: bool = True,
    ) -> None:
        """Detect confirmed swing highs and swing lows."""
        assert self._df is not None
        if self._df.empty:
            return
        if initialize:
            self._initialize_candidate(0)
        assert self._candidate is not None

        for bar_index in range(start_index, len(self._df)):
            if self._state in (
                SwingSearchState.TRACKING_HIGH,
                SwingSearchState.TRACKING_LOW,
            ):
                self._update_candidate(bar_index)
                if self._is_reversal_confirmed(bar_index):
                    if self._state == SwingSearchState.TRACKING_HIGH:
                        self._state = SwingSearchState.WAITING_HIGH_CONFIRMATION
                    else:
                        self._state = SwingSearchState.WAITING_LOW_CONFIRMATION
                    continue

            if self._state == SwingSearchState.WAITING_HIGH_CONFIRMATION:
                if bar_index - self._candidate.bar_index >= config.MIN_SWING_CONFIRMATION_BARS:
                    self._confirm_candidate(bar_index)
            elif self._state == SwingSearchState.WAITING_LOW_CONFIRMATION:
                if bar_index - self._candidate.bar_index >= config.MIN_SWING_CONFIRMATION_BARS:
                    self._confirm_candidate(bar_index)

    def _initialize_candidate(self, bar_index: int) -> None:
        if self._state == SwingSearchState.TRACKING_HIGH:
            self._candidate = CandidateSwing(
                bar_index=bar_index,
                week_beginning=self._weeks[bar_index],
                type=SwingType.HIGH,
                price=float(self._high[bar_index]),
            )
        else:
            self._candidate = CandidateSwing(
                bar_index=bar_index,
                week_beginning=self._weeks[bar_index],
                type=SwingType.LOW,
                price=float(self._low[bar_index]),
            )

    def _update_candidate(self, bar_index: int) -> None:
        assert self._candidate is not None
        if self._state == SwingSearchState.TRACKING_HIGH:
            if self._high[bar_index] > self._candidate.price:
                self._candidate.bar_index = bar_index
                self._candidate.week_beginning = self._weeks[bar_index]
                self._candidate.price = float(self._high[bar_index])
            return
        if self._state == SwingSearchState.TRACKING_LOW:
            if self._low[bar_index] < self._candidate.price:
                self._candidate.bar_index = bar_index
                self._candidate.week_beginning = self._weeks[bar_index]
                self._candidate.price = float(self._low[bar_index])
            return

    def _is_reversal_confirmed(self, confirmation_index: int) -> bool:
        assert self._candidate is not None
        bars_since_candidate = confirmation_index - self._candidate.bar_index
        if bars_since_candidate < config.MIN_SWING_CONFIRMATION_BARS:
            return False
        threshold = self._reversal_threshold(confirmation_index)
        if self._state == SwingSearchState.TRACKING_HIGH:
            if self._candidate.price - self._low[confirmation_index] < threshold:
                return False
        elif self._high[confirmation_index] - self._candidate.price < threshold:
            return False
        else:
            return self._is_structurally_confirmed(confirmation_index)
        return self._is_structurally_confirmed(confirmation_index)

    def _reversal_threshold(self, bar_index: int) -> float:
        avg_spread = max(float(self._avg_spread[bar_index]), 0.01)
        return avg_spread * config.SWING_REVERSAL_SPREAD_MULTIPLIER

    def _confirm_candidate(self, confirmation_index: int) -> None:
        assert self._candidate is not None
        swing = Swing(
            bar_index=self._candidate.bar_index,
            confirmation_index=confirmation_index,
            week_beginning=self._candidate.week_beginning,
            type=self._candidate.type,
            price=self._candidate.price,
            metrics_index=self._candidate.bar_index,
        )
        self._swings.append(swing)
        Log.debug(
            "Confirmed %s swing at %.2f (bar=%d, confirmed=%d)",
            swing.type.name,
            swing.price,
            swing.bar_index,
            confirmation_index,
        )
        if self._state == SwingSearchState.WAITING_HIGH_CONFIRMATION:
            self._state = SwingSearchState.TRACKING_LOW
        elif self._state == SwingSearchState.WAITING_LOW_CONFIRMATION:
            self._state = SwingSearchState.TRACKING_HIGH
        else:
            raise RuntimeError(f"Unknown swing search state: {self._state}")
        self._initialize_candidate(confirmation_index)
        assert self._candidate is not None

    def _is_structurally_confirmed(self, confirmation_index: int) -> bool:
        assert self._candidate is not None
        if confirmation_index < self._candidate.bar_index + 2:
            return False
        if self._state == SwingSearchState.TRACKING_HIGH:
            high1 = self._high[confirmation_index - 1]
            high2 = self._high[confirmation_index]
            return self._candidate.price > high1 and high1 > high2
        low1 = self._low[confirmation_index - 1]
        low2 = self._low[confirmation_index]
        return self._candidate.price < low1 and low1 < low2
