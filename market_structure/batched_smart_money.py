from __future__ import annotations

from models import ScoreBreakdown, SmartMoneyScore
from .smart_money import SmartMoneyAnalyzer
import config
from utils.scoring import component


class BatchedSmartMoneyAnalyzer(SmartMoneyAnalyzer):
    """Smart Money analyzer with fully batched scalar-equivalent semantics."""

    @staticmethod
    def score_values_batch_raw(
        *,
        open_values,
        low_values,
        close_values,
        spread_values,
        avg_spread_values,
        volume_values,
        avg_volume_values,
        indices,
    ):
        return SmartMoneyAnalyzer.score_values_batch_raw(
            open_values=open_values,
            low_values=low_values,
            close_values=close_values,
            spread_values=spread_values,
            avg_spread_values=avg_spread_values,
            volume_values=volume_values,
            avg_volume_values=avg_volume_values,
            indices=indices,
        )

    @staticmethod
    def score_from_batch_raw(
        raw_scores,
        position: int,
        *,
        source_index: int,
        include_components: bool = False,
    ) -> SmartMoneyScore:
        (
            stopping_volume,
            stopping_close,
            stopping_tail,
            stopping_overall,
            climactic_volume,
            climactic_spread,
            climactic_close,
            climactic_overall,
            overall,
        ) = raw_scores

        if source_index == 0:
            stopping = ScoreBreakdown.empty()
        else:
            if include_components:
                stopping_components = (
                    component(float(stopping_volume[position]), config.SMART_MONEY_STOPPING_VOLUME_WEIGHT),
                    component(float(stopping_close[position]), config.SMART_MONEY_STOPPING_CLOSE_WEIGHT),
                    component(float(stopping_tail[position]), config.SMART_MONEY_STOPPING_TAIL_WEIGHT),
                )
            else:
                stopping_components = ()

            stopping = ScoreBreakdown(
                overall=float(stopping_overall[position]),
                components=stopping_components,
            )

        if include_components:
            climactic_components = (
                component(float(climactic_volume[position]), config.SMART_MONEY_CLIMACTIC_VOLUME_WEIGHT),
                component(float(climactic_spread[position]), config.SMART_MONEY_CLIMACTIC_SPREAD_WEIGHT),
                component(float(climactic_close[position]), config.SMART_MONEY_CLIMACTIC_CLOSE_WEIGHT),
            )
        else:
            climactic_components = ()

        climactic = ScoreBreakdown(
            overall=float(climactic_overall[position]),
            components=climactic_components,
        )

        return SmartMoneyScore(
            stopping_volume=stopping.overall,
            stopping_breakdown=stopping,
            climactic_volume=climactic.overall,
            climactic_breakdown=climactic,
            overall=float(overall[position]),
        )

    @staticmethod
    def score_values_batch(
        *,
        open_values,
        low_values,
        close_values,
        spread_values,
        avg_spread_values,
        volume_values,
        avg_volume_values,
        indices,
        include_components: bool = False,
    ) -> tuple[SmartMoneyScore, ...]:
        return SmartMoneyAnalyzer.score_values_batch(
            open_values=open_values,
            low_values=low_values,
            close_values=close_values,
            spread_values=spread_values,
            avg_spread_values=avg_spread_values,
            volume_values=volume_values,
            avg_volume_values=avg_volume_values,
            indices=indices,
            include_components=include_components,
        )
