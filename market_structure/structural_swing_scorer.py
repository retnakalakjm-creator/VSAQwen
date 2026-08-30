from __future__ import annotations

import config

from models import (
    StructuralSwingEvaluation,
    StructuralSwingScore,
    SwingContext,
    SwingHistorySnapshot,
)
from utils.ranking import percentile_rank, percentile_rank_sorted
from collections.abc import Sequence

from line_profiler import profile


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
        self._price_weight = config.STRUCTURE_PRICE_WEIGHT
        self._structural_size_weight = config.STRUCTURE_STRUCTURAL_SIZE_WEIGHT
        self._duration_weight = config.STRUCTURE_DURATION_WEIGHT
        self._volume_weight = config.STRUCTURE_VOLUME_WEIGHT
        self._spread_weight = config.STRUCTURE_SPREAD_WEIGHT
        self._total_weight = (
            self._price_weight
            + self._structural_size_weight
            + self._duration_weight
            + self._volume_weight
            + self._spread_weight
        )

    @profile
    def score(
        self,
        ctx: SwingContext,
    ) -> StructuralSwingEvaluation:

        history = ctx.history
        rank_sorted = percentile_rank_sorted

        amplitude = history.current_amplitude
        amplitude_sample = history.sorted_amplitudes
        price = (
            rank_sorted(amplitude, amplitude_sample)
            if amplitude_sample
            else 0.0
        )

        structural_size_value = history.current_spread_adjusted_amplitude
        structural_size_sample = history.sorted_spread_adjusted_amplitudes
        structural_size = (
            rank_sorted(structural_size_value, structural_size_sample)
            if structural_size_value is not None and structural_size_sample
            else 0.0
        )

        duration = history.current_duration
        duration_sample = history.sorted_durations
        duration_score = (
            rank_sorted(duration, duration_sample)
            if duration_sample
            else 0.0
        )

        volume = ctx.metrics.volume
        volume_sample = history.sorted_volumes
        volume_score = (
            rank_sorted(volume, volume_sample)
            if volume_sample
            else 0.0
        )

        spread = ctx.metrics.spread
        spread_sample = history.sorted_spreads
        spread_score = (
            rank_sorted(spread, spread_sample)
            if spread_sample
            else 0.0
        )

        return self._combine_scores(
            snapshot=history,
            price=price,
            structural_size=structural_size,
            duration=duration_score,
            volume=volume_score,
            spread=spread_score,
        )

    def _prepared_values(
        self,
        *,
        snapshot: SwingHistorySnapshot,
        volume: float,
        spread: float,
    ) -> tuple[float, float, float, float, float, float]:
        rank_sorted = percentile_rank_sorted

        amplitude = snapshot.current_amplitude
        amplitude_sample = snapshot.sorted_amplitudes
        price = (
            rank_sorted(amplitude, amplitude_sample)
            if amplitude_sample
            else 0.0
        )

        structural_size_value = snapshot.current_spread_adjusted_amplitude
        structural_size_sample = snapshot.sorted_spread_adjusted_amplitudes
        structural_size = (
            rank_sorted(structural_size_value, structural_size_sample)
            if structural_size_value is not None and structural_size_sample
            else 0.0
        )

        duration = snapshot.current_duration
        duration_sample = snapshot.sorted_durations
        duration_score = (
            rank_sorted(duration, duration_sample)
            if duration_sample
            else 0.0
        )

        volume_sample = snapshot.sorted_volumes
        volume_score = (
            rank_sorted(volume, volume_sample)
            if volume_sample
            else 0.0
        )

        spread_sample = snapshot.sorted_spreads
        spread_score = (
            rank_sorted(spread, spread_sample)
            if spread_sample
            else 0.0
        )

        total_weight = self._total_weight
        if total_weight <= 0:
            overall = 0.0
        else:
            overall = min(
                (
                    price * self._price_weight
                    + structural_size * self._structural_size_weight
                    + duration_score * self._duration_weight
                    + volume_score * self._volume_weight
                    + spread_score * self._spread_weight
                ) / total_weight,
                1.0,
            )

        return (
            price,
            structural_size,
            duration_score,
            volume_score,
            spread_score,
            overall,
        )

    @profile
    def score_prepared(
        self,
        *,
        snapshot: SwingHistorySnapshot,
        volume: float,
        spread: float,
    ) -> StructuralSwingEvaluation:
        """
        Score a prepared swing directly from its history snapshot and
        current scalar metrics, avoiding SwingContext construction.
        """

        (
            price,
            structural_size,
            duration_score,
            volume_score,
            spread_score,
            overall,
        ) = self._prepared_values(
            snapshot=snapshot,
            volume=volume,
            spread=spread,
        )

        return StructuralSwingEvaluation(
            score=StructuralSwingScore(
                price=price,
                structural_size=structural_size,
                duration=duration_score,
                volume=volume_score,
                spread=spread_score,
                overall=overall,
            ),
            snapshot=snapshot,
        )

    # ------------------------------------------
    # Internal helpers
    # ------------------------------------------
    def _percentile_score(
        self,
        value: float | None,
        sample: Sequence[float],
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

        return percentile_rank_sorted(value, sample)

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

    @profile
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

        total_weight = self._total_weight

        if total_weight <= 0:
            overall = 0.0
        else:
            overall = min(
                (
                    price * self._price_weight
                    + structural_size * self._structural_size_weight
                    + duration * self._duration_weight
                    + volume * self._volume_weight
                    + spread * self._spread_weight
                ) / total_weight,
                1.0,
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
