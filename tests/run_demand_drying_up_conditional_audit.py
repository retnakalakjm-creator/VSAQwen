from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from conditional_demand_drying_up_audit import (
    DEFAULT_TARGET_CONTEXTS,
    summarize_by_context,
    summarize_complement,
    summarize_context_set,
)
from matched_demand_drying_up_audit import _scan_cases, build_matches
from run_nse_increasing_demand_universe_audit import SYMBOLS


def _print_rows(title: str, rows: list[dict[str, object]]) -> None:
    print(title)
    print(f"{'State':<12}{'Direction':<10}{'H':>4}{'Pairs':>7}{'Delta':>11}{'95% Low':>11}{'95% High':>11}{'Robust':>12}")
    for row in rows:
        robust = "negative" if row["robust_negative"] else "positive" if row["robust_positive"] else "inconclusive"
        print(
            f"{str(row['state']):<12}{str(row['direction']):<10}{int(row['horizon']):>4}"
            f"{int(row['pairs']):>7}{float(row['observed_delta']):>10.3%}"
            f"{float(row['ci_low']):>10.3%}{float(row['ci_high']):>10.3%}{robust:>12}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Conditional robustness audit for DEMAND_DRYING_UP.")
    parser.add_argument("--iterations", type=int, default=5000)
    parser.add_argument("--sample-bars", type=int, default=520)
    parser.add_argument("--min-cases", type=int, default=3)
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
    contexts = DEFAULT_TARGET_CONTEXTS
    selected = summarize_context_set(pairs, contexts, iterations=args.iterations, min_cases=args.min_cases)
    complement = summarize_complement(pairs, contexts, iterations=args.iterations, min_cases=args.min_cases)

    print("=== DEMAND_DRYING_UP CONDITIONAL ROBUSTNESS AUDIT ===")
    print(f"symbols requested: {len(SYMBOLS)}")
    print(f"symbols scanned: {scanned}")
    print(f"unique matched pairs: {len(pairs)}")
    print(f"minimum cases: {args.min_cases}")
    print(f"bootstrap iterations: {args.iterations}")
    print()
    print("TARGETED NEGATIVE-CONTEXT SET")
    _print_rows("", [
        {"state": "target-set", "direction": "mixed", **row}
        for row in selected
    ])
    print()
    print("COMPLEMENT")
    _print_rows("", [
        {"state": "complement", "direction": "mixed", **row}
        for row in complement
    ])
    print()
    print("=== CONTEXT ROBUSTNESS ===")
    _print_rows("", summarize_by_context(pairs, iterations=args.iterations, min_cases=args.min_cases))

    if skipped:
        print()
        print("=== SKIPPED ===")
        for symbol, error_type, message in skipped:
            print(f"{symbol:<14}{error_type}: {message}")


if __name__ == "__main__":
    main()
