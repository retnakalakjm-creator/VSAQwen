"""Optimized semantic-quality audit for DEMAND_COMING_IN.

Analysis-only. Reuses the exact 281-candidate definition from the semantic and
robustness audits. No EvidenceEngine or TrendAnalyzer replay is performed.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data import daily_to_weekly, download_data
from engine.columns import (
    COL_CLOSE,
    COL_CLOSE_POSITION,
    COL_DIRECTION,
    COL_HIGH,
    COL_LOW,
    COL_SPREAD_CLASS,
    COL_VOLUME_CLASS,
    COL_WEEK,
)
from evidence.rules import (
    has_strong_spread,
    is_very_high_volume,
    makes_higher_low,
    volume_increasing,
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
FORWARD_HORIZON = 8
MIN_REPLAY_BARS = 20


def is_candidate(row) -> bool:
    return (
        Direction(int(row[COL_DIRECTION])) == Direction.DOWN
        and VolumeClass(int(row[COL_VOLUME_CLASS])) >= VolumeClass.HIGH
        and SpreadClass(int(row[COL_SPREAD_CLASS])) >= SpreadClass.ABOVE_AVERAGE
        and int(row[COL_CLOSE_POSITION]) >= 2
    )


def outcome(metrics, index: int) -> str:
    future = index + FORWARD_HORIZON
    if future >= len(metrics):
        return "INSUFFICIENT_FORWARD_DATA"
    current = float(metrics.iloc[index][COL_CLOSE])
    future_close = float(metrics.iloc[future][COL_CLOSE])
    if future_close > current:
        return "POSITIVE_8_BAR"
    if future_close < current:
        return "NEGATIVE_8_BAR"
    return "FLAT_8_BAR"


def collect_symbol(symbol: str) -> list[dict]:
    metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
    rows: list[dict] = []

    for bar_index in range(MIN_REPLAY_BARS, len(metrics)):
        row = metrics.iloc[bar_index]
        if not is_candidate(row):
            continue

        previous = metrics.iloc[bar_index - 1]
        rows.append(
            {
                "symbol": symbol,
                "bar_index": bar_index,
                "week": str(row[COL_WEEK]),
                "outcome": outcome(metrics, bar_index),
                "close_position": int(row[COL_CLOSE_POSITION]),
                "volume_class": int(row[COL_VOLUME_CLASS]),
                "spread_class": int(row[COL_SPREAD_CLASS]),
                "very_high_volume": bool(is_very_high_volume(row)),
                "wide_spread": bool(has_strong_spread(row)),
                "volume_increasing": bool(volume_increasing(row, previous)),
                "higher_low": bool(makes_higher_low(row, previous)),
            }
        )

    return rows


def summarize(rows: list[dict]) -> dict:
    counts = Counter(row["outcome"] for row in rows)
    decisive = counts["POSITIVE_8_BAR"] + counts["NEGATIVE_8_BAR"]

    volume_increasing = sum(row["volume_increasing"] for row in rows)
    higher_low = sum(row["higher_low"] for row in rows)
    both_supporting = sum(
        row["volume_increasing"] and row["higher_low"] for row in rows
    )
    non_climactic = sum(
        not row["very_high_volume"] and not row["wide_spread"] for row in rows
    )
    semantic_quality_like = sum(
        row["close_position"] >= 2
        and not row["very_high_volume"]
        and not row["wide_spread"]
        and (row["volume_increasing"] or row["higher_low"])
        for row in rows
    )

    return {
        "events": len(rows),
        "positive": counts["POSITIVE_8_BAR"],
        "negative": counts["NEGATIVE_8_BAR"],
        "flat": counts["FLAT_8_BAR"],
        "insufficient_forward_data": counts["INSUFFICIENT_FORWARD_DATA"],
        "decisive": decisive,
        "positive_decisive_rate": counts["POSITIVE_8_BAR"] / decisive if decisive else 0.0,
        "volume_increasing": volume_increasing,
        "higher_low": higher_low,
        "both_supporting": both_supporting,
        "non_climactic": non_climactic,
        "semantic_quality_like": semantic_quality_like,
        "semantic_quality_like_rate": semantic_quality_like / len(rows) if rows else 0.0,
    }


def main() -> None:
    all_rows: list[dict] = []
    failures: list[dict[str, str]] = []
    by_symbol: dict[str, list[dict]] = {symbol: [] for symbol in SYMBOLS}

    for symbol in SYMBOLS:
        try:
            rows = collect_symbol(symbol)
            by_symbol[symbol].extend(rows)
            all_rows.extend(rows)
        except Exception as exc:  # noqa: BLE001
            failures.append({"symbol": symbol, "error": repr(exc)})

    summary = summarize(all_rows)
    print("DEMAND COMING IN SEMANTIC QUALITY AUDIT SUMMARY")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_candidates": len({row["symbol"] for row in all_rows}),
        "candidate_events": len(all_rows),
        **summary,
        "failures": failures,
    })

    print("DEMAND COMING IN SEMANTIC QUALITY AUDIT BY_SYMBOL")
    for symbol in SYMBOLS:
        print(symbol, summarize(by_symbol[symbol]))


if __name__ == "__main__":
    main()
