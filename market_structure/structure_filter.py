from __future__ import annotations
import math

import pandas as pd
import config

from engine.columns import COL_AVG_SPREAD, COL_AVG_VOLUME, COL_VOLUME
from models import StructuralSwingScore, Swing, SwingType
from models import StructuralSwing
from models import SwingGrade
from models import StructuralSwingEvaluation, SwingProfessionalEvaluation, SwingProfessionalScore
from models import ScoreBreakdown, SmartMoneyScore
from utils.scoring import component
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
        scorer = ProfessionalScorer()
        swing_tuple = tuple(swings)
        metric_indices = tuple(swing.metrics_index for swing in swing_tuple)
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
        (
            stopping_volume,
            stopping_close,
            stopping_tail,
            stopping_overall,
            climactic_volume,
            climactic_spread,
            climactic_close,
            climactic_overall,
            smart_money_overall,
        ) = scorer._smart_money.score_values_batch_raw(
            open_values=open_values,
            low_values=low_values,
            close_values=close_values,
            spread_values=spread_values,
            avg_spread_values=avg_spread_values,
            volume_values=volume_values,
            avg_volume_values=avg_volume_values,
            indices=metric_indices,
        )

        total_weight = scorer._professional_total_weight
        structure_weight = scorer._professional_structure_weight
        smart_money_weight = scorer._professional_smart_money_weight
        prepared_values = scorer._structure._prepared_values
        is_structural = self._is_structural

        for index, current in enumerate(swing_tuple):
            if index == 0:
                continue

            snapshot = history_snapshots[index]
            if snapshot is None:
                continue

            metric_index = metric_indices[index]
            (
                price,
                structural_size,
                duration_score,
                volume_score,
                spread_score,
                structure_overall,
            ) = prepared_values(
                snapshot=snapshot,
                volume=float(volume_values[metric_index]),
                spread=float(spread_values[metric_index]),
            )

            smart_money_score = float(smart_money_overall[index])
            if total_weight <= 0:
                professional_overall = 0.0
            else:
                professional_overall = min(
                    (
                        structure_overall * structure_weight
                        + smart_money_score * smart_money_weight
                    ) / total_weight,
                    1.0,
                )

            if not is_structural(professional_overall):
                continue

            stopping = ScoreBreakdown(
                overall=float(stopping_overall[index]),
                components=(
                    component(
                        float(stopping_volume[index]),
                        config.SMART_MONEY_STOPPING_VOLUME_WEIGHT,
                    ),
                    component(
                        float(stopping_close[index]),
                        config.SMART_MONEY_STOPPING_CLOSE_WEIGHT,
                    ),
                    component(
                        float(stopping_tail[index]),
                        config.SMART_MONEY_STOPPING_TAIL_WEIGHT,
                    ),
                ),
            )
            climactic = ScoreBreakdown(
                overall=float(climactic_overall[index]),
                components=(
                    component(
                        float(climactic_volume[index]),
                        config.SMART_MONEY_CLIMACTIC_VOLUME_WEIGHT,
                    ),
                    component(
                        float(climactic_spread[index]),
                        config.SMART_MONEY_CLIMACTIC_SPREAD_WEIGHT,
                    ),
                    component(
                        float(climactic_close[index]),
                        config.SMART_MONEY_CLIMACTIC_CLOSE_WEIGHT,
                    ),
                ),
            )
            smart_money = SmartMoneyScore(
                stopping_volume=stopping.overall,
                stopping_breakdown=stopping,
                climactic_volume=climactic.overall,
                climactic_breakdown=climactic,
                overall=smart_money_score,
            )

            structure_score = StructuralSwingScore(
                price=price,
                structural_size=structural_size,
                duration=duration_score,
                volume=volume_score,
                spread=spread_score,
                overall=structure_overall,
            )
            structure_evaluation = StructuralSwingEvaluation(
                score=structure_score,
                snapshot=snapshot,
            )
            professional_score = SwingProfessionalScore(
                structure=structure_score,
                smart_money=smart_money,
                overall=professional_overall,
            )
            evaluation = SwingProfessionalEvaluation(
                structure=structure_evaluation,
                smart_money=smart_money,
                professional=professional_score,
            )

            grade = self._grade_swing(professional_overall)
            structural.append(
                StructuralSwing(
                    swing=current,
                    evaluation=evaluation,
                    grade=grade,
                )
            )

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
