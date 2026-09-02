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
        history_amplitudes: deque[float] = deque()
        history_durations: deque[int] = deque()
        history_volumes: deque[float] = deque()
        history_spreads: deque[float] = deque()
        high_adjusted: deque[float] = deque()
        low_adjusted: deque[float] = deque()

        for index, current in enumerate(swings):
            if index == 0:
                continue

            pair_amplitude = pair_amplitudes[index - 1]
            pair_duration = pair_durations[index - 1]
            metrics_index = current.metrics_index
            avg_spread = avg_spread_values[metrics_index]
            is_high = current.type is SwingType.HIGH

            if history_amplitudes:
                amplitudes = tuple(history_amplitudes)
                sorted_amplitudes = tuple(sorted(history_amplitudes))
            else:
                amplitudes = ()
                sorted_amplitudes = ()

            if history_durations:
                durations = tuple(history_durations)
                sorted_durations = tuple(sorted(history_durations))
            else:
                durations = ()
                sorted_durations = ()

            if history_volumes:
                volumes = tuple(history_volumes)
                sorted_volumes = tuple(sorted(history_volumes))
            else:
                volumes = ()
                sorted_volumes = ()

            if history_spreads:
                spreads = tuple(history_spreads)
                sorted_spreads = tuple(sorted(history_spreads))
            else:
                spreads = ()
                sorted_spreads = ()

            adjusted_window = high_adjusted if is_high else low_adjusted
            if adjusted_window:
                spread_adjusted_amplitudes = tuple(adjusted_window)
                sorted_spread_adjusted_amplitudes = tuple(sorted(adjusted_window))
            else:
                spread_adjusted_amplitudes = ()
                sorted_spread_adjusted_amplitudes = ()

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
                sorted_amplitudes=sorted_amplitudes,
                sorted_spread_adjusted_amplitudes=sorted_spread_adjusted_amplitudes,
                sorted_durations=sorted_durations,
                sorted_volumes=sorted_volumes,
                sorted_spreads=sorted_spreads,
            )

            if history_size == 0:
                continue

            if len(history_amplitudes) >= history_size:
                history_amplitudes.popleft()
                history_durations.popleft()

            history_amplitudes.append(pair_amplitude)
            history_durations.append(pair_duration)

            if avg_spread_valid[metrics_index] and avg_spread > 0:
                adjusted = pair_amplitude / avg_spread
                target = high_adjusted if is_high else low_adjusted
                if len(target) >= history_size:
                    target.popleft()
                target.append(adjusted)

            if volume_valid[metrics_index]:
                if len(history_volumes) >= history_size:
                    history_volumes.popleft()
                history_volumes.append(float(volume_values[metrics_index]))

            if spread_valid[metrics_index]:
                if len(history_spreads) >= history_size:
                    history_spreads.popleft()
                history_spreads.append(float(spread_values[metrics_index]))

        return tuple(snapshots)
'''


def main() -> None:
    source = PATH.read_text(encoding="utf-8")
    start = source.index(OLD_START)
    end = source.index(NEXT_DEF, start)
    updated = source[:start] + NEW_METHOD + source[end:]
    PATH.write_text(updated, encoding="utf-8")
    print(f"Updated {PATH}")


if __name__ == "__main__":
    main()
