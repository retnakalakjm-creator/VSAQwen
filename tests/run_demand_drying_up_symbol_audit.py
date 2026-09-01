from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from coverage_demand_drying_up_audit import summarize_by_symbol_context
from matched_demand_drying_up_audit import _scan_cases, build_matches
from run_nse_increasing_demand_universe_audit import SYMBOLS


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Per-symbol concentration audit for DEMAND_DRYING_UP matched pairs."
    )
    parser.add_argument("--sample-bars", type=int, default=520)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--min-cases", type=int, default=3)
    args = parser.parse_args()

    all_cases = []
    skipped: list[tuple[str, str, str]] = []
    scanned = 0
    for symbol in SYMBOLS:
        try:
            all_cases.extend(_scan_cases(symbol, args.sample_bars, (3, 5, 10), args.refresh))
            scanned += 1
        except Exception as exc:
            skipped.append((symbol, type(exc).__name__, str(exc)))

    pairs = build_matches(all_cases)
    rows = summarize_by_symbol_context(pairs)

    print("=== DEMAND_DRYING_UP SYMBOL CONCENTRATION AUDIT ===")
    print(f"symbols requested: {len(SYMBOLS)}")
    print(f"symbols scanned: {scanned}")
    print(f"unique matched pairs: {len(pairs)}")
    print(f"minimum cases for stability flag: {args.min_cases}")
    print()
    print(f"{'Symbol':<14}{'State':<12}{'Direction':<10}{'H':>4}{'Pairs':>7}{'Delta':>11}{'Positive':>10}")
    for row in rows:
        flag = " *" if int(row["pairs"]) >= args.min_cases else ""
        print(
            f"{str(row['symbol']):<14}"
            f"{str(row['state']):<12}"
            f"{str(row['direction']):<10}"
            f"{int(row['horizon']):>4}"
            f"{int(row['pairs']):>7}"
            f"{float(row['mean_delta']):>10.3%}"
            f"{int(row['positive']):>6}/{int(row['pairs']):<3}{flag}"
        )

    print()
    print("* symbol/context/horizon bucket meets minimum-case threshold")
    if skipped:
        print()
        print("=== SKIPPED ===")
        for symbol, error_type, message in skipped:
            print(f"{symbol:<14}{error_type}: {message}")


if __name__ == "__main__":
    main()
