from __future__ import annotations

import pandas as pd
import config

from models import (
    Swing,
    StructuralSwing,
    SwingGrade,
)
from .professional_scorer import ProfessionalScorer
from line_profiler import profile


class StructureFilter:
    """Converts confirmed micro swings into structurally significant swings."""

    DEFAULT_INTERMEDIATE_GRADE_SCORE = 0.65
    DEFAULT_MAJOR_GRADE_SCORE = 0.80

    @profile
    def filter(
        self,
        swings: list[Swing] | tuple[Swing, ...],
        metrics: pd.DataFrame,
    ) -> list[StructuralSwing]:
        self._metrics = metrics
        structural: list[StructuralSwing] = []
        swing_tuple = tuple(swings)
        batch = ProfessionalScorer().score_batch(
            swing_tuple,
            metrics,
        )

        for index, current in enumerate(swing_tuple):
            if index == 0:
                continue

            professional_overall = batch.professional_overall(index)
            if professional_overall is None:
                continue
            if not self._is_structural(professional_overall):
                continue

            evaluation = batch.evaluation(
                index,
                include_components=True,
            )
            if evaluation is None:
                continue

            structural.append(
                StructuralSwing(
                    swing=current,
                    evaluation=evaluation,
                    grade=self._grade_swing(professional_overall),
                )
            )

        return structural

    def filter_incremental(
        self,
        swings: tuple[Swing, ...] | list[Swing],
        metrics: pd.DataFrame,
        *,
        cached: tuple[StructuralSwing, ...],
        previous_swing_count: int,
    ) -> list[StructuralSwing]:
        """Extend stable structural evaluations for newly confirmed swings.

        A confirmed swing's professional evaluation uses only that swing and
        earlier point-in-time history. Previously evaluated swings therefore do
        not need to be rescored when a later bar adds no new confirmed swing.

        The bounded window includes one extra leading swing so the existing
        batch-history preparation sees the same lookback membership as a full
        history calculation.
        """

        swing_tuple = tuple(swings)
        if previous_swing_count < 0 or previous_swing_count > len(swing_tuple):
            raise ValueError("previous_swing_count is outside current swings")

        if previous_swing_count == 0:
            return self.filter(list(swing_tuple), metrics)

        structural = list(cached)
        if previous_swing_count == len(swing_tuple):
            return structural

        for index in range(previous_swing_count, len(swing_tuple)):
            window_start = max(0, index - config.STRUCTURE_LOOKBACK)
            window = swing_tuple[window_start : index + 1]
            target = swing_tuple[index]
            scored = self.filter(list(window), metrics)
            match = next(
                (item for item in scored if item.swing == target),
                None,
            )
            if match is not None:
                structural.append(match)

        return structural

    def _grade_swing(
        self,
        score: float,
    ) -> SwingGrade:
        """Map a structural swing score into an importance grade."""
        major_threshold = getattr(
            config,
            "STRUCTURE_MAJOR_GRADE_SCORE",
            self.DEFAULT_MAJOR_GRADE_SCORE,
        )
        intermediate_threshold = getattr(
            config,
            "STRUCTURE_INTERMEDIATE_GRADE_SCORE",
            self.DEFAULT_INTERMEDIATE_GRADE_SCORE,
        )

        if score >= major_threshold:
            return SwingGrade.MAJOR
        if score >= intermediate_threshold:
            return SwingGrade.INTERMEDIATE
        return SwingGrade.MINOR

    def _is_structural(
        self,
        score: float,
    ) -> bool:
        return score >= config.MIN_STRUCTURE_SCORE
