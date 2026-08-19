"""Decision-value audit for DEMAND_COMING_IN.

Analysis-only. Uses the exact 281-candidate definition from the semantic audit.
Compares candidate outcomes with the full eligible weekly market population and
reports incremental lift by symbol. No production detector, weight, or scanner
behavior is changed.
"""
from __future__ import annotations

import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from engine.columns import (
    COL_CLOSE,
    COL_CLOSE_POSITION,
    COL_DIRECTION,
    COL_SPREAD_CLASS,
    COL_VOLUME_CLASS,
    COL_WEEK,
)
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
FORWARD_HORIZON = 8


def is_candidate(row) -> bool:
    return (
        Direction(int(row[COL_DIRECTION])) == Direction.DOWN
        and VolumeClass(int(row[COL_VOLUME_CLASS])) >= VolumeClass.HIGH
        and SpreadClass(int(row[COL_SPREAD_CLASS])) >= SpreadClass.ABOVE_AVERAGE
        and int(row[COL_CLOSE_POSITION]) >= 2
    )


def outcome(metrics, index: int) -> str | None:
    future = index + FORWARD_HORIZON
    if future >= len(metrics):
        return None
    current = float(metrics.iloc[index][COL_CLOSE])
    future_close = float(metrics.iloc[future][COL_CLOSE])
    if future_close > current:
        return "POSITIVE_8_BAR"
    if future_close < current:
        return "NEGATIVE_8_BAR"
    return "FLAT_8_BAR"


def summarize(rows: list[dict]) -> dict:
    counts = Counter(row["outcome"] for row in rows)
    decisive = counts["POSITIVE_8_BAR"] + counts["NEGATIVE_8_BAR"]
    return {
        "events": len(rows),
        "positive": counts["POSITIVE_8_BAR"],
        "negative": counts["NEGATIVE_8_BAR"],
        "flat": counts["FLAT_8_BAR"],
        "decisive": decisive,
        "positive_decisive_rate": counts["POSITIVE_8_BAR"] / decisive if decisive else 0.0,
    }


def inspect_symbol(symbol: str) -> dict:
    metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
    candidate_rows: list[dict] = []
    eligible_rows: list[dict] = []

    for index in range(MIN_REPLAY_BARS, len(metrics) - FORWARD_HORIZON):
        event_outcome = outcome(metrics, index)
        if event_outcome is None:
            continue
        row = metrics.iloc[index]
        payload = {
            "symbol": symbol,
            "bar_index": index,
            "week": str(row[COL_WEEK]),
            "outcome": event_outcome,
        }
        eligible_rows.append(payload)
        if is_candidate(row):
            candidate_rows.append(payload)

    candidate = summarize(candidate_rows)
    eligible = summarize(eligible_rows)
    candidate_rate = candidate["events"] / eligible["events"] if eligible["events"] else 0.0
    lift = candidate["positive_decisive_rate"] - eligible["positive_decisive_rate"]

    return {
        "symbol": symbol,
        "candidate": candidate,
        "eligible": eligible,
        "candidate_event_rate": candidate_rate,
        "positive_rate_lift": lift,
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

    candidate_all: list[dict] = []
    eligible_all: list[dict] = []
    for row in rows:
        # Reconstruct aggregate counts from each symbol summary.
        candidate = row["candidate"]
        eligible = row["eligible"]
        candidate_all.extend(
            [{"outcome": "POSITIVE_8_BAR"}] * candidate["positive"]
            + [{"outcome": "NEGATIVE_8_BAR"}] * candidate["negative"]
            + [{"outcome": "FLAT_8_BAR"}] * candidate["flat"]
        )
        eligible_all.extend(
            [{"outcome": "POSITIVE_8_BAR"}] * eligible["positive"]
            + [{"outcome": "NEGATIVE_8_BAR"}] * eligible["negative"]
            + [{"outcome": "FLAT_8_BAR"}] * eligible["flat"]
        )

    overall_candidate = summarize(candidate_all)
    overall_eligible = summarize(eligible_all)
    overall_lift = (
        overall_candidate["positive_decisive_rate"]
        - overall_eligible["positive_decisive_rate"]
    )

    print("DEMAND COMING IN DECISION VALUE SUMMARY")
    print({
        "symbols_requested": len(symbols),
        "symbols_with_results": len(rows),
        "failures": failures,
        "candidate": overall_candidate,
        "eligible_market": overall_eligible,
        "positive_decisive_rate_lift": overall_lift,
        "candidate_share_of_eligible": (
            overall_candidate["events"] / overall_eligible["events"]
            if overall_eligible["events"] else 0.0
        ),
        "production_weight": 0.00,
        "production_path": "DISABLED",
    })

    print("DEMAND COMING IN DECISION VALUE BY_SYMBOL")
    for row in sorted(rows, key=lambda item: item["symbol"]):
        print(row)


if __name__ == "__main__":
    main()
