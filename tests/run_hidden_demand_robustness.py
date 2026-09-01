from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.matched_hidden_demand_audit import build_matches, scan_cases, summarize
from tests.robustness_hidden_demand_audit import summarize as bootstrap_summarize
from tests.run_nse_increasing_demand_universe_audit import SYMBOLS


DEFAULT_SAMPLE_BARS = 520
DEFAULT_ITERATIONS = 5000
HORIZONS = (3, 5, 10)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Matched-control and bootstrap robustness audit for HIDDEN_DEMAND."
    )
    parser.add_argument("--sample-bars", type=int, default=DEFAULT_SAMPLE_BARS)
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--symbols", nargs="+", default=None)
    args = parser.parse_args()

    symbols = tuple(args.symbols) if args.symbols else SYMBOLS
    if args.sample_bars <= max(HORIZONS):
        raise ValueError("--sample-bars must exceed the maximum horizon")
    if args.iterations <= 0:
        raise ValueError("--iterations must be positive")

    all_cases = []
    failures: list[tuple[str, str, str]] = []
    with ThreadPoolExecutor(max_workers=min(4, len(symbols))) as executor:
        futures = {
            executor.submit(scan_cases, symbol, args.sample_bars, HORIZONS, args.refresh): symbol
            for symbol in symbols
        }
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                all_cases.extend(future.result())
            except Exception as exc:
                failures.append((symbol, type(exc).__name__, str(exc)))

    pairs = build_matches(all_cases)
    matched = summarize(pairs)
    robust = bootstrap_summarize(pairs, iterations=args.iterations)

    candidate_events = sum(1 for _, is_target in all_cases if is_target)
    control_events = len(all_cases) - candidate_events
    symbols_scanned = len(symbols) - len(failures)

    print("=== HIDDEN_DEMAND MATCHED-CONTROL ROBUSTNESS AUDIT ===")
    print(f"symbols requested: {len(symbols)}")
    print(f"symbols scanned: {symbols_scanned}")
    print(f"sample bars per symbol: {args.sample_bars}")
    print(f"candidate events: {candidate_events}")
    print(f"control events: {control_events}")
    print(f"unique matched pairs: {len(pairs)}")
    print(f"bootstrap iterations: {args.iterations}")
    print()
    print("MATCHED CONTROL")
    print(f"{'Horizon':>8}{'Pairs':>8}{'Target':>12}{'Control':>12}{'Delta':>12}")
    for row in matched:
        print(
            f"{row['horizon']:>8}{row['pairs']:>8}"
            f"{row['target_mean_return']:>11.3%}"
            f"{row['control_mean_return']:>11.3%}"
            f"{row['return_delta']:>11.3%}"
        )

    print()
    print("BOOTSTRAP ROBUSTNESS")
    print(f"{'Horizon':>8}{'Pairs':>8}{'Delta':>12}{'95% Low':>12}{'95% High':>12}{'Robust':>13}")
    for row in robust:
        print(
            f"{row['horizon']:>8}{row['pairs']:>8}"
            f"{row['observed_delta']:>11.3%}"
            f"{row['ci_low']:>11.3%}"
            f"{row['ci_high']:>11.3%}"
            f"{row['robust']:>13}"
        )

    if failures:
        print()
        print("=== SCAN FAILURES ===")
        for symbol, error_type, message in failures:
            print(f"{symbol:<14}{error_type}: {message}")


if __name__ == "__main__":
    main()
