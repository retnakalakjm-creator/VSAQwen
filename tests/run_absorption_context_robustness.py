from __future__ import annotations

import argparse
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.matched_absorption_audit import build_matches, scan_cases
from tests.run_nse_increasing_demand_universe_audit import SYMBOLS

HORIZONS = (3, 5, 10)
BOOTSTRAP_ITERATIONS = 5000
MIN_CASES = 5


def bootstrap(values: list[float], seed: int) -> tuple[float, float, float]:
    observed = sum(values) / len(values)
    if len(values) == 1:
        return observed, observed, observed
    rng = random.Random(seed)
    means = sorted(
        sum(values[rng.randrange(len(values))] for _ in values) / len(values)
        for _ in range(BOOTSTRAP_ITERATIONS)
    )
    return observed, means[int(0.025 * BOOTSTRAP_ITERATIONS)], means[int(0.975 * BOOTSTRAP_ITERATIONS) - 1]


def main() -> None:
    parser = argparse.ArgumentParser(description="ABSORPTION state/direction robustness audit.")
    parser.add_argument("--sample-bars", type=int, default=520)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--symbols", nargs="+", default=None)
    parser.add_argument("--min-cases", type=int, default=MIN_CASES)
    args = parser.parse_args()
    symbols = tuple(args.symbols) if args.symbols else tuple(SYMBOLS)
    if args.min_cases < 1:
        raise ValueError("--min-cases must be at least 1")

    all_cases = []
    failures = []
    with ThreadPoolExecutor(max_workers=min(4, len(symbols))) as executor:
        futures = {executor.submit(scan_cases, s, args.sample_bars, HORIZONS, args.refresh): s for s in symbols}
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                all_cases.extend(future.result())
            except Exception as exc:
                failures.append((symbol, type(exc).__name__, str(exc)))

    pairs = build_matches(all_cases)
    print("=== ABSORPTION CONTEXT ROBUSTNESS AUDIT ===")
    print(f"symbols requested: {len(symbols)}")
    print(f"symbols scanned: {len(symbols) - len(failures)}")
    print(f"unique matched pairs: {len(pairs)}")
    print(f"minimum cases: {args.min_cases}")
    print(f"bootstrap iterations: {BOOTSTRAP_ITERATIONS}")
    print()
    print(f"{'State':<12}{'Direction':<12}{'H':>4}{'Pairs':>8}{'Delta':>11}{'95% Low':>11}{'95% High':>11}{'Robust':>12}")
    groups = {}
    for pair in pairs:
        key = (pair.target.trend_state, pair.target.trend_direction, pair.target.horizon)
        if pair.target.forward_return is None or pair.control.forward_return is None:
            continue
        groups.setdefault(key, []).append(pair)

    for (state, direction, horizon), bucket in sorted(groups.items()):
        if len(bucket) < args.min_cases:
            continue
        deltas = [p.target.forward_return - p.control.forward_return for p in bucket]
        observed, low, high = bootstrap(deltas, seed=7000 + horizon)
        robust = "positive" if low > 0 else "negative" if high < 0 else "inconclusive"
        print(f"{state:<12}{direction:<12}{horizon:>4}{len(bucket):>8}{observed:>10.3%}{low:>10.3%}{high:>10.3%}{robust:>12}")

    if failures:
        print("\n=== SCAN FAILURES ===")
        for symbol, error_type, message in failures:
            print(f"{symbol:<16}{error_type}: {message}")


if __name__ == "__main__":
    main()
