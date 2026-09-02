from pathlib import Path

PATH = Path("market_structure/professional_scorer.py")

REPLACEMENTS = (
    (
        """        history_volumes: deque[tuple[int, float]] = deque()\n        history_spreads: deque[tuple[int, float]] = deque()\n        history_sorted_volumes: list[float] = []\n        history_sorted_spreads: list[float] = []\n\n        high_adjusted: deque[tuple[int, float]] = deque()\n        low_adjusted: deque[tuple[int, float]] = deque()\n        sorted_high_adjusted: list[float] = []\n        sorted_low_adjusted: list[float] = []\n""",
        """        volume_indices: deque[int] = deque()\n        history_volumes: deque[float] = deque()\n        spread_indices: deque[int] = deque()\n        history_spreads: deque[float] = deque()\n        history_sorted_volumes: list[float] = []\n        history_sorted_spreads: list[float] = []\n\n        high_adjusted_indices: deque[int] = deque()\n        high_adjusted: deque[float] = deque()\n        low_adjusted_indices: deque[int] = deque()\n        low_adjusted: deque[float] = deque()\n        sorted_high_adjusted: list[float] = []\n        sorted_low_adjusted: list[float] = []\n""",
    ),
    (
        """            while history_volumes and history_volumes[0][0] < start_index:\n                _, old_volume = history_volumes.popleft()\n                del history_sorted_volumes[\n                    bisect_left(history_sorted_volumes, old_volume)\n                ]\n\n            while history_spreads and history_spreads[0][0] < start_index:\n                _, old_spread = history_spreads.popleft()\n                del history_sorted_spreads[\n                    bisect_left(history_sorted_spreads, old_spread)\n                ]\n\n            while high_adjusted and high_adjusted[0][0] < start_index:\n                _, old_adjusted = high_adjusted.popleft()\n                del sorted_high_adjusted[\n                    bisect_left(sorted_high_adjusted, old_adjusted)\n                ]\n\n            while low_adjusted and low_adjusted[0][0] < start_index:\n                _, old_adjusted = low_adjusted.popleft()\n                del sorted_low_adjusted[\n                    bisect_left(sorted_low_adjusted, old_adjusted)\n                ]\n""",
        """            while volume_indices and volume_indices[0] < start_index:\n                volume_indices.popleft()\n                old_volume = history_volumes.popleft()\n                del history_sorted_volumes[\n                    bisect_left(history_sorted_volumes, old_volume)\n                ]\n\n            while spread_indices and spread_indices[0] < start_index:\n                spread_indices.popleft()\n                old_spread = history_spreads.popleft()\n                del history_sorted_spreads[\n                    bisect_left(history_sorted_spreads, old_spread)\n                ]\n\n            while high_adjusted_indices and high_adjusted_indices[0] < start_index:\n                high_adjusted_indices.popleft()\n                old_adjusted = high_adjusted.popleft()\n                del sorted_high_adjusted[\n                    bisect_left(sorted_high_adjusted, old_adjusted)\n                ]\n\n            while low_adjusted_indices and low_adjusted_indices[0] < start_index:\n                low_adjusted_indices.popleft()\n                old_adjusted = low_adjusted.popleft()\n                del sorted_low_adjusted[\n                    bisect_left(sorted_low_adjusted, old_adjusted)\n                ]\n""",
    ),
    (
        """            volumes = tuple(value for _, value in history_volumes)\n            spreads = tuple(value for _, value in history_spreads)\n""",
        """            volumes = tuple(history_volumes)\n            spreads = tuple(history_spreads)\n""",
    ),
    (
        """            spread_adjusted_amplitudes = tuple(\n                value for _, value in adjusted_window\n            )\n""",
        """            spread_adjusted_amplitudes = tuple(adjusted_window)\n""",
    ),
    (
        """                    high_adjusted.append((index, adjusted))\n                    insort_left(sorted_high_adjusted, adjusted)\n""",
        """                    high_adjusted_indices.append(index)\n                    high_adjusted.append(adjusted)\n                    insort_left(sorted_high_adjusted, adjusted)\n""",
    ),
    (
        """                    low_adjusted.append((index, adjusted))\n                    insort_left(sorted_low_adjusted, adjusted)\n""",
        """                    low_adjusted_indices.append(index)\n                    low_adjusted.append(adjusted)\n                    insort_left(sorted_low_adjusted, adjusted)\n""",
    ),
    (
        """                history_volumes.append((index, volume))\n                insort_left(history_sorted_volumes, volume)\n""",
        """                volume_indices.append(index)\n                history_volumes.append(volume)\n                insort_left(history_sorted_volumes, volume)\n""",
    ),
    (
        """                history_spreads.append((index, spread))\n                insort_left(history_sorted_spreads, spread)\n""",
        """                spread_indices.append(index)\n                history_spreads.append(spread)\n                insort_left(history_sorted_spreads, spread)\n""",
    ),
)


def main() -> None:
    source = PATH.read_text(encoding="utf-8")
    for old, new in REPLACEMENTS:
        if old not in source:
            raise RuntimeError("Expected history snapshot pattern was not found")
        source = source.replace(old, new, 1)
    PATH.write_text(source, encoding="utf-8")
    print(f"Updated {PATH}")


if __name__ == "__main__":
    main()
