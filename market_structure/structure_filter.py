from __future__ import annotations
import math

import pandas as pd
import config

from engine.columns import COL_AVG_SPREAD, COL_AVG_VOLUME, COL_VOLUME
from models import StructuralSwingScore, Swing, SwingType
from models import StructuralSwing
from models import SwingGrade
from .professional_scorer import ProfessionalScorer
from .prepared_scoring import score_prepared
from debug.professional_report import print_professional_score
from line_profiler import profile

class StructureFilter:
    """
    Converts confirmed micro swings into
    structurally significant swings.
    """

    @profile
    def filter(
        self,
        swings: list[Swing],
        metrics: pd.DataFrame,
    ) -> list[StructuralSwing]:

        self._metrics = metrics
        structural: list[StructuralSwing] = []
        previous: Swing | None = None
        scorer = ProfessionalScorer()
        swing_tuple = tuple(swings)
        arrays = scorer._metric_arrays(metrics)
        history_snapshots = scorer.prepare_history_snapshots(
            swing_tuple,
            arrays,
            config.STRUCTURE_LOOKBACK,
        )

        (
            open_values,
            _high_values,
            low_values,
            close_values,
            volume_values,
            spread_values,
            avg_volume_values,
            avg_spread_values,
        ) = arrays
        smart_money_scores = scorer._smart_money.score_values_batch(
            open_values=open_values,
            low_values=low_values,
            close_values=close_values,
            spread_values=spread_values,
            avg_spread_values=avg_spread_values,
            volume_values=volume_values,
            avg_volume_values=avg_volume_values,
            indices=[swing.metrics_index for swing in swing_tuple],
        )

        for index, current in enumerate(swings):

            # A first confirmed swing has no previous swing, so its
            # amplitude-based professional metrics are undefined.
            # It cannot be structurally scored yet.
            if index == 0:
                previous = current
                continue

            evaluation = score_prepared(
                scorer,
                current,
                arrays,
                history_snapshots[index],
                smart_money=smart_money_scores[index],
            )

            # testing
            # if evaluation.professional.overall >= 0.70:
            #     print_professional_score(
            #         current,
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
