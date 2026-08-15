"""Robustness audit for the provisional Stopping Volume candidate.

Candidate:
    current rule + bearish bar + close_ratio >= 0.70 + prior 3-bar decline.

Read-only diagnostic. No production detector or weight changes.
"""
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from engine.columns import (
    COL_CLOSE,
    COL_CLOSE_RATIO,
    COL_DIRECTION,
    COL_SPREAD,
    COL_VOLUME_PERCENTILE,
    COL_SPREAD_PERCENTILE,
    COL_WEEK,
)
from metrics_engine import MetricsEngine
from models import Direction
from smart_money.rules.stopping_volume import StoppingVolumeRule

DEFAULT_SYMBOLS = (
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
OUTCOME_THRESHOLD = 0.02


def outcome(forward_return: float) -> str:
    if forward_return > OUTCOME_THRESHOLD:
        return "POSITIVE_8_BAR"
    if forward_return < -OUTCOME_THRESHOLD:
        return "NEGATIVE_8_BAR"
    return "FLAT_8_BAR"


def summarize(events: list[dict]) -> dict:
    positive = sum(e["outcome"] == "POSITIVE_8_BAR" for e in events)
    negative = sum(e["outcome"] == "NEGATIVE_8_BAR" for e in events)
    flat = sum(e["outcome"] == "FLAT_8_BAR" for e in events)
    decisive = positive + negative
    return {
        "events": len(events),
        "positive": positive,
        "negative": negative,
        "flat": flat,
        "decisive": decisive,
        "positive_decisive_rate": positive / decisive if decisive else None,
    }


def current_rule_detects(metrics, index: int, rule: StoppingVolumeRule) -> bool:
    ctx = type(
        "StoppingVolumeRuleAuditContext",
        (),
        {
            "metrics": metrics.iloc[: index + 1],
            "swing": type("Swing", (), {"metrics_index": index})(),
            "history": type("History", (), {"has_previous": index > 0})(),
        },
    )()
    return bool(rule._detect(ctx))


def inspect_symbol(symbol: str) -> list[dict]:
    daily = download_data(symbol)
    metrics = MetricsEngine().calculate(daily_to_weekly(daily))
    rule = StoppingVolumeRule()
    events: list[dict] = []

    for index in range(MIN_REPLAY_BARS + 3, len(metrics)):
        future_index = index + FORWARD_HORIZON
        if future_index >= len(metrics):
            break
        if not current_rule_detects(metrics, index, rule):
            continue

        row = metrics.iloc[index]
        direction = Direction(row[COL_DIRECTION])
        if direction is not Direction.DOWN:
            continue

        close_ratio = float(row[COL_CLOSE_RATIO])
        if close_ratio < 0.70:
            continue

        current = float(row[COL_CLOSE])
        future = float(metrics.iloc[future_index][COL_CLOSE])
        if current != current or future != future or current == 0.0:
            continue

        start_close = float(metrics.iloc[index - 3][COL_CLOSE])
        if not start_close > current:
            continue

        spread = float(row[COL_SPREAD])
        lower_tail = min(float(row["open"]), current) - float(row["low"])
        tail_ratio = lower_tail / spread if spread > 0.0 else 0.0
        forward_return = (future - current) / current

        events.append({
            "symbol": symbol,
            "bar_index": index,
            "week": str(row[COL_WEEK]),
            "tail_ratio": tail_ratio,
            "close_ratio": close_ratio,
            "volume_percentile": float(row[COL_VOLUME_PERCENTILE]),
            "spread_percentile": float(row[COL_SPREAD_PERCENTILE]),
            "forward_return": forward_return,
            "outcome": outcome(forward_return),
        })

    return events


def main() -> None:
    symbols = tuple(sys.argv[1:]) or DEFAULT_SYMBOLS
    all_events: list[dict] = []
    failures: list[dict] = []

    with ThreadPoolExecutor(max_workers=min(4, len(symbols))) as executor:
        futures = {executor.submit(inspect_symbol, symbol): symbol for symbol in symbols}
        for future, symbol in futures.items():
            try:
                all_events.extend(future.result())
            except Exception as exc:
                failures.append({"symbol": symbol, "error": repr(exc)})

    print("STOPPING VOLUME CANDIDATE ROBUSTNESS SUMMARY")
    print({
        "symbols_requested": len(symbols),
        "failures": failures,
        "candidate_events": len(all_events),
        "candidate": summarize(all_events),
    })

    print("STOPPING VOLUME CANDIDATE BY_SYMBOL")
    for symbol in symbols:
        symbol_events = [e for e in all_events if e["symbol"] == symbol]
        print({"symbol": symbol, **summarize(symbol_events)})

    print("STOPPING VOLUME CANDIDATE LEAVE_ONE_OUT")
    for excluded in symbols:
        remaining = [e for e in all_events if e["symbol"] != excluded]
        print({"excluded_symbol": excluded, **summarize(remaining)})


if __name__ == "__main__":
    main()
