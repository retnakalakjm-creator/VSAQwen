from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from matched_demand_drying_up_audit import _scan_cases, build_matches
from run_nse_increasing_demand_universe_audit import SYMBOLS
from stratified_demand_drying_up_audit import summarize


def main() -> None:
    parser = argparse.ArgumentParser(description="Context-stratified DEMAND_DRYING_UP audit.")
    parser.add_argument("--sample-bars", type=int, default=520)
    parser.add_argument("--refresh", action="store_true")
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
    rows = summarize(pairs)

    print("=== DEMAND_DRYING_UP CONTEXT-STRATIFIED AUDIT ===")
    print(f"symbols requested: {len(SYMBOLS)}")
    print(f"symbols scanned: {scanned}")
    print(f"unique matched pairs: {len(pairs)}")
    print()
    print(f"{'State':<12}{'Direction':<10}{'Horizon':>8}{'Pairs':>8}{'Delta':>12}{'Positive':>12}")
    for row in rows:
        print(
            f"{str(row['state']):<12}"
            f"{str(row['direction']):<10}"
            f"{int(row['horizon']):>8}"
            f"{int(row['pairs']):>8}"
            f"{float(row['mean_delta']):>11.3%}"
            f"{int(row['positive']):>7}/{int(row['pairs'])}"
        )

    if skipped:
        print()
        print("=== SKIPPED ===")
        for symbol, error_type, message in skipped:
            print(f"{symbol:<14}{error_type}: {message}")


if __name__ == "__main__":
    main()
