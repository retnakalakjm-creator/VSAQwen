from __future__ import annotations

from engine.columns import (
    COL_CLOSE_RATIO,
    COL_SPREAD_PERCENTILE,
    COL_VOLUME_PERCENTILE,
)

from models import SwingContext

from .base_rule import BaseEvidenceRule


class BasePercentileRule(BaseEvidenceRule):
    """
    Base class for percentile-based Smart Money rules.

    Provides standardized helpers for reading normalized
    metrics, threshold comparisons, and confidence scoring.
    """

    # ---------------------------------------------------------
    # Metric accessors
    # ---------------------------------------------------------

    def _volume_percentile(
        self,
        ctx: SwingContext,
    ) -> float:
        return self._metric(
            ctx,
            COL_VOLUME_PERCENTILE,
        )

    def _spread_percentile(
        self,
        ctx: SwingContext,
    ) -> float:
        return self._metric(
            ctx,
            COL_SPREAD_PERCENTILE,
        )

    def _close_ratio(
        self,
        ctx: SwingContext,
    ) -> float:
        return self._metric(
            ctx,
            COL_CLOSE_RATIO,
        )

    # ---------------------------------------------------------
    # Threshold helpers
    # ---------------------------------------------------------

    @staticmethod
    def _at_least(
        value: float,
        threshold: float,
    ) -> bool:
        return value >= threshold

    @staticmethod
    def _at_most(
        value: float,
        threshold: float,
    ) -> bool:
        return value <= threshold

    @staticmethod
    def _between(
        value: float,
        minimum: float,
        maximum: float,
    ) -> bool:
        return minimum <= value <= maximum

    # ---------------------------------------------------------
    # Confidence
    # ---------------------------------------------------------

    def _confidence_from(
        self,
        *values: float,
    ) -> float:

        normalized = [
            v / 100 if v > 1 else v
            for v in values
        ]

        return self._mean_confidence(
            *normalized,
        )