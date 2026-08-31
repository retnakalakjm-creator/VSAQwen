from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import download_data, daily_to_weekly
from metrics_engine import MetricsEngine
from tests.matched_demand_coming_in_audit import _scan_cases, build_matches, summarize
from tests.run_nse_increasing_demand_universe_audit import SYMBOLS


def main() -> None:
    parser = argparse.ArgumentParser(description="Matched-control DEMAND_COMING_IN audit.")
    parser.add_argument("--sample-bars", type=int, default=520)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    horizons = (3, 5, 10)

    all_cases = []
    skipped = []
    for symbol in SYMBOLS:
        try:
            all_cases.extend(_scan_cases(symbol, args.sample_bars, horizons, args.refresh))
        except Exception as exc:
            skipped.append((symbol, type(exc).__name__, str(exc)))

    pairs = build_matches(all_cases)
    print("=== DEMAND_COMING_IN MATCHED-CONTROL AUDIT ===")
    print(f"symbols requested: {len(SYMBOLS)}")
    print(f"symbols scanned: {len(SYMBOLS) - len(skipped)}")
    print(f"target cases: {sum(1 for _, event in all_cases if event)}")
    print(f"control cases: {sum(1 for _, event in all_cases if not event)}")
    print(f"unique matched pairs: {len(pairs)}")
    print()
    print(f"{'Horizon':>8}{'Pairs':>8}{'Target':>12}{'Control':>12}{'Delta':>12}")
    for row in summarize(pairs):
        print(
            f"{row['horizon']:>8}{row['pairs']:>8}"
            f"{row['target_mean_return']:>11.3%}"
            f"{row['control_mean_return']:>11.3%}"
            f"{row['return_delta']:>11.3%}"
        )

    print()
    print("=== PAIR COVERAGE ===")
    coverage = defaultdict(int)
    for pair in pairs:
        coverage[pair.target.symbol] += 1
    for symbol in SYMBOLS:
        print(f"{symbol:<14}{coverage[symbol]:>6}")

    if skipped:
        print()
        print("=== SKIPPED ===")
        for symbol, error_type, message in skipped:
            print(f"{symbol:<14}{error_type}: {message}")


if __name__ == "__main__":
    main()
