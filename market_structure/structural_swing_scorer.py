from __future__ import annotations
import config

from models import (
    StructuralSwingEvaluation,
    StructuralSwingScore,
    SwingContext,
    SwingHistorySnapshot,
)
from utils.ranking import percentile_rank
from collections.abc import Sequence

from utils.scoring import ScoreComponent, combine_scores, component




class StructuralSwingScorer:
    """
    Measure the structural significance of the current
    swing amplitude relative to recent confirmed swings.
    """
    def __init__(
        self,
        *,
        structure_lookback: int,
    ) -> None:

        self._structure_lookback = structure_lookback

    def score(
        self,
        ctx: SwingContext,
    ) -> StructuralSwingEvaluation:

        price  = self._evaluate_amplitude(ctx)

        structural_size = self._evaluate_structural_size(ctx)

        duration = self._evaluate_duration(ctx)

        volume = self._evaluate_volume(ctx)

        spread = self._evaluate_spread(ctx)

        

        return self._combine_scores(
            snapshot=ctx.history,
            price=price,
            structural_size=structural_size,
            duration=duration,
            volume=volume,
            spread=spread,            
        )
    
    
    # ------------------------------------------
    # Internal helpers
    # ------------------------------------------

    def _percentile_score(
        self,
        value: float | None,
        sample: Sequence[float | None],
    ) -> float:
        """
        Convert a value into a normalized percentile score
        relative to a historical sample.

        Returns
        -------
        float
            Score in the range [0.0, 1.0].
        """

        if value is None:
            return 0.0

        # Remove invalid historical values
        if not sample:
            return 0.0

        return percentile_rank(
            value,
            sample,
        )
            
    # ------------------------------------------
    # Individual scoring components
    # ------------------------------------------

    def _evaluate_amplitude(
        self,
        ctx: SwingContext,
    ) -> float:
        """
        Structural importance based on swing amplitude.
        """

        amplitude = ctx.history.current_amplitude

        sample = ctx.history.amplitudes

        return self._percentile_score(
            amplitude,
            sample,
        )
    
    def _evaluate_structural_size(
        self,
        ctx: SwingContext,
    ) -> float:
        """
        Score swing amplitude relative to the
        average spread at the current swing.
        """
            
        value = ctx.history.current_spread_adjusted_amplitude

        sample = ctx.history.spread_adjusted_amplitudes

        return self._percentile_score(
            value,
            sample,
        )
    
    def _evaluate_duration(
        self,
        ctx: SwingContext,
    ) -> float:
        """
        Score swing duration relative to recent history.
        """

        duration = ctx.history.current_duration

        sample = ctx.history.durations

        return self._percentile_score(
            duration,
            sample,
        )
    
    def _evaluate_volume(
        self,
        ctx: SwingContext,
    ) -> float:
        """
        Score swing volume relative to previous
        structural swings.
        """

        volume = ctx.metrics.volume

        sample = ctx.history.volumes

        return self._percentile_score(
            volume,
            sample,
        )

    def _evaluate_spread(
        self,
        ctx: SwingContext,
    ) -> float:
        """
        Score swing spread relative to previous
        structural swings.
        """

        spread = ctx.metrics.spread

        sample = ctx.history.spreads

        return self._percentile_score(
            spread,
            sample,
        )

    # ------------------------------------------
    # Final aggregation
    # ------------------------------------------

    def _combine_scores(
        self,
        *,
        snapshot: SwingHistorySnapshot,
        price: float,
        structural_size: float,
        duration: float,
        volume: float,
        spread: float,
    ) -> StructuralSwingEvaluation:
        
        components = (
            component(
                price,
                config.STRUCTURE_PRICE_WEIGHT,
            ),
            component(
                structural_size,
                config.STRUCTURE_STRUCTURAL_SIZE_WEIGHT,
            ),
            component(
                duration,
                config.STRUCTURE_DURATION_WEIGHT,
            ),
            component(
                volume,
                config.STRUCTURE_VOLUME_WEIGHT,
            ),
            component(
                spread,
                config.STRUCTURE_SPREAD_WEIGHT,
            ),
        )

        overall = combine_scores(
            components,
        )

        return StructuralSwingEvaluation(
            score=StructuralSwingScore(
                price=price,
                structural_size=structural_size,
                duration=duration,
                volume=volume,
                spread=spread,
                overall=overall,
            ),
            snapshot=snapshot,
        )