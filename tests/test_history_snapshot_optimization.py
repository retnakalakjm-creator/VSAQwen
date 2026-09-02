from bisect import bisect_left, insort_left
from collections import deque

import numpy as np

from market_structure.professional_scorer import ProfessionalScorer
from models import Swing, SwingHistorySnapshot, SwingType
from benchmark_history_snapshots import make_inputs
from engine.columns import COL_AVG_SPREAD, COL_SPREAD, COL_VOLUME


def optimized_history_snapshots(
    scorer: ProfessionalScorer,
    swings: list[Swing] | tuple[Swing, ...],
    arrays,
    lookback: int,
) -> tuple[SwingHistorySnapshot | None, ...]:
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

    volume_valid, spread_valid, avg_spread_valid = scorer._metric_valid_cache
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
    history_volumes: deque[tuple[int, float]] = deque()
    history_spreads: deque[tuple[int, float]] = deque()
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

        while history_volumes and history_volumes[0][0] < start_index:
            _, old_volume = history_volumes.popleft()
            del history_sorted_volumes[
                bisect_left(history_sorted_volumes, old_volume)
            ]

        while history_spreads and history_spreads[0][0] < start_index:
            _, old_spread = history_spreads.popleft()
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
        volumes = tuple(value for _, value in history_volumes)
        spreads = tuple(value for _, value in history_spreads)

        adjusted_window = high_adjusted if is_high else low_adjusted
        sorted_adjusted_window = (
            sorted_high_adjusted if is_high else sorted_low_adjusted
        )
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
            history_volumes.append((index, volume))
            insort_left(history_sorted_volumes, volume)

        if spread_valid[metrics_index]:
            spread = float(spread_values[metrics_index])
            history_spreads.append((index, spread))
            insort_left(history_sorted_spreads, spread)

    return tuple(snapshots)


def assert_snapshot_sets_match(expected, actual) -> None:
    assert len(expected) == len(actual)
    for index, (left, right) in enumerate(zip(expected, actual)):
        assert left == right, f"history snapshot mismatch at index {index}:\n{left}\n{right}"


def test_optimized_history_matches_reference_multiple_lookbacks() -> None:
    metrics, swings = make_inputs(500)
    scorer = ProfessionalScorer()
    arrays = scorer._metric_arrays(metrics)

    for lookback in (1, 2, 3, 5, 10, 25, 500):
        expected = scorer.prepare_history_snapshots(swings, arrays, lookback)
        actual = optimized_history_snapshots(scorer, swings, arrays, lookback)
        assert_snapshot_sets_match(expected, actual)


def test_optimized_history_matches_reference_with_invalid_metrics() -> None:
    metrics, swings = make_inputs(100)
    metrics.loc[[3, 11, 29], COL_VOLUME] = np.nan
    metrics.loc[[5, 17, 31], COL_SPREAD] = np.nan
    metrics.loc[[7, 19, 43], COL_AVG_SPREAD] = np.nan
    metrics.loc[[23, 61], COL_AVG_SPREAD] = 0.0

    scorer = ProfessionalScorer()
    arrays = scorer._metric_arrays(metrics)

    for lookback in (2, 5, 10):
        expected = scorer.prepare_history_snapshots(swings, arrays, lookback)
        actual = optimized_history_snapshots(scorer, swings, arrays, lookback)
        assert_snapshot_sets_match(expected, actual)
