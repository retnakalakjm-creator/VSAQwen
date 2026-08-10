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


# =============================================================================
# Internal Models
# =============================================================================
@dataclass(slots=True)
class CandidateSwing:
    """
    Internal representation of a potential swing.

    A CandidateSwing is not confirmed until the TrendAnalyzer
    validates it using the swing confirmation rules.
    """

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
        """
        Detect and classify all confirmed swings.
        """

        self._reset(metrics)

        self._find_potential_swings()

        #self._classify_swings()

        return tuple(self._swings)

    def _reset(
        self,
        df: pd.DataFrame,
    ) -> None:
        """
        Reset analyzer state.
        """
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

    def _find_potential_swings(self) -> None:
        """
        Detect confirmed swing highs and swing lows.

        The algorithm maintains a single swing candidate and
        confirms it only after a sufficient reversal.
        """

        assert self._df is not None

        if self._df.empty:
            return

        # Initialize first candidate.
        self._initialize_candidate(0)
        
        assert self._candidate is not None

        # Process remaining bars.
        for bar_index in range(1, len(self._df)):

            

            # ------------------------------
            # Tracking
            # ------------------------------

            if self._state in (
                SwingSearchState.TRACKING_HIGH,
                SwingSearchState.TRACKING_LOW,
            ):
                
                self._update_candidate(bar_index)

                if self._is_reversal_confirmed(bar_index):

                    if self._state == SwingSearchState.TRACKING_HIGH:
                        self._state = (
                            SwingSearchState.WAITING_HIGH_CONFIRMATION
                        )

                    else:
                        self._state = (
                            SwingSearchState.WAITING_LOW_CONFIRMATION
                        )
                    continue
            # ------------------------------
            # Waiting for confirmation
            # ------------------------------

            if (
                self._state
                == SwingSearchState.WAITING_HIGH_CONFIRMATION
            ):

                if (
                    bar_index - self._candidate.bar_index
                    >= config.MIN_SWING_CONFIRMATION_BARS
                ):
                    self._confirm_candidate(bar_index)

            elif (
                self._state
                == SwingSearchState.WAITING_LOW_CONFIRMATION
            ):

                if (
                    bar_index - self._candidate.bar_index
                    >= config.MIN_SWING_CONFIRMATION_BARS
                ):
                    self._confirm_candidate(bar_index)      

    def _initialize_candidate(
        self,
        bar_index: int,
    ) -> None:
        """
        Initialize a new swing candidate.

        Parameters
        ----------
        bar_index
        Index of the bar that becomes the initial candidate.
        """

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


    def _update_candidate(
        self,
        bar_index: int,
    ) -> None:

        assert self._candidate is not None

        if self._state == SwingSearchState.TRACKING_HIGH:

            if self._high[bar_index] > self._candidate.price:

                self._candidate.bar_index = bar_index
                self._candidate.week_beginning = self._weeks[bar_index]
                self._candidate.price = float(
                    self._high[bar_index]
                )

            return

        if self._state == SwingSearchState.TRACKING_LOW:

            if self._low[bar_index] < self._candidate.price:

                self._candidate.bar_index = bar_index
                self._candidate.week_beginning = self._weeks[bar_index]
                self._candidate.price = float(
                    self._low[bar_index]
                )

            return

        # Candidate is frozen while waiting for confirmation.
        return
            
            
    def _is_reversal_confirmed(
        self,
        confirmation_index: int,
    ) -> bool:

        assert self._candidate is not None

        bars_since_candidate = (
            confirmation_index
            - self._candidate.bar_index
        )

        if bars_since_candidate < config.MIN_SWING_CONFIRMATION_BARS:
            return False

        threshold = self._reversal_threshold(
            confirmation_index
        )

        if self._state == SwingSearchState.TRACKING_HIGH:

            if (
                self._candidate.price
                - self._low[confirmation_index]
            ) < threshold:
                return False

            return self._is_structurally_confirmed(
                confirmation_index
            )

        if (
            self._high[confirmation_index]
            - self._candidate.price
        ) < threshold:
            return False

        return self._is_structurally_confirmed(
            confirmation_index
        )      
            
   
    def _reversal_threshold(
        self,
        bar_index: int,
    ) -> float:
        """
        Calculate the minimum reversal required to confirm
        a swing at the specified bar.
        """

        avg_spread = max(
            float(self._avg_spread[bar_index]),
            0.01,
        )
        
        return (
            avg_spread
            * config.SWING_REVERSAL_SPREAD_MULTIPLIER
        )
            

    def _confirm_candidate(
        self,
        confirmation_index: int,
    ) -> None:
        """
        Confirm the current swing candidate.
        """

        assert self._candidate is not None

        # ------------------------------------------------------------------
        # Create immutable Swing
        # ------------------------------------------------------------------

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

        # ------------------------------------------------------------------
        # Switch search direction
        # ------------------------------------------------------------------

        if self._state == SwingSearchState.WAITING_HIGH_CONFIRMATION:
            self._state = SwingSearchState.TRACKING_LOW
        elif self._state == SwingSearchState.WAITING_LOW_CONFIRMATION:
            self._state = SwingSearchState.TRACKING_HIGH    
        else:
            raise RuntimeError(
                f"Unknown swing search state: {self._state}"
            )    
        # ------------------------------------------------------------------
        # Start searching from the confirmation bar
        # ------------------------------------------------------------------

        self._initialize_candidate(confirmation_index)
        assert self._candidate is not None

    
    def _is_structurally_confirmed(
        self,
        confirmation_index: int,
    ) -> bool:

        assert self._candidate is not None

        # Need two completed bars after the candidate.
        if confirmation_index < self._candidate.bar_index + 2:
            return False

        if self._state == SwingSearchState.TRACKING_HIGH:

            high1 = self._high[confirmation_index - 1]
            high2 = self._high[confirmation_index]

            return (
                high1 < self._candidate.price
                and high2 < high1
            )

        low1 = self._low[confirmation_index - 1]
        low2 = self._low[confirmation_index]

        return (
            low1 > self._candidate.price
            and low2 > low1
        )                  