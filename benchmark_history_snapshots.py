from __future__ import annotations

import argparse
import time

import numpy as np
import pandas as pd

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
from models import Swing, SwingType


def make_inputs(size: int, seed: int = 42):
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
            type=SwingType.HIGH if index % 2 == 0 else SwingType.LOW,
            price=float(high[index] if index % 2 == 0 else low[index]),
            bar_index=index,
            confirmation_index=index + 1,
            week_beginning=f"2025-01-{(index % 28) + 1:02d}",
            metrics_index=index,
        )
        for index in range(size)
    )

    return metrics, swings


def elapsed(fn, repeats: int) -> float:
    start = time.perf_counter()
    for _ in range(repeats):
        fn()
    return (time.perf_counter() - start) / repeats


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark ProfessionalScorer history snapshot preparation."
    )
    parser.add_argument("--size", type=int, default=5000)
    parser.add_argument("--repeats", type=int, default=20)
    parser.add_argument("--lookback", type=int, default=10)
    args = parser.parse_args()

    if args.size <= 0 or args.repeats <= 0 or args.lookback <= 0:
        raise SystemExit("--size, --repeats and --lookback must be greater than zero")

    metrics, swings = make_inputs(args.size)
    scorer = ProfessionalScorer()
    arrays = scorer._metric_arrays(metrics)

    baseline = scorer.prepare_history_snapshots(
        swings,
        arrays,
        args.lookback,
    )

    elapsed_time = elapsed(
        lambda: scorer.prepare_history_snapshots(
            swings,
            arrays,
            args.lookback,
        ),
        args.repeats,
    )

    print(f"swings:     {args.size}")
    print(f"repeats:    {args.repeats}")
    print(f"lookback:   {args.lookback}")
    print(f"time:       {elapsed_time * 1000:.3f} ms")
    print(f"snapshots:  {sum(snapshot is not None for snapshot in baseline):,}")


if __name__ == "__main__":
    main()
