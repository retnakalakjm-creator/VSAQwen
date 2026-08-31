from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from matched_increasing_demand_audit import _scan_cases, build_matches, summarize
from run_nse_increasing_demand_universe_audit import SYMBOLS


def main() -> None:
    parser = argparse.ArgumentParser(description="Matched-control increasing_demand audit.")
    parser.add_argument("--sample-bars", type=int, default=520)
    parser.add_argument("--score-band", type=float, default=0.10)
    parser.add_argument("--pressure-band", type=float, default=0.25)
    parser.add_argument("--max-age-gap", type=int, default=1)
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

    pairs = build_matches(
        all_cases,
        score_band=args.score_band,
        pressure_band=args.pressure_band,
        max_age_gap=args.max_age_gap,
    )

    print("=== MATCHED INCREASING_DEMAND AUDIT ===")
    print(f"symbols requested: {len(SYMBOLS)}")
    print(f"symbols scanned: {len({c.symbol for c, _ in all_cases})}")
    print(f"changed cases: {len({c.bar_index for c, changed in all_cases if changed})}")
    print(f"case-horizon rows: {len(all_cases)}")
    print(f"matched pairs: {len(pairs)}")
    print()
    print(f"{'Change':<14}{'Horizon':>8}{'Pairs':>8}{'TargetRet':>12}{'ControlRet':>12}{'Delta':>12}")
    grouped = {}
    for pair in pairs:
        key = (pair.target.change, pair.horizon)
        grouped.setdefault(key, []).append(pair)
    for key in sorted(grouped):
        change, horizon = key
        summary = summarize(grouped[key])
        print(
            f"{change:<14}{horizon:>8}{summary['pairs']:>8}"
            f"{summary['target_mean_return']:>11.3%}"
            f"{summary['control_mean_return']:>11.3%}"
            f"{summary['return_delta']:>11.3%}"
        )

    print()
    print("=== MATCHES ===")
    for pair in sorted(pairs, key=lambda p: (p.target.symbol, p.target.bar_index, p.horizon)):
        print(
            f"{pair.target.symbol:<14} target={pair.target.bar_index:<4} "
            f"control={pair.control.bar_index:<4} state={pair.target.state:<10} "
            f"change={pair.target.change:<12} h={pair.horizon:<2} "
            f"target={pair.target.forward_return:+.4%} "
            f"control={pair.control.forward_return:+.4%} "
            f"delta={pair.target.forward_return - pair.control.forward_return:+.4%}"
        )

    if skipped:
        print()
        print("=== SKIPPED ===")
        for symbol, error_type, message in skipped:
            print(f"{symbol:<14}{error_type}: {message}")


if __name__ == "__main__":
    main()
