"""
trend.py

Professional Trend Engine.

Builds market structure from classified weekly bars.

Responsibilities
----------------
- Detect confirmed swing highs and lows
- Classify swings (HH, HL, LH, LL)
- Build trend structure
- Measure trend quality
- Produce TrendResult

Does NOT
--------
- Detect VSA patterns
- Evaluate smart money activity
- Determine Wyckoff phases
- Generate trading signals
"""

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
    TrendDirection,    
    TrendResult,
    TrendState,
    TrendStructure,
    StructuralSwing,
)
from market_structure.swing_engine import CandidateSwing, SwingEngine
from market_structure.structure_filter import StructureFilter

# logger = Log(__name__)


# =============================================================================
# Trend Analyzer
# =============================================================================


class TrendAnalyzer:
    """
    Professional Trend Analysis Engine.

    Pipeline
    --------
        Weekly Bars
              │
              ▼
        Swing Detection
              │
              ▼
        Swing Classification
              │
              ▼
        Trend Structure
              │
              ▼
        Trend Strength
              │
              ▼
          TrendResult
    """

    def __init__(self) -> None:
        
        # Source data
        self._df: pd.DataFrame | None = None
        
        # Cached arrays
        self._weeks: list[str] = []
        
        self._open: np.ndarray | None = None
        self._high: np.ndarray | None = None
        self._low: np.ndarray | None = None
        self._close: np.ndarray | None = None
        self._volume: np.ndarray | None = None
        
        self._avg_spread: np.ndarray | None = None
        
       
        self._classified_swings: list[ClassifiedSwing] = []

        self._swing_engine = SwingEngine()

        self._structure: TrendStructure | None = None

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def analyze(
        self,
        df: pd.DataFrame,
    ) -> TrendResult:

        Log.info("Starting trend analysis.")

        self._reset(df)

        swings = list(
            self._swing_engine.calculate(df)
        )

        structural_swings = StructureFilter().filter(
            swings,
            df,
        )

        self._classified_swings = self._classify_swings(
            structural_swings
        )
        self._structural_swings = structural_swings
        self._create_structure()

        Log.info(
            "Trend analysis completed. Confirmed swings: %d",
            len(self._classified_swings),
        )
        
        return self._build_result()

    # -------------------------------------------------------------------------
    # Initialization
    # -------------------------------------------------------------------------

    def _reset(
        self,
        df: pd.DataFrame,
    ) -> None:

        if df.empty:
            raise ValueError(
                "TrendAnalyzer received an empty DataFrame."
            )

        self._structure = None
    
    # -------------------------------------------------------------------------
    # Trend Engine
    # -------------------------------------------------------------------------
    @staticmethod
    def _calculate_weights(
        size: int,
    ) -> list[float]:

        if size <= 1:
            return [1.0]

        return [
            0.30 + 0.70 * i / (size - 1)
            for i in range(size)
        ]
        

    @staticmethod
    def _weighted_label_counts(
        swings: list[ClassifiedSwing],
    ) -> dict[SwingLabel, float]:
        """
        Calculate recency-weighted counts of
        HH, HL, LH and LL swings.
        """

        swings = swings[-config.TREND_RECENT_SWINGS :]

        counts = {
            SwingLabel.HH: 0.0,
            SwingLabel.HL: 0.0,
            SwingLabel.LH: 0.0,
            SwingLabel.LL: 0.0,
        }

        weights = TrendAnalyzer._calculate_weights(
        len(swings)
    )

        for swing, weight in zip(swings, weights):           

            counts[swing.label] += weight

        return counts        

    @staticmethod
    def _count_labels(
        swings: list[ClassifiedSwing],
    ) -> dict[SwingLabel, float]:

        counts = {
        SwingLabel.HH: 0,
        SwingLabel.HL: 0,
        SwingLabel.LH: 0,
        SwingLabel.LL: 0,
    }

        for swing in swings:

            if swing.label is not None:

                counts[swing.label] += 1

        return counts    
    
   
    @staticmethod
    def _label_counts(
        labels: list[SwingLabel],
    ) -> tuple[int, int]:
        """
        Return bullish and bearish label counts.
        """

        bullish = sum(
            label in (
                SwingLabel.HH,
                SwingLabel.HL,
            )
            for label in labels
        )

        bearish = sum(
            label in (
                SwingLabel.LH,
                SwingLabel.LL,
            )
            for label in labels
        )

        return bullish, bearish
   
   
    @staticmethod
    def _determine_direction(
        weighted_counts: dict[SwingLabel, float],
    ) -> TrendDirection:
                       
        bullish = (
        weighted_counts[SwingLabel.HH]
        + weighted_counts[SwingLabel.HL]
    )

        bearish = (
        weighted_counts[SwingLabel.LH]
        + weighted_counts[SwingLabel.LL]
    )

        total = bullish + bearish
                
        if total == 0:
            return TrendDirection.UNKNOWN
        
        dominance = (bullish - bearish) / total

        if dominance  > config.TREND_DIRECTION_MARGIN:
            return TrendDirection.UP

        if dominance  < -config.TREND_DIRECTION_MARGIN:
            return TrendDirection.DOWN

        return TrendDirection.RANGE
    
    
    @staticmethod
    def _measure_strength(
        weighted_counts: dict[SwingLabel, float],
    ) -> float:

        bullish = (
        weighted_counts[SwingLabel.HH]
        + weighted_counts[SwingLabel.HL]
    )

        bearish = (
        weighted_counts[SwingLabel.LH]
        + weighted_counts[SwingLabel.LL]
    )

        total = bullish + bearish

        if total == 0:
            return 0.0

        dominance = abs(bullish - bearish) / total
        return min(1.0, max(0.0, dominance))
    
    @staticmethod
    def _recent_labels(
        recent: list[ClassifiedSwing],
    ) -> list[SwingLabel]:
        labels = [
            s.label
            for s in recent
            if s.label is not None
        ]

        return labels[-config.TREND_STATE_LOOKBACK:]
    
    @staticmethod
    def _state_metrics(
        recent: list[ClassifiedSwing],
    ) -> tuple[
        list[SwingLabel],
        int,
        int,
        SwingLabel,
    ] | None:
        """
        Prepare the information required by all
        Trend State detectors.

        Returns
        -------
        labels
            Recent swing labels.

        bullish
            Number of bullish labels (HH + HL).

        bearish
            Number of bearish labels (LH + LL).

        latest
            Most recent swing label.
        """

        labels = TrendAnalyzer._recent_labels(recent)

        if len(labels) < config.TREND_STATE_LOOKBACK:
            return None

        bullish, bearish = TrendAnalyzer._label_counts(labels)

        latest = labels[-1]

        return (
            labels,
            bullish,
            bearish,
            latest,
        )     
   
        
    @staticmethod
    def _is_reversing(
        direction: TrendDirection,
        recent: list[ClassifiedSwing],
    ) -> bool:
        """
        Return True when the recent swing structure
        indicates that control has shifted to the
        opposing side.
        """

        state = TrendAnalyzer._state_metrics(recent)

        if state is None:
            return False

        _, bullish, bearish, latest = state

        if direction == TrendDirection.UP:
            return (
                bearish > bullish
                and latest in (
                    SwingLabel.LH,
                    SwingLabel.LL,
                )
            )

        if direction == TrendDirection.DOWN:
            return (
                bullish > bearish
                and latest in (
                    SwingLabel.HH,
                    SwingLabel.HL,
                )
            )

        return False
    
    
    @staticmethod
    def _is_exhausted(
        direction: TrendDirection,
        recent: list[ClassifiedSwing],
    ) -> bool:
        """
        Return True when neither buyers nor sellers
        have a clear structural advantage.

        An exhausted trend has balanced bullish and
        bearish swing evidence.
        """

        state = TrendAnalyzer._state_metrics(recent)

        if state is None:
            return False

        _, bullish, bearish, _ = state

        return bullish == bearish
    
    
    @staticmethod
    def _is_correcting(
        direction: TrendDirection,
        recent: list[ClassifiedSwing],
    ) -> bool:
        """
        Return True when the dominant trend remains intact,
        but recent swings indicate a normal correction.
        """

        state = TrendAnalyzer._state_metrics(recent)

        if state is None:
            return False

        _, bullish, bearish, latest = state

        if direction == TrendDirection.UP:
            return (
                bullish > bearish
                and bearish >= 1
                and latest in (
                    SwingLabel.LH,
                    SwingLabel.LL,
                )
            )

        if direction == TrendDirection.DOWN:
            return (
                bearish > bullish
                and bullish >= 1
                and latest in (
                    SwingLabel.HH,
                    SwingLabel.HL,
                )
            )

        return False
    
    
    @staticmethod
    def _is_healthy(
        direction: TrendDirection,
        recent: list[ClassifiedSwing],
    ) -> bool:
        """
        Return True when the recent classified swings
        continue to support the dominant trend.

        A healthy trend requires:
        - overwhelming majority of swings support the trend
        - latest swing confirms the trend
        """

        state = TrendAnalyzer._state_metrics(recent)

        if state is None:
            return False
       
        _, bullish, bearish, latest = state         

        required = config.TREND_STATE_LOOKBACK - 1

        print("bullish:", bullish)
        print("bearish:", bearish)
        print("latest :", latest)
        print("required:", required)

        if direction == TrendDirection.UP:         
            
            return (
                bullish >= required
                and latest in (
                    SwingLabel.HH,
                    SwingLabel.HL,
                )
            )

        if direction == TrendDirection.DOWN:           

            return (
               bearish >= required
               and latest in (
                    SwingLabel.LH,
                    SwingLabel.LL,
                )
            )
        
        return False        
    
    
    def _determine_state(
        self,
        direction: TrendDirection,
    ) -> TrendState:

        if direction in (
            TrendDirection.UNKNOWN,
            TrendDirection.RANGE,
        ):    
            return TrendState.UNKNOWN  
        
                
        lookback = min(
            len(self._classified_swings),
            config.TREND_RECENT_SWINGS,
        )    
        
        if lookback == 0:
            return TrendState.UNKNOWN

        recent = self._classified_swings[-lookback:]
        
        
        if len(recent) < config.TREND_STATE_LOOKBACK:
            return TrendState.UNKNOWN
        
        if self._is_reversing(direction, recent):
            return TrendState.REVERSING

        if self._is_exhausted(direction, recent):
            return TrendState.EXHAUSTED

        if self._is_correcting(direction, recent):
            return TrendState.CORRECTING

        if self._is_healthy(direction, recent):
            return TrendState.HEALTHY        
        

        return TrendState.DEVELOPING    
    

    @staticmethod
    def _measure_confidence(
        direction: TrendDirection,
        state: TrendState,
        strength: float,
        swing_count: int,
    ) -> float:
        """
        Calculate confidence in the detected trend.
        """

        if direction in (
            TrendDirection.UNKNOWN,
            TrendDirection.RANGE,
        ):    
            return 0.0
        
        # ----------------------------
        # State score
        # ----------------------------
        state_score = config.TREND_STATE_SCORES[state]
        
        # ----------------------------
        # Swing maturity
        # ----------------------------
        maturity = min(
            swing_count / config.TREND_RECENT_SWINGS,
            1.0,
        )
        
        confidence = (
            config.TREND_CONFIDENCE_STRENGTH_WEIGHT * strength 
            + config.TREND_CONFIDENCE_STATE_WEIGHT * state_score
            + config.TREND_CONFIDENCE_MATURITY_WEIGHT * maturity
        )
        
        return max(0.0, min(confidence, 1.0))   
    
    
    
    def _create_structure(self) -> None:
        """
        Create the structural trend interpretation
        from the classified swings.
        """

        swings = self._classified_swings
        swing_count = len(swings)

        raw_counts = self._count_labels(swings)

        weighted_counts = self._weighted_label_counts(swings)

        direction = self._determine_direction(weighted_counts)

        strength = self._measure_strength(weighted_counts)

        state = self._determine_state(direction)

        confidence = self._measure_confidence(
            direction=direction,
            state=state,
            strength=strength,
            swing_count=swing_count,
        )

        self._structure = TrendStructure(
            direction=direction,
            state=state,
            strength=strength,
            confidence=confidence,
            swing_count=swing_count,
            swings=tuple(swings),
            structural_swings=tuple(self._structural_swings),
            hh_count=raw_counts[SwingLabel.HH],
            hl_count=raw_counts[SwingLabel.HL],
            lh_count=raw_counts[SwingLabel.LH],
            ll_count=raw_counts[SwingLabel.LL],
        )
        
    # ------------------------------------------------------------------
    # Swing Classification
    # ------------------------------------------------------------------
    @staticmethod
    def _classify_swing(
            current: Swing,
            previous: Swing | None,
        ) -> SwingLabel | None:
            """
            Classify a confirmed swing relative to the previous
            confirmed swing of the same type.
    
            Returns
            -------
            SwingLabel | None
    
            None is returned for the first swing of each type,
            which serves as the reference swing for future
            classification.
            """
    
            if previous is None:
                return None
    
            match current.type:
    
                case SwingType.HIGH:
    
                    if current.price > previous.price:
                        return SwingLabel.HH
    
                    return SwingLabel.LH
    
                case SwingType.LOW:
    
                    if current.price > previous.price:
                        return SwingLabel.HL
    
                    return SwingLabel.LL
    
    def _classify_swings(
        self,
        swings: list[StructuralSwing],
    ) -> list[ClassifiedSwing]:
        """
        Classify confirmed swings as HH, HL, LH or LL.
        """

        previous_high: Swing | None = None
        previous_low: Swing | None = None

        classified: list[ClassifiedSwing] = []

        for swing in swings:

            if swing.swing.type == SwingType.HIGH:

                label = self._classify_swing(
                    current=swing.swing,
                    previous=previous_high,
                )

                previous_high = swing.swing

            else:

                label = self._classify_swing(
                    current=swing.swing,
                    previous=previous_low,
                )

                previous_low = swing.swing

            if label is not None:

                classified.append(
                    ClassifiedSwing(
                        swing=swing.swing,
                        label=label,
                    )
                )

        return classified  
    # -------------------------------------------------------------------------
    # Result Builder
    # -------------------------------------------------------------------------

    def _build_result(self) -> TrendResult:
        """
        Build the final TrendResult.
        """

        assert self._structure is not None

        return TrendResult(
            structure=self._structure,
    )


__all__ = [
    "TrendAnalyzer",
]
