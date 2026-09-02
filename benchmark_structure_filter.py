from __future__ import annotations

import argparse
import time

import numpy as np
import pandas as pd

import config
from engine.columns import (
    COL_AVG_SPREAD,
    COL_AVG_VOLUME,
    COL_CLOSE,
    COL_HIGH,
    COL_LOW,
    COL_OPEN,
    COL_SPREAD,
    COL_VOLUME,
)
from market_structure.professional_scorer import ProfessionalScorer
from market_structure.structure_filter import StructureFilter
from models import Swing, SwingType


def make_inputs(size: int, seed: int = 42):
    if size < 2:
        raise ValueError("size must be at least 2")

    rng = np.random.default_rng(seed)
    low = rng.uniform(50.0, 150.0, size)
    spread = rng.uniform(0.5, 8.0, size)
    high = low + spread
    open_values = low + rng.uniform(0.05, 0.95, size) * spread
    close_values = low + rng.uniform(0.05, 0.95, size) * spread
    volume = rng.uniform(50_000.0, 2_000_000.0, size)
    avg_volume = rng.uniform(250_000.0, 1_500_000.0, size)
    avg_spread = rng.uniform(1.0, 6.0, size)

    metrics = pd.DataFrame(
        {
            COL_OPEN: open_values,
            COL_HIGH: high,
            COL_LOW: low,
            COL_CLOSE: close_values,
            COL_VOLUME: volume,
            COL_SPREAD: spread,
            COL_AVG_VOLUME: avg_volume,
            COL_AVG_SPREAD: avg_spread,
        }
    )

    swings = tuple(
        Swing(
            type=SwingType.HIGH if i % 2 == 0 else SwingType.LOW,
            price=float(high[i] if i % 2 == 0 else low[i]),
            bar_index=i,
            confirmation_index=i + 1,
            week_beginning=f"2025-01-{(i % 28) + 1:02d}",
            metrics_index=i,
        )
        for i in range(size - 1)
    )

    return swings, metrics


def scalar_smart_money_scores(self: ProfessionalScorer, arrays, indices, *, include_components=True):
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

    return tuple(
        self._smart_money.score_values(
            bar_count=2 if int(index) > 0 else 1,
            open_value=float(open_values[index]),
            low_value=float(low_values[index]),
            close_value=float(close_values[index]),
            spread_value=float(spread_values[index]),
            avg_spread=float(avg_spread_values[index]),
            volume_value=float(volume_values[index]),
            avg_volume=float(avg_volume_values[index]),
            include_components=include_components,
        )
        for index in indices
    )


def run_filter(swings, metrics, *, scalar: bool) -> list:
    original = ProfessionalScorer.smart_money_scores_batch
    try:
        if scalar:
            ProfessionalScorer.smart_money_scores_batch = scalar_smart_money_scores
        return StructureFilter().filter(swings, metrics)
    finally:
        ProfessionalScorer.smart_money_scores_batch = original


def elapsed(fn, repeats: int) -> float:
    start = time.perf_counter()
    for _ in range(repeats):
        fn()
    return (time.perf_counter() - start) / repeats


def signature(results):
    return tuple(
        (
            item.swing.metrics_index,
            item.evaluation.smart_money,
            item.evaluation.professional.overall,
        )
        for item in results
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark full StructureFilter scoring: scalar Smart Money vs batch Smart Money."
    )
    parser.add_argument("--size", type=int, default=5000)
    parser.add_argument("--repeats", type=int, default=10)
    args = parser.parse_args()

    if args.size < 2 or args.repeats <= 0:
        raise SystemExit("--size must be >= 2 and --repeats must be > 0")

    swings, metrics = make_inputs(args.size)

    batch_results = run_filter(swings, metrics, scalar=False)
    scalar_results = run_filter(swings, metrics, scalar=True)

    if signature(batch_results) != signature(scalar_results):
        raise RuntimeError("Batch StructureFilter results do not match scalar results.")

    batch_time = elapsed(
        lambda: run_filter(swings, metrics, scalar=False),
        args.repeats,
    )
    scalar_time = elapsed(
        lambda: run_filter(swings, metrics, scalar=True),
        args.repeats,
    )
    speedup = scalar_time / batch_time if batch_time > 0 else float("inf")

    print(f"swings:     {len(swings):,}")
    print(f"repeats:    {args.repeats}")
    print(f"scalar:     {scalar_time * 1000:.3f} ms")
    print(f"batch:      {batch_time * 1000:.3f} ms")
    print(f"speedup:    {speedup:.2f}x")
    print(f"structural: {len(batch_results):,}")


if __name__ == "__main__":
    main()
