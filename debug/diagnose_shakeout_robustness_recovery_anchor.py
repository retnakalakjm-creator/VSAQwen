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
from evidence.engine import EvidenceEngine
from evidence.rules import has_strong_spread, is_bearish_bar, is_very_high_volume, makes_lower_low
from metrics_engine import MetricsEngine
from models import Direction, SpreadClass, VolumeClass
from trend import TrendAnalyzer

DEFAULT_SYMBOLS = (
    "BHARTIARTL.NS", "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "INFY.NS", "TCS.NS", "SBIN.NS", "LT.NS",
)
MIN_REPLAY_BARS = 20


def candidate_indices(metrics) -> list[int]:
    result: list[int] = []
    for i in range(MIN_REPLAY_BARS, len(metrics)):
        row = metrics.iloc[i]
        direction = Direction(int(row[COL_DIRECTION]))
        volume = VolumeClass(int(row[COL_VOLUME_CLASS]))
        spread = SpreadClass(int(row[COL_SPREAD_CLASS]))
        if direction == Direction.DOWN and volume >= VolumeClass.VERY_HIGH and spread >= SpreadClass.WIDE:
            result.append(i)
    return result


def inspect_symbol(symbol: str) -> list[dict]:
    daily = download_data(symbol)
    weekly = daily_to_weekly(daily)
    metrics = MetricsEngine().calculate(weekly)
    confirmed: list[dict] = []

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
        if not (
            has_selling_campaign(ctx)
            and is_bearish_bar(bar)
            and has_strong_spread(bar)
            and is_very_high_volume(bar)
            and makes_lower_low(bar, ctx.previous)
        ):
            continue

        validation = validate_shakeout(metrics=metrics, shakeout_index=candidate_index)
        recovery_index = validation.recovery.recovery_index
        if recovery_index is None:
            continue
        confirmed.append({
            "symbol": symbol,
            "candidate_bar_index": candidate_index,
            "test_bar_index": validation.test.test_index,
            "recovery_bar_index": int(recovery_index),
            "week": str(metrics.iloc[int(recovery_index)][COL_WEEK]),
        })
    return confirmed


def summarize(events: list[dict], symbols: tuple[str, ...], excluded: str | None = None) -> dict:
    counts = Counter(e["symbol"] for e in events)
    return {
        "excluded_symbol": excluded,
        "events": len(events),
        "symbols_with_confirmed_shakeouts": len({e["symbol"] for e in events}),
        "by_symbol": {symbol: counts.get(symbol, 0) for symbol in symbols if symbol != excluded},
    }


def main() -> None:
    symbols = tuple(sys.argv[1:]) or DEFAULT_SYMBOLS
    events: list[dict] = []
    failures: list[dict] = []
    with ThreadPoolExecutor(max_workers=min(4, len(symbols))) as executor:
        futures = {executor.submit(inspect_symbol, s): s for s in symbols}
        for future, symbol in futures.items():
            try:
                events.extend(future.result())
            except Exception as exc:
                failures.append({"symbol": symbol, "error": repr(exc)})

    print("SHAKEOUT RECOVERY-ANCHOR ROBUSTNESS SUMMARY")
    print({**summarize(events, symbols), "failures": failures})
    print("SHAKEOUT RECOVERY-ANCHOR ROBUSTNESS BY_SYMBOL")
    for symbol in symbols:
        symbol_events = [e for e in events if e["symbol"] == symbol]
        print({"symbol": symbol, "confirmed_shakeouts": len(symbol_events)})

    print("SHAKEOUT RECOVERY-ANCHOR ROBUSTNESS LEAVE_ONE_OUT")
    for excluded in symbols:
        subset = [e for e in events if e["symbol"] != excluded]
        print(summarize(subset, symbols, excluded))


if __name__ == "__main__":
    main()
