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
TEST_BARS = {149, 152, 248, 942, 1084}


def classify_outcome(index: int, metrics):
    if index + 4 >= len(metrics):
        return "INSUFFICIENT_FORWARD_DATA"

    test_low = float(metrics.iloc[index]["low"])
    closes = [float(metrics.iloc[i]["close"]) for i in range(index + 1, index + 5)]
    lows = [float(metrics.iloc[i]["low"]) for i in range(index + 1, index + 5)]

    if all(low >= test_low for low in lows):
        if max(closes) > float(metrics.iloc[index]["close"]):
            return "HOLD"
        return "PARTIAL_HOLD"
    return "EARLY_AREA_FAILURE"


def audit_at(metrics, index: int) -> dict:
    replay = metrics.iloc[: index + 1].copy()
    trend = TrendAnalyzer().analyze(replay)
    structural_swings = tuple(trend.structure.structural_swings)
    result = EvidenceEngine().collect(
        metrics=replay,
        trend=trend,
        structural_swings=structural_swings,
        validation_metrics=metrics,
    )

    items = tuple(result.evidence)
    test = tuple(item for item in items if str(item.code).lower() == "test")
    other = tuple(item for item in items if str(item.code).lower() != "test")

    return {
        "bar_index": index,
        "outcome": classify_outcome(index, metrics),
        "test_present": bool(test),
        "cooccurring_current_bar": sorted(
            {
                str(item.code)
                for item in other
                if item.bar_index == index
            }
        ),
        "cooccurring_campaign": sorted(
            {
                str(item.code)
                for item in other
            }
        ),
        "test_quality": [item.quality for item in test],
        "test_strength": [item.strength for item in test],
        "current_bar_count": sum(item.bar_index == index for item in other),
    }


def main() -> None:
    daily = download_data(SYMBOL)
    metrics = MetricsEngine().calculate(daily_to_weekly(daily))

    rows = [audit_at(metrics, index) for index in sorted(TEST_BARS)]

    print("=" * 72)
    print("TEST CONFLUENCE / SUPPORTING-EVIDENCE AUDIT")
    print("=" * 72)

    for row in rows:
        print(row)

    print("\nTEST CONFLUENCE GROUP SUMMARY")
    groups: dict[tuple[str, tuple[str, ...]], list[dict]] = {}
    for row in rows:
        key = (
            row["outcome"],
            tuple(row["cooccurring_current_bar"]),
        )
        groups.setdefault(key, []).append(row)

    for (outcome, events), members in sorted(groups.items()):
        print(
            {
                "outcome": outcome,
                "current_bar_confluence": events,
                "events": len(members),
                "bars": [item["bar_index"] for item in members],
            }
        )


if __name__ == "__main__":
    main()
