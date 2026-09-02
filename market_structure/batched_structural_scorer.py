from __future__ import annotations

from bisect import bisect_right

import numpy as np

from models import SwingHistorySnapshot


def score_prepared_batch(
    scorer,
    snapshots: tuple[SwingHistorySnapshot | None, ...],
    volume_values,
    spread_values,
    metric_indices,
) -> tuple[np.ndarray, ...]:
    """Score all prepared structural snapshots without per-swing scorer calls."""

    count = len(snapshots)
    price = np.zeros(count, dtype=float)
    structural_size = np.zeros(count, dtype=float)
    duration = np.zeros(count, dtype=float)
    volume = np.zeros(count, dtype=float)
    spread = np.zeros(count, dtype=float)
    overall = np.zeros(count, dtype=float)

    price_weight = scorer._price_weight
    structural_size_weight = scorer._structural_size_weight
    duration_weight = scorer._duration_weight
    volume_weight = scorer._volume_weight
    spread_weight = scorer._spread_weight
    total_weight = scorer._total_weight

    if total_weight <= 0:
        return price, structural_size, duration, volume, spread, overall

    for index, snapshot in enumerate(snapshots):
        if snapshot is None:
            continue

        amplitude_sample = snapshot.sorted_amplitudes
        if amplitude_sample:
            price[index] = bisect_right(
                amplitude_sample,
                snapshot.current_amplitude,
            ) / len(amplitude_sample)

        structural_value = snapshot.current_spread_adjusted_amplitude
        structural_sample = snapshot.sorted_spread_adjusted_amplitudes
        if structural_value is not None and structural_sample:
            structural_size[index] = bisect_right(
                structural_sample,
                structural_value,
            ) / len(structural_sample)

        duration_sample = snapshot.sorted_durations
        if duration_sample:
            duration[index] = bisect_right(
                duration_sample,
                snapshot.current_duration,
            ) / len(duration_sample)

        metric_index = int(metric_indices[index])

        volume_sample = snapshot.sorted_volumes
        if volume_sample:
            volume_value = float(volume_values[metric_index])
            volume[index] = bisect_right(
                volume_sample,
                volume_value,
            ) / len(volume_sample)

        spread_sample = snapshot.sorted_spreads
        if spread_sample:
            spread_value = float(spread_values[metric_index])
            spread[index] = bisect_right(
                spread_sample,
                spread_value,
            ) / len(spread_sample)

        overall[index] = min(
            (
                price[index] * price_weight
                + structural_size[index] * structural_size_weight
                + duration[index] * duration_weight
                + volume[index] * volume_weight
                + spread[index] * spread_weight
            ) / total_weight,
            1.0,
        )

    return price, structural_size, duration, volume, spread, overall
