from __future__ import annotations

import pandas as pd

from engine.columns import COL_AVG_SPREAD, COL_AVG_VOLUME, COL_CLOSE, COL_HIGH, COL_LOW, COL_OPEN, COL_SPREAD, COL_VOLUME
import config

from market_structure.swing_history import SwingHistoryAnalyzer

from models import (
    SmartMoneyBar,
    SmartMoneySnapshot,
    Swing,
    SwingContext,
    SwingHistorySnapshot,
    SwingMetricSnapshot,
    SwingProfessionalEvaluation,
    SwingProfessionalScore,
)
from .structural_swing_scorer import StructuralSwingScorer
from .smart_money import SmartMoneyAnalyzer


class ProfessionalScorer:

    def __init__(self) -> None:
        self._structure = StructuralSwingScorer(
            structure_lookback=config.STRUCTURE_LOOKBACK,
        )
        self._smart_money = SmartMoneyAnalyzer()
        self._metric_array_cache = None

    def _metric_arrays(self, metrics: pd.DataFrame):
        cached = self._metric_array_cache

        if cached is None or cached[0] is not metrics:
            cached = (
                metrics,
                metrics[COL_OPEN].to_numpy(copy=False),
                metrics[COL_HIGH].to_numpy(copy=False),
                metrics[COL_LOW].to_numpy(copy=False),
                metrics[COL_CLOSE].to_numpy(copy=False),
                metrics[COL_VOLUME].to_numpy(copy=False),
                metrics[COL_SPREAD].to_numpy(copy=False),
                metrics[COL_AVG_VOLUME].to_numpy(copy=False),
                metrics[COL_AVG_SPREAD].to_numpy(copy=False),
            )
            self._metric_array_cache = cached

        return cached[1:]

    @staticmethod
    def _valid_float(value) -> bool:
        return not pd.isna(value)

    def _history_snapshot(
        self,
        history: SwingHistoryAnalyzer,
        arrays,
        lookback: int,
    ) -> SwingHistorySnapshot:
        (
            _open_values,
            _high_values,
            _low_values,
            _close_values,
            volume_values,
            spread_values,
            _avg_volume_values,
            avg_spread_values,
        ) = arrays

        current = history.current()
        previous = history.previous()

        current_amplitude = (
            abs(current.price - previous.price)
            if previous is not None
            else None
        )
        current_duration = (
            abs(current.bar_index - previous.bar_index)
            if previous is not None
            else None
        )

        avg_spread = avg_spread_values[current.metrics_index]
        current_spread_adjusted_amplitude = (
            current_amplitude / avg_spread
            if current_amplitude is not None
            and self._valid_float(avg_spread)
            and avg_spread > 0
            else None
        )

        start = max(0, history.current_index - lookback + 1)
        previous_swings = history.swings[start:history.current_index]

        amplitudes_list: list[float] = []
        durations_list: list[float] = []
        spread_adjusted_amplitudes: list[float] = []

        for previous_swing, current_swing in zip(
            previous_swings[:-1],
            previous_swings[1:],
        ):
            amplitudes_list.append(
                abs(current_swing.price - previous_swing.price)
            )

            durations_list.append(
                abs(current_swing.bar_index - previous_swing.bar_index)
            )

            if current_swing.type != current.type:
                continue

            value = avg_spread_values[current_swing.metrics_index]
            if not self._valid_float(value) or value <= 0:
                continue

            spread_adjusted_amplitudes.append(
                abs(current_swing.price - previous_swing.price) / value
            )

        amplitudes = tuple(amplitudes_list)
        durations = tuple(durations_list)

        volumes: list[float] = []
        spreads: list[float] = []
        for swing in previous_swings:
            volume = volume_values[swing.metrics_index]
            if self._valid_float(volume):
                volumes.append(float(volume))

            spread = spread_values[swing.metrics_index]
            if self._valid_float(spread):
                spreads.append(float(spread))

        return SwingHistorySnapshot(
            current_amplitude=current_amplitude,
            current_duration=current_duration,
            current_spread_adjusted_amplitude=current_spread_adjusted_amplitude,
            amplitudes=amplitudes,
            spread_adjusted_amplitudes=tuple(spread_adjusted_amplitudes),
            durations=durations,
            volumes=tuple(volumes),
            spreads=tuple(spreads),
        )

    def _build_context(
        self,
        history: SwingHistoryAnalyzer,
        metrics: pd.DataFrame,
        current: Swing,
        arrays=None,
    ) -> SwingContext:
        if arrays is None:
            arrays = self._metric_arrays(metrics)

        return SwingContext(
            swing=current,
            history=self._history_snapshot(
                history,
                arrays,
                config.STRUCTURE_LOOKBACK,
            ),
            metrics=self._metric_snapshot(
                arrays,
                current,
            ),
        )

    def score(
        self,
        history: SwingHistoryAnalyzer,
        metrics: pd.DataFrame,
    ) -> SwingProfessionalEvaluation:
        current = history.current()
        arrays = self._metric_arrays(metrics)

        ctx = self._build_context(
            history,
            metrics,
            current,
            arrays,
        )

        evaluation = self._structure.score(ctx)

        snapshot = self._smart_money_snapshot(
            arrays,
            current,
        )

        smart_money = self._smart_money.score(snapshot)

        professional_score = SwingProfessionalScore.create(
            evaluation.score,
            smart_money,
        )
        return SwingProfessionalEvaluation(
            structure=evaluation,
            smart_money=smart_money,
            professional=professional_score,
        )

    def _metric_snapshot(
        self,
        source,
        swing: Swing,
    ) -> SwingMetricSnapshot:
        arrays = (
            self._metric_arrays(source)
            if isinstance(source, pd.DataFrame)
            else source
        )
        (
            _open_values,
            _high_values,
            _low_values,
            _close_values,
            volume_values,
            spread_values,
            avg_volume_values,
            avg_spread_values,
        ) = arrays

        i = swing.metrics_index

        return SwingMetricSnapshot(
            volume=float(volume_values[i]),
            spread=float(spread_values[i]),
            avg_volume=float(avg_volume_values[i]),
            avg_spread=float(avg_spread_values[i]),
        )

    def _smart_money_snapshot(
        self,
        source,
        swing: Swing,
        lookback: int = 3,
    ) -> SmartMoneySnapshot:
        end = swing.metrics_index + 1
        start = max(0, end - lookback)

        arrays = (
            self._metric_arrays(source)
            if isinstance(source, pd.DataFrame)
            else source
        )
        (
            open_values,
            high_values,
            low_values,
            close_values,
            volume_values,
            spread_values,
            avg_volume_values,
            avg_spread_values,
        ) = arrays

        bars = tuple(
            SmartMoneyBar(
                open=float(open_values[index]),
                high=float(high_values[index]),
                low=float(low_values[index]),
                close=float(close_values[index]),
                spread=float(spread_values[index]),
                avg_spread=float(avg_spread_values[index]),
                volume=float(volume_values[index]),
                avg_volume=float(avg_volume_values[index]),
            )
            for index in range(start, end)
        )

        return SmartMoneySnapshot(bars=bars)
