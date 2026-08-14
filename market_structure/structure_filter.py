from __future__ import annotations
import math

import pandas as pd

import config
from engine.columns import COL_AVG_SPREAD, COL_AVG_VOLUME, COL_VOLUME
from models import StructuralSwingScore, Swing, SwingType
from models import StructuralSwing
from models import SwingGrade
from .professional_scorer import ProfessionalScorer
from .swing_history import SwingHistoryAnalyzer
from debug.professional_report import print_professional_score

class StructureFilter:
    """
    Converts confirmed micro swings into
    structurally significant swings.
    """

    def filter(
        self,
        swings: list[Swing],
        metrics: pd.DataFrame,
    ) -> list[StructuralSwing]:

        self._metrics = metrics
        structural: list[StructuralSwing] = []
        previous: Swing | None = None

        for index, current in enumerate(swings):

            # A first confirmed swing has no previous swing, so its
            # amplitude-based professional metrics are undefined.
            # It cannot be structurally scored yet.
            if index == 0:
                previous = current
                continue

            history = SwingHistoryAnalyzer(
                swings=tuple(swings),
                current_index=index,
            )

            evaluation = ProfessionalScorer().score(
                history,
                metrics,
            )

            # testing
            # if evaluation.professional.overall >= 0.70:
            #     print_professional_score(
            #         history.current(),
            #         evaluation
            #     )
            # testing

            grade = self._grade_swing(evaluation.professional.overall)

            structural_swing = StructuralSwing(
                swing=current,
                evaluation=evaluation,
                grade=grade,
            )

            if self._is_structural(evaluation.professional.overall):
                structural.append(
                    structural_swing,
                )
            previous = current

        return structural

    def _grade_swing(
        self,
        score: StructuralSwingScore,
    ) -> SwingGrade:

        return SwingGrade.MAJOR

    def _is_structural(
        self,
        score: float,
    ) -> bool:

        return score >= config.MIN_STRUCTURE_SCORE
