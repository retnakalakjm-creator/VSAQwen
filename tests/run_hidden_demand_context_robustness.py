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
STATES = ("unknown", "developing", "healthy", "correcting", "exhausted", "reversing")
DIRECTIONS = ("up", "down", "range", "unknown")


def _robust_label(low: float, high: float) -> str:
    if low > 0.0:
        return "positive"
    if high < 0.0:
        return "negative"
    return "inconclusive"


def _scan(symbol: str, sample_bars: int, refresh: bool):
    return scan_cases(symbol, sample_bars, HORIZONS, refresh)


def main() -> None:
    parser = argparse.ArgumentParser(description="Context-stratified robustness audit for HIDDEN_DEMAND.")
    parser.add_argument("--sample-bars", type=int, default=520)
    parser.add_argument("--iterations", type=int, default=5000)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--symbols", nargs="+", default=None)
    parser.add_argument("--min-cases", type=int, default=5)
    args = parser.parse_args()

    symbols = tuple(args.symbols) if args.symbols else SYMBOLS
    if args.sample_bars <= max(HORIZONS):
        raise ValueError("--sample-bars must exceed the maximum horizon")
    if args.iterations <= 0:
        raise ValueError("--iterations must be positive")
    if args.min_cases < 1:
        raise ValueError("--min-cases must be positive")

    all_cases = []
    failures: list[tuple[str, str, str]] = []
    with ThreadPoolExecutor(max_workers=min(4, len(symbols))) as executor:
        futures = {
            executor.submit(_scan, symbol, args.sample_bars, args.refresh): symbol
            for symbol in symbols
        }
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                all_cases.extend(future.result())
            except Exception as exc:
                failures.append((symbol, type(exc).__name__, str(exc)))

    pairs = build_matches(all_cases)
    rows: list[dict[str, object]] = []
    for state in STATES:
        for direction in DIRECTIONS:
            for horizon in HORIZONS:
                bucket = [
                    pair for pair in pairs
                    if pair.target.trend_state == state
                    and pair.target.trend_direction == direction
                    and pair.target.horizon == horizon
                ]
                if len(bucket) < args.min_cases:
                    continue
                observed, low, high = bootstrap_delta(
                    bucket,
                    iterations=args.iterations,
                )
                rows.append({
                    "state": state,
                    "direction": direction,
                    "horizon": horizon,
                    "pairs": len(bucket),
                    "delta": observed,
                    "ci_low": low,
                    "ci_high": high,
                    "robust": _robust_label(low, high),
                })

    print("=== HIDDEN_DEMAND CONTEXT-STRATIFIED ROBUSTNESS AUDIT ===")
    print(f"symbols requested: {len(symbols)}")
    print(f"symbols scanned: {len(symbols) - len(failures)}")
    print(f"sample bars per symbol: {args.sample_bars}")
    print(f"unique matched pairs: {len(pairs)}")
    print(f"minimum cases: {args.min_cases}")
    print(f"bootstrap iterations: {args.iterations}")
    print()
    print(f"{'State':<12}{'Direction':<11}{'H':>3}{'Pairs':>8}{'Delta':>11}{'95% Low':>11}{'95% High':>11}{'Robust':>13}")
    for row in rows:
        print(
            f"{str(row['state']):<12}{str(row['direction']):<11}{int(row['horizon']):>3}"
            f"{int(row['pairs']):>8}{float(row['delta']):>10.3%}"
            f"{float(row['ci_low']):>10.3%}{float(row['ci_high']):>10.3%}{str(row['robust']):>13}"
        )

    if failures:
        print()
        print("=== SCAN FAILURES ===")
        for symbol, error_type, message in failures:
            print(f"{symbol:<14}{error_type}: {message}")


if __name__ == "__main__":
    main()
