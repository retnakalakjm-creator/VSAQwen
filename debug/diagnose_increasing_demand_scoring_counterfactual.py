from __future__ import annotations

import json
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
from evidence.evidence_registry import build_evidence
from evidence.rules import is_above_average_spread, is_bullish_bar, is_high_volume, volume_increasing
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
OUTPUT_DIR = ROOT / "debug" / "output"
OUTPUT_FILE = OUTPUT_DIR / "increasing_demand_scoring_counterfactual.json"


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
        Direction(int(row[COL_DIRECTION])) == Direction.UP
        and VolumeClass(int(row[COL_VOLUME_CLASS])) >= VolumeClass.HIGH
        and SpreadClass(int(row[COL_SPREAD_CLASS])) >= SpreadClass.ABOVE_AVERAGE
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

    evidence = list(engine._evidence)
    if not any(item.code == EvidenceCode.INCREASING_DEMAND and item.bar_index == index for item in evidence):
        evidence.append(build_evidence(
            EvidenceCode.INCREASING_DEMAND,
            strength=0.90,
            weight=1.00,
            bar_index=index,
            week_beginning=bar.week_beginning,
        ))
    return tuple(evidence), outcome_for(metrics, index)


def inspect_symbol(symbol: str) -> list[dict]:
    daily = download_data(symbol)
    metrics = MetricsEngine().calculate(daily_to_weekly(daily))
    return [
        {"symbol": symbol, "bar_index": index, "outcome": outcome, "evidence": evidence,
         "baseline": EvidenceAggregator().aggregate(evidence)}
        for index in range(MIN_REPLAY_BARS, len(metrics) - HORIZON)
        if (replayed := replay_event(metrics, index)) is not None
        for evidence, outcome in (replayed,)
    ]


def counterfactual_summary(records: list[dict], weight: float) -> dict:
    by_outcome = {key: [] for key in ("POSITIVE_8_BAR", "NEGATIVE_8_BAR", "FLAT_8_BAR")}
    bias_changes: dict[str, int] = {}
    deltas: list[float] = []
    for record in records:
        adjusted = tuple(
            replace(item, weight=weight)
            if item.code == EvidenceCode.INCREASING_DEMAND and item.bar_index == record["bar_index"]
            else item
            for item in record["evidence"]
        )
        baseline = record["baseline"]
        candidate = EvidenceAggregator().aggregate(adjusted)
        delta = candidate.net_score - baseline.net_score
        deltas.append(delta)
        by_outcome[record["outcome"]].append(delta)
        if candidate.bias != baseline.bias:
            key = f"{baseline.bias.name}->{candidate.bias.name}"
            bias_changes[key] = bias_changes.get(key, 0) + 1

    def avg(values):
        return sum(values) / len(values) if values else 0.0

    return {
        "candidate_weight": weight,
        "events": len(records),
        "avg_net_score_delta": avg(deltas),
        "max_net_score_delta": max(deltas) if deltas else 0.0,
        "min_net_score_delta": min(deltas) if deltas else 0.0,
        "positive_avg_delta": avg(by_outcome["POSITIVE_8_BAR"]),
        "negative_avg_delta": avg(by_outcome["NEGATIVE_8_BAR"]),
        "flat_avg_delta": avg(by_outcome["FLAT_8_BAR"]),
        "bias_changes": bias_changes,
    }


def main() -> None:
    symbols = tuple(sys.argv[1:]) or DEFAULT_SYMBOLS
    all_records, failures = [], []
    with ThreadPoolExecutor(max_workers=min(4, len(symbols))) as executor:
        futures = {executor.submit(inspect_symbol, symbol): symbol for symbol in symbols}
        for future, symbol in futures.items():
            try:
                all_records.extend(future.result())
            except Exception as exc:
                failures.append({"symbol": symbol, "error": repr(exc)})

    outcomes = {key: sum(x["outcome"] == key for x in all_records)
                for key in ("POSITIVE_8_BAR", "NEGATIVE_8_BAR", "FLAT_8_BAR")}
    impacts = [counterfactual_summary(all_records, weight) for weight in WEIGHTS]
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps({
        "symbols_requested": len(symbols),
        "symbols_with_events": len({x["symbol"] for x in all_records}),
        "events": len(all_records), "outcomes": outcomes,
        "candidate_weights": WEIGHTS, "failures": failures, "weight_impacts": impacts,
    }, indent=2, default=str), encoding="utf-8")

    print("INCREASING DEMAND SCORING COUNTERFACTUAL SUMMARY")
    print({"symbols_requested": len(symbols),
           "symbols_with_events": len({x["symbol"] for x in all_records}),
           "events": len(all_records), "outcomes": outcomes,
           "candidate_weights": WEIGHTS, "failures": len(failures)})
    print("INCREASING DEMAND SCORING IMPACT BY WEIGHT")
    for item in impacts:
        print({"candidate_weight": item["candidate_weight"], "events": item["events"],
               "avg_net_score_delta": round(item["avg_net_score_delta"], 6),
               "positive_avg_delta": round(item["positive_avg_delta"], 6),
               "negative_avg_delta": round(item["negative_avg_delta"], 6),
               "flat_avg_delta": round(item["flat_avg_delta"], 6),
               "bias_changes": item["bias_changes"]})
    print(f"DETAILS: {OUTPUT_FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
