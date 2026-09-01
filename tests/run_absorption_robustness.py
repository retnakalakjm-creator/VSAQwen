from __future__ import annotations

import argparse
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from matched_absorption_audit import build_matches, scan_cases
from run_nse_increasing_demand_universe_audit import SYMBOLS

HORIZONS = (3, 5, 10)
BOOTSTRAP_ITERATIONS = 5000


def _bootstrap(values: list[float], seed: int) -> tuple[float, float, float]:
    if not values:
        return 0.0, 0.0, 0.0
    observed = sum(values) / len(values)
    if len(values) == 1:
        return observed, observed, observed
    rng = random.Random(seed)
    samples = [
        sum(values[rng.randrange(len(values))] for _ in values) / len(values)
        for _ in range(BOOTSTRAP_ITERATIONS)
    ]
    samples.sort()
    low = samples[int(0.025 * BOOTSTRAP_ITERATIONS)]
    high = samples[int(0.975 * BOOTSTRAP_ITERATIONS) - 1]
    return observed, low, high


def main() -> None:
    parser = argparse.ArgumentParser(description="Full-universe ABSORPTION matched-control robustness audit.")
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
    failures: list[tuple[str, str, str]] = []

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

    print("=== ABSORPTION CONDITIONAL ROBUSTNESS AUDIT ===")
    print(f"symbols requested: {len(symbols)}")
    print(f"symbols scanned: {len(symbols) - len(failures)}")
    print(f"sample bars per symbol: {args.sample_bars}")
    print(f"candidate events: {sum(1 for _, target in all_cases if target)}")
    print(f"control events: {sum(1 for _, target in all_cases if not target)}")
    print(f"unique matched pairs: {len(pairs)}")
    print(f"minimum cases: {args.min_cases}")
    print(f"bootstrap iterations: {BOOTSTRAP_ITERATIONS}")
    print()
    print(f"{'Horizon':>8}{'Pairs':>8}{'Target':>12}{'Control':>12}{'Delta':>12}{'95% Low':>12}{'95% High':>12}{'Robust':>12}")

    for horizon in HORIZONS:
        bucket = [
            pair for pair in pairs
            if pair.target.horizon == horizon
            and pair.target.forward_return is not None
            and pair.control.forward_return is not None
        ]
        if len(bucket) < args.min_cases:
            print(f"{horizon:>8}{len(bucket):>8}      insufficient cases")
            continue
        target_returns = [pair.target.forward_return for pair in bucket]
        control_returns = [pair.control.forward_return for pair in bucket]
        deltas = [target - control for target, control in zip(target_returns, control_returns)]
        observed, low, high = _bootstrap(deltas, seed=1000 + horizon)
        target_mean = sum(target_returns) / len(target_returns)
        control_mean = sum(control_returns) / len(control_returns)
        robust = "positive" if low > 0.0 else "negative" if high < 0.0 else "inconclusive"
        print(
            f"{horizon:>8}{len(bucket):>8}"
            f"{target_mean:>11.3%}{control_mean:>11.3%}"
            f"{observed:>11.3%}{low:>11.3%}{high:>11.3%}{robust:>12}"
        )

    if failures:
        print()
        print("=== SCAN FAILURES ===")
        for symbol, error_type, message in failures:
            print(f"{symbol:<16}{error_type}: {message}")


if __name__ == "__main__":
    main()
