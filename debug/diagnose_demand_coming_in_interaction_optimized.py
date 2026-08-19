"""Optimized interaction audit for DEMAND_COMING_IN.

Analysis-only. Reuses the exact 281-candidate definition from the semantic audit
and replays supply evidence point-in-time through the production context path.
It does not modify detector logic, weights, aggregation, or scanner behavior.
"""
from __future__ import annotations

import sys
from collections import Counter, defaultdict
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
from evidence.engine import EvidenceEngine
from evidence.supply import collect_supply
from metrics_engine import MetricsEngine
from models import Direction, EvidenceCode, SpreadClass, VolumeClass
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
NEARBY_WINDOW = 5

SUPPLY_CODES = (
    EvidenceCode.BUYING_CLIMAX,
    EvidenceCode.SUPPLY_COMING_IN,
    EvidenceCode.HIDDEN_SUPPLY,
    EvidenceCode.INCREASING_SUPPLY,
    EvidenceCode.SUPPLY_DRYING_UP,
    EvidenceCode.UPTHRUST,
    EvidenceCode.NO_DEMAND,
)

DIRECT_CONTRADICTION_CODES = {
    EvidenceCode.BUYING_CLIMAX,
    EvidenceCode.SUPPLY_COMING_IN,
    EvidenceCode.INCREASING_SUPPLY,
    EvidenceCode.UPTHRUST,
    EvidenceCode.NO_DEMAND,
}


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
        "positive_decisive_rate": (
            counts["POSITIVE_8_BAR"] / decisive if decisive else 0.0
        ),
    }


def inspect_symbol(symbol: str) -> list[dict]:
    metrics = MetricsEngine().calculate(
        daily_to_weekly(download_data(symbol))
    )
    events: list[dict] = []

    for index in range(MIN_REPLAY_BARS, len(metrics)):
        row = metrics.iloc[index]
        if not is_candidate(row):
            continue

        event_outcome = outcome(metrics, index)
        if event_outcome is None:
            continue

        replay = metrics.iloc[: index + 1]
        trend = TrendAnalyzer().analyze(replay)
        engine = EvidenceEngine()
        engine.collect(
            metrics=replay,
            trend=trend,
            structural_swings=tuple(trend.structure.structural_swings),
            validation_metrics=replay,
        )

        assert engine._ctx is not None
        supply = collect_supply(engine._ctx)

        by_bar: dict[int, set[EvidenceCode]] = defaultdict(set)
        for item in supply:
            if item.code in SUPPLY_CODES:
                by_bar[item.bar_index].add(item.code)

        same_bar = tuple(sorted(
            (code.name for code in by_bar.get(index, set())),
        ))
        nearby: set[EvidenceCode] = set()
        for bar_index, codes in by_bar.items():
            distance = abs(bar_index - index)
            if 1 <= distance <= NEARBY_WINDOW:
                nearby.update(codes)

        same_direct = bool(
            set(by_bar.get(index, set())) & DIRECT_CONTRADICTION_CODES
        )
        nearby_direct = bool(nearby & DIRECT_CONTRADICTION_CODES)

        events.append({
            "symbol": symbol,
            "bar_index": index,
            "week": str(row[COL_WEEK]),
            "outcome": event_outcome,
            "same_bar": same_bar,
            "nearby": tuple(sorted(code.name for code in nearby)),
            "same_direct_conflict": same_direct,
            "nearby_direct_conflict": nearby_direct,
        })

    return events


def group_rows(rows: list[dict], field: str) -> dict[tuple[str, ...], dict]:
    groups: dict[tuple[str, ...], list[dict]] = defaultdict(list)
    for row in rows:
        groups[row[field]].append(row)
    return {key: summarize(value) for key, value in groups.items()}


def boolean_group(rows: list[dict], field: str) -> dict[str, dict]:
    return {
        "present": summarize([row for row in rows if row[field]]),
        "absent": summarize([row for row in rows if not row[field]]),
    }


def interaction_code_summary(rows: list[dict], field: str) -> dict[str, dict]:
    summary: dict[str, dict] = {}
    for code in EvidenceCode:
        if code not in SUPPLY_CODES:
            continue
        present = [row for row in rows if code.name in row[field]]
        if present:
            summary[code.name] = summarize(present)
    return summary


def main() -> None:
    symbols = tuple(sys.argv[1:]) or SYMBOLS
    all_rows: list[dict] = []
    failures: list[dict[str, str]] = []

    with ThreadPoolExecutor(max_workers=min(4, len(symbols))) as executor:
        futures = {executor.submit(inspect_symbol, symbol): symbol for symbol in symbols}
        for future, symbol in futures.items():
            try:
                all_rows.extend(future.result())
            except Exception as exc:  # noqa: BLE001
                failures.append({"symbol": symbol, "error": repr(exc)})

    baseline = summarize(all_rows)
    same_groups = group_rows(all_rows, "same_bar")
    nearby_groups = group_rows(all_rows, "nearby")

    print("DEMAND COMING IN INTERACTION AUDIT SUMMARY")
    print({
        "symbols_requested": len(symbols),
        "symbols_with_events": len({row["symbol"] for row in all_rows}),
        "candidate_events": len(all_rows),
        "nearby_window_bars": NEARBY_WINDOW,
        "baseline": baseline,
        "failures": failures,
    })

    print("DEMAND COMING IN SAME_BAR_INTERACTIONS")
    for key, value in sorted(same_groups.items(), key=lambda item: (-item[1]["events"], item[0])):
        print({"supply_codes": key, **value})

    print("DEMAND COMING IN NEARBY_INTERACTIONS")
    for key, value in sorted(nearby_groups.items(), key=lambda item: (-item[1]["events"], item[0])):
        print({"supply_codes": key, **value})

    print("DEMAND COMING IN DIRECT_CONTRADICTION_AUDIT")
    print({
        "same_bar": boolean_group(all_rows, "same_direct_conflict"),
        "nearby": boolean_group(all_rows, "nearby_direct_conflict"),
    })

    print("DEMAND COMING IN SAME_BAR_CODE_OUTCOMES")
    for code, value in sorted(interaction_code_summary(all_rows, "same_bar").items()):
        print(code, value)

    print("DEMAND COMING IN NEARBY_CODE_OUTCOMES")
    for code, value in sorted(interaction_code_summary(all_rows, "nearby").items()):
        print(code, value)

    print("DEMAND COMING IN INTERACTION BY_SYMBOL")
    for symbol in symbols:
        symbol_rows = [row for row in all_rows if row["symbol"] == symbol]
        print(symbol, {
            "baseline": summarize(symbol_rows),
            "same_bar_direct": boolean_group(symbol_rows, "same_direct_conflict"),
            "nearby_direct": boolean_group(symbol_rows, "nearby_direct_conflict"),
        })


if __name__ == "__main__":
    main()
