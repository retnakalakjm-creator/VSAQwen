"""Analysis-only decision-value audit for HIDDEN_DEMAND.

Compares the validated candidate population against the eligible-market
baseline and tests a small synthetic scoring-weight range. No production
collector, registry, weight, or aggregation logic is modified.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from engine.columns import COL_CLOSE, COL_DIRECTION, COL_VOLUME_CLASS, COL_CLOSE_POSITION
from metrics_engine import MetricsEngine
from models import ClosePosition, Direction, VolumeClass

SYMBOLS = (
    "BHARTIARTL.NS", "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "INFY.NS", "TCS.NS", "SBIN.NS", "LT.NS",
)
FORWARD_BARS = 8
WEIGHTS = (0.0, 0.25, 0.30, 0.38, 0.45, 0.50)


def _candidate(row) -> bool:
    return (
        Direction(int(row[COL_DIRECTION])) == Direction.DOWN
        and VolumeClass(int(row[COL_VOLUME_CLASS])) >= VolumeClass.HIGH
        and ClosePosition(int(row[COL_CLOSE_POSITION])) >= ClosePosition.UPPER
    )


def _audit_symbol(symbol: str) -> dict:
    metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
    candidate_returns: list[float] = []
    eligible_returns: list[float] = []

    for index in range(21, len(metrics)):
        future_index = index + FORWARD_BARS
        if future_index >= len(metrics):
            continue
        start = float(metrics.iloc[index][COL_CLOSE])
        end = float(metrics.iloc[future_index][COL_CLOSE])
        if start == 0.0:
            continue
        forward = end / start - 1.0
        eligible_returns.append(forward)
        if _candidate(metrics.iloc[index]):
            candidate_returns.append(forward)

    def summary(values: list[float]) -> dict:
        positive = sum(v > 0 for v in values)
        negative = sum(v < 0 for v in values)
        decisive = positive + negative
        return {
            "events": len(values),
            "positive": positive,
            "negative": negative,
            "flat": len(values) - decisive,
            "decisive": decisive,
            "positive_decisive_rate": positive / decisive if decisive else 0.0,
            "mean_return": sum(values) / len(values) if values else 0.0,
        }

    candidate = summary(candidate_returns)
    eligible = summary(eligible_returns)
    return {"symbol": symbol, "candidate": candidate, "eligible": eligible}


def main() -> None:
    failures = []
    results = []
    with ThreadPoolExecutor(max_workers=min(4, len(SYMBOLS))) as executor:
        futures = {executor.submit(_audit_symbol, s): s for s in SYMBOLS}
        for future, symbol in futures.items():
            try:
                results.append(future.result())
            except Exception as exc:
                failures.append({"symbol": symbol, "error": repr(exc)})

    candidate_events = sum(r["candidate"]["events"] for r in results)
    candidate_positive = sum(r["candidate"]["positive"] for r in results)
    candidate_negative = sum(r["candidate"]["negative"] for r in results)
    candidate_decisive = candidate_positive + candidate_negative
    eligible_events = sum(r["eligible"]["events"] for r in results)
    eligible_positive = sum(r["eligible"]["positive"] for r in results)
    eligible_negative = sum(r["eligible"]["negative"] for r in results)
    eligible_decisive = eligible_positive + eligible_negative

    candidate_rate = candidate_positive / candidate_decisive if candidate_decisive else 0.0
    eligible_rate = eligible_positive / eligible_decisive if eligible_decisive else 0.0

    candidate_mean = (
        sum(r["candidate"]["mean_return"] * r["candidate"]["events"] for r in results) / candidate_events
        if candidate_events else 0.0
    )
    eligible_mean = (
        sum(r["eligible"]["mean_return"] * r["eligible"]["events"] for r in results) / eligible_events
        if eligible_events else 0.0
    )

    # Synthetic ranking impact: a positive candidate weight changes a neutral/bearish
    # score by a bounded amount. We report candidate weight only; production scoring
    # is intentionally untouched.
    weight_summary = []
    for weight in WEIGHTS:
        weight_summary.append({
            "weight": weight,
            "candidate_score_contribution": round(weight, 6),
            "relative_candidate_strength": round(weight * 0.90, 6),
        })

    print("HIDDEN DEMAND DECISION VALUE AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": len(results),
        "candidate": {
            "events": candidate_events,
            "positive": candidate_positive,
            "negative": candidate_negative,
            "decisive": candidate_decisive,
            "positive_decisive_rate": candidate_rate,
            "mean_return": candidate_mean,
        },
        "eligible_market": {
            "events": eligible_events,
            "positive": eligible_positive,
            "negative": eligible_negative,
            "decisive": eligible_decisive,
            "positive_decisive_rate": eligible_rate,
            "mean_return": eligible_mean,
        },
        "positive_decisive_rate_lift": candidate_rate - eligible_rate,
        "mean_return_lift": candidate_mean - eligible_mean,
        "candidate_share_of_eligible": candidate_events / eligible_events if eligible_events else 0.0,
        "weights_tested": WEIGHTS,
        "failures": failures,
        "status": "PASS" if not failures else "FAIL",
    })
    print("HIDDEN DEMAND DECISION VALUE WEIGHTS")
    for row in weight_summary:
        print(row)
    print("HIDDEN DEMAND DECISION VALUE BY_SYMBOL")
    for row in sorted(results, key=lambda x: x["symbol"]):
        print(row)


if __name__ == "__main__":
    main()
