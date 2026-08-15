from __future__ import annotations

import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from engine.columns import COL_DIRECTION, COL_SPREAD_CLASS, COL_VOLUME_CLASS, COL_WEEK
from evidence.demand import _collect_test
from evidence.engine import EvidenceEngine
from metrics_engine import MetricsEngine
from models import Direction, EvidenceCode, SpreadClass, VolumeClass
from trend import TrendAnalyzer

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

CONFLICT_CODES = {
    EvidenceCode.BUYING_CLIMAX,
    EvidenceCode.UPTHRUST,
    EvidenceCode.INCREASING_SUPPLY,
    EvidenceCode.SUPPLY_COMING_IN,
    EvidenceCode.NO_DEMAND,
    EvidenceCode.STOPPING_VOLUME,
    EvidenceCode.NO_SUPPLY,
    EvidenceCode.SHAKEOUT,
}


def candidate_indices(metrics) -> list[int]:
    indices: list[int] = []
    for index in range(MIN_REPLAY_BARS, len(metrics)):
        row = metrics.iloc[index]
        if (
            Direction(int(row[COL_DIRECTION])) == Direction.DOWN
            and VolumeClass(int(row[COL_VOLUME_CLASS])) <= VolumeClass.LOW
            and SpreadClass(int(row[COL_SPREAD_CLASS])) <= SpreadClass.NARROW
        ):
            indices.append(index)
    return indices


def inspect_symbol(symbol: str) -> list[dict]:
    daily = download_data(symbol)
    weekly = daily_to_weekly(daily)
    metrics = MetricsEngine().calculate(weekly)
    rows: list[dict] = []

    candidates = candidate_indices(metrics)
    for index in candidates:
        replay = metrics.iloc[: index + 1].copy()
        trend = TrendAnalyzer().analyze(replay)
        structural_swings = tuple(trend.structure.structural_swings)

        engine = EvidenceEngine()
        result = engine.collect(
            metrics=replay,
            trend=trend,
            structural_swings=structural_swings,
        )
        ctx = engine._ctx
        if ctx is None:
            continue

        test_events = tuple(event for event in _collect_test(ctx) if event.bar_index == index)
        if not test_events:
            continue

        evidence = tuple(result.evidence)
        same_bar = tuple(
            sorted({
                item.code.value
                for item in evidence
                if item.bar_index == index and item.code in CONFLICT_CODES
            })
        )

        nearby: dict[str, tuple[str, ...]] = {}
        for offset in (-2, -1, 1, 2):
            neighbor = index + offset
            codes = tuple(sorted({
                item.code.value
                for item in evidence
                if item.bar_index == neighbor and item.code in CONFLICT_CODES
            }))
            if codes:
                nearby[str(offset)] = codes

        rows.append({
            "symbol": symbol,
            "bar_index": index,
            "week": str(metrics.iloc[index][COL_WEEK]),
            "test_events": len(test_events),
            "same_bar_conflicts": same_bar,
            "nearby_conflicts": nearby,
        })

    return rows


def main() -> None:
    symbols = tuple(sys.argv[1:]) or DEFAULT_SYMBOLS
    events: list[dict] = []
    failures: list[dict] = []

    with ThreadPoolExecutor(max_workers=min(4, len(symbols))) as executor:
        futures = {executor.submit(inspect_symbol, symbol): symbol for symbol in symbols}
        for future, symbol in futures.items():
            try:
                events.extend(future.result())
            except Exception as exc:
                failures.append({"symbol": symbol, "error": repr(exc)})

    same_bar_events = [row for row in events if row["same_bar_conflicts"]]
    nearby_events = [row for row in events if row["nearby_conflicts"]]
    same_bar_counts = Counter(
        code
        for row in events
        for code in row["same_bar_conflicts"]
    )

    print("TEST INTERACTION AUDIT SUMMARY")
    print({
        "symbols_requested": len(symbols),
        "symbols_with_events": len({row["symbol"] for row in events}),
        "test_events": len(events),
        "same_bar_conflict_events": len(same_bar_events),
        "nearby_conflict_events": len(nearby_events),
        "same_bar_conflict_codes": dict(sorted(same_bar_counts.items())),
        "failures": failures,
    })

    print("TEST INTERACTION AUDIT BY_SYMBOL")
    for symbol in symbols:
        subset = [row for row in events if row["symbol"] == symbol]
        print({
            "symbol": symbol,
            "events": len(subset),
            "same_bar_conflict_events": sum(bool(row["same_bar_conflicts"]) for row in subset),
            "nearby_conflict_events": sum(bool(row["nearby_conflicts"]) for row in subset),
        })

    print("TEST INTERACTION AUDIT EVENTS")
    for row in events:
        print(row)


if __name__ == "__main__":
    main()
