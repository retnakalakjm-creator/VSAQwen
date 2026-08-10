from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from models import (
    EvidenceStrength,
    SmartMoneyEvidence,
    SwingContext,
)


class BaseEvidenceRule(ABC):
    """
    Base class for all Smart Money evidence rules.
    """
    WEIGHT: float = 1.0

    def __call__(
        self,
        ctx: SwingContext,
    ) -> SmartMoneyEvidence | None:

        if not self._validate(ctx):
            return None

        if not self._detect(ctx):
            return None

        confidence = self._calculate_confidence(ctx)

        return self._build_evidence(
            ctx,
            confidence,
        )

    def _validate(
        self,
        ctx: SwingContext,
    ) -> bool:
        """
        Override only if validation is required.
        """

        return True
    

    # ------------------------------------------
    # Internal helpers
    # ------------------------------------------
    def _metrics(
        self,
        ctx: SwingContext,
    ) -> pd.Series:
        """
        Metrics row corresponding to the current swing.
        """

        index = ctx.swing.metrics_index

        if index is None:
            raise ValueError(
                "Swing.metrics_index is None."
            )

        return ctx.metrics.iloc[index]



    def _metric(
        self,
        ctx: SwingContext,
        column: str,
    ) -> float:
        """
        Return one metric value for the current swing.
        """

        value = self._metrics(ctx)[column]

        if pd.isna(value):
            raise ValueError(
                f"Metric '{column}' is NaN."
            )

        return float(value)

    def _safe_confidence(
        self,
        value: float,
    ) -> float:
        """
        Clamp confidence into [0,1].
        """

        return max(
            0.0,
            min(
                1.0,
                value,
            ),
        )

    def _mean_confidence(
        self,
        *values: float,
    ) -> float:
        """
        Mean confidence from normalized inputs.
        """

        if not values:
            return 0.0

        return self._safe_confidence(
            sum(values) / len(values)
        )

    def _percentile(
        self,
        ctx: SwingContext,
        column: str,
    ) -> float:
        """
        Return percentile normalized to [0,1].
        """

        return self._safe_confidence(
            self._metric(
                ctx,
                column,
            ) / 100.0
        )

       


    @abstractmethod
    def _detect(
        self,
        ctx: SwingContext,
    ) -> bool:
        ...

    @abstractmethod
    def _calculate_confidence(
        self,
        ctx: SwingContext,
    ) -> float:
        """
        Calculate confidence for the detected evidence.
        """
        ...
        ...

    @abstractmethod
    def _build_evidence(
        self,
        ctx: SwingContext,
        confidence: float,
    ) -> SmartMoneyEvidence:
        ...


    def _strength(
        self,
        confidence: float,
    ) -> EvidenceStrength:
        """
        Convert confidence into a qualitative strength.
        """

        confidence = self._safe_confidence(confidence)

        if confidence >= 0.90:
            return EvidenceStrength.MAJOR

        if confidence >= 0.75:
            return EvidenceStrength.STRONG

        if confidence >= 0.55:
            return EvidenceStrength.MODERATE

        return EvidenceStrength.WEAK    