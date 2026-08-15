"""Semantic audit for the provisional Stopping Volume candidate.

Candidate population:
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
    COL_HIGH,
    COL_LOW,
    COL_OPEN,
    COL_PREV_CLOSE,
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
    absorption = sum(e["absorption_like"] for e in events)
    prior_down = sum(e["prior_bar_down"] for e in events)
    volume_extreme = sum(e["volume_percentile"] >= 90.0 for e in events)
    spread_extreme = sum(e["spread_percentile"] >= 90.0 for e in events)
    return {
        "events": len(events),
        "positive": positive,
        "negative": negative,
        "flat": flat,
        "decisive": decisive,
        "positive_decisive_rate": positive / decisive if decisive else None,
        "absorption_like": absorption,
        "absorption_like_rate": absorption / len(events) if events else None,
        "prior_bar_down": prior_down,
        "prior_bar_down_rate": prior_down / len(events) if events else None,
        "volume_ge_90": volume_extreme,
        "spread_ge_90": spread_extreme,
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
        if Direction(row[COL_DIRECTION]) is not Direction.DOWN:
            continue
        if float(row[COL_CLOSE_RATIO]) < 0.70:
            continue

        current = float(row[COL_CLOSE])
        future = float(metrics.iloc[future_index][COL_CLOSE])
        if current != current or future != future or current == 0.0:
            continue

        start_close = float(metrics.iloc[index - 3][COL_CLOSE])
        if not start_close > current:
            continue

        spread = float(row[COL_SPREAD])
        if spread <= 0.0:
            continue

        open_price = float(row[COL_OPEN])
        low_price = float(row[COL_LOW])
        high_price = float(row[COL_HIGH])
        lower_tail = min(open_price, current) - low_price
        upper_tail = high_price - max(open_price, current)
        tail_ratio = lower_tail / spread
        prior_close = float(row[COL_PREV_CLOSE])
        prior_bar_down = prior_close > open_price
        prior_bar_range = max(high_price - low_price, 1e-12)
        close_recovery = (current - low_price) / prior_bar_range

        # Conservative semantic proxy:
        # bearish current bar + strong close + meaningful lower-tail recovery
        # + prior bar itself bearish. This is audit-only, not production logic.
        absorption_like = (
            prior_bar_down
            and tail_ratio >= 0.25
            and float(row[COL_CLOSE_RATIO]) >= 0.70
            and close_recovery >= 0.70
        )

        forward_return = (future - current) / current

        events.append(
            {
                "symbol": symbol,
                "bar_index": index,
                "week": str(row[COL_WEEK]),
                "volume_percentile": float(row[COL_VOLUME_PERCENTILE]),
                "spread_percentile": float(row[COL_SPREAD_PERCENTILE]),
                "close_ratio": float(row[COL_CLOSE_RATIO]),
                "tail_ratio": tail_ratio,
                "close_recovery": close_recovery,
                "prior_bar_down": prior_bar_down,
                "absorption_like": absorption_like,
                "lower_tail": lower_tail,
                "upper_tail": upper_tail,
                "forward_return": forward_return,
                "outcome": outcome(forward_return),
            }
        )

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

    absorption_events = [e for e in all_events if e["absorption_like"]]

    print("STOPPING VOLUME CANDIDATE SEMANTIC AUDIT SUMMARY")
    print({
        "symbols_requested": len(symbols),
        "failures": failures,
        "candidate": summarize(all_events),
        "absorption_like": summarize(absorption_events),
    })

    print("STOPPING VOLUME CANDIDATE SEMANTIC AUDIT BY_SYMBOL")
    for symbol in symbols:
        symbol_events = [e for e in all_events if e["symbol"] == symbol]
        print({
            "symbol": symbol,
            "candidate": summarize(symbol_events),
            "absorption_like": summarize([e for e in symbol_events if e["absorption_like"]]),
        })

    print("STOPPING VOLUME CANDIDATE SEMANTIC EVENTS")
    for event in all_events:
        print(event)


if __name__ == "__main__":
    main()
