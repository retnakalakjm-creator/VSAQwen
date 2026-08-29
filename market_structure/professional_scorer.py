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
from line_profiler import profile


class ProfessionalScorer:

    def __init__(self) -> None:
        self._structure = StructuralSwingScorer(
            structure_lookback=config.STRUCTURE_LOOKBACK,
        )
        self._smart_money = SmartMoneyAnalyzer()
        self._metric_array_cache = None
        self._metric_valid_cache = None

    def _metric_arrays(self, metrics: pd.DataFrame):
        cached = self._metric_array_cache

        if cached is None or cached[0] is not metrics:
            open_values = metrics[COL_OPEN].to_numpy(copy=False)
            high_values = metrics[COL_HIGH].to_numpy(copy=False)
            low_values = metrics[COL_LOW].to_numpy(copy=False)
            close_values = metrics[COL_CLOSE].to_numpy(copy=False)
            volume_values = metrics[COL_VOLUME].to_numpy(copy=False)
            spread_values = metrics[COL_SPREAD].to_numpy(copy=False)
            avg_volume_values = metrics[COL_AVG_VOLUME].to_numpy(copy=False)
            avg_spread_values = metrics[COL_AVG_SPREAD].to_numpy(copy=False)

            cached = (
                metrics,
                open_values,
                high_values,
                low_values,
                close_values,
                volume_values,
                spread_values,
                avg_volume_values,
                avg_spread_values,
            )
            self._metric_array_cache = cached
            self._metric_valid_cache = (
                pd.notna(volume_values),
                pd.notna(spread_values),
                pd.notna(avg_spread_values),
            )

        return cached[1:]

    @staticmethod
    def _valid_float(value) -> bool:
        return not pd.isna(value)

    def prepare_history_snapshots(
        self,
        swings: list[Swing] | tuple[Swing, ...],
        arrays,
        lookback: int,
    ) -> tuple[SwingHistorySnapshot | None, ...]:
        """
        Prepare structural history snapshots once for a swing sequence.

        The resulting snapshots preserve the same historical window and
        validity rules as _history_snapshot(), but avoid rebuilding the
        swing-derived history independently for every score call.
        """
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

        volume_valid, spread_valid, avg_spread_valid = self._metric_valid_cache
        swings = tuple(swings)
        snapshots: list[SwingHistorySnapshot | None] = [None] * len(swings)

        pair_amplitudes: list[float | None] = [None] * len(swings)
        pair_durations: list[int | None] = [None] * len(swings)
        spread_adjusted_high: list[float | None] = [None] * len(swings)
        spread_adjusted_low: list[float | None] = [None] * len(swings)
        swing_volumes: list[float | None] = [None] * len(swings)
        swing_spreads: list[float | None] = [None] * len(swings)

        for index, current in enumerate(swings):
            if index == 0:
                continue

            previous = swings[index - 1]
            pair_amplitude = abs(current.price - previous.price)
            pair_duration = abs(current.bar_index - previous.bar_index)
            pair_amplitudes[index] = pair_amplitude
            pair_durations[index] = pair_duration

            metrics_index = current.metrics_index
            avg_spread = avg_spread_values[metrics_index]
            if avg_spread_valid[metrics_index] and avg_spread > 0:
                adjusted = pair_amplitude / avg_spread
                if current.type.value == "high":
                    spread_adjusted_high[index] = adjusted
                else:
                    spread_adjusted_low[index] = adjusted

            if volume_valid[metrics_index]:
                swing_volumes[index] = float(volume_values[metrics_index])
            if spread_valid[metrics_index]:
                swing_spreads[index] = float(spread_values[metrics_index])

            start = max(0, index - lookback + 1)
            history_end = index

            current_adjusted_history = (
                spread_adjusted_high
                if current.type.value == "high"
                else spread_adjusted_low
            )
            amplitudes = tuple(
                value
                for value in pair_amplitudes[start:history_end]
                if value is not None
            )

            spread_adjusted_amplitudes = tuple(
                value
                for value in current_adjusted_history[start:history_end]
                if value is not None
            )

            durations = tuple(
                value
                for value in pair_durations[start:history_end]
                if value is not None
            )

            volumes = tuple(
                value
                for value in swing_volumes[start:index]
                if value is not None
            )

            spreads = tuple(
                value
                for value in swing_spreads[start:index]
                if value is not None
            )
            snapshots[index] = SwingHistorySnapshot(
                current_amplitude=pair_amplitude,
                current_duration=pair_duration,
                current_spread_adjusted_amplitude=(
                    pair_amplitude / avg_spread
                    if avg_spread_valid[metrics_index] and avg_spread > 0
                    else None
                ),
                amplitudes=amplitudes,
                spread_adjusted_amplitudes=spread_adjusted_amplitudes,
                durations=durations,
                volumes=volumes,
                spreads=spreads,
                sorted_amplitudes=tuple(sorted(amplitudes)),
                sorted_spread_adjusted_amplitudes=tuple(
                    sorted(spread_adjusted_amplitudes)
                ),
                sorted_durations=tuple(sorted(durations)),
                sorted_volumes=tuple(sorted(volumes)),
                sorted_spreads=tuple(sorted(spreads)),
            )

        return tuple(snapshots)

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

        volume_valid, spread_valid, avg_spread_valid = self._metric_valid_cache

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
            and avg_spread_valid[current.metrics_index]
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

            metrics_index = current_swing.metrics_index
            value = avg_spread_values[metrics_index]
            if not avg_spread_valid[metrics_index] or value <= 0:
                continue

            spread_adjusted_amplitudes.append(
                abs(current_swing.price - previous_swing.price) / value
            )

        amplitudes = tuple(amplitudes_list)
        durations = tuple(durations_list)

        volumes: list[float] = []
        spreads: list[float] = []
        for swing in previous_swings:
            metrics_index = swing.metrics_index

            volume = volume_values[metrics_index]
            if volume_valid[metrics_index]:
                volumes.append(float(volume))

            spread = spread_values[metrics_index]
            if spread_valid[metrics_index]:
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
        history_snapshot: SwingHistorySnapshot | None = None,
    ) -> SwingContext:
        if arrays is None:
            arrays = self._metric_arrays(metrics)

        if history_snapshot is None:
            history_snapshot = self._history_snapshot(
                history,
                arrays,
                config.STRUCTURE_LOOKBACK,
            )

        return SwingContext(
            swing=current,
            history=history_snapshot,
            metrics=self._metric_snapshot(
                arrays,
                current,
            ),
        )

    @profile
    def score(
        self,
        history: SwingHistoryAnalyzer,
        metrics: pd.DataFrame,
        arrays=None,
        history_snapshot: SwingHistorySnapshot | None = None,
    ) -> SwingProfessionalEvaluation:
        current = history.current()
        if arrays is None:
            arrays = self._metric_arrays(metrics)

        ctx = self._build_context(
            history,
            metrics,
            current,
            arrays,
            history_snapshot,
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

    @profile
    def _smart_money_snapshot(
        self,
        source,
        swing: Swing,
        lookback: int = 3,
    ) -> SmartMoneySnapshot:
        end = swing.metrics_index + 1
        start = max(0, end - 2)

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
