from __future__ import annotations

import config

from models import (
    Swing,
    SwingHistorySnapshot,
    SmartMoneyScore,
    SwingProfessionalEvaluation,
    SwingProfessionalScore,
)
from .professional_scorer import ProfessionalScorer
from line_profiler import profile


@profile
def score_prepared(
    scorer: ProfessionalScorer,
    current: Swing,
    arrays,
    history_snapshot: SwingHistorySnapshot,
    smart_money: SmartMoneyScore | None = None,
) -> SwingProfessionalEvaluation:
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

    i = current.metrics_index

    evaluation = scorer._structure.score_prepared(
        snapshot=history_snapshot,
        volume=float(volume_values[i]),
        spread=float(spread_values[i]),
    )

    if smart_money is None:
        smart_money = scorer._smart_money.score_values(
            bar_count=2 if i > 0 else 1,
            open_value=float(open_values[i]),
            low_value=float(low_values[i]),
            close_value=float(close_values[i]),
            spread_value=float(spread_values[i]),
            avg_spread=float(avg_spread_values[i]),
            volume_value=float(volume_values[i]),
            avg_volume=float(avg_volume_values[i]),
        )

    structure_score = evaluation.score.overall
    smart_money_score = smart_money.overall
    total_weight = scorer._professional_total_weight

    if total_weight <= 0:
        professional_overall = 0.0
    else:
        professional_overall = min(
            (
                structure_score * scorer._professional_structure_weight
                + smart_money_score * scorer._professional_smart_money_weight
            ) / total_weight,
            1.0,
        )

    professional_score = SwingProfessionalScore(
        structure=evaluation.score,
        smart_money=smart_money,
        overall=professional_overall,
    )

    return SwingProfessionalEvaluation(
        structure=evaluation,
        smart_money=smart_money,
        professional=professional_score,
    )