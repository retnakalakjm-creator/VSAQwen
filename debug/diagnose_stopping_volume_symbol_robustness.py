"""Per-symbol robustness audit for candidate Stopping Volume thresholds.

Read-only diagnostic. It does not modify production detectors, weights, or
EvidenceEngine registration.
"""
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from engine.columns import COL_CLOSE, COL_WEEK, COL_SPREAD_PERCENTILE, COL_VOLUME_PERCENTILE, COL_CLOSE_RATIO
from metrics_engine import MetricsEngine

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

THRESHOLD_SETS = (
    ("BASELINE_85_70_060", 85.0, 70.0, 0.60),
    ("CANDIDATE_A_80_60_055", 80.0, 60.0, 0.55),
    ("CANDIDATE_B_85_60_055", 85.0, 60.0, 0.55),
    ("CANDIDATE_C_90_60_055", 90.0, 60.0, 0.55),
    ("CANDIDATE_D_85_60_060", 85.0, 60.0, 0.60),
)


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


def inspect_symbol(symbol: str) -> dict[str, list[dict]]:
    daily = download_data(symbol)
    metrics = MetricsEngine().calculate(daily_to_weekly(daily))
    results = {name: [] for name, *_ in THRESHOLD_SETS}

    for index in range(MIN_REPLAY_BARS, len(metrics)):
        future_index = index + FORWARD_HORIZON
        if future_index >= len(metrics):
            break

        row = metrics.iloc[index]
        volume_percentile = float(row[COL_VOLUME_PERCENTILE])
        spread_percentile = float(row[COL_SPREAD_PERCENTILE])
        close_ratio = float(row[COL_CLOSE_RATIO])
        current = float(row[COL_CLOSE])
        future = float(metrics.iloc[future_index][COL_CLOSE])

        if current != current or future != future or current == 0.0:
            continue

        forward_return = (future - current) / current
        outcome = (
            "POSITIVE_8_BAR" if forward_return > OUTCOME_THRESHOLD
            else "NEGATIVE_8_BAR" if forward_return < -OUTCOME_THRESHOLD
            else "FLAT_8_BAR"
        )

        for name, volume_min, spread_min, close_min in THRESHOLD_SETS:
            if (
                volume_percentile >= volume_min
                and spread_percentile >= spread_min
                and close_ratio >= close_min
            ):
                results[name].append({
                    "symbol": symbol,
                    "bar_index": index,
                    "week": str(row[COL_WEEK]),
                    "forward_return": forward_return,
                    "outcome": outcome,
                })

    return results


def main() -> None:
    symbols = tuple(sys.argv[1:]) or DEFAULT_SYMBOLS
    by_threshold: dict[str, list[dict]] = {
        name: [] for name, *_ in THRESHOLD_SETS
    }
    failures: list[dict] = []

    with ThreadPoolExecutor(max_workers=min(4, len(symbols))) as executor:
        futures = {
            executor.submit(inspect_symbol, symbol): symbol
            for symbol in symbols
        }
        for future, symbol in futures.items():
            try:
                results = future.result()
                for name, events in results.items():
                    by_threshold[name].extend(events)
            except Exception as exc:
                failures.append({"symbol": symbol, "error": repr(exc)})

    print("STOPPING VOLUME SYMBOL ROBUSTNESS SUMMARY")
    print({
        "symbols_requested": len(symbols),
        "failures": failures,
        "threshold_sets": {
            name: _summarize(events)
            for name, events in by_threshold.items()
        },
    })

    print("STOPPING VOLUME SYMBOL ROBUSTNESS BY THRESHOLD")
    for name, events in by_threshold.items():
        by_symbol = {}
        for symbol in symbols:
            symbol_events = [e for e in events if e["symbol"] == symbol]
            by_symbol[symbol] = _summarize(symbol_events)
        print({"threshold_set": name, "by_symbol": by_symbol})


if __name__ == "__main__":
    main()
