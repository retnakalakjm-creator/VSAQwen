"""Optimized final qualification audit for DEMAND_COMING_IN.

Analysis-only. Uses the validated candidate replay and compares outcomes
for events where the 0.38 target contribution changes bias versus events
where it does not.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from data import daily_to_weekly, download_data
from engine.columns import (
    COL_CLOSE,
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
FORWARD_BARS = 8


def _candidate_indices(metrics: pd.DataFrame):
    for index in range(20, len(metrics)):
        row = metrics.iloc[index]
        if (
            int(row[COL_DIRECTION]) == -1
            and VolumeClass(int(row[COL_VOLUME_CLASS])) >= VolumeClass.HIGH
            and SpreadClass(int(row[COL_SPREAD_CLASS])) >= SpreadClass.ABOVE_AVERAGE
            and int(row[COL_CLOSE_POSITION]) >= 2
        ):
            yield index


def _collect_at(metrics: pd.DataFrame, index: int):
    replay = metrics.iloc[: index + 1]
    trend = TrendAnalyzer().analyze(replay)
    engine = EvidenceEngine()
    return engine.collect(
        metrics=replay,
        trend=trend,
        structural_swings=tuple(trend.structure.structural_swings),
        validation_metrics=replay,
    )


def _forward_return(metrics: pd.DataFrame, index: int) -> float | None:
    future_index = index + FORWARD_BARS
    if future_index >= len(metrics):
        return None
    start = float(metrics.iloc[index][COL_CLOSE])
    end = float(metrics.iloc[future_index][COL_CLOSE])
    if start == 0.0:
        return None
    return end / start - 1.0


def main() -> None:
    failures = []
    changed_returns: list[float] = []
    unchanged_returns: list[float] = []
    changed_positive = 0
    changed_negative = 0
    unchanged_positive = 0
    unchanged_negative = 0
    changed_events = 0
    unchanged_events = 0
    by_symbol = {}

    for symbol in SYMBOLS:
        try:
            metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
            changed = []
            unchanged = []

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
                forward = _forward_return(metrics, index)
                if forward is None:
                    continue

                record = (forward, target)
                (changed if with_target != without_target else unchanged).append(record)

            changed_returns.extend(value for value, _ in changed)
            unchanged_returns.extend(value for value, _ in unchanged)
            changed_events += len(changed)
            unchanged_events += len(unchanged)
            changed_positive += sum(v > 0 for v, _ in changed)
            changed_negative += sum(v < 0 for v, _ in changed)
            unchanged_positive += sum(v > 0 for v, _ in unchanged)
            unchanged_negative += sum(v < 0 for v, _ in unchanged)

            by_symbol[symbol] = {
                "bias_changed_events": len(changed),
                "bias_unchanged_events": len(unchanged),
                "changed_mean_return": sum(v for v, _ in changed) / len(changed) if changed else 0.0,
                "unchanged_mean_return": sum(v for v, _ in unchanged) / len(unchanged) if unchanged else 0.0,
                "changed_positive_rate": sum(v > 0 for v, _ in changed) / len(changed) if changed else 0.0,
                "unchanged_positive_rate": sum(v > 0 for v, _ in unchanged) / len(unchanged) if unchanged else 0.0,
                "target_weights": sorted({
                    item.weight
                    for _, targets in changed + unchanged
                    for item in targets
                }),
            }
        except Exception as exc:
            failures.append((symbol, str(exc)))

    changed_mean = sum(changed_returns) / len(changed_returns) if changed_returns else 0.0
    unchanged_mean = sum(unchanged_returns) / len(unchanged_returns) if unchanged_returns else 0.0
    changed_rate = changed_positive / changed_events if changed_events else 0.0
    unchanged_rate = unchanged_positive / unchanged_events if unchanged_events else 0.0

    print("DEMAND COMING IN FINAL QUALIFICATION OPTIMIZED AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": len(by_symbol),
        "bias_changed_events": changed_events,
        "bias_unchanged_events": unchanged_events,
        "changed_mean_return": changed_mean,
        "unchanged_mean_return": unchanged_mean,
        "mean_return_delta_changed_minus_unchanged": changed_mean - unchanged_mean,
        "changed_positive_rate": changed_rate,
        "unchanged_positive_rate": unchanged_rate,
        "positive_rate_delta_changed_minus_unchanged": changed_rate - unchanged_rate,
        "all_target_weights_038": all(
            info["target_weights"] == [WEIGHT] for info in by_symbol.values()
        ),
        "failures": failures,
        "status": "PASS" if not failures and changed_events > 0 else "FAIL",
    })
    print("DEMAND COMING IN FINAL QUALIFICATION BY_SYMBOL")
    for symbol, info in by_symbol.items():
        print({"symbol": symbol, **info})


if __name__ == "__main__":
    main()
