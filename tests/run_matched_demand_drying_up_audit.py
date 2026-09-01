from __future__ import annotations

import argparse

from matched_demand_drying_up_audit import _scan_cases, build_matches, summarize
from run_nse_increasing_demand_universe_audit import SYMBOLS


def main() -> None:
    parser = argparse.ArgumentParser(description="Matched-control DEMAND_DRYING_UP audit.")
    parser.add_argument("--sample-bars", type=int, default=520)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    horizons = (3, 5, 10)

    all_cases = []
    scanned = 0
    skipped = []

    for symbol in SYMBOLS:
        try:
            all_cases.extend(_scan_cases(symbol, args.sample_bars, horizons, args.refresh))
            scanned += 1
        except Exception as exc:
            skipped.append((symbol, type(exc).__name__, str(exc)))

    pairs = build_matches(all_cases)
    rows = summarize(pairs)

    print("=== DEMAND_DRYING_UP MATCHED-CONTROL AUDIT ===")
    print(f"symbols requested: {len(SYMBOLS)}")
    print(f"symbols scanned: {scanned}")
    print(f"target cases: {sum(has_event for _, has_event in all_cases)}")
    print(f"control cases: {sum(not has_event for _, has_event in all_cases)}")
    print(f"unique matched pairs: {len(pairs)}")
    print()
    print(f"{'Horizon':>8}{'Pairs':>8}{'Target':>12}{'Control':>12}{'Delta':>12}")

    for row in rows:
        target = row["target_mean_return"]
        control = row["control_mean_return"]
        delta = row["return_delta"]
        print(
            f"{int(row['horizon']):>8}{int(row['pairs']):>8}"
            f"{target:>11.3%}{control:>11.3%}{delta:>11.3%}"
        )

    if skipped:
        print()
        print("=== SKIPPED ===")
        for symbol, error_type, message in skipped:
            print(f"{symbol:<14}{error_type}: {message}")


if __name__ == "__main__":
    main()
