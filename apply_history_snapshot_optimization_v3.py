from pathlib import Path

PATH = Path("market_structure/professional_scorer.py")
OLD_START = "    @profile\n    def prepare_history_snapshots(\n"
NEXT_DEF = "\n    def smart_money_scores_batch(\n"

NEW_METHOD = '''    @profile
    def prepare_history_snapshots(
        self,
        swings: list[Swing] | tuple[Swing, ...],
        arrays,
        lookback: int,
    ) -> tuple[SwingHistorySnapshot | None, ...]:
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
        history_indices: deque[int] = deque()
        history_amplitudes: deque[float] = deque()
        history_durations: deque[int] = deque()
        history_volumes: deque[tuple[int, float]] = deque()
        history_spreads: deque[tuple[int, float]] = deque()
        high_adjusted: deque[tuple[int, float]] = deque()
        low_adjusted: deque[tuple[int, float]] = deque()

        for index, current in enumerate(swings):
            if index == 0:
                continue

            start = max(0, index - lookback + 1)
            start_index = max(1, start)

            while history_indices and history_indices[0] < start_index:
                history_indices.popleft()
                history_amplitudes.popleft()
                history_durations.popleft()

            while history_volumes and history_volumes[0][0] < start_index:
                history_volumes.popleft()

            while history_spreads and history_spreads[0][0] < start_index:
                history_spreads.popleft()

            while high_adjusted and high_adjusted[0][0] < start_index:
                high_adjusted.popleft()

            while low_adjusted and low_adjusted[0][0] < start_index:
                low_adjusted.popleft()

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
                sorted_amplitudes=tuple(sorted(amplitudes)),
                sorted_spread_adjusted_amplitudes=tuple(
                    sorted(spread_adjusted_amplitudes)
                ),
                sorted_durations=tuple(sorted(durations)),
                sorted_volumes=tuple(sorted(volumes)),
                sorted_spreads=tuple(sorted(spreads)),
            )

            if history_size == 0:
                continue

            history_indices.append(index)
            history_amplitudes.append(pair_amplitude)
            history_durations.append(pair_duration)

            if avg_spread_valid[metrics_index] and avg_spread > 0:
                adjusted = pair_amplitude / avg_spread
                (high_adjusted if is_high else low_adjusted).append(
                    (index, adjusted)
                )

            if volume_valid[metrics_index]:
                history_volumes.append(
                    (index, float(volume_values[metrics_index]))
                )

            if spread_valid[metrics_index]:
                history_spreads.append(
                    (index, float(spread_values[metrics_index]))
                )

        return tuple(snapshots)
'''


def main() -> None:
    source = PATH.read_text(encoding="utf-8")
    start = source.index(OLD_START)
    end = source.index(NEXT_DEF, start)
    PATH.write_text(source[:start] + NEW_METHOD + source[end:], encoding="utf-8")
    print(f"Updated {PATH}")


if __name__ == "__main__":
    main()
