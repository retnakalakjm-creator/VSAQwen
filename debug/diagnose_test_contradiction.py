from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from evidence.engine import EvidenceEngine
from metrics_engine import MetricsEngine
from trend import TrendAnalyzer

SYMBOL = "BHARTIARTL.NS"

STRONG_CONTRADICTION = {
    "increasing_supply",
    "no_demand",
    "structural_progression_weakening",
}


def main() -> None:
    daily = download_data(SYMBOL)
    metrics = MetricsEngine().calculate(daily_to_weekly(daily))

    rows = []
    for index in range(20, len(metrics)):
        replay = metrics.iloc[: index + 1].copy()
        trend = TrendAnalyzer().analyze(replay)
        evidence = EvidenceEngine().collect(
            metrics=replay,
            trend=trend,
            structural_swings=tuple(trend.structure.structural_swings),
            validation_metrics=metrics,
        )
        current = tuple(
            str(item.code).lower()
            for item in evidence.evidence
            if item.bar_index == index
        )
        tests = [item for item in evidence.evidence if str(item.code).lower() == "test" and item.bar_index == index]
        if not tests:
            continue

        contradictions = tuple(code for code in current if code in STRONG_CONTRADICTION)
        outcome = "UNKNOWN"
        if index in {149, 152}:
            outcome = "PARTIAL_HOLD"
        elif index == 248:
            outcome = "STRONG_HOLD"
        elif index in {942, 1084}:
            outcome = "EARLY_AREA_FAILURE"

        rows.append({
            "bar_index": index,
            "outcome": outcome,
            "current_bar_codes": current,
            "strong_contradictions": contradictions,
            "contradiction_count": len(contradictions),
        })

    print("=" * 72)
    print("TEST CONTRADICTION / CONFLUENCE AUDIT")
    print("=" * 72)
    for row in rows:
        print(row)

    print("\nTEST CONTRADICTION GROUP SUMMARY")
    groups: dict[tuple[str, ...], list[dict]] = {}
    for row in rows:
        key = row["strong_contradictions"]
        groups.setdefault(key, []).append(row)

    for key, items in groups.items():
        print({
            "strong_contradictions": key,
            "events": len(items),
            "bars": [item["bar_index"] for item in items],
            "outcomes": [item["outcome"] for item in items],
        })


if __name__ == "__main__":
    main()
