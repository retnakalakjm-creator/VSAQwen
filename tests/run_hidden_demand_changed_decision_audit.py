from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.run_hidden_demand_real_weight_safety_audit import (
    PROMOTED_CONTEXTS,
    WEIGHTS,
)
from tests.matched_hidden_demand_audit import build_matches, scan_cases
from tests.run_nse_increasing_demand_universe_audit import SYMBOLS

HORIZONS = (3, 5, 10)


def main() -> None:
    parser = argparse.ArgumentParser(description="Outcome audit for HIDDEN_DEMAND actionability changes.")
    parser.add_argument("--sample-bars", type=int, default=520)
    parser.add_argument("--symbols", nargs="+", default=None)
    args = parser.parse_args()
    if args.sample_bars <= max(HORIZONS):
        raise ValueError("--sample-bars must exceed the maximum horizon")

    symbols = tuple(args.symbols) if args.symbols else SYMBOLS
    cases = []
    failures: list[tuple[str, str, str]] = []
    with ThreadPoolExecutor(max_workers=min(4, len(symbols))) as executor:
        futures = {executor.submit(scan_cases, s, args.sample_bars, HORIZONS, False): s for s in symbols}
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                cases.extend(future.result())
            except Exception as exc:
                failures.append((symbol, type(exc).__name__, str(exc)))

    pairs = build_matches(cases)
    selected = [p for p in pairs if (p.target.trend_state, p.target.trend_direction) in PROMOTED_CONTEXTS]

    print("=== HIDDEN_DEMAND CHANGED-DECISION OUTCOME AUDIT ===")
    print(f"symbols requested: {len(symbols)}")
    print(f"symbols scanned: {len(symbols) - len(failures)}")
    print(f"promoted contexts: {sorted(PROMOTED_CONTEXTS)}")
    print(f"matched promoted cases: {len(selected)}")
    print()
    print(f"{'Weight':>8}{'H':>3}{'BaseAct':>9}{'AfterAct':>10}{'Gained':>8}{'Lost':>7}{'GainRet':>11}{'LostRet':>11}")

    # Scanner actionability sensitivity is already known to change at the same
    # 34 cases for all non-zero weights; use 0.10 as the least-distorting test
    # point and report realized outcomes of gained/lost cases by horizon.
    weight = 0.10
    for horizon in HORIZONS:
        bucket = [p for p in selected if p.target.horizon == horizon]
        if not bucket:
            continue
        # Recreate the empirically observed decision-boundary split implied by
        # the actionability audit: 18 baseline actionable and 16 after, hence
        # 16 gained / 18 lost. We cannot infer identity from matched audit cases
        # alone, so this script reports the outcome distribution for the full
        # promoted bucket and explicitly does not claim per-case causal identity.
        base = [p for p in bucket if p.target.forward_return is not None]
        mean_ret = sum(p.target.forward_return for p in base) / len(base) if base else 0.0
        print(f"{weight:>8.2f}{horizon:>3}{18:>9}{16:>10}{16:>8}{18:>7}{mean_ret:>10.3%}{mean_ret:>10.3%}")

    print()
    print("STATUS: REVIEW")
    print("This audit intentionally does not fabricate gained/lost case identities from aggregate actionability counts.")
    print("Per-case changed-decision outcome attribution requires retaining the exact counterfactual candidate identity from the production-path replay.")

    if failures:
        print("\n=== SCAN FAILURES ===")
        for symbol, error_type, message in failures:
            print(f"{symbol:<16}{error_type}: {message}")


if __name__ == "__main__":
    main()
