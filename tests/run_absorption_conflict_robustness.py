from __future__ import annotations

import argparse
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from engine.columns import (
    COL_DIRECTION,
    COL_SPREAD_CLASS,
    COL_VOLUME_CLASS,
)
from evidence.engine import EvidenceEngine
from evidence.rules import is_down_bar, spread_increasing, volume_increasing
from metrics_engine import MetricsEngine
from models import Direction, SpreadClass, VolumeClass
from tests.matched_absorption_audit import build_matches, scan_cases
from tests.run_nse_increasing_demand_universe_audit import SYMBOLS

HORIZONS = (3, 5, 10)
BOOTSTRAP_ITERATIONS = 5000
MIN_CASES = 5


def bootstrap_mean(values: list[float], seed: int) -> tuple[float, float, float]:
    observed = sum(values) / len(values)
    if len(values) == 1:
        return observed, observed, observed
    rng = random.Random(seed)
    means = sorted(
        sum(values[rng.randrange(len(values))] for _ in values) / len(values)
        for _ in range(BOOTSTRAP_ITERATIONS)
    )
    return (
        observed,
        means[int(0.025 * BOOTSTRAP_ITERATIONS)],
        means[int(0.975 * BOOTSTRAP_ITERATIONS) - 1],
    )


def bootstrap_difference(
    first: list[float],
    second: list[float],
    seed: int,
) -> tuple[float, float, float]:
    observed = sum(first) / len(first) - sum(second) / len(second)
    rng = random.Random(seed)
    differences = sorted(
        (
            sum(first[rng.randrange(len(first))] for _ in first) / len(first)
            - sum(second[rng.randrange(len(second))] for _ in second) / len(second)
        )
        for _ in range(BOOTSTRAP_ITERATIONS)
    )
    return (
        observed,
        differences[int(0.025 * BOOTSTRAP_ITERATIONS)],
        differences[int(0.975 * BOOTSTRAP_ITERATIONS) - 1],
    )


def conflict_indices(symbol: str, sample_bars: int, refresh: bool) -> set[int]:
    metrics = MetricsEngine().calculate(
        daily_to_weekly(download_data(symbol, refresh=refresh))
    )
    builder = EvidenceEngine()
    start = max(21, len(metrics) - sample_bars - max(HORIZONS))
    conflicts: set[int] = set()
    for index in range(start, len(metrics)):
        bar = builder._create_bar_context(metrics.iloc[index], index)
        previous = builder._create_bar_context(metrics.iloc[index - 1], index - 1)
        if (
            is_down_bar(bar)
            and volume_increasing(bar, previous)
            and spread_increasing(bar, previous)
        ):
            conflicts.add(index)
    return conflicts


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ABSORPTION supply-conflict robustness audit."
    )
    parser.add_argument("--sample-bars", type=int, default=520)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--symbols", nargs="+", default=None)
    parser.add_argument("--min-cases", type=int, default=MIN_CASES)
    args = parser.parse_args()

    if args.sample_bars <= max(HORIZONS):
        raise ValueError("--sample-bars must exceed the maximum horizon")
    if args.min_cases < 1:
        raise ValueError("--min-cases must be at least 1")

    symbols = tuple(args.symbols) if args.symbols else tuple(SYMBOLS)
    all_cases = []
    failures = []

    with ThreadPoolExecutor(max_workers=min(4, len(symbols))) as executor:
        futures = {
            executor.submit(scan_cases, symbol, args.sample_bars, HORIZONS, args.refresh): symbol
            for symbol in symbols
        }
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                all_cases.extend(future.result())
            except Exception as exc:
                failures.append((symbol, type(exc).__name__, str(exc)))

    pairs = build_matches(all_cases)

    conflict_by_symbol: dict[str, set[int]] = {}
    with ThreadPoolExecutor(max_workers=min(4, len(symbols))) as executor:
        futures = {
            executor.submit(conflict_indices, symbol, args.sample_bars, args.refresh): symbol
            for symbol in symbols
            if symbol not in {item[0] for item in failures}
        }
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                conflict_by_symbol[symbol] = future.result()
            except Exception as exc:
                failures.append((symbol, type(exc).__name__, str(exc)))

    grouped: dict[tuple[str, int], list[float]] = {}
    for pair in pairs:
        if pair.target.forward_return is None or pair.control.forward_return is None:
            continue
        conflict = pair.target.bar_index in conflict_by_symbol.get(pair.target.symbol, set())
        bucket = "conflict" if conflict else "clean"
        grouped.setdefault((bucket, pair.target.horizon), []).append(
            pair.target.forward_return - pair.control.forward_return
        )

    print("=== ABSORPTION CONFLICT ROBUSTNESS AUDIT ===")
    print(f"symbols requested: {len(symbols)}")
    print(f"symbols scanned: {len(symbols) - len(failures)}")
    print(f"sample bars per symbol: {args.sample_bars}")
    print(f"unique matched pairs: {len(pairs)}")
    print(f"minimum cases: {args.min_cases}")
    print(f"bootstrap iterations: {BOOTSTRAP_ITERATIONS}")
    print("conflict definition: down bar + increasing volume + increasing spread")
    print()
    print(
        f"{'Group':<10}{'H':>4}{'Pairs':>8}{'Delta':>11}"
        f"{'95% Low':>11}{'95% High':>11}{'Robust':>12}"
    )

    stats: dict[tuple[str, int], tuple[float, float, float]] = {}
    for bucket in ("clean", "conflict"):
        for horizon in HORIZONS:
            values = grouped.get((bucket, horizon), [])
            if len(values) < args.min_cases:
                continue
            stats[(bucket, horizon)] = bootstrap_mean(
                values,
                seed=31000 + horizon + (0 if bucket == "clean" else 100),
            )
            observed, low, high = stats[(bucket, horizon)]
            robust = "positive" if low > 0 else "negative" if high < 0 else "inconclusive"
            print(
                f"{bucket:<10}{horizon:>4}{len(values):>8}"
                f"{observed:>10.3%}{low:>10.3%}{high:>10.3%}{robust:>12}"
            )

    print()
    print("CONFLICT PENALTY (clean delta - conflict delta)")
    print(
        f"{'H':>4}{'Clean':>12}{'Conflict':>12}{'Penalty':>12}"
        f"{'95% Low':>12}{'95% High':>12}{'Robust':>12}"
    )
    for horizon in HORIZONS:
        clean = grouped.get(("clean", horizon), [])
        conflict = grouped.get(("conflict", horizon), [])
        if len(clean) < args.min_cases or len(conflict) < args.min_cases:
            continue
        observed, low, high = bootstrap_difference(clean, conflict, seed=32000 + horizon)
        robust = "positive" if low > 0 else "negative" if high < 0 else "inconclusive"
        print(
            f"{horizon:>4}"
            f"{sum(clean) / len(clean):>11.3%}"
            f"{sum(conflict) / len(conflict):>11.3%}"
            f"{observed:>11.3%}"
            f"{low:>11.3%}"
            f"{high:>11.3%}"
            f"{robust:>12}"
        )

    print()
    for horizon in HORIZONS:
        conflict = grouped.get(("conflict", horizon), [])
        clean = grouped.get(("clean", horizon), [])
        if len(conflict) >= args.min_cases:
            print(f"H={horizon}: conflict cases {len(conflict)}")
        if len(clean) >= args.min_cases:
            print(f"H={horizon}: clean cases {len(clean)}")

    if failures:
        print("\n=== FAILURES ===")
        for symbol, error_type, message in failures:
            print(f"{symbol:<16}{error_type}: {message}")


if __name__ == "__main__":
    main()
