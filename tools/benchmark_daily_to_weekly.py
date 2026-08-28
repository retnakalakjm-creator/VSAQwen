from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from config import WEEK_RULE
from data import daily_to_weekly


def reference_daily_to_weekly(df: pd.DataFrame) -> pd.DataFrame:
    weekly = (
        df.resample(WEEK_RULE)
        .agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }
        )
        .dropna()
    )
    week_start = df.groupby(pd.Grouper(freq=WEEK_RULE)).apply(
        lambda x: x.index.min()
    )
    weekly["week_beginning"] = week_start
    weekly = weekly[
        ["week_beginning", "open", "high", "low", "close", "volume"]
    ]
    return weekly.reset_index(drop=True)


def timed(fn, df: pd.DataFrame, repeats: int) -> tuple[pd.DataFrame, float]:
    best = float("inf")
    result = None
    for _ in range(repeats):
        start = time.perf_counter()
        result = fn(df)
        elapsed = time.perf_counter() - start
        best = min(best, elapsed)
    return result, best


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", type=int, default=100_000)
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()

    if args.size <= 0:
        parser.error("--size must be greater than zero")
    if args.repeats <= 0:
        parser.error("--repeats must be greater than zero")

    # Use a bounded minute-resolution index. This avoids constructing a
    # Timedelta proportional to --size, which can overflow for large inputs.
    # The benchmark needs a regular DatetimeIndex for resampling, not a
    # multi-century calendar span.
    end = pd.Timestamp("2025-12-31 23:59:00")
    index = pd.date_range(end=end, periods=args.size, freq="min")

    rng = np.random.default_rng(42)
    close = 100.0 + np.cumsum(rng.normal(0.0, 1.0, args.size))
    spread = rng.uniform(0.1, 2.0, args.size)
    df = pd.DataFrame(
        {
            "open": close + rng.normal(0.0, 0.3, args.size),
            "high": close + spread,
            "low": close - spread,
            "close": close,
            "volume": rng.integers(1_000, 100_000, args.size),
        },
        index=index,
    )
    df.index.name = "date"

    expected, reference_time = timed(reference_daily_to_weekly, df, args.repeats)
    actual, optimized_time = timed(daily_to_weekly, df, args.repeats)

    pd.testing.assert_frame_equal(actual, expected, check_exact=True)

    print(f"size={args.size:,}")
    print(f"repeats={args.repeats}")
    print(f"reference_best_seconds={reference_time:.6f}")
    print(f"optimized_best_seconds={optimized_time:.6f}")
    print(f"speedup={reference_time / optimized_time:.2f}x")
    print("equivalence=PASS")


if __name__ == "__main__":
    main()
