from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data import daily_to_weekly, download_data
from engine.columns import COL_CLOSE, COL_WEEK
from evidence.demand import _collect_no_supply, _collect_stopping_volume, _collect_shakeout
from evidence.engine import EvidenceEngine
from evidence.supply import collect_supply
from metrics_engine import MetricsEngine
from trend import TrendAnalyzer


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

PRIMARY_CODES = {"stopping_volume", "shakeout", "spring"}
SUPPORT_CODES = {"no_demand", "increasing_supply", "supply_coming_in"}


def build_point_in_time_contexts(metrics):
    contexts: dict[int, object] = {}
    for index in range(MIN_REPLAY_BARS, len(metrics)):
        replay = metrics.iloc[: index + 1]
        trend = TrendAnalyzer().analyze(replay)
        engine = EvidenceEngine()
        engine._reset(
            metrics=replay,
            trend=trend,
            structural_swings=tuple(trend.structure.structural_swings),
            validation_metrics=replay,
        )
        assert engine._ctx is not None
        contexts[index] = engine._ctx
    return contexts


def bar_evidence(ctx):
    evidence = []
    evidence.extend(_collect_stopping_volume(ctx))
    evidence.extend(_collect_no_supply(ctx))
    try:
        evidence.extend(collect_supply(ctx))
    except TypeError:
        pass
    return tuple(evidence)


def outcome(metrics, bar_index: int) -> str:
    future = bar_index + FORWARD_HORIZON
    if future >= len(metrics):
        return "INSUFFICIENT_FORWARD_DATA"
    current = float(metrics.iloc[bar_index][COL_CLOSE])
    future_close = float(metrics.iloc[future][COL_CLOSE])
    if future_close > current:
        return "POSITIVE_8_BAR"
    if future_close < current:
        return "NEGATIVE_8_BAR"
    return "FLAT_8_BAR"


def anchor_population(symbol: str):
    daily = download_data(symbol)
    weekly = daily_to_weekly(daily)
    metrics = MetricsEngine().calculate(weekly)
    contexts = build_point_in_time_contexts(metrics)

    rows = []
    for bar_index, ctx in contexts.items():
        evidence = bar_evidence(ctx)
        primary = tuple(e for e in evidence if e.code.value in PRIMARY_CODES)
        no_supply = tuple(e for e in evidence if e.code.value == "no_supply")
        if not primary:
            continue

        codes = tuple(sorted({e.code.value for e in evidence}))
        rows.append(
            {
                "symbol": symbol,
                "bar_index": bar_index,
                "week": str(metrics.iloc[bar_index][COL_WEEK]),
                "outcome": outcome(metrics, bar_index),
                "primary_codes": tuple(sorted({e.code.value for e in primary})),
                "all_codes": codes,
                "has_no_supply": bool(no_supply),
                "trend_direction": ctx.trend.direction.value,
                "trend_state": ctx.trend.state.value,
            }
        )
    return rows


def summarize(rows):
    counts = Counter(r["outcome"] for r in rows)
    decisive = counts["POSITIVE_8_BAR"] + counts["NEGATIVE_8_BAR"]
    positive_rate = counts["POSITIVE_8_BAR"] / decisive if decisive else 0.0
    return {
        "events": len(rows),
        "positive": counts["POSITIVE_8_BAR"],
        "negative": counts["NEGATIVE_8_BAR"],
        "flat": counts["FLAT_8_BAR"],
        "insufficient_forward_data": counts["INSUFFICIENT_FORWARD_DATA"],
        "decisive": decisive,
        "positive_decisive_rate": positive_rate,
    }


def pair_value(rows):
    with_event = [r for r in rows if r["has_no_supply"]]
    without_event = [r for r in rows if not r["has_no_supply"]]
    return {
        "with_no_supply": summarize(with_event),
        "without_no_supply": summarize(without_event),
    }


def main() -> None:
    all_rows = []
    failures = []
    by_symbol: dict[str, list[dict]] = defaultdict(list)

    for symbol in SYMBOLS:
        try:
            rows = anchor_population(symbol)
            all_rows.extend(rows)
            by_symbol[symbol].extend(rows)
        except Exception as exc:
            failures.append({"symbol": symbol, "error": repr(exc)})

    with_event = [r for r in all_rows if r["has_no_supply"]]
    without_event = [r for r in all_rows if not r["has_no_supply"]]

    print("NO SUPPLY SUPPORT-VALUE AUDIT SUMMARY")
    print(
        {
            "symbols_requested": len(SYMBOLS),
            "symbols_with_primary_events": len({r["symbol"] for r in all_rows}),
            "anchor_events": len(all_rows),
            "with_no_supply": len(with_event),
            "without_no_supply": len(without_event),
            "failures": failures,
        }
    )

    print("NO SUPPLY SUPPORT-VALUE COMPARISON")
    print(pair_value(all_rows))

    print("NO SUPPLY SUPPORT-VALUE BY_PRIMARY_EVENT")
    by_primary: dict[str, list[dict]] = defaultdict(list)
    for row in all_rows:
        for code in row["primary_codes"]:
            by_primary[code].append(row)
    for code, rows in sorted(by_primary.items()):
        print(code)
        print(pair_value(rows))

    print("NO SUPPLY SUPPORT-VALUE BY_SYMBOL")
    for symbol in SYMBOLS:
        print(symbol)
        print(pair_value(by_symbol[symbol]))

    print("NO SUPPLY SUPPORT-VALUE INTERACTIONS")
    interactions = Counter()
    for row in all_rows:
        support = tuple(code for code in row["all_codes"] if code in SUPPORT_CODES)
        if support:
            interactions[(row["has_no_supply"], support, row["outcome"])] += 1
    for key, value in sorted(interactions.items(), key=lambda item: str(item[0])):
        print({"key": key, "count": value})


if __name__ == "__main__":
    main()
