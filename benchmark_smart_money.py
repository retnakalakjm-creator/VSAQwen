from __future__ import annotations

import argparse
import time

import numpy as np

from market_structure.batched_smart_money import BatchedSmartMoneyAnalyzer
from market_structure.smart_money import SmartMoneyAnalyzer


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

    indices = np.arange(size, dtype=np.int64)

    return (
        open_values,
        high,
        low,
        close_values,
        volume,
        spread,
        avg_volume,
        avg_spread,
        indices,
    )


def scalar_score(analyzer: SmartMoneyAnalyzer, values):
    (
        open_values,
        _high,
        low_values,
        close_values,
        volume_values,
        spread_values,
        avg_volume_values,
        avg_spread_values,
        indices,
    ) = values

    return tuple(
        analyzer.score_values(
            bar_count=2 if int(index) > 0 else 1,
            open_value=float(open_values[index]),
            low_value=float(low_values[index]),
            close_value=float(close_values[index]),
            spread_value=float(spread_values[index]),
            avg_spread=float(avg_spread_values[index]),
            volume_value=float(volume_values[index]),
            avg_volume=float(avg_volume_values[index]),
        )
        for index in indices
    )


def batch_score(analyzer: BatchedSmartMoneyAnalyzer, values):
    (
        open_values,
        _high,
        low_values,
        close_values,
        volume_values,
        spread_values,
        avg_volume_values,
        avg_spread_values,
        indices,
    ) = values

    return analyzer.score_values_batch(
        open_values=open_values,
        low_values=low_values,
        close_values=close_values,
        spread_values=spread_values,
        avg_spread_values=avg_spread_values,
        volume_values=volume_values,
        avg_volume_values=avg_volume_values,
        indices=indices,
    )


def elapsed(fn, repeats: int) -> float:
    start = time.perf_counter()
    for _ in range(repeats):
        fn()
    return (time.perf_counter() - start) / repeats


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark scalar vs batched Smart Money scoring.")
    parser.add_argument("--size", type=int, default=5000)
    parser.add_argument("--repeats", type=int, default=20)
    args = parser.parse_args()

    if args.size <= 0 or args.repeats <= 0:
        raise SystemExit("--size and --repeats must be greater than zero")

    values = make_inputs(args.size)
    scalar = SmartMoneyAnalyzer()
    batch = BatchedSmartMoneyAnalyzer()

    scalar_scores = scalar_score(scalar, values)
    batch_scores = batch_score(batch, values)
    if scalar_scores != batch_scores:
        raise RuntimeError("Batch scores do not match scalar scores.")

    scalar_time = elapsed(lambda: scalar_score(scalar, values), args.repeats)
    batch_time = elapsed(lambda: batch_score(batch, values), args.repeats)
    speedup = scalar_time / batch_time if batch_time > 0 else float("inf")

    print(f"rows:       {args.size}")
    print(f"repeats:    {args.repeats}")
    print(f"scalar:     {scalar_time * 1000:.3f} ms")
    print(f"batch:      {batch_time * 1000:.3f} ms")
    print(f"speedup:    {speedup:.2f}x")


if __name__ == "__main__":
    main()
