from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from engine.columns import COL_AVG_SPREAD, COL_DIRECTION, COL_SPREAD_CLASS, COL_VOLUME_CLASS, COL_WEEK
from evidence.campaign import _recent_structural_weakness, has_recent_weakness, has_selling_campaign
from evidence.demand import _collect_test
from evidence.engine import EvidenceEngine
from evidence.rules import is_confirmed_downtrend, is_low_volume, is_narrow_spread, is_strong_close, is_weak_close, makes_higher_low, volume_decreasing
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
        if (
            Direction(int(row[COL_DIRECTION])) == Direction.DOWN
            and VolumeClass(int(row[COL_VOLUME_CLASS])) <= VolumeClass.LOW
            and SpreadClass(int(row[COL_SPREAD_CLASS])) <= SpreadClass.NARROW
        ):
            indices.append(index)
    return indices


def audit_symbol(symbol: str) -> list[dict]:
    daily = download_data(symbol)
    weekly = daily_to_weekly(daily)
    metrics = MetricsEngine().calculate(weekly)
    rows: list[dict] = []

    for index in candidate_indices(metrics):
        replay = metrics.iloc[: index + 1].copy()
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

        events = tuple(event for event in _collect_test(ctx) if event.bar_index == index)
        if not events:
            continue

        bar = ctx.current
        previous = ctx.previous
        campaign = has_selling_campaign(ctx)
        recent_weakness = has_recent_weakness(ctx)
        structural_weakness = _recent_structural_weakness(ctx)
        confirmed_downtrend = is_confirmed_downtrend(ctx.trend)

        higher_low = makes_higher_low(bar, previous) if previous is not None else False
        volume_dec = volume_decreasing(bar, previous) if previous is not None else False
        strong_close = is_strong_close(bar)
        weak_close = is_weak_close(bar)

        low_effort_probe = is_low_volume(bar) and is_narrow_spread(bar)
        meaningful_selling_context = campaign or recent_weakness
        contradiction = confirmed_downtrend and not structural_weakness

        rows.append(
            {
                "symbol": symbol,
                "bar_index": index,
                "week": str(metrics.iloc[index][COL_WEEK]),
                "low_effort_probe": low_effort_probe,
                "selling_campaign": campaign,
                "recent_weakness": recent_weakness,
                "structural_weakness": structural_weakness,
                "confirmed_downtrend": confirmed_downtrend,
                "contradictory_downtrend": contradiction,
                "volume_decreasing": volume_dec,
                "higher_low": higher_low,
                "strong_close": strong_close,
                "weak_close": weak_close,
                "spread_ratio": float(bar.spread_ratio),
                "volume_ratio": float(bar.volume_ratio),
                "avg_spread": float(metrics.iloc[index][COL_AVG_SPREAD]),
                "semantic_quality_like": (
                    low_effort_probe and meaningful_selling_context and not contradiction
                ),
            }
        )

    return rows


def main() -> None:
    symbols = tuple(sys.argv[1:]) or DEFAULT_SYMBOLS
    rows: list[dict] = []
    failures: list[dict] = []

    with ThreadPoolExecutor(max_workers=min(4, len(symbols))) as executor:
        futures = {executor.submit(audit_symbol, symbol): symbol for symbol in symbols}
        for future, symbol in futures.items():
            try:
                rows.extend(future.result())
            except Exception as exc:
                failures.append({"symbol": symbol, "error": repr(exc)})

    total = len(rows)
    low_effort = sum(row["low_effort_probe"] for row in rows)
    meaningful_context = sum(row["selling_campaign"] or row["recent_weakness"] for row in rows)
    contradictions = sum(row["contradictory_downtrend"] for row in rows)
    higher_low = sum(row["higher_low"] for row in rows)
    volume_decreasing_count = sum(row["volume_decreasing"] for row in rows)
    strong_close = sum(row["strong_close"] for row in rows)
    semantic_like = sum(row["semantic_quality_like"] for row in rows)

    print("TEST SEMANTIC QUALITY AUDIT SUMMARY")
    print(
        {
            "symbols_requested": len(symbols),
            "symbols_with_events": len({row["symbol"] for row in rows}),
            "test_events": total,
            "low_effort_probe": low_effort,
            "low_effort_rate": low_effort / total if total else 0.0,
            "meaningful_selling_context": meaningful_context,
            "meaningful_selling_context_rate": meaningful_context / total if total else 0.0,
            "contradictory_downtrend": contradictions,
            "contradiction_rate": contradictions / total if total else 0.0,
            "higher_low": higher_low,
            "higher_low_rate": higher_low / total if total else 0.0,
            "volume_decreasing": volume_decreasing_count,
            "volume_decreasing_rate": volume_decreasing_count / total if total else 0.0,
            "strong_close": strong_close,
            "strong_close_rate": strong_close / total if total else 0.0,
            "semantic_quality_like": semantic_like,
            "semantic_quality_like_rate": semantic_like / total if total else 0.0,
            "failures": failures,
        }
    )

    print("TEST SEMANTIC QUALITY AUDIT BY_SYMBOL")
    for symbol in symbols:
        subset = [row for row in rows if row["symbol"] == symbol]
        print(
            {
                "symbol": symbol,
                "events": len(subset),
                "semantic_quality_like": sum(row["semantic_quality_like"] for row in subset),
                "contradictions": sum(row["contradictory_downtrend"] for row in subset),
            }
        )

    print("TEST SEMANTIC QUALITY AUDIT EVENTS")
    for row in rows:
        print(row)


if __name__ == "__main__":
    main()
