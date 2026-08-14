"""Audit-only Spring weight leave-one-symbol-out calibration.

Uses the existing Spring interaction calibration replay and evaluates the
candidate weights after excluding each symbol in turn. No production
registry, detector, or scoring configuration is modified.
"""
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from debug.diagnose_spring_weight_calibration import (
    CANDIDATE_WEIGHTS,
    DEFAULT_SYMBOLS,
    _calibrate,
    inspect_symbol,
)


def main() -> None:
    symbols = tuple(sys.argv[1:]) or DEFAULT_SYMBOLS
    all_rows: list[dict] = []
    failures: list[dict] = []

    with ThreadPoolExecutor(max_workers=min(4, len(symbols))) as executor:
        futures = {executor.submit(inspect_symbol, symbol): symbol for symbol in symbols}
        for future, symbol in futures.items():
            try:
                all_rows.extend(future.result())
            except Exception as exc:
                failures.append({"symbol": symbol, "error": repr(exc)})

    print("SPRING WEIGHT LEAVE-ONE-SYMBOL-OUT SUMMARY")
    print({
        "symbols_requested": len(symbols),
        "symbols_with_events": len({row["symbol"] for row in all_rows}),
        "events": len(all_rows),
        "candidate_weights": CANDIDATE_WEIGHTS,
        "failures": failures,
    })

    print("SPRING WEIGHT LEAVE-ONE-SYMBOL-OUT BY EXCLUSION")
    for excluded in symbols:
        rows = [row for row in all_rows if row["symbol"] != excluded]
        for weight in CANDIDATE_WEIGHTS:
            result = _calibrate(rows, weight)
            print({
                "excluded_symbol": excluded,
                **result,
            })


if __name__ == "__main__":
    main()
