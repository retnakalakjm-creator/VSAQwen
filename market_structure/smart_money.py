from __future__ import annotations

import config

from models import ScoreBreakdown, SmartMoneyBar, SmartMoneyScore, SmartMoneySnapshot
from utils.scoring import band_score, component, combine_scores
from line_profiler import profile


class SmartMoneyAnalyzer:
    """
    Analyze smart-money activity inside the current swing.
    """

    @profile
    def score(
        self,
        snapshot: SmartMoneySnapshot,
    ) -> SmartMoneyScore:
        bars = snapshot.bars

        stopping = self._evaluate_stopping_volume(bars)
        climactic = self._evaluate_climactic_volume(bars)

        return self._build_score(stopping, climactic)

    @profile
    def score_values(
        self,
        *,
        bar_count: int,
        open_value: float,
        low_value: float,
        close_value: float,
        spread_value: float,
        avg_spread: float,
        volume_value: float,
        avg_volume: float,
        include_components: bool = False,
    ) -> SmartMoneyScore:
        """
        Score the latest Smart Money bar directly from scalar metrics.

        This avoids constructing SmartMoneyBar/SmartMoneySnapshot objects
        during the normal professional-scoring hot path. Component details
        are omitted by default for normal scanning and can be requested
        explicitly when detailed diagnostics are needed.
        """
        if bar_count < 2:
            stopping = ScoreBreakdown.empty()
        else:
            volume_ratio = (
                volume_value / avg_volume
                if avg_volume > 0
                else 0.0
            )
            close_position = (
                (close_value - low_value) / spread_value
                if spread_value > 0
                else 0.5
            )
            lower_tail_ratio = (
                (min(open_value, close_value) - low_value) / spread_value
                if spread_value > 0
                else 0.0
            )

            volume = self._stopping_volume_band(volume_ratio)
            close = self._stopping_close_band(close_position)
            tail = self._stopping_tail_band(lower_tail_ratio)

            stopping_weight = config.SMART_MONEY_STOPPING_WEIGHT
            volume_weight = config.SMART_MONEY_STOPPING_VOLUME_WEIGHT
            close_weight = config.SMART_MONEY_STOPPING_CLOSE_WEIGHT
            tail_weight = config.SMART_MONEY_STOPPING_TAIL_WEIGHT
            stopping_total_weight = volume_weight + close_weight + tail_weight

            if stopping_total_weight <= 0:
                stopping_overall = 0.0
            else:
                stopping_overall = min(
                    (
                        volume * volume_weight
                        + close * close_weight
                        + tail * tail_weight
                    ) / stopping_total_weight,
                    1.0,
                )

            if include_components:
                stopping_components = (
                    component(volume, volume_weight),
                    component(close, close_weight),
                    component(tail, tail_weight),
                )
            else:
                stopping_components = ()

            stopping = ScoreBreakdown(
                overall=stopping_overall,
                components=stopping_components,
            )

        if bar_count == 0:
            climactic = ScoreBreakdown.empty()
        else:
            volume_ratio = (
                volume_value / avg_volume
                if avg_volume > 0
                else 0.0
            )
            spread_ratio = (
                spread_value / avg_spread
                if avg_spread > 0
                else 0.0
            )
            close_position = (
                (close_value - low_value) / spread_value
                if spread_value > 0
                else 0.5
            )
            extreme_close_position = max(close_position, 1.0 - close_position)

            volume = self._climactic_volume_band(volume_ratio)
            spread_score = self._climactic_spread_band(spread_ratio)
            close_score = self._climactic_close_band(extreme_close_position)

            volume_weight = config.SMART_MONEY_CLIMACTIC_VOLUME_WEIGHT
            spread_weight = config.SMART_MONEY_CLIMACTIC_SPREAD_WEIGHT
            close_weight = config.SMART_MONEY_CLIMACTIC_CLOSE_WEIGHT
            climactic_total_weight = volume_weight + spread_weight + close_weight

            if climactic_total_weight <= 0:
                climactic_overall = 0.0
            else:
                climactic_overall = min(
                    (
                        volume * volume_weight
                        + spread_score * spread_weight
                        + close_score * close_weight
                    ) / climactic_total_weight,
                    1.0,
                )

            if include_components:
                climactic_components = (
                    component(volume, volume_weight),
                    component(spread_score, spread_weight),
                    component(close_score, close_weight),
                )
            else:
                climactic_components = ()

            climactic = ScoreBreakdown(
                overall=climactic_overall,
                components=climactic_components,
            )

        return self._build_score(stopping, climactic)

    @staticmethod
    def _stopping_volume_band(value: float) -> float:
        if value >= 2.00:
            return 0.40
        if value >= 1.50:
            return 0.20
        return 0.0

    @staticmethod
    def _stopping_close_band(value: float) -> float:
        if value >= 0.70:
            return 0.30
        if value >= 0.60:
            return 0.15
        return 0.0

    @staticmethod
    def _stopping_tail_band(value: float) -> float:
        if value >= 0.35:
            return 0.30
        if value >= 0.25:
            return 0.15
        return 0.0

    @staticmethod
    def _climactic_volume_band(value: float) -> float:
        if value >= 2.50:
            return 1.00
        if value >= 2.00:
            return 0.70
        if value >= 1.50:
            return 0.40
        return 0.0

    @staticmethod
    def _climactic_spread_band(value: float) -> float:
        if value >= 2.00:
            return 1.00
        if value >= 1.50:
            return 0.70
        if value >= 1.20:
            return 0.40
        return 0.0

    @staticmethod
    def _climactic_close_band(value: float) -> float:
        if value >= 0.90:
            return 1.00
        if value >= 0.80:
            return 0.70
        if value >= 0.70:
            return 0.40
        return 0.0

    @staticmethod
    def _build_score(
        stopping: ScoreBreakdown,
        climactic: ScoreBreakdown,
    ) -> SmartMoneyScore:
        stopping_weight = config.SMART_MONEY_STOPPING_WEIGHT
        climactic_weight = config.SMART_MONEY_CLIMACTIC_WEIGHT
        total_weight = stopping_weight + climactic_weight

        if total_weight <= 0:
            overall = 0.0
        else:
            overall = min(
                (
                    stopping.overall * stopping_weight
                    + climactic.overall * climactic_weight
                ) / total_weight,
                1.0,
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

        overall = combine_scores(components)

        return ScoreBreakdown(
            overall=overall,
            components=components,
        )

    @profile
    @staticmethod
    def _evaluate_stopping_values(
        *,
        open_value: float,
        low: float,
        close_value: float,
        spread: float,
        volume_value: float,
        avg_volume: float,
        include_components: bool = False,
        volume_ratio: float | None = None,
        close_position: float | None = None,
    ) -> ScoreBreakdown:
        if volume_ratio is None:
            volume_ratio = (
                volume_value / avg_volume
                if avg_volume > 0
                else 0.0
            )
        if close_position is None:
            close_position = (
                (close_value - low) / spread
                if spread > 0
                else 0.5
            )
        lower_tail_ratio = (
            (min(open_value, close_value) - low) / spread
            if spread > 0
            else 0.0
        )

        volume = band_score(volume_ratio, config.STOPPING_VOLUME_BANDS)
        close = band_score(close_position, config.STOPPING_CLOSE_POSITION_BANDS)
        tail = band_score(lower_tail_ratio, config.STOPPING_LOWER_TAIL_BANDS)

        volume_weight = config.SMART_MONEY_STOPPING_VOLUME_WEIGHT
        close_weight = config.SMART_MONEY_STOPPING_CLOSE_WEIGHT
        tail_weight = config.SMART_MONEY_STOPPING_TAIL_WEIGHT
        total_weight = volume_weight + close_weight + tail_weight

        if total_weight <= 0:
            overall = 0.0
        else:
            overall = min(
                (
                    volume * volume_weight
                    + close * close_weight
                    + tail * tail_weight
                ) / total_weight,
                1.0,
            )

        if include_components:
            components = (
                component(volume, volume_weight),
                component(close, close_weight),
                component(tail, tail_weight),
            )
        else:
            components = ()

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

        overall = combine_scores(components)

        return ScoreBreakdown(
            overall=overall,
            components=components,
        )

    @profile
    @staticmethod
    def _evaluate_climactic_values(
        *,
        low: float,
        close_value: float,
        spread: float,
        avg_spread: float,
        volume_value: float,
        avg_volume: float,
        include_components: bool = False,
        volume_ratio: float | None = None,
        close_position: float | None = None,
    ) -> ScoreBreakdown:
        if volume_ratio is None:
            volume_ratio = (
                volume_value / avg_volume
                if avg_volume > 0
                else 0.0
            )
        spread_ratio = (
            spread / avg_spread
            if avg_spread > 0
            else 0.0
        )
        if close_position is None:
            close_position = (
                (close_value - low) / spread
                if spread > 0
                else 0.5
            )
        extreme_close_position = max(close_position, 1.0 - close_position)

        volume = band_score(volume_ratio, config.CLIMACTIC_VOLUME_BANDS)
        spread_score = band_score(spread_ratio, config.CLIMACTIC_SPREAD_BANDS)
        close_score = band_score(
            extreme_close_position,
            config.CLIMACTIC_CLOSE_POSITION_BANDS,
        )

        volume_weight = config.SMART_MONEY_CLIMACTIC_VOLUME_WEIGHT
        spread_weight = config.SMART_MONEY_CLIMACTIC_SPREAD_WEIGHT
        close_weight = config.SMART_MONEY_CLIMACTIC_CLOSE_WEIGHT
        total_weight = volume_weight + spread_weight + close_weight

        if total_weight <= 0:
            overall = 0.0
        else:
            overall = min(
                (
                    volume * volume_weight
                    + spread_score * spread_weight
                    + close_score * close_weight
                ) / total_weight,
                1.0,
            )

        if include_components:
            components = (
                component(volume, volume_weight),
                component(spread_score, spread_weight),
                component(close_score, close_weight),
            )
        else:
            components = ()

        return ScoreBreakdown(
            overall=overall,
            components=components,
        )
