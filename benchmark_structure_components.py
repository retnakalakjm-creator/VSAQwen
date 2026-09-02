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
from market_structure.swing_history import SwingHistoryAnalyzer
from models import Swing, SwingType


def make_inputs(size: int, seed: int = 42):
    rng = np.random.default_rng(seed)
    low = rng.uniform(50.0, 150.0, size)
    spread = rng.uniform(0.5, 8.0, size)
    high = low + spread
    opens = low + rng.uniform(0.05, 0.95, size) * spread
    closes = low + rng.uniform(0.05, 0.95, size) * spread
    volume = rng.uniform(50_000.0, 2_000_000.0, size)
    avg_volume = rng.uniform(250_000.0, 1_500_000.0, size)
    avg_spread = rng.uniform(1.0, 6.0, size)
    metrics = pd.DataFrame(
        {
            COL_OPEN: opens,
            COL_HIGH: high,
            COL_LOW: low,
            COL_CLOSE: closes,
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
    parser = argparse.ArgumentParser(description="Benchmark ProfessionalScorer history and structural stages.")
    parser.add_argument("--size", type=int, default=5000)
    parser.add_argument("--repeats", type=int, default=20)
    parser.add_argument("--lookback", type=int, default=10)
    args = parser.parse_args()

    if args.size <= 1 or args.repeats <= 0 or args.lookback <= 0:
        raise SystemExit("--size > 1, --repeats > 0 and --lookback > 0 are required")

    metrics, swings = make_inputs(args.size)
    scorer = ProfessionalScorer()
    arrays = scorer._metric_arrays(metrics)

    snapshots = scorer.prepare_history_snapshots(swings, arrays, args.lookback)
    indices = tuple(swing.metrics_index for swing in swings)
    smart_money = scorer.smart_money_scores_batch(arrays, indices)
    prepared_values = scorer._structure._prepared_values

    history_time = elapsed(
        lambda: scorer.prepare_history_snapshots(swings, arrays, args.lookback),
        args.repeats,
    )
    smart_money_time = elapsed(
        lambda: scorer.smart_money_scores_batch(arrays, indices),
        args.repeats,
    )

    def structural_stage() -> int:
        count = 0
        for index, swing in enumerate(swings):
            if index == 0:
                continue
            snapshot = snapshots[index]
            if snapshot is None:
                continue
            metric_index = indices[index]
            prepared = prepared_values(
                snapshot=snapshot,
                volume=float(arrays[4][metric_index]),
                spread=float(arrays[5][metric_index]),
            )
            smart_money_score = smart_money[index].overall
            if (prepared[-1] + smart_money_score) >= 0.0:
                count += 1
        return count

    structural_time = elapsed(structural_stage, args.repeats)
    total_isolated = history_time + smart_money_time + structural_time

    print(f"swings:             {args.size:,}")
    print(f"repeats:            {args.repeats}")
    print(f"lookback:           {args.lookback}")
    print(f"history snapshots:  {history_time * 1000:.3f} ms")
    print(f"smart money batch:  {smart_money_time * 1000:.3f} ms")
    print(f"structural stage:   {structural_time * 1000:.3f} ms")
    print(f"isolated total:     {total_isolated * 1000:.3f} ms")
    print(f"snapshots:          {len(snapshots) - 1:,}")


if __name__ == "__main__":
    main()
