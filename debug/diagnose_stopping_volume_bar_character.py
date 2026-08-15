"""Audit the actual bar character of current Stopping Volume detections.

Read-only diagnostic. It does not modify production detectors, weights, or
EvidenceEngine registration.
"""
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from collections import defaultdict

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
    COL_PRICE_CHANGE_PCT,
    COL_SPREAD,
    COL_VOLUME_PERCENTILE,
    COL_SPREAD_PERCENTILE,
    COL_WEEK,
)
from metrics_engine import MetricsEngine
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


def _outcome(forward_return: float | None) -> str:
    if forward_return is None:
        return "INSUFFICIENT_FORWARD_DATA"
    if forward_return > OUTCOME_THRESHOLD:
        return "POSITIVE_8_BAR"
    if forward_return < -OUTCOME_THRESHOLD:
        return "NEGATIVE_8_BAR"
    return "FLAT_8_BAR"


def _summarize(events: list[dict]) -> dict:
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


def _bucket_direction(value: str) -> str:
    return str(value).split(".")[-1].upper()


def _bucket_close(value: float) -> str:
    if value < 0.30:
        return "LOW"
    if value < 0.50:
        return "LOWER_MID"
    if value < 0.70:
        return "UPPER_MID"
    return "HIGH"


def _bucket_tail_ratio(row) -> str:
    spread = float(row[COL_SPREAD])
    if spread <= 0:
        return "ZERO_SPREAD"
    tail_ratio = (float(row["low"]) and (float(row[COL_CLOSE]) - float(row[COL_LOW])))
    lower_tail = float(row.get("lower_shadow", 0.0))
    ratio = lower_tail / spread
    if ratio < 0.15:
        return "SMALL"
    if ratio < 0.30:
        return "MEDIUM"
    return "LARGE"


def inspect_symbol(symbol: str) -> list[dict]:
    daily = download_data(symbol)
    metrics = MetricsEngine().calculate(daily_to_weekly(daily))
    rule = StoppingVolumeRule()
    events: list[dict] = []

    for index in range(MIN_REPLAY_BARS, len(metrics)):
        future_index = index + FORWARD_HORIZON
        if future_index >= len(metrics):
            break

        row = metrics.iloc[index]
        ctx = type(
            "StoppingVolumeAuditContext",
            (),
            {
                "metrics": metrics.iloc[: index + 1],
                "swing": type("Swing", (), {"metrics_index": index})(),
                "history": type("History", (), {"has_previous": index > 0})(),
            },
        )()

        if not rule._detect(ctx):
            continue

        current = float(row[COL_CLOSE])
        future = float(metrics.iloc[future_index][COL_CLOSE])
        if current != current or future != future or current == 0.0:
            continue

        events.append({
            "symbol": symbol,
            "bar_index": index,
            "week": str(row[COL_WEEK]),
            "direction": _bucket_direction(row[COL_DIRECTION]),
            "close_bucket": _bucket_close(float(row[COL_CLOSE_RATIO])),
            "lower_tail_bucket": _bucket_tail_ratio(row),
            "price_change_pct": float(row[COL_PRICE_CHANGE_PCT]),
            "volume_percentile": float(row[COL_VOLUME_PERCENTILE]),
            "spread_percentile": float(row[COL_SPREAD_PERCENTILE]),
            "forward_return": (future - current) / current,
            "outcome": _outcome((future - current) / current),
        })

    return events


def _cohort(events: list[dict], key: str, value: str) -> list[dict]:
    return [e for e in events if e[key] == value]


def main() -> None:
    symbols = tuple(sys.argv[1:]) or DEFAULT_SYMBOLS
    all_events: list[dict] = []
    failures: list[dict] = []

    with ThreadPoolExecutor(max_workers=min(4, len(symbols))) as executor:
        futures = {
            executor.submit(inspect_symbol, symbol): symbol
            for symbol in symbols
        }
        for future, symbol in futures.items():
            try:
                events = future.result()
                all_events.extend(events)
                print({"symbol": symbol, "events": len(events)})
            except Exception as exc:
                failures.append({"symbol": symbol, "error": repr(exc)})
                print(f"FAILED {symbol}: {exc!r}")

    by_direction = {
        direction: _summarize(_cohort(all_events, "direction", direction))
        for direction in sorted({e["direction"] for e in all_events})
    }
    by_close = {
        bucket: _summarize(_cohort(all_events, "close_bucket", bucket))
        for bucket in ("LOW", "LOWER_MID", "UPPER_MID", "HIGH")
    }
    by_tail = {
        bucket: _summarize(_cohort(all_events, "lower_tail_bucket", bucket))
        for bucket in ("SMALL", "MEDIUM", "LARGE", "ZERO_SPREAD")
        if any(e["lower_tail_bucket"] == bucket for e in all_events)
    }

    print("STOPPING VOLUME BAR CHARACTER AUDIT SUMMARY")
    print({
        "symbols_requested": len(symbols),
        "events": len(all_events),
        "failures": failures,
        "overall": _summarize(all_events),
        "by_direction": by_direction,
        "by_close_bucket": by_close,
        "by_lower_tail_bucket": by_tail,
        "mean_price_change_pct": (
            sum(e["price_change_pct"] for e in all_events) / len(all_events)
            if all_events else None
        ),
    })

    print("STOPPING VOLUME BAR CHARACTER AUDIT EVENTS")
    for event in all_events:
        print(event)


if __name__ == "__main__":
    main()
