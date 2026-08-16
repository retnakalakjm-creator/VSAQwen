from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from diagnose_no_supply import SYMBOLS, audit_symbol


EXCLUDED_SYMBOLS = SYMBOLS


def summarize(events: list[dict]) -> dict:
    counts = Counter(event["outcome"] for event in events)
    positive = counts["POSITIVE_8_BAR"]
    negative = counts["NEGATIVE_8_BAR"]
    flat = counts["FLAT_8_BAR"]
    insufficient = counts["INSUFFICIENT_FORWARD_DATA"]
    decisive = positive + negative

    return {
        "events": len(events),
        "positive": positive,
        "negative": negative,
        "flat": flat,
        "insufficient_forward_data": insufficient,
        "decisive": decisive,
        "positive_decisive_rate": positive / decisive if decisive else 0.0,
    }


def main() -> None:
    by_symbol: dict[str, list[dict]] = {}
    failures: list[dict[str, str]] = []

    for symbol in SYMBOLS:
        try:
            by_symbol[symbol] = audit_symbol(symbol)
        except Exception as exc:  # diagnostic boundary
            by_symbol[symbol] = []
            failures.append({"symbol": symbol, "error": repr(exc)})

    all_events = [event for symbol in SYMBOLS for event in by_symbol[symbol]]
    full = summarize(all_events)

    print("NO SUPPLY ROBUSTNESS SUMMARY")
    print(
        {
            "symbols_requested": len(SYMBOLS),
            "symbols_with_events": sum(bool(by_symbol[s]) for s in SYMBOLS),
            "failures": failures,
            **full,
        }
    )

    print("NO SUPPLY ROBUSTNESS BY_SYMBOL")
    for symbol in SYMBOLS:
        events = by_symbol[symbol]
        print({"symbol": symbol, **summarize(events)})

    print("NO SUPPLY ROBUSTNESS LEAVE_ONE_OUT")
    for excluded in EXCLUDED_SYMBOLS:
        remaining = [
            event
            for symbol in SYMBOLS
            if symbol != excluded
            for event in by_symbol[symbol]
        ]
        print({"excluded_symbol": excluded, **summarize(remaining)})


if __name__ == "__main__":
    main()
