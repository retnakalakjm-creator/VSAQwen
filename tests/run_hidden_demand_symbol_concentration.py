from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.matched_hidden_demand_audit import build_matches, scan_cases
from tests.robustness_hidden_demand_audit import bootstrap_delta
from tests.run_nse_increasing_demand_universe_audit import SYMBOLS

HORIZONS = (3, 5, 10)
DEFAULT_SAMPLE_BARS = 520
DEFAULT_ITERATIONS = 5000
DEFAULT_MIN_CASES = 5


def _scan(symbol: str, sample_bars: int, refresh: bool):
    return scan_cases(symbol, sample_bars, HORIZONS, refresh)


def _robust_label(low: float, high: float) -> str:
    if low > 0.0:
        return "positive"
    if high < 0.0:
        return "negative"
    return "inconclusive"


def _run_bucket(bucket, iterations: int, min_cases: int):
    if len(bucket) < min_cases:
        return None
    observed, low, high = bootstrap_delta(bucket, iterations=iterations)
    return observed, low, high, _robust_label(low, high)


def main() -> None:
    parser = argparse.ArgumentParser(description="Symbol concentration audit for HIDDEN_DEMAND.")
    parser.add_argument("--sample-bars", type=int, default=DEFAULT_SAMPLE_BARS)
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--symbols", nargs="+", default=None)
    parser.add_argument("--min-cases", type=int, default=DEFAULT_MIN_CASES)
    args = parser.parse_args()

    symbols = tuple(args.symbols) if args.symbols else SYMBOLS
    if args.sample_bars <= max(HORIZONS):
        raise ValueError("--sample-bars must exceed the maximum horizon")
    if args.iterations <= 0:
        raise ValueError("--iterations must be positive")
    if args.min_cases < 1:
        raise ValueError("--min-cases must be positive")

    all_cases = []
    failures: list[tuple[str, str, str]] = []
    with ThreadPoolExecutor(max_workers=min(4, len(symbols))) as executor:
        futures = {
            executor.submit(_scan, symbol, args.sample_bars, args.refresh): symbol
            for symbol in symbols
        }
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                all_cases.extend(future.result())
            except Exception as exc:
                failures.append((symbol, type(exc).__name__, str(exc)))

    pairs = build_matches(all_cases)
    print("=== HIDDEN_DEMAND SYMBOL CONCENTRATION AUDIT ===")
    print(f"symbols requested: {len(symbols)}")
    print(f"symbols scanned: {len(symbols) - len(failures)}")
    print(f"sample bars per symbol: {args.sample_bars}")
    print(f"unique matched pairs: {len(pairs)}")
    print(f"minimum cases: {args.min_cases}")
    print(f"bootstrap iterations: {args.iterations}")
    print()
    print(f"{'Symbol':<16}{'H':>3}{'Pairs':>8}{'Delta':>11}{'95% Low':>11}{'95% High':>11}{'Robust':>13}")

    symbol_rows = []
    for symbol in sorted(symbols):
        symbol_pairs = [pair for pair in pairs if pair.target.symbol == symbol]
        for horizon in HORIZONS:
            bucket = [pair for pair in symbol_pairs if pair.target.horizon == horizon]
            result = _run_bucket(bucket, args.iterations, args.min_cases)
            if result is None:
                continue
            observed, low, high, robust = result
            symbol_rows.append((symbol, horizon, len(bucket), robust))
            print(
                f"{symbol:<16}{horizon:>3}{len(bucket):>8}"
                f"{observed:>10.3%}{low:>10.3%}{high:>10.3%}{robust:>13}"
            )

    print()
    print("=== LEAVE-ONE-SYMBOL-OUT ===")
    print(f"{'Dropped':<16}{'H':>3}{'Pairs':>8}{'Delta':>11}{'95% Low':>11}{'95% High':>11}{'Robust':>13}")

    loo_rows = []
    for dropped in sorted(symbols):
        remaining = [pair for pair in pairs if pair.target.symbol != dropped]
        for horizon in HORIZONS:
            bucket = [pair for pair in remaining if pair.target.horizon == horizon]
            result = _run_bucket(bucket, args.iterations, args.min_cases)
            if result is None:
                continue
            observed, low, high, robust = result
            loo_rows.append((dropped, horizon, len(bucket), robust))
            print(
                f"{dropped:<16}{horizon:>3}{len(bucket):>8}"
                f"{observed:>10.3%}{low:>10.3%}{high:>10.3%}{robust:>13}"
            )

    positive_loo = sum(robust == "positive" for _, _, _, robust in loo_rows)
    print()
    print("=== CONCENTRATION SUMMARY ===")
    print(f"symbol-horizon rows reported: {len(symbol_rows)}")
    print(f"leave-one-out positive rows: {positive_loo}/{len(loo_rows)}")
    print(f"leave-one-out all-positive: {positive_loo == len(loo_rows) and bool(loo_rows)}")

    if failures:
        print()
        print("=== SCAN FAILURES ===")
        for symbol, error_type, message in failures:
            print(f"{symbol:<16}{error_type}: {message}")


if __name__ == "__main__":
    main()
