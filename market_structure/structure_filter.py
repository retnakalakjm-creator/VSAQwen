from __future__ import annotations

import pandas as pd
import config

from models import (
    StructuralSwingScore,
    Swing,
    SwingType,
    StructuralSwing,
    SwingGrade,
    StructuralSwingEvaluation,
    SwingProfessionalEvaluation,
    SwingProfessionalScore,
)
from .professional_scorer import ProfessionalScorer
from line_profiler import profile


class StructureFilter:
    """Converts confirmed micro swings into structurally significant swings."""

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
        raw_smart_money = scorer._smart_money.score_values_batch_raw(
            open_values=arrays[0],
            low_values=arrays[2],
            close_values=arrays[3],
            spread_values=arrays[5],
            avg_spread_values=arrays[7],
            volume_values=arrays[4],
            avg_volume_values=arrays[6],
            indices=metric_indices,
        )

        total_weight = scorer._professional_total_weight
        structure_weight = scorer._professional_structure_weight
        smart_money_weight = scorer._professional_smart_money_weight
        prepared_values = scorer._structure._prepared_values
        is_structural = self._is_structural
        score_from_batch_raw = scorer._smart_money.score_from_batch_raw

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
                volume=float(arrays[4][metric_index]),
                spread=float(arrays[5][metric_index]),
            )

            smart_money_score = float(raw_smart_money[-1][index])
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

            smart_money = score_from_batch_raw(
                raw_smart_money,
                index,
                source_index=int(metric_index),
                include_components=True,
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
