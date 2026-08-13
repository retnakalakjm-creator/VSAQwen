from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from debug.opt_diagnose_test_multi_symbol import DEFAULT_SYMBOLS, inspect_symbol


def main() -> None:
    all_events: list[dict] = []
    failures: list[dict] = []

    print("=" * 72)
    print("TEST CONTEXTUAL OUTCOME AUDIT")
    print("=" * 72)

    for symbol in DEFAULT_SYMBOLS:
        try:
            all_events.extend(inspect_symbol(symbol))
        except Exception as exc:
            failures.append({"symbol": symbol, "error": repr(exc)})

    groups: dict[tuple[str, ...], dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))

    for item in all_events:
        evidence = tuple(sorted({
            code
            for code in item["evidence"]
            if code != "test"
        }))
        groups[evidence][item["8_bar_class"]].append(item["bar_index"])

    print("\nTEST CONTEXTUAL GROUP SUMMARY")
    for evidence, outcomes in sorted(groups.items(), key=lambda x: (-sum(len(v) for v in x[1].values()), x[0])):
        print({
            "cooccurring_evidence": evidence,
            "events": sum(len(v) for v in outcomes.values()),
            "positive_8_bar": len(outcomes.get("POSITIVE_8_BAR", [])),
            "negative_8_bar": len(outcomes.get("NEGATIVE_8_BAR", [])),
            "flat_8_bar": len(outcomes.get("FLAT_8_BAR", [])),
            "bars_by_outcome": dict(outcomes),
        })

    print("\nTEST SINGLE-EVIDENCE OUTCOME SUMMARY")
    evidence_stats: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for item in all_events:
        outcome = item["8_bar_class"]
        for code in set(item["evidence"]):
            if code == "test":
                continue
            evidence_stats[code][outcome] += 1

    for code, stats in sorted(evidence_stats.items(), key=lambda x: -sum(x[1].values())):
        print({
            "evidence": code,
            "events": sum(stats.values()),
            "positive_8_bar": stats.get("POSITIVE_8_BAR", 0),
            "negative_8_bar": stats.get("NEGATIVE_8_BAR", 0),
            "flat_8_bar": stats.get("FLAT_8_BAR", 0),
        })

    print("\nTEST CONTEXTUAL AUDIT SUMMARY")
    print({
        "events": len(all_events),
        "symbols": len({item["symbol"] for item in all_events}),
        "failures": failures,
    })


if __name__ == "__main__":
    main()
