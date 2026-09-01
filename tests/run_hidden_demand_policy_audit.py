from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.matched_hidden_demand_audit import build_matches, scan_cases
from tests.run_nse_increasing_demand_universe_audit import SYMBOLS

HORIZONS = (3, 5, 10)
PROMOTED_CONTEXTS = frozenset({("healthy", "up"), ("unknown", "range")})


def _scan(symbol: str, sample_bars: int, refresh: bool):
    return scan_cases(symbol, sample_bars, HORIZONS, refresh)


def _summary(pairs, predicate) -> dict[str, object]:
    selected = [pair for pair in pairs if predicate(pair)]
    rows = []
    for horizon in HORIZONS:
        bucket = [pair for pair in selected if pair.target.horizon == horizon]
        if not bucket:
            continue
        deltas = [
            float(pair.target.forward_return) - float(pair.control.forward_return)
            for pair in bucket
            if pair.target.forward_return is not None and pair.control.forward_return is not None
        ]
        rows.append({
            "horizon": horizon,
            "pairs": len(deltas),
            "mean_delta": sum(deltas) / len(deltas) if deltas else 0.0,
            "positive_pairs": sum(delta > 0 for delta in deltas),
        })
    return {"pairs": len(selected), "rows": rows}


def main() -> None:
    parser = argparse.ArgumentParser(description="Research-only production-policy audit for HIDDEN_DEMAND.")
    parser.add_argument("--sample-bars", type=int, default=520)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--symbols", nargs="+", default=None)
    args = parser.parse_args()

    symbols = tuple(args.symbols) if args.symbols else SYMBOLS
    if args.sample_bars <= max(HORIZONS):
        raise ValueError("--sample-bars must exceed the maximum horizon")

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
    universal = _summary(pairs, lambda pair: True)
    qualified = _summary(
        pairs,
        lambda pair: (pair.target.trend_state, pair.target.trend_direction) in PROMOTED_CONTEXTS,
    )
    excluded = _summary(
        pairs,
        lambda pair: (pair.target.trend_state, pair.target.trend_direction) not in PROMOTED_CONTEXTS,
    )

    print("=== HIDDEN_DEMAND POLICY-VALUE AUDIT ===")
    print(f"symbols requested: {len(symbols)}")
    print(f"symbols scanned: {len(symbols) - len(failures)}")
    print(f"unique matched pairs: {len(pairs)}")
    print(f"promoted contexts: {sorted(PROMOTED_CONTEXTS)}")
    print()
    for name, result in (("UNIVERSAL", universal), ("CONTEXT-QUALIFIED", qualified), ("EXCLUDED", excluded)):
        print(name)
        print(f"{'H':>3}{'Pairs':>8}{'Delta':>12}{'Positive':>12}")
        for row in result["rows"]:
            print(f"{row['horizon']:>3}{row['pairs']:>8}{row['mean_delta']:>11.3%}{row['positive_pairs']:>8}/{row['pairs']}")
        print()

    if failures:
        print("=== SCAN FAILURES ===")
        for symbol, error_type, message in failures:
            print(f"{symbol:<16}{error_type}: {message}")


if __name__ == "__main__":
    main()
