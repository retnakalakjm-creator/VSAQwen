"""Analysis-only decision-value audit for ABSORPTION."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from engine.columns import (
    COL_CLOSE,
    COL_CLOSE_POSITION,
    COL_DIRECTION,
    COL_LOW,
    COL_SPREAD_CLASS,
    COL_VOLUME_CLASS,
)
from metrics_engine import MetricsEngine
from models import ClosePosition, Direction, SpreadClass, VolumeClass

SYMBOLS = (
    "BHARTIARTL.NS", "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "INFY.NS", "TCS.NS", "SBIN.NS", "LT.NS",
)
FORWARD_BARS = 8
WEIGHTS = (0.0, 0.25, 0.30, 0.38, 0.45, 0.50)
CONFLICT_PENALTY = 0.20


def candidate(bar, previous) -> bool:
    return (
        Direction(int(bar[COL_DIRECTION])) == Direction.DOWN
        and VolumeClass(int(bar[COL_VOLUME_CLASS])) >= VolumeClass.HIGH
        and SpreadClass(int(bar[COL_SPREAD_CLASS])) >= SpreadClass.ABOVE_AVERAGE
        and ClosePosition(int(bar[COL_CLOSE_POSITION])) >= ClosePosition.UPPER
        and float(bar[COL_LOW]) < float(previous[COL_LOW])
    )


def conflict(bar, previous) -> bool:
    return (
        Direction(int(bar[COL_DIRECTION])) == Direction.DOWN
        and VolumeClass(int(bar[COL_VOLUME_CLASS])) > VolumeClass(int(previous[COL_VOLUME_CLASS]))
        and SpreadClass(int(bar[COL_SPREAD_CLASS])) > SpreadClass(int(previous[COL_SPREAD_CLASS]))
    )


def audit_symbol(symbol: str) -> dict:
    metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
    candidates = []
    eligible = []

    for index in range(21, len(metrics)):
        if index + FORWARD_BARS >= len(metrics):
            continue
        bar = metrics.iloc[index]
        previous = metrics.iloc[index - 1]
        start = float(bar[COL_CLOSE])
        end = float(metrics.iloc[index + FORWARD_BARS][COL_CLOSE])
        if start == 0.0:
            continue
        forward = end / start - 1.0
        eligible.append(forward)
        if candidate(bar, previous):
            candidates.append((forward, conflict(bar, previous)))

    return {"symbol": symbol, "candidates": candidates, "eligible": eligible}


def summarize(values: list[float]) -> dict:
    positive = sum(v > 0 for v in values)
    negative = sum(v < 0 for v in values)
    decisive = positive + negative
    return {
        "events": len(values),
        "positive": positive,
        "negative": negative,
        "decisive": decisive,
        "positive_decisive_rate": positive / decisive if decisive else 0.0,
        "mean_return": sum(values) / len(values) if values else 0.0,
    }


def main() -> None:
    failures = []
    results = []
    with ThreadPoolExecutor(max_workers=min(4, len(SYMBOLS))) as executor:
        futures = {executor.submit(audit_symbol, symbol): symbol for symbol in SYMBOLS}
        for future, symbol in futures.items():
            try:
                results.append(future.result())
            except Exception as exc:
                failures.append({"symbol": symbol, "error": repr(exc)})

    candidate_events = []
    eligible_events = []
    for item in results:
        candidate_events.extend(item["candidates"])
        eligible_events.extend(item["eligible"])

    candidates_all = [x[0] for x in candidate_events]
    clean = [x[0] for x in candidate_events if not x[1]]
    conflict_values = [x[0] for x in candidate_events if x[1]]

    base = summarize(candidates_all)
    eligible = summarize(eligible_events)
    clean_summary = summarize(clean)
    conflict_summary = summarize(conflict_values)

    print("ABSORPTION DECISION VALUE AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": len(results),
        "candidate": base,
        "eligible_market": eligible,
        "clean_candidate": clean_summary,
        "conflict_candidate": conflict_summary,
        "positive_decisive_rate_lift": base["positive_decisive_rate"] - eligible["positive_decisive_rate"],
        "mean_return_lift": base["mean_return"] - eligible["mean_return"],
        "candidate_share_of_eligible": base["events"] / eligible["events"] if eligible["events"] else 0.0,
        "conflict_penalty": CONFLICT_PENALTY,
        "weights_tested": WEIGHTS,
        "failures": failures,
        "status": "PASS" if not failures and base["events"] > 0 else "FAIL",
    })

    print("ABSORPTION DECISION VALUE WEIGHTS")
    for weight in WEIGHTS:
        clean_strength = weight
        conflict_strength = weight * (1.0 - CONFLICT_PENALTY)
        print({
            "weight": weight,
            "candidate_score_contribution": weight,
            "effective_conflict_weight": conflict_strength,
            "clean_weight": clean_strength,
            "relative_conflict_strength": conflict_strength * 0.9,
        })


if __name__ == "__main__":
    main()
