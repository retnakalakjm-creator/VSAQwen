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

from data import daily_to_weekly
from metrics_engine import MetricsEngine
from scanner import ScannerEngine


def make_daily(size: int, seed: int) -> pd.DataFrame:
    end = pd.Timestamp("2025-12-31")
    start = end - pd.to_timedelta(size - 1, unit="D")
    index = pd.date_range(start=start, periods=size, freq="D")
    rng = np.random.default_rng(seed)
    log_returns = rng.normal(0.0, 0.01, size)
    close = 100.0 * np.exp(np.cumsum(log_returns))
    spread = rng.uniform(0.1, 2.0, size)
    frame = pd.DataFrame(
        {
            "open": close * np.exp(rng.normal(0.0, 0.003, size)),
            "high": close + spread,
            "low": np.maximum(close - spread, 0.01),
            "close": close,
            "volume": rng.integers(1_000, 100_000, size),
        },
        index=index,
    )
    frame.index.name = "date"
    return frame


def prepare(symbol_count: int, daily_size: int):
    datasets = []
    for symbol_id in range(symbol_count):
        daily = make_daily(daily_size, 1000 + symbol_id)
        weekly = daily_to_weekly(daily)
        metrics = MetricsEngine().calculate(weekly)
        datasets.append(metrics)
    return datasets


def scan_sequential(datasets):
    engine = ScannerEngine()
    results = []
    for metrics in datasets:
        results.append(engine.scan_actionable(metrics))
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark multi-symbol latest-bar scanning")
    parser.add_argument("--symbols", type=int, default=10)
    parser.add_argument("--daily-size", type=int, default=5000)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()

    if args.symbols <= 0 or args.daily_size <= 0 or args.repeats <= 0:
        parser.error("symbols, daily-size and repeats must be greater than zero")

    datasets = prepare(args.symbols, args.daily_size)
    best = float("inf")
    result = None
    for _ in range(args.repeats):
        start = time.perf_counter()
        result = scan_sequential(datasets)
        best = min(best, time.perf_counter() - start)

    actionable = sum(bool(item) for item in result)
    print(f"symbols={args.symbols:,}")
    print(f"daily_size={args.daily_size:,}")
    print(f"weekly_size={len(datasets[0]):,}")
    print(f"repeats={args.repeats}")
    print(f"total_best_seconds={best:.6f}")
    print(f"symbols_per_second={args.symbols / best:.2f}")
    print(f"actionable_symbols={actionable}")


if __name__ == "__main__":
    main()
