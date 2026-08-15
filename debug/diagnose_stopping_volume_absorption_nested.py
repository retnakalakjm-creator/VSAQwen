"""Nested absorption audit over current Stopping Volume detections.

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
    COL_LOW,
    COL_OPEN,
    COL_SPREAD,
    COL_SPREAD_PERCENTILE,
    COL_VOLUME_PERCENTILE,
    COL_WEEK,
)
from metrics_engine import MetricsEngine
from models import Direction
from smart_money.rules.stopping_volume import StoppingVolumeRule

DEFAULT_SYMBOLS = (
    "BHARTIARTL.NS", "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "INFY.NS", "TCS.NS", "SBIN.NS", "LT.NS",
)
MIN_REPLAY_BARS = 20
FORWARD_HORIZON = 8
OUTCOME_THRESHOLD = 0.02
TAIL_THRESHOLDS = (0.25, 0.35)
CLOSE_THRESHOLDS = (0.60, 0.70)


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

    for index in range(MIN_REPLAY_BARS + 5, len(metrics)):
        future_index = index + FORWARD_HORIZON
        if future_index >= len(metrics):
            break
        if not current_rule_detects(metrics, index, rule):
            continue

        row = metrics.iloc[index]
        spread = float(row[COL_SPREAD])
        if spread <= 0.0:
            continue

        lower_tail = min(float(row[COL_OPEN]), float(row[COL_CLOSE])) - float(row[COL_LOW])
        tail_ratio = lower_tail / spread
        close_ratio = float(row[COL_CLOSE_RATIO])
        direction = Direction(row[COL_DIRECTION])
        current = float(row[COL_CLOSE])
        future = float(metrics.iloc[future_index][COL_CLOSE])
        forward_return = (future - current) / current
        decline3 = index >= 3 and float(metrics.iloc[index - 3][COL_CLOSE]) > current
        decline5 = index >= 5 and float(metrics.iloc[index - 5][COL_CLOSE]) > current

        events.append({
            "symbol": symbol,
            "bar_index": index,
            "week": str(row[COL_WEEK]),
            "direction": direction.name,
            "tail_ratio": tail_ratio,
            "close_ratio": close_ratio,
            "volume_percentile": float(row[COL_VOLUME_PERCENTILE]),
            "spread_percentile": float(row[COL_SPREAD_PERCENTILE]),
            "decline3": decline3,
            "decline5": decline5,
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

    cohorts = {
        "CURRENT_RULE": list(all_events),
        "CURRENT_RULE_PLUS_BEARISH": [e for e in all_events if e["direction"] == "DOWN"],
    }
    for tail_min in TAIL_THRESHOLDS:
        for close_min in CLOSE_THRESHOLDS:
            name = f"BEARISH_TAIL{int(tail_min * 100)}_CLOSE{int(close_min * 100)}"
            base = [e for e in all_events if e["direction"] == "DOWN" and e["tail_ratio"] >= tail_min and e["close_ratio"] >= close_min]
            cohorts[name] = base
            cohorts[name + "_DECLINE3"] = [e for e in base if e["decline3"]]
            cohorts[name + "_DECLINE5"] = [e for e in base if e["decline5"]]

    print("STOPPING VOLUME NESTED ABSORPTION AUDIT SUMMARY")
    print({
        "symbols_requested": len(symbols),
        "failures": failures,
        "current_rule_events": len(all_events),
        "cohorts": {name: summarize(events) for name, events in cohorts.items()},
    })
    print("STOPPING VOLUME NESTED ABSORPTION AUDIT FLAGS")
    print({
        "current_rule_bearish": sum(e["direction"] == "DOWN" for e in all_events),
        "current_rule_decline3": sum(e["decline3"] for e in all_events),
        "current_rule_decline5": sum(e["decline5"] for e in all_events),
    })


if __name__ == "__main__":
    main()
