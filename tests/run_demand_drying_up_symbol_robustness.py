from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from matched_demand_drying_up_audit import _scan_cases, build_matches
from run_nse_increasing_demand_universe_audit import SYMBOLS
from symbol_robustness_demand_drying_up_audit import (
    leave_one_symbol_out,
    summarize_symbol_robustness,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Symbol-level robustness and leave-one-symbol-out audit for DEMAND_DRYING_UP."
    )
    parser.add_argument("--iterations", type=int, default=5000)
    parser.add_argument("--sample-bars", type=int, default=520)
    parser.add_argument("--min-cases", type=int, default=3)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    all_cases = []
    skipped: list[tuple[str, str, str]] = []
    for symbol in SYMBOLS:
        try:
            all_cases.extend(_scan_cases(symbol, args.sample_bars, (3, 5, 10), args.refresh))
        except Exception as exc:
            skipped.append((symbol, type(exc).__name__, str(exc)))

    pairs = build_matches(all_cases)
    robustness = summarize_symbol_robustness(
        pairs,
        iterations=args.iterations,
        min_cases=args.min_cases,
    )
    loo = leave_one_symbol_out(pairs)

    print("=== DEMAND_DRYING_UP SYMBOL ROBUSTNESS AUDIT ===")
    print(f"symbols requested: {len(SYMBOLS)}")
    print(f"symbols scanned: {len(SYMBOLS) - len(skipped)}")
    print(f"unique matched pairs: {len(pairs)}")
    print(f"minimum cases for robustness: {args.min_cases}")
    print(f"bootstrap iterations: {args.iterations}")
    print()
    print(f"{'Symbol':<14}{'H':>4}{'Pairs':>7}{'Delta':>11}{'95% Low':>11}{'95% High':>11}{'Robust':>10}")
    for row in robustness:
        robust = "negative" if row["robust_negative"] else "positive" if row["robust_positive"] else "inconclusive"
        print(
            f"{str(row['symbol']):<14}"
            f"{int(row['horizon']):>4}"
            f"{int(row['pairs']):>7}"
            f"{float(row['observed_delta']):>10.3%}"
            f"{float(row['ci_low']):>10.3%}"
            f"{float(row['ci_high']):>10.3%}"
            f"{robust:>12}"
        )

    print()
    print("=== LEAVE-ONE-SYMBOL-OUT ===")
    print(f"{'Excluded':<14}{'H':>4}{'Pairs':>7}{'Mean Delta':>14}")
    for row in loo:
        print(
            f"{str(row['excluded_symbol']):<14}"
            f"{int(row['horizon']):>4}"
            f"{int(row['pairs']):>7}"
            f"{float(row['mean_delta']):>13.3%}"
        )

    if skipped:
        print()
        print("=== SKIPPED ===")
        for symbol, error_type, message in skipped:
            print(f"{symbol:<14}{error_type}: {message}")


if __name__ == "__main__":
    main()
