"""Temporal stability audit for DEMAND_COMING_IN decision value.

Analysis-only. Uses the exact semantic candidate definition and compares the
candidate outcome rate against the full eligible market rate in chronological
windows. Production scoring remains disabled.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from collections import Counter

from data import daily_to_weekly, download_data
from engine.columns import COL_CLOSE, COL_CLOSE_POSITION, COL_DIRECTION, COL_SPREAD_CLASS, COL_VOLUME_CLASS, COL_WEEK
from metrics_engine import MetricsEngine
from models import Direction, SpreadClass, VolumeClass

SYMBOLS = (
    "BHARTIARTL.NS", "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "INFY.NS", "TCS.NS", "SBIN.NS", "LT.NS",
)
MIN_REPLAY_BARS = 20
HORIZON = 8
WINDOWS = 4


def is_candidate(row) -> bool:
    return (
        Direction(int(row[COL_DIRECTION])) == Direction.DOWN
        and VolumeClass(int(row[COL_VOLUME_CLASS])) >= VolumeClass.HIGH
        and SpreadClass(int(row[COL_SPREAD_CLASS])) >= SpreadClass.ABOVE_AVERAGE
        and int(row[COL_CLOSE_POSITION]) >= 2
    )


def outcome(metrics, index: int) -> str | None:
    future = index + HORIZON
    if future >= len(metrics):
        return None
    current = float(metrics.iloc[index][COL_CLOSE])
    future_close = float(metrics.iloc[future][COL_CLOSE])
    if future_close > current:
        return "POSITIVE"
    if future_close < current:
        return "NEGATIVE"
    return "FLAT"


def summarize(rows: list[dict]) -> dict:
    counts = Counter(row["outcome"] for row in rows)
    decisive = counts["POSITIVE"] + counts["NEGATIVE"]
    return {
        "events": len(rows),
        "positive": counts["POSITIVE"],
        "negative": counts["NEGATIVE"],
        "flat": counts["FLAT"],
        "decisive": decisive,
        "positive_decisive_rate": counts["POSITIVE"] / decisive if decisive else 0.0,
    }


def collect_symbol(symbol: str) -> list[dict]:
    metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
    rows: list[dict] = []
    for index in range(MIN_REPLAY_BARS, len(metrics) - HORIZON):
        row = metrics.iloc[index]
        event_outcome = outcome(metrics, index)
        if event_outcome is None:
            continue
        rows.append({
            "symbol": symbol,
            "index": index,
            "week": str(row[COL_WEEK]),
            "candidate": is_candidate(row),
            "outcome": event_outcome,
        })
    return rows


def main() -> None:
    by_symbol: dict[str, list[dict]] = {}
    failures: list[dict[str, str]] = []

    for symbol in SYMBOLS:
        try:
            by_symbol[symbol] = collect_symbol(symbol)
        except Exception as exc:  # noqa: BLE001
            failures.append({"symbol": symbol, "error": repr(exc)})
            by_symbol[symbol] = []

    all_rows = [row for rows in by_symbol.values() for row in rows]
    print("DEMAND COMING IN TEMPORAL STABILITY SUMMARY")
    print({"symbols": len(SYMBOLS), "symbols_with_results": len([s for s, rows in by_symbol.items() if rows]), "failures": failures})

    overall_start = min((row["index"] for row in all_rows), default=0)
    overall_end = max((row["index"] for row in all_rows), default=0)
    span = max(1, overall_end - overall_start + 1)
    boundaries = [overall_start + round(span * i / WINDOWS) for i in range(WINDOWS + 1)]

    for window in range(WINDOWS):
        start = boundaries[window]
        end = boundaries[window + 1]
        rows = [row for row in all_rows if start <= row["index"] < end]
        candidate = summarize([row for row in rows if row["candidate"]])
        eligible = summarize(rows)
        lift = candidate["positive_decisive_rate"] - eligible["positive_decisive_rate"]
        print({"window": window + 1, "start_index": start, "end_index": end - 1, "candidate": candidate, "eligible": eligible, "positive_rate_lift": lift})

    print("DEMAND COMING IN TEMPORAL STABILITY BY_SYMBOL")
    for symbol, rows in by_symbol.items():
        if not rows:
            continue
        start = min(row["index"] for row in rows)
        end = max(row["index"] for row in rows)
        span = max(1, end - start + 1)
        boundaries = [start + round(span * i / WINDOWS) for i in range(WINDOWS + 1)]
        windows = []
        for window in range(WINDOWS):
            w_start = boundaries[window]
            w_end = boundaries[window + 1]
            subset = [row for row in rows if w_start <= row["index"] < w_end]
            candidate = summarize([row for row in subset if row["candidate"]])
            eligible = summarize(subset)
            windows.append({
                "window": window + 1,
                "candidate_events": candidate["events"],
                "eligible_events": eligible["events"],
                "candidate_positive_rate": candidate["positive_decisive_rate"],
                "eligible_positive_rate": eligible["positive_decisive_rate"],
                "lift": candidate["positive_decisive_rate"] - eligible["positive_decisive_rate"] if candidate["events"] else 0.0,
            })
        print(symbol, windows)


if __name__ == "__main__":
    main()
