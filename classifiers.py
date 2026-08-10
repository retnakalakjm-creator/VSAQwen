"""
Professional VSA Swing Scanner
Classification Engine

Converts quantitative market metrics into semantic
VSA classifications used throughout the system.

Responsibilities
----------------
• Classify spread
• Classify volume
• Classify direction
• Classify close position

This module performs no VSA interpretation.
It only converts numerical metrics into
semantic enums consumed by the Trend,
Background and Pattern engines.
"""

from __future__ import annotations
import math




from config import (
    PercentileThresholds,
    SPREAD_THRESHOLDS,
    VOLUME_THRESHOLDS,
)
from models import (    
    ClassificationBucket,
    ClosePosition,
    Direction,
    SpreadClass,
    VolumeClass,
)


# =============================================================================
# Private Classifiers
# =============================================================================

class PercentileClassifier:
    """
    Generic percentile classifier.

    Converts a rolling percentile into one of seven generic buckets,
    then maps those buckets to the appropriate enum.
    """

    _SPREAD_MAPPING = {
        ClassificationBucket.ULTRA_LOW: SpreadClass.NARROW,
        ClassificationBucket.VERY_LOW: SpreadClass.BELOW_AVERAGE,
        
        # Spread has six semantic levels.
        # LOW and AVERAGE percentile buckets
        # both map to an average spread.
        ClassificationBucket.LOW: SpreadClass.AVERAGE,        
        
        ClassificationBucket.AVERAGE: SpreadClass.AVERAGE,
        ClassificationBucket.HIGH: SpreadClass.ABOVE_AVERAGE,
        ClassificationBucket.VERY_HIGH: SpreadClass.WIDE,
        ClassificationBucket.ULTRA_HIGH: SpreadClass.VERY_WIDE,
    }

    _VOLUME_MAPPING = {
        ClassificationBucket.ULTRA_LOW: VolumeClass.ULTRA_LOW,
        ClassificationBucket.VERY_LOW: VolumeClass.VERY_LOW,
        ClassificationBucket.LOW: VolumeClass.LOW,
        ClassificationBucket.AVERAGE: VolumeClass.AVERAGE,        
        ClassificationBucket.HIGH: VolumeClass.HIGH,
        ClassificationBucket.VERY_HIGH: VolumeClass.VERY_HIGH,
        ClassificationBucket.ULTRA_HIGH: VolumeClass.ULTRA_HIGH,
    }

    @staticmethod
    def _classify(
        percentile: float,
        thresholds: PercentileThresholds,
    ) -> ClassificationBucket:
        """
        Convert a percentile into a generic classification bucket.
        """
        if math.isnan(percentile):
            raise ValueError("Percentile cannot be NaN.")


        if not 0.0 <= percentile <= 100.0:
            raise ValueError(
                f"Invalid percentile: {percentile}"
            )    
        

        if percentile <= thresholds.ultra_low:
            return ClassificationBucket.ULTRA_LOW
         
        if percentile <= thresholds.very_low:
            return ClassificationBucket.VERY_LOW

        if percentile <= thresholds.low:
            return ClassificationBucket.LOW

        if percentile < thresholds.high:
            return ClassificationBucket.AVERAGE

        if percentile < thresholds.very_high:
            return ClassificationBucket.HIGH

        if percentile < thresholds.ultra_high:
            return ClassificationBucket.VERY_HIGH

        return ClassificationBucket.ULTRA_HIGH

    @classmethod
    def classify_spread(
        cls,
        percentile: float,
        thresholds: PercentileThresholds,
    ) -> SpreadClass:
        """
        Classify spread percentile.
        """

        bucket = cls._classify(
            percentile,
            thresholds,
        )

        return cls._SPREAD_MAPPING[bucket]

    @classmethod
    def classify_volume(
        cls,
        percentile: float,
        thresholds: PercentileThresholds,
    ) -> VolumeClass:
        """
        Classify volume percentile.
        """

        bucket = cls._classify(
            percentile,
            thresholds,
        )
                
        return cls._VOLUME_MAPPING[bucket]


# ---------------------------------------------------------------------
# Public wrappers
# ---------------------------------------------------------------------



def classify_spread(
    percentile: float,
) -> SpreadClass:
    """
    Classify spread percentile.
    """

    return PercentileClassifier.classify_spread(
        percentile,
        SPREAD_THRESHOLDS,
    )


def classify_volume(
    percentile: float,
) -> VolumeClass:
    """
    Classify volume percentile.
    """

    return PercentileClassifier.classify_volume(
        percentile,
        VOLUME_THRESHOLDS,
    )


# ---------------------------------------------------------------------
# Existing classifiers
# ---------------------------------------------------------------------


def classify_direction(
    open_: float,
    close: float,
) -> Direction:
    """
    Classify bar direction.
    """

    if close > open_:
        return Direction.UP

    if close < open_:
        return Direction.DOWN

    return Direction.NEUTRAL


def classify_close_position(
    close_ratio: float,
) -> ClosePosition:
    """
    Classify closing position inside the bar.
    """

    if not 0.0 <= close_ratio <= 1.0:
        raise ValueError(f"Invalid close ratio: {close_ratio}")

    if close_ratio <= 0.10:
        return ClosePosition.ON_LOW

    if close_ratio <= 0.35:
        return ClosePosition.LOWER

    if close_ratio <= 0.65:
        return ClosePosition.MIDDLE

    if close_ratio <= 0.90:
        return ClosePosition.UPPER

    return ClosePosition.ON_HIGH

