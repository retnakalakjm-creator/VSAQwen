from __future__ import annotations

import config

from models import ScoreBreakdown, SmartMoneyBar, SmartMoneyScore, SmartMoneySnapshot
from utils.scoring import band_score, component, combine_scores
from line_profiler import profile


class SmartMoneyAnalyzer:
    """
    Analyze smart-money activity inside the current swing.
    """

    def score(
        self,
        snapshot: SmartMoneySnapshot,
    ) -> SmartMoneyScore:

        bars = snapshot.bars

        stopping = self._evaluate_stopping_volume(
            bars,
        )

        climactic = self._evaluate_climactic_volume(
            bars,
        )

        components = (
            component(
                stopping.overall,
                config.SMART_MONEY_STOPPING_WEIGHT,
            ),
            component(
                climactic.overall,
                config.SMART_MONEY_CLIMACTIC_WEIGHT,
            ),
        )

        overall = combine_scores(
            components,
        )

        return SmartMoneyScore(
            stopping_volume=stopping.overall,
            stopping_breakdown=stopping,
            climactic_volume=climactic.overall,
            climactic_breakdown=climactic,
            overall=overall,
        )

    @profile
    def _evaluate_stopping_volume(
        self,
        bars: tuple[SmartMoneyBar, ...],
    ) -> ScoreBreakdown:

        if len(bars) < 2:
            return ScoreBreakdown.empty()

        bar = bars[-1]

        volume = band_score(
            bar.volume_ratio,
            config.STOPPING_VOLUME_BANDS,
        )

        close = band_score(
            bar.close_position,
            config.STOPPING_CLOSE_POSITION_BANDS,
        )

        tail = band_score(
            bar.lower_tail_ratio,
            config.STOPPING_LOWER_TAIL_BANDS,
        )

        components = (
            component(
                volume,
                config.SMART_MONEY_STOPPING_VOLUME_WEIGHT,
            ),
            component(
                close,
                config.SMART_MONEY_STOPPING_CLOSE_WEIGHT,
            ),
            component(
                tail,
                config.SMART_MONEY_STOPPING_TAIL_WEIGHT,
            ),
        )

        overall = combine_scores(
            components,
        )

        return ScoreBreakdown(
            overall=overall,
            components=components,
        )

    @profile
    def _evaluate_climactic_volume(
        self,
        bars: tuple[SmartMoneyBar, ...],
    ) -> ScoreBreakdown:

        if len(bars) == 0:
            return ScoreBreakdown.empty()

        bar = bars[-1]

        volume = band_score(
            bar.volume_ratio,
            config.CLIMACTIC_VOLUME_BANDS,
        )

        spread = band_score(
            bar.spread_ratio,
            config.CLIMACTIC_SPREAD_BANDS,
        )

        close_score = band_score(
            bar.extreme_close_position,
            config.CLIMACTIC_CLOSE_POSITION_BANDS,
        )

        components = (
            component(
                volume,
                config.SMART_MONEY_CLIMACTIC_VOLUME_WEIGHT,
            ),
            component(
                spread,
                config.SMART_MONEY_CLIMACTIC_SPREAD_WEIGHT,
            ),
            component(
                close_score,
                config.SMART_MONEY_CLIMACTIC_CLOSE_WEIGHT,
            ),
        )

        overall = combine_scores(
            components,
        )

        return ScoreBreakdown(
            overall=overall,
            components=components,
        )
