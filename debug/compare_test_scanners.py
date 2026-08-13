from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from debug.diagnose_test_multi_symbol import inspect_symbol as baseline_inspect
from debug.opt_diagnose_test_multi_symbol import inspect_symbol as optimized_inspect

DEFAULT_SYMBOLS = (
    "BHARTIARTL.NS",
    "RELIANCE.NS",
    "HDFCBANK.NS",
    "ICICIBANK.NS",
    "INFY.NS",
    "TCS.NS",
    "SBIN.NS",
    "LT.NS",
)


def event_key(item: dict) -> tuple:
    returns = tuple(sorted(item["forward_returns"].items()))
    return (
        item["bar_index"],
        item["week"],
        returns,
        tuple(item["evidence"]),
    )


def main() -> None:
    symbols = tuple(sys.argv[1:]) or DEFAULT_SYMBOLS
    mismatches: list[dict] = []
    total_baseline = 0
    total_optimized = 0

    print("=" * 72)
    print("TEST SCANNER EQUIVALENCE AUDIT")
    print("=" * 72)
    print({"symbols": symbols})

    for symbol in symbols:
        baseline = baseline_inspect(symbol)
        optimized = optimized_inspect(symbol)
        total_baseline += len(baseline)
        total_optimized += len(optimized)

        baseline_map = {item["bar_index"]: event_key(item) for item in baseline}
        optimized_map = {item["bar_index"]: event_key(item) for item in optimized}

        if baseline_map != optimized_map:
            mismatches.append(
                {
                    "symbol": symbol,
                    "baseline_bars": sorted(baseline_map),
                    "optimized_bars": sorted(optimized_map),
                    "missing_from_optimized": sorted(set(baseline_map) - set(optimized_map)),
                    "missing_from_baseline": sorted(set(optimized_map) - set(baseline_map)),
                    "changed_events": sorted(
                        bar for bar in set(baseline_map) & set(optimized_map)
                        if baseline_map[bar] != optimized_map[bar]
                    ),
                }
            )
        else:
            print({"symbol": symbol, "status": "MATCH", "events": len(baseline)})

    print("\nTEST SCANNER EQUIVALENCE SUMMARY")
    print({
        "symbols": len(symbols),
        "baseline_events": total_baseline,
        "optimized_events": total_optimized,
        "mismatches": len(mismatches),
        "status": "PASS" if not mismatches else "FAIL",
    })

    if mismatches:
        print("\nTEST SCANNER EQUIVALENCE MISMATCHES")
        for item in mismatches:
            print(item)


if __name__ == "__main__":
    main()
