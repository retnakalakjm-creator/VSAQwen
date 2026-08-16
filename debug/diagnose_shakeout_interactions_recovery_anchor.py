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
from evidence.campaign import has_selling_campaign, validate_shakeout
from evidence.engine import EvidenceEngine
from evidence.rules import has_strong_spread, is_bearish_bar, is_very_high_volume, makes_lower_low
from metrics_engine import MetricsEngine
from models import Direction, EvidenceCode, SpreadClass, VolumeClass
from trend import TrendAnalyzer

DEFAULT_SYMBOLS = (
    "BHARTIARTL.NS", "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "INFY.NS", "TCS.NS", "SBIN.NS", "LT.NS",
)
MIN_REPLAY_BARS = 20
WINDOW = 2
CONFLICT_CODES = frozenset({
    EvidenceCode.BUYING_CLIMAX,
    EvidenceCode.UPTHRUST,
    EvidenceCode.INCREASING_SUPPLY,
    EvidenceCode.SUPPLY_COMING_IN,
    EvidenceCode.HIDDEN_SUPPLY,
    EvidenceCode.SUPPLY_ABSORPTION,
    EvidenceCode.NO_DEMAND,
})


def candidate_indices(metrics) -> list[int]:
    out: list[int] = []
    for index in range(MIN_REPLAY_BARS, len(metrics)):
        row = metrics.iloc[index]
        if (
            Direction(int(row[COL_DIRECTION])) == Direction.DOWN
            and VolumeClass(int(row[COL_VOLUME_CLASS])) >= VolumeClass.VERY_HIGH
            and SpreadClass(int(row[COL_SPREAD_CLASS])) >= SpreadClass.WIDE
        ):
            out.append(index)
    return out


def inspect_symbol(symbol: str) -> list[dict]:
    daily = download_data(symbol)
    weekly = daily_to_weekly(daily)
    metrics = MetricsEngine().calculate(weekly)
    rows: list[dict] = []

    for candidate_index in candidate_indices(metrics):
        replay = metrics.iloc[: candidate_index + 1].copy()
        trend = TrendAnalyzer().analyze(replay)
        structural_swings = tuple(trend.structure.structural_swings)
        engine = EvidenceEngine()
        engine.collect(metrics=replay, trend=trend, structural_swings=structural_swings)
        ctx = engine._ctx
        if ctx is None or ctx.previous is None:
            continue
        bar = ctx.current
        previous = ctx.previous
        if not (
            has_selling_campaign(ctx)
            and is_bearish_bar(bar)
            and has_strong_spread(bar)
            and is_very_high_volume(bar)
            and makes_lower_low(bar, previous)
        ):
            continue

        validation = validate_shakeout(metrics=metrics, shakeout_index=candidate_index)
        recovery_index = validation.recovery.recovery_index
        test_index = validation.test.test_index
        if test_index is None or recovery_index is None:
            continue

        start = max(0, int(recovery_index) - WINDOW)
        end = min(len(metrics), int(recovery_index) + WINDOW + 1)
        nearby_conflicts: list[str] = []
        same_bar_conflicts: list[str] = []

        # Rebuild production-style evidence prefix at each bar in the local window.
        for inspect_index in range(start, end):
            local_replay = metrics.iloc[: inspect_index + 1].copy()
            local_trend = TrendAnalyzer().analyze(local_replay)
            local_swings = tuple(local_trend.structure.structural_swings)
            local_result = EvidenceEngine().collect(
                metrics=local_replay,
                trend=local_trend,
                structural_swings=local_swings,
            )
            for item in local_result.evidence:
                if item.code not in CONFLICT_CODES:
                    continue
                if item.bar_index != inspect_index:
                    continue
                if inspect_index == recovery_index:
                    same_bar_conflicts.append(str(item.code))
                else:
                    nearby_conflicts.append(str(item.code))

        rows.append({
            "symbol": symbol,
            "candidate_bar_index": candidate_index,
            "test_bar_index": test_index,
            "recovery_bar_index": recovery_index,
            "recovery_week": str(metrics.iloc[recovery_index][COL_WEEK]),
            "same_bar_conflicts": sorted(set(same_bar_conflicts)),
            "nearby_conflicts": sorted(set(nearby_conflicts)),
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

    same_bar = sum(bool(e["same_bar_conflicts"]) for e in events)
    nearby = sum(bool(e["nearby_conflicts"]) for e in events)
    conflict_counts = Counter()
    for e in events:
        for code in set(e["same_bar_conflicts"] + e["nearby_conflicts"]):
            conflict_counts[code] += 1

    print("SHAKEOUT RECOVERY-ANCHOR INTERACTION AUDIT SUMMARY")
    print({
        "symbols_requested": len(symbols),
        "symbols_with_confirmed_shakeouts": len({e["symbol"] for e in events}),
        "confirmed_shakeouts": len(events),
        "same_bar_conflict_events": same_bar,
        "nearby_conflict_events": nearby,
        "conflict_event_counts": dict(sorted(conflict_counts.items())),
        "failures": failures,
    })

    print("SHAKEOUT RECOVERY-ANCHOR INTERACTION AUDIT BY_SYMBOL")
    for symbol in symbols:
        se = [e for e in events if e["symbol"] == symbol]
        print({
            "symbol": symbol,
            "confirmed_shakeouts": len(se),
            "same_bar_conflict_events": sum(bool(e["same_bar_conflicts"]) for e in se),
            "nearby_conflict_events": sum(bool(e["nearby_conflicts"]) for e in se),
        })

    print("SHAKEOUT RECOVERY-ANCHOR INTERACTION AUDIT EVENTS")
    for e in events:
        print(e)


if __name__ == "__main__":
    main()
