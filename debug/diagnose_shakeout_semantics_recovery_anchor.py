from __future__ import annotations

import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from engine.columns import (
    COL_DIRECTION,
    COL_LOW,
    COL_CLOSE,
    COL_SPREAD_CLASS,
    COL_VOLUME_CLASS,
    COL_WEEK,
)
from evidence.campaign import has_selling_campaign, validate_shakeout
from evidence.engine import EvidenceEngine
from evidence.rules import (
    has_strong_spread,
    is_bearish_bar,
    is_very_high_volume,
    makes_lower_low,
)
from metrics_engine import MetricsEngine
from models import Direction, SpreadClass, VolumeClass
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


def candidate_indices(metrics) -> list[int]:
    indices: list[int] = []
    for index in range(MIN_REPLAY_BARS, len(metrics)):
        row = metrics.iloc[index]
        direction = Direction(int(row[COL_DIRECTION]))
        volume = VolumeClass(int(row[COL_VOLUME_CLASS]))
        spread = SpreadClass(int(row[COL_SPREAD_CLASS]))
        if direction == Direction.DOWN and volume >= VolumeClass.VERY_HIGH and spread >= SpreadClass.WIDE:
            indices.append(index)
    return indices


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
        candidate_semantics = (
            has_selling_campaign(ctx)
            and is_bearish_bar(bar)
            and has_strong_spread(bar)
            and is_very_high_volume(bar)
            and makes_lower_low(bar, previous)
        )
        if not candidate_semantics:
            continue

        validation = validate_shakeout(metrics=metrics, shakeout_index=candidate_index)
        test_index = validation.test.test_index
        recovery_index = validation.recovery.recovery_index
        if test_index is None or recovery_index is None:
            continue

        test_row = metrics.iloc[test_index]
        recovery_row = metrics.iloc[recovery_index]
        candidate_row = metrics.iloc[candidate_index]

        rows.append(
            {
                "symbol": symbol,
                "candidate_bar_index": candidate_index,
                "test_bar_index": test_index,
                "recovery_bar_index": recovery_index,
                "candidate_week": str(candidate_row[COL_WEEK]),
                "test_week": str(test_row[COL_WEEK]),
                "recovery_week": str(recovery_row[COL_WEEK]),
                "test_delay": test_index - candidate_index,
                "recovery_delay_from_test": recovery_index - test_index,
                "candidate_selling_campaign": True,
                "candidate_bearish": True,
                "candidate_wide_spread": True,
                "candidate_very_high_volume": True,
                "candidate_lower_low": True,
                "test_volume_ratio": validation.test.volume_ratio,
                "test_spread_ratio": validation.test.spread_ratio,
                "test_distance_ratio": validation.test.distance_ratio,
                "test_close_position": validation.test.close_position,
                "recovery_spread_ratio": validation.recovery.spread_ratio,
                "recovery_volume_ratio": validation.recovery.volume_ratio,
                "recovery_close_position": validation.recovery.close_position,
                "recovery_close_change_spread_ratio": validation.recovery.close_change_spread_ratio,
                "recovery_low_clearance_ratio": validation.recovery.low_clearance_ratio,
            }
        )

    return rows


def main() -> None:
    symbols = tuple(sys.argv[1:]) or DEFAULT_SYMBOLS
    events: list[dict] = []
    failures: list[dict] = []

    with ThreadPoolExecutor(max_workers=min(4, len(symbols))) as executor:
        futures = {executor.submit(inspect_symbol, symbol): symbol for symbol in symbols}
        for future, symbol in futures.items():
            try:
                symbol_events = future.result()
                events.extend(symbol_events)
            except Exception as exc:
                failures.append({"symbol": symbol, "error": repr(exc)})

    test_close_positions = [e["test_close_position"] for e in events if e["test_close_position"] is not None]
    higher_quality_tests = sum(
        e["test_volume_ratio"] is not None and e["test_volume_ratio"] <= 0.75
        and e["test_spread_ratio"] is not None and e["test_spread_ratio"] <= 0.75
        for e in events
    )
    recovery_strong_close = sum(
        e["recovery_close_position"] is not None and e["recovery_close_position"] >= 3
        for e in events
    )

    avg_test_delay = (
        sum(e["test_delay"] for e in events) / len(events)
        if events else 0.0
    )
    avg_recovery_delay = (
        sum(e["recovery_delay_from_test"] for e in events) / len(events)
        if events else 0.0
    )

    print("SHAKEOUT RECOVERY-ANCHOR SEMANTIC QUALITY AUDIT SUMMARY")
    print(
        {
            "symbols_requested": len(symbols),
            "symbols_with_confirmed_shakeouts": len({e["symbol"] for e in events}),
            "confirmed_shakeouts": len(events),
            "candidate_semantics_pass": len(events),
            "valid_test_count": len(events),
            "valid_recovery_count": len(events),
            "avg_test_delay": avg_test_delay,
            "avg_recovery_delay_from_test": avg_recovery_delay,
            "test_volume_spread_both_le_0.75": higher_quality_tests,
            "recovery_close_position_ge_3": recovery_strong_close,
            "failures": failures,
        }
    )

    print("SHAKEOUT RECOVERY-ANCHOR SEMANTIC QUALITY AUDIT BY_SYMBOL")
    for symbol in symbols:
        symbol_events = [e for e in events if e["symbol"] == symbol]
        print(
            {
                "symbol": symbol,
                "confirmed_shakeouts": len(symbol_events),
                "test_volume_spread_both_le_0.75": sum(
                    e["test_volume_ratio"] is not None and e["test_volume_ratio"] <= 0.75
                    and e["test_spread_ratio"] is not None and e["test_spread_ratio"] <= 0.75
                    for e in symbol_events
                ),
                "recovery_close_position_ge_3": sum(
                    e["recovery_close_position"] is not None and e["recovery_close_position"] >= 3
                    for e in symbol_events
                ),
            }
        )

    print("SHAKEOUT RECOVERY-ANCHOR SEMANTIC QUALITY AUDIT EVENTS")
    for event in events:
        print(event)


if __name__ == "__main__":
    main()
