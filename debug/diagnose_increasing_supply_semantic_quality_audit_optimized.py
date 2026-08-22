"""Semantic-quality audit for INCREASING_SUPPLY.

Validates the frozen 528-event candidate population against the exact
point-in-time production detector semantics:
- down bar
- increasing volume versus previous bar
- increasing spread versus previous bar
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from data import daily_to_weekly, download_data
from evidence.engine import EvidenceEngine
from evidence.rules import is_down_bar, spread_increasing, volume_increasing
from metrics_engine import MetricsEngine
from models import EvidenceCode, Direction, SpreadClass, VolumeClass
from trend import TrendAnalyzer
from engine.columns import COL_DIRECTION, COL_SPREAD_CLASS, COL_VOLUME_CLASS

SYMBOLS = (
    "BHARTIARTL.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "LT.NS", "RELIANCE.NS", "SBIN.NS", "TCS.NS",
)
TARGET_CODE = EvidenceCode.INCREASING_SUPPLY
EXPECTED_EVENTS = 528


def _cheap_candidate(metrics, index: int) -> bool:
    row = metrics.iloc[index]
    return (
        Direction(int(row[COL_DIRECTION])) == Direction.DOWN
        and VolumeClass(int(row[COL_VOLUME_CLASS])) >= VolumeClass.HIGH
        and SpreadClass(int(row[COL_SPREAD_CLASS])) >= SpreadClass.ABOVE_AVERAGE
    )


def _audit_symbol(symbol: str) -> dict[str, object]:
    metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
    candidate_events: list[int] = []
    semantic_counts = {
        "down_bar": 0,
        "volume_increasing": 0,
        "spread_increasing": 0,
    }
    failures: list[str] = []
    heavy_rebuilds = 0

    for index in range(1, len(metrics)):
        # Restrict validation to the same frozen cheap-candidate population
        # used by the candidate audit. This prevents unrelated historical
        # production emissions from entering the semantic audit.
        if not _cheap_candidate(metrics, index):
            continue

        replay = metrics.iloc[: index + 1].copy()
        trend = TrendAnalyzer().analyze(replay)
        structural_swings = tuple(trend.structure.structural_swings)
        engine = EvidenceEngine()
        result = engine.collect(
            metrics=replay,
            trend=trend,
            structural_swings=structural_swings,
        )
        heavy_rebuilds += 1

        target = [
            e for e in result.evidence
            if e.code is TARGET_CODE
            and getattr(e, "bar_index", None) == index
        ]
        if len(target) > 1:
            failures.append(
                f"{symbol}:{index}: expected at most one target emission, got {len(target)}"
            )
            continue
        if not target:
            continue

        bar = replay.iloc[index]
        previous = replay.iloc[index - 1]

        down = bool(is_down_bar(bar))
        vol_inc = bool(volume_increasing(bar, previous))
        spread_inc = bool(spread_increasing(bar, previous))

        semantic_counts["down_bar"] += int(down)
        semantic_counts["volume_increasing"] += int(vol_inc)
        semantic_counts["spread_increasing"] += int(spread_inc)

        if not (down and vol_inc and spread_inc):
            failures.append(
                f"{symbol}:{index}: emitted target failed semantic check "
                f"down_bar={down}, volume_increasing={vol_inc}, spread_increasing={spread_inc}"
            )
            continue

        candidate_events.append(index)

    return {
        "candidate_events": candidate_events,
        "semantic_counts": semantic_counts,
        "heavy_rebuilds": heavy_rebuilds,
        "failures": failures,
    }


def main() -> None:
    symbols_with_results = 0
    candidate_events = 0
    semantic_counts = {
        "down_bar": 0,
        "volume_increasing": 0,
        "spread_increasing": 0,
    }
    heavy_rebuilds = 0
    failures: list[dict[str, str]] = []

    for symbol in SYMBOLS:
        try:
            result = _audit_symbol(symbol)
            symbols_with_results += 1
            candidate_events += len(result["candidate_events"])
            counts = result["semantic_counts"]
            for key in semantic_counts:
                semantic_counts[key] += int(counts[key])
            heavy_rebuilds += int(result["heavy_rebuilds"])
            failures.extend(
                {"symbol": symbol, "error": msg}
                for msg in result["failures"]
            )
        except Exception as exc:
            failures.append({"symbol": symbol, "error": str(exc)})

    semantic_failures = sum(1 for item in failures if "semantic check" in item["error"])

    print("INCREASING SUPPLY SEMANTIC QUALITY AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": symbols_with_results,
        "candidate_events": candidate_events,
        "expected_candidate_events": EXPECTED_EVENTS,
        "semantic_counts": semantic_counts,
        "semantic_failures": semantic_failures,
        "heavy_context_rebuilds": heavy_rebuilds,
        "target_bar_only": True,
        "point_in_time": True,
        "frozen_candidate_population": True,
        "failures": failures,
        "status": "PASS" if not failures and candidate_events == EXPECTED_EVENTS else "FAIL",
    })


if __name__ == "__main__":
    main()
