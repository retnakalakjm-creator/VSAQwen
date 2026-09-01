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
PROMOTED_CONTEXTS = {("healthy", "up"), ("unknown", "range")}
WEIGHTS = (0.0, 0.10, 0.15, 0.20, 0.25, 0.30)


def _summary(pairs):
    rows = []
    for horizon in HORIZONS:
        bucket = [p for p in pairs if p.target.horizon == horizon]
        if not bucket:
            continue
        observed, low, high = bootstrap_delta(bucket, iterations=5000)
        rows.append((horizon, len(bucket), observed, low, high))
    return rows


def _policy_score(pair, weight: float, contextual: bool) -> float:
    selected = not contextual or (pair.target.trend_state, pair.target.trend_direction) in PROMOTED_CONTEXTS
    return weight if selected else 0.0


def main() -> None:
    parser = argparse.ArgumentParser(description="Research-only HIDDEN_DEMAND weight/ranking safety audit.")
    parser.add_argument("--sample-bars", type=int, default=520)
    parser.add_argument("--symbols", nargs="+", default=None)
    args = parser.parse_args()
    if args.sample_bars <= max(HORIZONS):
        raise ValueError("--sample-bars must exceed the maximum horizon")

    symbols = tuple(args.symbols) if args.symbols else SYMBOLS
    all_cases = []
    failures = []
    with ThreadPoolExecutor(max_workers=min(4, len(symbols))) as executor:
        futures = {executor.submit(scan_cases, symbol, args.sample_bars, HORIZONS, False): symbol for symbol in symbols}
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                all_cases.extend(future.result())
            except Exception as exc:
                failures.append((symbol, type(exc).__name__, str(exc)))

    pairs = build_matches(all_cases)
    print("=== HIDDEN_DEMAND WEIGHT / RANKING SAFETY AUDIT ===")
    print(f"symbols requested: {len(symbols)}")
    print(f"symbols scanned: {len(symbols) - len(failures)}")
    print(f"unique matched pairs: {len(pairs)}")
    print(f"promoted contexts: {sorted(PROMOTED_CONTEXTS)}")
    print()
    print("BASELINE ROBUSTNESS")
    for horizon, count, delta, low, high in _summary(pairs):
        print(f"H={horizon:>2} pairs={count:>3} delta={delta:>8.3%} 95%=[{low:>8.3%}, {high:>8.3%}]")

    print()
    print("POLICY WEIGHTS")
    print(f"{'Weight':>8}{'Selected':>10}{'Excluded':>10}")
    for weight in WEIGHTS:
        selected = sum(_policy_score(p, weight, True) > 0 for p in pairs)
        print(f"{weight:>8.2f}{selected:>10}{len(pairs) - selected:>10}")

    print()
    print("DECISION SAFETY")
    for weight in WEIGHTS:
        selected_pairs = [p for p in pairs if _policy_score(p, weight, True) > 0]
        excluded_pairs = [p for p in pairs if _policy_score(p, weight, True) == 0]
        selected_rows = _summary(selected_pairs)
        excluded_rows = _summary(excluded_pairs)
        print(f"weight={weight:.2f}")
        for horizon in HORIZONS:
            s = next((r for r in selected_rows if r[0] == horizon), None)
            e = next((r for r in excluded_rows if r[0] == horizon), None)
            if s and e:
                print(f"  H={horizon:>2} selected_delta={s[2]:>8.3%} excluded_delta={e[2]:>8.3%}")

    if failures:
        print()
        print("=== SCAN FAILURES ===")
        for symbol, error_type, message in failures:
            print(f"{symbol:<16}{error_type}: {message}")


if __name__ == "__main__":
    main()
