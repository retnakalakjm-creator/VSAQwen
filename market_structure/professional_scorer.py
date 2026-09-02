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
    SwingType,
)
from .structural_swing_scorer import StructuralSwingScorer
from .smart_money import SmartMoneyAnalyzer
from .batched_smart_money import BatchedSmartMoneyAnalyzer
from line_profiler import profile


class ProfessionalScorer:

    def __init__(self) -> None:
        self._structure = StructuralSwingScorer(
            structure_lookback=config.STRUCTURE_LOOKBACK,
        )
        self._smart_money = BatchedSmartMoneyAnalyzer()
        self._professional_structure_weight = config.PROFESSIONAL_STRUCTURE_WEIGHT
        self._professional_smart_money_weight = config.PROFESSIONAL_SMART_MONEY_WEIGHT
        self._professional_total_weight = (
            self._professional_structure_weight
            + self._professional_smart_money_weight
        )
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

    @profile
    def prepare_history_snapshots(
        self,
        swings: list[Swing] | tuple[Swing, ...],
        arrays,
        lookback: int,
    ) -> tuple[SwingHistorySnapshot | None, ...]:
        from bisect import bisect_left, insort_left
        from collections import deque

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

        pair_amplitudes = [
            abs(current.price - previous.price)
            for previous, current in zip(swings[:-1], swings[1:])
        ]
        pair_durations = [
            abs(current.bar_index - previous.bar_index)
            for previous, current in zip(swings[:-1], swings[1:])
        ]

        history_size = max(0, lookback - 1)
        pair_indices: deque[int] = deque()
        history_amplitudes: deque[float] = deque()
        history_durations: deque[int] = deque()
        history_sorted_amplitudes: list[float] = []
        history_sorted_durations: list[int] = []

        history_volume_indices: deque[int] = deque()
        history_volumes: deque[float] = deque()
        history_spread_indices: deque[int] = deque()
        history_spreads: deque[float] = deque()
        history_sorted_volumes: list[float] = []
        history_sorted_spreads: list[float] = []

        high_adjusted: deque[tuple[int, float]] = deque()
        low_adjusted: deque[tuple[int, float]] = deque()
        sorted_high_adjusted: list[float] = []
        sorted_low_adjusted: list[float] = []

        def remove_before(start_index: int) -> None:
            while pair_indices and pair_indices[0] < start_index:
                pair_indices.popleft()
                old_amplitude = history_amplitudes.popleft()
                old_duration = history_durations.popleft()
                del history_sorted_amplitudes[
                    bisect_left(history_sorted_amplitudes, old_amplitude)
                ]
                del history_sorted_durations[
                    bisect_left(history_sorted_durations, old_duration)
                ]

            while history_volume_indices and history_volume_indices[0] < start_index:
                history_volume_indices.popleft()
                old_volume = history_volumes.popleft()
                del history_sorted_volumes[
                    bisect_left(history_sorted_volumes, old_volume)
                ]

            while history_spread_indices and history_spread_indices[0] < start_index:
                history_spread_indices.popleft()
                old_spread = history_spreads.popleft()
                del history_sorted_spreads[
                    bisect_left(history_sorted_spreads, old_spread)
                ]

            while high_adjusted and high_adjusted[0][0] < start_index:
                _, old_adjusted = high_adjusted.popleft()
                del sorted_high_adjusted[
                    bisect_left(sorted_high_adjusted, old_adjusted)
                ]

            while low_adjusted and low_adjusted[0][0] < start_index:
                _, old_adjusted = low_adjusted.popleft()
                del sorted_low_adjusted[
                    bisect_left(sorted_low_adjusted, old_adjusted)
                ]

        for index, current in enumerate(swings):
            if index == 0:
                continue

            history_start = max(0, index - lookback + 1)
            start_index = max(1, history_start)
            remove_before(start_index)

            pair_amplitude = pair_amplitudes[index - 1]
            pair_duration = pair_durations[index - 1]
            metrics_index = current.metrics_index
            avg_spread = avg_spread_values[metrics_index]
            is_high = current.type is SwingType.HIGH

            amplitudes = tuple(history_amplitudes)
            durations = tuple(history_durations)
            volumes = tuple(history_volumes)
            spreads = tuple(history_spreads)

            if is_high:
                adjusted_window = high_adjusted
                sorted_adjusted_window = sorted_high_adjusted
            else:
                adjusted_window = low_adjusted
                sorted_adjusted_window = sorted_low_adjusted
            spread_adjusted_amplitudes = tuple(
                value for _, value in adjusted_window
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
                sorted_amplitudes=tuple(history_sorted_amplitudes),
                sorted_spread_adjusted_amplitudes=tuple(sorted_adjusted_window),
                sorted_durations=tuple(history_sorted_durations),
                sorted_volumes=tuple(history_sorted_volumes),
                sorted_spreads=tuple(history_sorted_spreads),
            )

            if history_size == 0:
                continue

            pair_indices.append(index)
            history_amplitudes.append(pair_amplitude)
            history_durations.append(pair_duration)
            insort_left(history_sorted_amplitudes, pair_amplitude)
            insort_left(history_sorted_durations, pair_duration)

            if avg_spread_valid[metrics_index] and avg_spread > 0:
                adjusted = pair_amplitude / avg_spread
                if is_high:
                    high_adjusted.append((index, adjusted))
                    insort_left(sorted_high_adjusted, adjusted)
                else:
                    low_adjusted.append((index, adjusted))
                    insort_left(sorted_low_adjusted, adjusted)

            if volume_valid[metrics_index]:
                volume = float(volume_values[metrics_index])
                history_volume_indices.append(index)
                history_volumes.append(volume)
                insort_left(history_sorted_volumes, volume)

            if spread_valid[metrics_index]:
                spread = float(spread_values[metrics_index])
                history_spread_indices.append(index)
                history_spreads.append(spread)
                insort_left(history_sorted_spreads, spread)

        return tuple(snapshots)

    def smart_money_scores_batch(
        self,
        arrays,
        indices,
        *,
        include_components: bool = True,
    ):
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

        return self._smart_money.score_values_batch(
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

    def _history_snapshot(self, history, arrays, lookback):
        current = history.current()
        previous = history.previous()
        current_amplitude = abs(current.price - previous.price) if previous else None
        current_duration = abs(current.bar_index - previous.bar_index) if previous else None
        avg_spread = arrays[7][current.metrics_index]
        current_spread_adjusted_amplitude = (
            current_amplitude / avg_spread if current_amplitude is not None and pd.notna(avg_spread) and avg_spread > 0 else None
        )
        start = max(0, history.current_index - lookback + 1)
        previous_swings = history.swings[start:history.current_index]
        amplitudes_list = []
        durations_list = []
        spread_adjusted_amplitudes = []
        for previous_swing, current_swing in zip(previous_swings[:-1], previous_swings[1:]):
            amplitudes_list.append(abs(current_swing.price - previous_swing.price))
            durations_list.append(abs(current_swing.bar_index - previous_swing.bar_index))
            if current_swing.type != current.type:
                continue
            metrics_index = current_swing.metrics_index
            value = arrays[7][metrics_index]
            if pd.notna(value) and value > 0:
                spread_adjusted_amplitudes.append(abs(current_swing.price - previous_swing.price) / value)
        volumes_list = []
        spreads_list = []
        for swing in previous_swings:
            metrics_index = swing.metrics_index
            if pd.notna(arrays[4][metrics_index]):
                volumes_list.append(float(arrays[4][metrics_index]))
            if pd.notna(arrays[5][metrics_index]):
                spreads_list.append(float(arrays[5][metrics_index]))
        return SwingHistorySnapshot(
            current_amplitude=current_amplitude,
            current_duration=current_duration,
            current_spread_adjusted_amplitude=current_spread_adjusted_amplitude,
            amplitudes=tuple(amplitudes_list),
            spread_adjusted_amplitudes=tuple(spread_adjusted_amplitudes),
            durations=tuple(durations_list),
            volumes=tuple(volumes_list),
            spreads=tuple(spreads_list),
            sorted_amplitudes=tuple(sorted(amplitudes_list)),
            sorted_spread_adjusted_amplitudes=tuple(sorted(spread_adjusted_amplitudes)),
            sorted_durations=tuple(sorted(durations_list)),
            sorted_volumes=tuple(sorted(volumes_list)),
            sorted_spreads=tuple(sorted(spreads_list)),
        )

    def _build_context(self, history, metrics, current, arrays=None, history_snapshot=None):
        if arrays is None:
            arrays = self._metric_arrays(metrics)
        if history_snapshot is None:
            history_snapshot = self._history_snapshot(history, arrays, config.STRUCTURE_LOOKBACK)
        return SwingContext(swing=current, history=history_snapshot, metrics=self._metric_snapshot(arrays, current))

    def score(self, history, metrics, arrays=None, history_snapshot=None):
        current = history.current()
        if arrays is None:
            arrays = self._metric_arrays(metrics)
        ctx = self._build_context(history, metrics, current, arrays, history_snapshot)
        evaluation = self._structure.score(ctx)
        open_values, _high_values, low_values, close_values, volume_values, spread_values, avg_volume_values, avg_spread_values = arrays
        i = current.metrics_index
        smart_money = self._smart_money.score_values(bar_count=2 if i > 0 else 1, open_value=float(open_values[i]), low_value=float(low_values[i]), close_value=float(close_values[i]), spread_value=float(spread_values[i]), avg_spread=float(avg_spread_values[i]), volume_value=float(volume_values[i]), avg_volume=float(avg_volume_values[i]))
        structure_score = evaluation.score.overall
        smart_money_score = smart_money.overall
        total_weight = self._professional_total_weight
        professional_overall = 0.0 if total_weight <= 0 else min((structure_score * self._professional_structure_weight + smart_money_score * self._professional_smart_money_weight) / total_weight, 1.0)
        professional_score = SwingProfessionalScore(structure=evaluation.score, smart_money=smart_money, overall=professional_overall)
        return SwingProfessionalEvaluation(structure=evaluation, smart_money=smart_money, professional=professional_score)

    def _metric_snapshot(self, source, swing):
        arrays = self._metric_arrays(source) if isinstance(source, pd.DataFrame) else source
        volume_values, spread_values, avg_volume_values, avg_spread_values = arrays[4], arrays[5], arrays[6], arrays[7]
        i = swing.metrics_index
        return SwingMetricSnapshot(volume=float(volume_values[i]), spread=float(spread_values[i]), avg_volume=float(avg_volume_values[i]), avg_spread=float(avg_spread_values[i]))
