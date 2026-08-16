from __future__ import annotations

import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from engine.columns import COL_CLOSE, COL_DIRECTION, COL_SPREAD_CLASS, COL_VOLUME_CLASS
from evidence.campaign import has_selling_campaign, validate_shakeout
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
        if direction == Direction.DOWN and volume >= VolumeClass.VERY_HIGH and spread >= SpreadClass.WIDE:
            indices.append(index)
    return indices


def forward_outcome(weekly, index: int) -> tuple[str, float | None]:
    future_index = index + 8
    if future_index >= len(weekly):
        return "INSUFFICIENT_FORWARD_DATA", None
    current = float(weekly.iloc[index][COL_CLOSE])
    future = float(weekly.iloc[future_index][COL_CLOSE])
    change = (future - current) / current
    if change > 0.02:
        return "POSITIVE_8_BAR", change
    if change < -0.02:
        return "NEGATIVE_8_BAR", change
    return "FLAT_8_BAR", change


def inspect_symbol(symbol: str) -> list[dict]:
    daily = download_data(symbol)
    weekly = daily_to_weekly(daily)
    metrics = MetricsEngine().calculate(weekly)
    events: list[dict] = []
    for candidate_index in candidate_indices(metrics):
        replay = metrics.iloc[: candidate_index + 1].copy()
        trend = TrendAnalyzer().analyze(replay)
        swings = tuple(trend.structure.structural_swings)
        engine = EvidenceEngine()
        engine.collect(metrics=replay, trend=trend, structural_swings=swings)
        ctx = engine._ctx
        if ctx is None or ctx.previous is None:
            continue
        bar = ctx.current
        previous = ctx.previous
        if not (has_selling_campaign(ctx) and is_bearish_bar(bar) and has_strong_spread(bar)
                and is_very_high_volume(bar) and makes_lower_low(bar, previous)):
            continue
        validation = validate_shakeout(metrics=metrics, shakeout_index=candidate_index)
        recovery_index = validation.recovery.recovery_index
        if recovery_index is None:
            continue
        recovery_index = int(recovery_index)
        outcome, forward_return = forward_outcome(weekly, recovery_index)
        events.append({
            "symbol": symbol,
            "candidate_index": candidate_index,
            "test_index": validation.test.test_index,
            "recovery_index": recovery_index,
            "outcome": outcome,
            "forward_return": forward_return,
        })
    return events


def summarize(rows: list[dict]) -> dict:
    counts = Counter(row["outcome"] for row in rows)
    decisive = counts["POSITIVE_8_BAR"] + counts["NEGATIVE_8_BAR"]
    return {
        "events": len(rows),
        "positive": counts["POSITIVE_8_BAR"],
        "negative": counts["NEGATIVE_8_BAR"],
        "flat": counts["FLAT_8_BAR"],
        "insufficient_forward_data": counts["INSUFFICIENT_FORWARD_DATA"],
        "decisive": decisive,
        "positive_decisive_rate": counts["POSITIVE_8_BAR"] / decisive if decisive else 0.0,
    }


def main() -> None:
    symbols = tuple(sys.argv[1:]) or DEFAULT_SYMBOLS
    failures: list[dict] = []
    all_events: list[dict] = []
    with ThreadPoolExecutor(max_workers=min(4, len(symbols))) as executor:
        futures = {executor.submit(inspect_symbol, symbol): symbol for symbol in symbols}
        for future, symbol in futures.items():
            try:
                all_events.extend(future.result())
            except Exception as exc:
                failures.append({"symbol": symbol, "error": repr(exc)})

    print("SHAKEOUT RECOVERY-ANCHOR OUTCOME ROBUSTNESS SUMMARY")
    baseline = summarize(all_events)
    print({**baseline, "symbols_requested": len(symbols),
           "symbols_with_confirmed_shakeouts": len({row['symbol'] for row in all_events}),
           "failures": failures})

    print("SHAKEOUT RECOVERY-ANCHOR OUTCOME ROBUSTNESS BY_SYMBOL")
    for symbol in symbols:
        rows = [r for r in all_events if r["symbol"] == symbol]
        print({"symbol": symbol, **summarize(rows)})

    print("SHAKEOUT RECOVERY-ANCHOR OUTCOME ROBUSTNESS LEAVE_ONE_OUT")
    for excluded in symbols:
        rows = [r for r in all_events if r["symbol"] != excluded]
        print({"excluded_symbol": excluded, **summarize(rows)})


if __name__ == "__main__":
    main()
