"""Focused interaction audit for DEMAND_COMING_IN.

Analysis-only. Tests the main nearby supply combinations identified by the
first interaction audit and reports symbol-level stability. No production
logic, weights, or actionability are changed.
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
from engine.columns import COL_CLOSE, COL_CLOSE_POSITION, COL_DIRECTION, COL_SPREAD_CLASS, COL_VOLUME_CLASS
from evidence.engine import EvidenceEngine
from evidence.supply import collect_supply
from metrics_engine import MetricsEngine
from models import Direction, EvidenceCode, SpreadClass, VolumeClass
from trend import TrendAnalyzer

SYMBOLS = (
    "BHARTIARTL.NS", "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "INFY.NS", "TCS.NS", "SBIN.NS", "LT.NS",
)
MIN_REPLAY_BARS = 20
FORWARD_HORIZON = 8
NEARBY_WINDOW = 5

FOCUS_GROUPS = {
    "INCREASING_SUPPLY": {EvidenceCode.INCREASING_SUPPLY},
    "BUYING_CLIMAX": {EvidenceCode.BUYING_CLIMAX},
    "UPTHRUST": {EvidenceCode.UPTHRUST},
    "BUYING_CLIMAX_OR_UPTHRUST": {EvidenceCode.BUYING_CLIMAX, EvidenceCode.UPTHRUST},
    "INCREASING_SUPPLY_AND_CLIMAX_TRAP": {
        EvidenceCode.INCREASING_SUPPLY, EvidenceCode.BUYING_CLIMAX, EvidenceCode.UPTHRUST,
    },
    "SUPPLY_COMING_IN": {EvidenceCode.SUPPLY_COMING_IN},
}


def candidate(row) -> bool:
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
        "positive_decisive_rate": counts["POSITIVE_8_BAR"] / decisive if decisive else 0.0,
    }


def inspect_symbol(symbol: str) -> list[dict]:
    metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
    rows: list[dict] = []

    for index in range(MIN_REPLAY_BARS, len(metrics)):
        if not candidate(metrics.iloc[index]):
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

        by_bar: dict[int, set[EvidenceCode]] = defaultdict(set)
        for item in collect_supply(engine._ctx):
            by_bar[item.bar_index].add(item.code)

        nearby: set[EvidenceCode] = set()
        for bar_index, codes in by_bar.items():
            distance = abs(bar_index - index)
            if 1 <= distance <= NEARBY_WINDOW:
                nearby.update(codes)

        rows.append({
            "symbol": symbol,
            "bar_index": index,
            "outcome": event_outcome,
            "nearby": nearby,
        })

    return rows


def group(rows: list[dict], name: str, codes: set[EvidenceCode]) -> list[dict]:
    selected = []
    for row in rows:
        nearby = row["nearby"]
        if name == "INCREASING_SUPPLY":
            matched = EvidenceCode.INCREASING_SUPPLY in nearby
        elif name == "BUYING_CLIMAX":
            matched = EvidenceCode.BUYING_CLIMAX in nearby
        elif name == "UPTHRUST":
            matched = EvidenceCode.UPTHRUST in nearby
        elif name == "BUYING_CLIMAX_OR_UPTHRUST":
            matched = bool(nearby & codes)
        elif name == "INCREASING_SUPPLY_AND_CLIMAX_TRAP":
            matched = (
                EvidenceCode.INCREASING_SUPPLY in nearby
                and bool(nearby & {EvidenceCode.BUYING_CLIMAX, EvidenceCode.UPTHRUST})
            )
        elif name == "SUPPLY_COMING_IN":
            matched = EvidenceCode.SUPPLY_COMING_IN in nearby
        else:
            matched = False
        if matched:
            selected.append(row)
    return selected


def main() -> None:
    symbols = tuple(sys.argv[1:]) or SYMBOLS
    all_rows: list[dict] = []
    by_symbol: dict[str, list[dict]] = {}
    failures: list[dict[str, str]] = []

    with ThreadPoolExecutor(max_workers=min(4, len(symbols))) as executor:
        futures = {executor.submit(inspect_symbol, symbol): symbol for symbol in symbols}
        for future, symbol in futures.items():
            try:
                rows = future.result()
                by_symbol[symbol] = rows
                all_rows.extend(rows)
            except Exception as exc:  # noqa: BLE001
                failures.append({"symbol": symbol, "error": repr(exc)})
                by_symbol[symbol] = []

    print("DEMAND COMING IN FOCUSED INTERACTION AUDIT")
    print({"events": len(all_rows), "symbols": len({r['symbol'] for r in all_rows}), "failures": failures})

    for name, codes in FOCUS_GROUPS.items():
        selected = group(all_rows, name, codes)
        absent = [row for row in all_rows if row not in selected]
        print(name, {
            "present": summarize(selected),
            "absent": summarize(absent),
        })

    print("DEMAND COMING IN FOCUSED INTERACTION BY_SYMBOL")
    for symbol in symbols:
        rows = by_symbol[symbol]
        output = {"events": len(rows)}
        for name, codes in FOCUS_GROUPS.items():
            selected = group(rows, name, codes)
            output[name] = summarize(selected)
        print(symbol, output)


if __name__ == "__main__":
    main()
