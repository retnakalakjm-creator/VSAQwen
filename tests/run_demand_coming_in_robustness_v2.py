from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from matched_demand_coming_in_audit import build_matches, _scan_cases
from robustness_demand_coming_in_audit import summarize
from run_nse_increasing_demand_universe_audit import SYMBOLS


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bootstrap robustness audit for DEMAND_COMING_IN matched pairs."
    )
    parser.add_argument("--iterations", type=int, default=5000)
    parser.add_argument("--sample-bars", type=int, default=520)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    all_cases = []
    skipped = []
    for symbol in SYMBOLS:
        try:
            all_cases.extend(
                _scan_cases(
                    symbol,
                    args.sample_bars,
                    (3, 5, 10),
                    args.refresh,
                )
            )
        except Exception as exc:
            skipped.append((symbol, type(exc).__name__, str(exc)))

    pairs = build_matches(all_cases)
    rows = summarize(pairs, iterations=args.iterations)

    print("=== DEMAND_COMING_IN ROBUSTNESS AUDIT ===")
    print(f"symbols requested: {len(SYMBOLS)}")
    print(f"symbols scanned: {len(SYMBOLS) - len(skipped)}")
    print(f"unique matched pairs: {len(pairs)}")
    print(f"bootstrap iterations: {args.iterations}")
    print()
    print(f"{'Horizon':>8}{'Pairs':>8}{'Delta':>12}{'95% Low':>12}{'95% High':>12}{'Negative':>11}")
    for row in rows:
        print(
            f"{row['horizon']:>8}{row['pairs']:>8}"
            f"{row['observed_delta']:>11.3%}"
            f"{row['ci_low']:>11.3%}"
            f"{row['ci_high']:>11.3%}"
            f"{row['negative_deltas']:>7}/{row['pairs']}"
        )

    if skipped:
        print()
        print("=== SKIPPED ===")
        for symbol, error_type, message in skipped:
            print(f"{symbol:<14}{error_type}: {message}")


if __name__ == "__main__":
    main()
