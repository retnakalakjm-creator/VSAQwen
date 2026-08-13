from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from engine.columns import COL_CLOSE, COL_DIRECTION, COL_SPREAD_CLASS, COL_VOLUME_CLASS
from evidence.aggregator import EvidenceAggregator
from evidence.engine import EvidenceEngine
from evidence.rules import (
    is_above_average_spread,
    is_bullish_bar,
    is_high_volume,
    volume_increasing,
)
from metrics_engine import MetricsEngine
from models import Direction, EvidenceCode, SpreadClass, VolumeClass
from trend import TrendAnalyzer

DEFAULT_SYMBOLS = (
    "BHARTIARTL.NS", "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "INFY.NS", "TCS.NS", "SBIN.NS", "LT.NS",
)
MIN_REPLAY_BARS = 20
HORIZON = 8
WEIGHTS = (0.25, 0.40, 0.60, 0.75, 0.85, 1.00)


def outcome_for(metrics, index: int) -> str:
    current = float(metrics.iloc[index][COL_CLOSE])
    future = float(metrics.iloc[index + HORIZON][COL_CLOSE])
    ret8 = (future - current) / current
    if ret8 > 0.02:
        return "POSITIVE_8_BAR"
    if ret8 < -0.02:
        return "NEGATIVE_8_BAR"
    return "FLAT_8_BAR"


def replay_event(metrics, index: int):
    row = metrics.iloc[index]
    if not (
        Direction(row[COL_DIRECTION]) == Direction.UP
        and VolumeClass(row[COL_VOLUME_CLASS]) >= VolumeClass.HIGH
        and SpreadClass(row[COL_SPREAD_CLASS]) >= SpreadClass.ABOVE_AVERAGE
    ):
        return None

    replay = metrics.iloc[: index + 1]
    trend = TrendAnalyzer().analyze(replay)
    engine = EvidenceEngine()
    engine.collect(
        metrics=replay,
        trend=trend,
        structural_swings=tuple(trend.structure.structural_swings),
        validation_metrics=metrics,
    )
    assert engine._ctx is not None
    bar = engine._ctx.current
    previous = engine._ctx.previous

    if previous is None or not all((
        is_bullish_bar(bar),
        is_high_volume(bar),
        is_above_average_spread(bar),
        volume_increasing(bar, previous),
    )):
        return None

    evidence = tuple(engine._evidence)
    current_event = tuple(
        item for item in evidence
        if item.code == EvidenceCode.INCREASING_DEMAND
        and item.bar_index == index
    )
    if not current_event:
        return None

    return evidence, outcome_for(metrics, index)


def inspect_symbol(symbol: str) -> list[dict]:
    daily = download_data(symbol)
    metrics = MetricsEngine().calculate(daily_to_weekly(daily))
    records: list[dict] = []

    for index in range(MIN_REPLAY_BARS, len(metrics) - HORIZON):
        replayed = replay_event(metrics, index)
        if replayed is None:
            continue
        evidence, outcome = replayed

        baseline = EvidenceAggregator().aggregate(evidence)
        records.append({
            "symbol": symbol,
            "bar_index": index,
            "outcome": outcome,
            "evidence": evidence,
            "baseline": baseline,
        })

    return records


def counterfactual_summary(records: list[dict], weight: float) -> dict:
    by_outcome: dict[str, list[float]] = {}
    bias_changes: dict[str, int] = {}
    deltas: list[float] = []

    for record in records:
        baseline = record["baseline"]
        adjusted = tuple(
            replace(item, weight=weight)
            if item.code == EvidenceCode.INCREASING_DEMAND
            and item.bar_index == record["bar_index"]
            else item
            for item in record["evidence"]
        )
        candidate = EvidenceAggregator().aggregate(adjusted)
        delta = candidate.net_score - baseline.net_score
        deltas.append(delta)
        outcome = record["outcome"]
        by_outcome.setdefault(outcome, []).append(delta)
        if candidate.bias != baseline.bias:
            key = f"{baseline.bias.name}->{candidate.bias.name}"
            bias_changes[key] = bias_changes.get(key, 0) + 1

    def avg(values: list[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    return {
        "candidate_weight": weight,
        "events": len(records),
        "avg_net_score_delta": avg(deltas),
        "max_net_score_delta": max(deltas) if deltas else 0.0,
        "min_net_score_delta": min(deltas) if deltas else 0.0,
        "positive_avg_delta": avg(by_outcome.get("POSITIVE_8_BAR", [])),
        "negative_avg_delta": avg(by_outcome.get("NEGATIVE_8_BAR", [])),
        "flat_avg_delta": avg(by_outcome.get("FLAT_8_BAR", [])),
        "bias_changes": bias_changes,
    }


def main() -> None:
    symbols = tuple(sys.argv[1:]) or DEFAULT_SYMBOLS
    all_records: list[dict] = []
    failures: list[dict] = []

    with ThreadPoolExecutor(max_workers=min(4, len(symbols))) as executor:
        futures = {executor.submit(inspect_symbol, symbol): symbol for symbol in symbols}
        for future, symbol in futures.items():
            try:
                all_records.extend(future.result())
            except Exception as exc:
                failures.append({"symbol": symbol, "error": repr(exc)})

    print("INCREASING DEMAND SCORING COUNTERFACTUAL SUMMARY")
    print({
        "symbols_requested": len(symbols),
        "symbols_with_events": len({x["symbol"] for x in all_records}),
        "events": len(all_records),
        "outcomes": {
            "POSITIVE_8_BAR": sum(x["outcome"] == "POSITIVE_8_BAR" for x in all_records),
            "NEGATIVE_8_BAR": sum(x["outcome"] == "NEGATIVE_8_BAR" for x in all_records),
            "FLAT_8_BAR": sum(x["outcome"] == "FLAT_8_BAR" for x in all_records),
        },
        "candidate_weights": WEIGHTS,
        "failures": failures,
    })

    print("INCREASING DEMAND SCORING IMPACT BY WEIGHT")
    for weight in WEIGHTS:
        print(counterfactual_summary(all_records, weight))


if __name__ == "__main__":
    main()
