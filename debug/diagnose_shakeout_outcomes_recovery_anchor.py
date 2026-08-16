from __future__ import annotations

import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from engine.columns import COL_CLOSE, COL_DIRECTION, COL_SPREAD_CLASS, COL_VOLUME_CLASS, COL_WEEK
from evidence.campaign import has_selling_campaign, validate_shakeout
from evidence.demand import _collect_shakeout
from evidence.engine import EvidenceEngine
from evidence.rules import has_strong_spread, is_bearish_bar, is_very_high_volume, makes_lower_low
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
        if (
            direction == Direction.DOWN
            and volume >= VolumeClass.VERY_HIGH
            and spread >= SpreadClass.WIDE
        ):
            indices.append(index)
    return indices


def forward_outcome(weekly, index: int) -> tuple[str, float | None]:
    future_index = index + 8
    if future_index >= len(weekly):
        return "INSUFFICIENT_FORWARD_DATA", None

    current = float(weekly.iloc[index][COL_CLOSE])
    future = float(weekly.iloc[future_index][COL_CLOSE])
    forward_return = (future - current) / current

    if forward_return > 0.02:
        return "POSITIVE_8_BAR", forward_return
    if forward_return < -0.02:
        return "NEGATIVE_8_BAR", forward_return
    return "FLAT_8_BAR", forward_return


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
        engine.collect(
            metrics=replay,
            trend=trend,
            structural_swings=structural_swings,
        )
        ctx = engine._ctx
        if ctx is None:
            continue

        bar = ctx.current
        previous = ctx.previous
        if not (
            has_selling_campaign(ctx)
            and is_bearish_bar(bar)
            and has_strong_spread(bar)
            and is_very_high_volume(bar)
            and previous is not None
            and makes_lower_low(bar, previous)
        ):
            continue

        validation = validate_shakeout(
            metrics=metrics,
            shakeout_index=candidate_index,
        )
        if validation.recovery.recovery_index is None:
            continue

        recovery_index = int(validation.recovery.recovery_index)
        outcome, forward_return = forward_outcome(weekly, recovery_index)
        rows.append(
            {
                "symbol": symbol,
                "candidate_bar_index": candidate_index,
                "test_bar_index": validation.test.test_index,
                "recovery_bar_index": recovery_index,
                "candidate_week": str(metrics.iloc[candidate_index][COL_WEEK]),
                "recovery_week": str(metrics.iloc[recovery_index][COL_WEEK]),
                "outcome": outcome,
                "forward_return": forward_return,
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
                print({"symbol": symbol, "confirmed_shakeouts": len(symbol_events)})
            except Exception as exc:
                failures.append({"symbol": symbol, "error": repr(exc)})

    counts = Counter(row["outcome"] for row in events)
    decisive = counts["POSITIVE_8_BAR"] + counts["NEGATIVE_8_BAR"]
    positive_decisive_rate = (
        counts["POSITIVE_8_BAR"] / decisive
        if decisive
        else 0.0
    )

    print("SHAKEOUT RECOVERY-ANCHOR OUTCOME AUDIT SUMMARY")
    print(
        {
            "symbols_requested": len(symbols),
            "symbols_with_confirmed_shakeouts": len({row["symbol"] for row in events}),
            "confirmed_shakeouts": len(events),
            "outcome_classes": {
                "POSITIVE_8_BAR": counts["POSITIVE_8_BAR"],
                "NEGATIVE_8_BAR": counts["NEGATIVE_8_BAR"],
                "FLAT_8_BAR": counts["FLAT_8_BAR"],
                "INSUFFICIENT_FORWARD_DATA": counts["INSUFFICIENT_FORWARD_DATA"],
            },
            "decisive": decisive,
            "positive_decisive_rate": positive_decisive_rate,
            "failures": failures,
        }
    )

    print("SHAKEOUT RECOVERY-ANCHOR OUTCOME AUDIT BY_SYMBOL")
    for symbol in symbols:
        symbol_events = [row for row in events if row["symbol"] == symbol]
        symbol_counts = Counter(row["outcome"] for row in symbol_events)
        symbol_decisive = symbol_counts["POSITIVE_8_BAR"] + symbol_counts["NEGATIVE_8_BAR"]
        rate = (
            symbol_counts["POSITIVE_8_BAR"] / symbol_decisive
            if symbol_decisive
            else 0.0
        )
        print(
            {
                "symbol": symbol,
                "confirmed_shakeouts": len(symbol_events),
                "positive": symbol_counts["POSITIVE_8_BAR"],
                "negative": symbol_counts["NEGATIVE_8_BAR"],
                "flat": symbol_counts["FLAT_8_BAR"],
                "insufficient_forward_data": symbol_counts["INSUFFICIENT_FORWARD_DATA"],
                "decisive": symbol_decisive,
                "positive_decisive_rate": rate,
            }
        )

    print("SHAKEOUT RECOVERY-ANCHOR OUTCOME AUDIT EVENTS")
    for row in events:
        print(row)


if __name__ == "__main__":
    main()
