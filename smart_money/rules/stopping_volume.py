from __future__ import annotations

from engine.columns import (
    COL_CLOSE_RATIO,
    COL_SPREAD_PERCENTILE,
    COL_VOLUME_PERCENTILE,
)

from config import (
    STOPPING_VOLUME_MIN_CLOSE_RATIO,
    STOPPING_VOLUME_MIN_SPREAD_PERCENTILE,
    STOPPING_VOLUME_MIN_VOLUME_PERCENTILE,
)

from models import (
    EvidenceCategory,
    EvidenceCode,
    EvidenceDirection,
    EvidenceStrength,
    SmartMoneyEvidence,
    SwingContext,
)

from smart_money.base_rule import BaseEvidenceRule


class StoppingVolumeRule(BaseEvidenceRule):
    """
    Classical Tom Williams Stopping Volume.

    Detects evidence only.

    This rule does NOT issue a buy signal.
    """

    DESCRIPTION = (
        "Stopping Volume detected after a decline. "
        "Professional buying is absorbing supply."
    )

    def _detect(
        self,
        ctx: SwingContext,
    ) -> bool:
        """
        Detect classical Stopping Volume.

        Conditions
        ----------
        • Previous swing exists
        • Exceptionally high volume
        • Wide spread
        • Strong close
        """

        history_ok = ctx.history.has_previous

        volume_ok = (
            self._metric(
                ctx,
                COL_VOLUME_PERCENTILE,
            )
            >= STOPPING_VOLUME_MIN_VOLUME_PERCENTILE
        )

        spread_ok = (
            self._metric(
                ctx,
                COL_SPREAD_PERCENTILE,
            )
            >= STOPPING_VOLUME_MIN_SPREAD_PERCENTILE
        )

        close_ok = (
            self._metric(
                ctx,
                COL_CLOSE_RATIO,
            )
            >= STOPPING_VOLUME_MIN_CLOSE_RATIO
        )

        return (
            history_ok
            and volume_ok
            and spread_ok
            and close_ok
        )

    def _calculate_confidence(
        self,
        ctx: SwingContext,
    ) -> float:
        """
        Confidence is derived from the three primary
        stopping-volume characteristics.
        """

        return self._mean_confidence(

            self._percentile(
                ctx,
                COL_VOLUME_PERCENTILE,
            ),

            self._percentile(
                ctx,
                COL_SPREAD_PERCENTILE,
            ),

            self._safe_confidence(
                self._metric(
                    ctx,
                    COL_CLOSE_RATIO,
                )
            ),
        )

    def _build_evidence(
        self,
        ctx: SwingContext,
        confidence: float,
    ) -> SmartMoneyEvidence:

        return SmartMoneyEvidence(

            code=EvidenceCode.STOPPING_VOLUME,

            category=EvidenceCategory.DEMAND,

            direction=EvidenceDirection.BULLISH,

            strength=self._strength(confidence),

            confidence=confidence,

            weight=self.WEIGHT,

            metrics_index=ctx.swing.metrics_index,

            description=self.DESCRIPTION,

            swing_index=ctx.history.current_index,
        )