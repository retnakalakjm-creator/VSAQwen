from __future__ import annotations

import argparse
import time

import numpy as np
import pandas as pd

from stats_utils import historical_percentile_rank


def reference(series: pd.Series, window: int) -> pd.Series:
    def percentile(values: pd.Series) -> float:
        current = values.iloc[-1]
        history = values.iloc[:-1]
        if history.empty:
            return 50.0
        return (history <= current).mean() * 100.0

    return (
        series.rolling(window=window + 1, min_periods=window + 1)
        .apply(percentile, raw=False)
        .fillna(50.0)
    )


def timed(fn, series: pd.Series, window: int, repeats: int) -> tuple[pd.Series, float]:
    best = float("inf")
    result = None
    for _ in range(repeats):
        start = time.perf_counter()
        result = fn(series, window)
        elapsed = time.perf_counter() - start
        best = min(best, elapsed)
    return result, best


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", type=int, default=100_000)
    parser.add_argument("--window", type=int, default=50)
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()

    rng = np.random.default_rng(42)
    values = rng.normal(size=args.size)
    # Include realistic missing values without making the test pathological.
    values[rng.random(args.size) < 0.01] = np.nan
    series = pd.Series(values)

    expected, reference_time = timed(reference, series, args.window, args.repeats)
    actual, optimized_time = timed(historical_percentile_rank, series, args.window, args.repeats)

    pd.testing.assert_series_equal(actual, expected, check_exact=True)

    print(f"size={args.size:,}")
    print(f"window={args.window}")
    print(f"repeats={args.repeats}")
    print(f"reference_best_seconds={reference_time:.6f}")
    print(f"optimized_best_seconds={optimized_time:.6f}")
    print(f"speedup={reference_time / optimized_time:.2f}x")
    print("equivalence=PASS")


if __name__ == "__main__":
    main()
