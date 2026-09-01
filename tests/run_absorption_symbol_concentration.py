from __future__ import annotations

import argparse
import random
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from matched_absorption_audit import build_matches, scan_cases
from run_nse_increasing_demand_universe_audit import SYMBOLS

HORIZONS = (3, 5, 10)
BOOTSTRAP_ITERATIONS = 5000


def bootstrap(values: list[float], seed: int) -> tuple[float, float, float]:
    if not values:
        return 0.0, 0.0, 0.0
    observed = sum(values) / len(values)
    if len(values) == 1:
        return observed, observed, observed
    rng = random.Random(seed)
    means = []
    for _ in range(BOOTSTRAP_ITERATIONS):
        means.append(sum(values[rng.randrange(len(values))] for _ in values) / len(values))
    means.sort()
    return observed, means[int(0.025 * BOOTSTRAP_ITERATIONS)], means[int(0.975 * BOOTSTRAP_ITERATIONS) - 1]


def horizon_deltas(pairs, horizon: int) -> list[float]:
    return [
        pair.target.forward_return - pair.control.forward_return
        for pair in pairs
        if pair.target.horizon == horizon
        and pair.target.forward_return is not None
        and pair.control.forward_return is not None
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="ABSORPTION symbol concentration audit.")
    parser.add_argument("--sample-bars", type=int, default=520)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--symbols", nargs="+", default=None)
    parser.add_argument("--min-cases", type=int, default=5)
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
    print("=== ABSORPTION SYMBOL CONCENTRATION AUDIT ===")
    print(f"symbols requested: {len(symbols)}")
    print(f"symbols scanned: {len(symbols) - len(failures)}")
    print(f"sample bars per symbol: {args.sample_bars}")
    print(f"unique matched pairs: {len(pairs)}")
    print(f"minimum cases: {args.min_cases}")
    print(f"bootstrap iterations: {BOOTSTRAP_ITERATIONS}")
    print()
    print("PER SYMBOL")
    print(f"{'Symbol':<16}{'H':>4}{'Pairs':>8}{'Delta':>11}{'95% Low':>11}{'95% High':>11}{'Robust':>12}")
    for symbol in symbols:
        symbol_pairs = [p for p in pairs if p.target.symbol == symbol]
        for horizon in HORIZONS:
            deltas = horizon_deltas(symbol_pairs, horizon)
            if len(deltas) < args.min_cases:
                continue
            observed, low, high = bootstrap(deltas, seed=100000 + abs(hash((symbol, horizon))) % 100000)
            robust = "positive" if low > 0 else "negative" if high < 0 else "inconclusive"
            print(f"{symbol:<16}{horizon:>4}{len(deltas):>8}{observed:>10.3%}{low:>10.3%}{high:>10.3%}{robust:>12}")

    print()
    print("LEAVE-ONE-SYMBOL-OUT")
    print(f"{'Dropped':<16}{'H':>4}{'Pairs':>8}{'Delta':>11}{'95% Low':>11}{'95% High':>11}{'Robust':>12}")
    positive_counts = {h: 0 for h in HORIZONS}
    robust_counts = {h: 0 for h in HORIZONS}
    for symbol in symbols:
        remaining = [p for p in pairs if p.target.symbol != symbol]
        for horizon in HORIZONS:
            deltas = horizon_deltas(remaining, horizon)
            if len(deltas) < args.min_cases:
                continue
            observed, low, high = bootstrap(deltas, seed=200000 + symbols.index(symbol) * 100 + horizon)
            robust = "positive" if low > 0 else "negative" if high < 0 else "inconclusive"
            positive_counts[horizon] += int(observed > 0)
            robust_counts[horizon] += int(robust == "positive")
            print(f"{symbol:<16}{horizon:>4}{len(deltas):>8}{observed:>10.3%}{low:>10.3%}{high:>10.3%}{robust:>12}")

    print()
    print("SUMMARY")
    for horizon in HORIZONS:
        print(
            f"H={horizon}: positive delta {positive_counts[horizon]}/{len(symbols)}; "
            f"robust positive {robust_counts[horizon]}/{len(symbols)}"
        )
    if failures:
        print("FAILURES")
        for symbol, error_type, message in failures:
            print(f"{symbol:<16}{error_type}: {message}")


if __name__ == "__main__":
    main()
