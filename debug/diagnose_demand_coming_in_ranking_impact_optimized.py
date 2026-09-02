"""Optimized ranking-impact audit for DEMAND_COMING_IN.

Analysis-only. Replays the same candidate population used by the
DEMAND_COMING_IN production-path audit and compares bias with and
without the target event contribution.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from engine.columns import (
    COL_CLOSE_POSITION,
    COL_DIRECTION,
    COL_SPREAD_CLASS,
    COL_VOLUME_CLASS,
)
from evidence.engine import EvidenceEngine
from evidence.scoring import _score_bias
from metrics_engine import MetricsEngine
from models import EvidenceCode, SpreadClass, VolumeClass
from trend import TrendAnalyzer

SYMBOLS = (
    "BHARTIARTL.NS", "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "INFY.NS", "TCS.NS", "SBIN.NS", "LT.NS",
)
TARGET = EvidenceCode.DEMAND_COMING_IN
WEIGHT = 0.38


def _candidate_indices(metrics):
    for index in range(20, len(metrics)):
        row = metrics.iloc[index]
        if (
            int(row[COL_DIRECTION]) == 1
            and VolumeClass(int(row[COL_VOLUME_CLASS])) >= VolumeClass.HIGH
            and SpreadClass(int(row[COL_SPREAD_CLASS])) >= SpreadClass.ABOVE_AVERAGE
            and int(row[COL_CLOSE_POSITION]) >= 3
        ):
            yield index


def _collect_at(metrics, index: int):
    replay = metrics.iloc[: index + 1]
    trend = TrendAnalyzer().analyze(replay)
    engine = EvidenceEngine()
    return engine.collect(
        metrics=replay,
        trend=trend,
        structural_swings=tuple(trend.structure.structural_swings),
        validation_metrics=replay,
    )


def audit_symbol(symbol: str):
    metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
    events = []
    for index in _candidate_indices(metrics):
        result = _collect_at(metrics, index)
        target = [item for item in result.evidence if item.code == TARGET]
        if not target:
            continue

        evidence = list(result.evidence)
        with_target = _score_bias(evidence)
        without_target = _score_bias(
            [item for item in evidence if item.code != TARGET]
        )
        events.append((with_target, without_target, target))

    return events


def main() -> None:
    failures = []
    by_symbol = {}
    total_events = 0
    total_changes = 0

    for symbol in SYMBOLS:
        try:
            events = audit_symbol(symbol)
            changes = sum(
                with_target != without_target
                for with_target, without_target, _ in events
            )
            total_events += len(events)
            total_changes += changes
            by_symbol[symbol] = {
                "target_events": len(events),
                "bias_changes": changes,
                "bias_change_rate": changes / len(events) if events else 0.0,
                "bias_without_target": (
                    events[-1][1].name if events else "NEUTRAL"
                ),
                "bias_with_target": (
                    events[-1][0].name if events else "NEUTRAL"
                ),
                "target_weights": sorted({
                    item.weight
                    for _, _, targets in events
                    for item in targets
                }),
                "ranking_safe_weight": all(
                    item.weight == WEIGHT
                    for _, _, targets in events
                    for item in targets
                ),
            }
        except Exception as exc:
            failures.append((symbol, str(exc)))

    print("DEMAND COMING IN RANKING IMPACT OPTIMIZED AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": len(by_symbol),
        "target_events": total_events,
        "bias_changes": total_changes,
        "bias_change_rate": (
            total_changes / total_events if total_events else 0.0
        ),
        "all_target_weights_038": all(
            info["ranking_safe_weight"] for info in by_symbol.values()
        ),
        "failures": failures,
        "status": "PASS" if not failures and total_events else "FAIL",
    })
    print("DEMAND COMING IN RANKING IMPACT BY_SYMBOL")
    for symbol, info in by_symbol.items():
        print({"symbol": symbol, **info})


if __name__ == "__main__":
    main()
