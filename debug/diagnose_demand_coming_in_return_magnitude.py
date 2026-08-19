"""Return-magnitude audit for DEMAND_COMING_IN.

Analysis-only. Keeps the exact candidate definition and 8-bar horizon used by
prior decision-value audits. Production behavior and weights are unchanged.
"""
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np

from data import daily_to_weekly, download_data
from engine.columns import COL_CLOSE, COL_CLOSE_POSITION, COL_DIRECTION, COL_SPREAD_CLASS, COL_VOLUME_CLASS
from metrics_engine import MetricsEngine
from models import Direction, SpreadClass, VolumeClass

SYMBOLS = (
    "BHARTIARTL.NS",
    "RELIANCE.NS",
    "HDFCBANK.NS",
    "ICICIBANK.NS",
    "INFY.NS",
    "TCS.NS",
    "SBIN.NS",
    "LT.NS",
)
MIN_REPLAY_BARS = 20
HORIZON = 8


def is_candidate(row) -> bool:
    return (
        Direction(int(row[COL_DIRECTION])) == Direction.DOWN
        and VolumeClass(int(row[COL_VOLUME_CLASS])) >= VolumeClass.HIGH
        and SpreadClass(int(row[COL_SPREAD_CLASS])) >= SpreadClass.ABOVE_AVERAGE
        and int(row[COL_CLOSE_POSITION]) >= 2
    )


def forward_return(metrics, index: int) -> float | None:
    future_index = index + HORIZON
    if future_index >= len(metrics):
        return None
    entry = float(metrics.iloc[index][COL_CLOSE])
    future = float(metrics.iloc[future_index][COL_CLOSE])
    if entry == 0.0:
        return None
    return (future - entry) / entry


def summarize(returns: list[float]) -> dict:
    if not returns:
        return {
            "events": 0,
            "mean_return": 0.0,
            "median_return": 0.0,
            "positive_rate": 0.0,
            "mean_positive_return": 0.0,
            "mean_negative_return": 0.0,
            "median_positive_return": 0.0,
            "median_negative_return": 0.0,
            "worst_return": 0.0,
            "best_return": 0.0,
            "mean_abs_return": 0.0,
        }

    values = np.asarray(returns, dtype=float)
    positive = values[values > 0]
    negative = values[values < 0]

    return {
        "events": int(values.size),
        "mean_return": float(values.mean()),
        "median_return": float(np.median(values)),
        "positive_rate": float((values > 0).mean()),
        "mean_positive_return": float(positive.mean()) if len(positive) else 0.0,
        "mean_negative_return": float(negative.mean()) if len(negative) else 0.0,
        "median_positive_return": float(np.median(positive)) if len(positive) else 0.0,
        "median_negative_return": float(np.median(negative)) if len(negative) else 0.0,
        "worst_return": float(values.min()),
        "best_return": float(values.max()),
        "mean_abs_return": float(np.abs(values).mean()),
    }


def inspect_symbol(symbol: str) -> dict:
    metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
    candidate_returns: list[float] = []
    eligible_returns: list[float] = []

    for index in range(MIN_REPLAY_BARS, len(metrics) - HORIZON):
        value = forward_return(metrics, index)
        if value is None:
            continue
        eligible_returns.append(value)
        if is_candidate(metrics.iloc[index]):
            candidate_returns.append(value)

    candidate = summarize(candidate_returns)
    eligible = summarize(eligible_returns)
    return {
        "symbol": symbol,
        "candidate": candidate,
        "eligible": eligible,
        "mean_return_delta": candidate["mean_return"] - eligible["mean_return"],
        "median_return_delta": candidate["median_return"] - eligible["median_return"],
        "mean_abs_return_delta": candidate["mean_abs_return"] - eligible["mean_abs_return"],
        "downside_mean_delta": candidate["mean_negative_return"] - eligible["mean_negative_return"],
    }


def main() -> None:
    symbols = tuple(sys.argv[1:]) or SYMBOLS
    rows: list[dict] = []
    failures: list[dict[str, str]] = []

    with ThreadPoolExecutor(max_workers=min(4, len(symbols))) as executor:
        futures = {executor.submit(inspect_symbol, symbol): symbol for symbol in symbols}
        for future, symbol in futures.items():
            try:
                rows.append(future.result())
            except Exception as exc:  # noqa: BLE001
                failures.append({"symbol": symbol, "error": repr(exc)})

    all_candidate = []
    all_eligible = []
    for row in rows:
        # Reconstruct pooled samples from summary fields is impossible, so report
        # per-symbol results and use weighted mean/median proxies only for mean.
        pass

    candidate_events = sum(row["candidate"]["events"] for row in rows)
    eligible_events = sum(row["eligible"]["events"] for row in rows)
    candidate_mean = (
        sum(row["candidate"]["mean_return"] * row["candidate"]["events"] for row in rows) / candidate_events
        if candidate_events else 0.0
    )
    eligible_mean = (
        sum(row["eligible"]["mean_return"] * row["eligible"]["events"] for row in rows) / eligible_events
        if eligible_events else 0.0
    )

    print("DEMAND COMING IN RETURN MAGNITUDE SUMMARY")
    print({
        "symbols": len(symbols),
        "symbols_with_results": len(rows),
        "failures": failures,
        "candidate_events": candidate_events,
        "eligible_events": eligible_events,
        "candidate_weighted_mean_return": candidate_mean,
        "eligible_weighted_mean_return": eligible_mean,
        "mean_return_lift": candidate_mean - eligible_mean,
    })

    print("DEMAND COMING IN RETURN MAGNITUDE BY_SYMBOL")
    for row in sorted(rows, key=lambda item: item["symbol"]):
        print(row)


if __name__ == "__main__":
    main()
