from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from matched_demand_coming_in_audit import _scan_cases, build_matches
from run_nse_increasing_demand_universe_audit import SYMBOLS
from stratified_demand_coming_in_robustness import summarize


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bootstrap context-stratified DEMAND_COMING_IN audit."
    )
    parser.add_argument("--sample-bars", type=int, default=520)
    parser.add_argument("--iterations", type=int, default=5000)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    all_cases = []
    skipped: list[tuple[str, str, str]] = []
    scanned = 0
    for symbol in SYMBOLS:
        try:
            all_cases.extend(
                _scan_cases(symbol, args.sample_bars, (3, 5, 10), args.refresh)
            )
            scanned += 1
        except Exception as exc:
            skipped.append((symbol, type(exc).__name__, str(exc)))

    pairs = build_matches(all_cases)
    rows = summarize(pairs, iterations=args.iterations)

    print("=== DEMAND_COMING_IN STRATIFIED ROBUSTNESS AUDIT ===")
    print(f"symbols requested: {len(SYMBOLS)}")
    print(f"symbols scanned: {scanned}")
    print(f"unique matched pairs: {len(pairs)}")
    print(f"bootstrap iterations: {args.iterations}")
    print()
    print(
        f"{'State':<12}{'Direction':<10}{'Horizon':>8}{'Pairs':>8}"
        f"{'Delta':>12}{'95% Low':>12}{'95% High':>12}{'Positive':>12}"
    )
    for row in rows:
        print(
            f"{str(row['state']):<12}"
            f"{str(row['direction']):<10}"
            f"{int(row['horizon']):>8}"
            f"{int(row['pairs']):>8}"
            f"{float(row['observed_delta']):>11.3%}"
            f"{float(row['ci_low']):>11.3%}"
            f"{float(row['ci_high']):>11.3%}"
            f"{int(row['positive']):>7}/{int(row['pairs'])}"
        )

    if skipped:
        print()
        print("=== SKIPPED ===")
        for symbol, error_type, message in skipped:
            print(f"{symbol:<14}{error_type}: {message}")


if __name__ == "__main__":
    main()
