"""Analysis-only semantic-quality audit for SELLING_CLIMAX candidates."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from engine.columns import (
    COL_CLOSE,
    COL_CLOSE_POSITION,
    COL_DIRECTION,
    COL_PREV_CLOSE,
    COL_SPREAD_CLASS,
    COL_VOLUME_CLASS,
)
from evidence.campaign import has_selling_campaign
from evidence.rules import (
    has_strong_spread,
    is_above_average_spread,
    is_bearish_bar,
    is_strong_close,
    is_very_high_volume,
    volume_increasing,
)
from metrics_engine import MetricsEngine
from models import ClosePosition, Direction, SpreadClass, VolumeClass
import config

SYMBOLS = (
    "BHARTIARTL.NS", "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "INFY.NS", "TCS.NS", "SBIN.NS", "LT.NS",
)
FORWARD_BARS = 8
BACKGROUND_WINDOW = config.BACKGROUND_LOOKBACK


def _cheap_campaign_score(metrics, index: int) -> int:
    start = max(0, index - BACKGROUND_WINDOW + 1)
    window = metrics.iloc[start:index + 1]
    directions = window[COL_DIRECTION].to_numpy(dtype=int)
    closes = window[COL_CLOSE].to_numpy(dtype=float)
    prev_closes = window[COL_PREV_CLOSE].to_numpy(dtype=float)
    close_positions = window[COL_CLOSE_POSITION].to_numpy(dtype=int)

    return (
        int(int((directions == int(Direction.DOWN)).sum()) >= config.CAMPAIGN_MIN_DOWN_BARS)
        + int(int((closes < prev_closes).sum()) >= config.CAMPAIGN_MIN_LOWER_CLOSES)
        + int(int((close_positions <= int(ClosePosition.LOWER)).sum()) >= config.CAMPAIGN_MIN_WEAK_CLOSES)
    )


def _bar_proxy(row):
    class Proxy:
        pass
    p = Proxy()
    p.direction = Direction(int(row[COL_DIRECTION]))
    p.volume = VolumeClass(int(row[COL_VOLUME_CLASS]))
    p.spread = SpreadClass(int(row[COL_SPREAD_CLASS]))
    p.close_position = ClosePosition(int(row[COL_CLOSE_POSITION]))
    return p


def _audit_symbol(symbol: str) -> dict:
    metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
    from trend import TrendAnalyzer
    from evidence.engine import EvidenceEngine

    out = {
        "symbol": symbol,
        "candidate_events": 0,
        "semantic_failures": 0,
        "bearish_bar": 0,
        "very_high_volume": 0,
        "above_average_spread": 0,
        "wide_spread": 0,
        "strong_close": 0,
        "volume_increasing": 0,
        "heavy_context_rebuilds": 0,
    }

    for index in range(21, len(metrics) - FORWARD_BARS):
        bar = metrics.iloc[index]

        if int(bar[COL_DIRECTION]) != int(Direction.DOWN):
            continue
        if VolumeClass(int(bar[COL_VOLUME_CLASS])) < VolumeClass.VERY_HIGH:
            continue
        if SpreadClass(int(bar[COL_SPREAD_CLASS])) < SpreadClass.ABOVE_AVERAGE:
            continue

        cheap_score = _cheap_campaign_score(metrics, index)
        if cheap_score < 2:
            continue

        replay = metrics.iloc[:index + 1]
        trend = TrendAnalyzer().analyze(replay)
        engine = EvidenceEngine()
        engine._reset(
            metrics=replay,
            trend=trend,
            structural_swings=tuple(trend.structure.structural_swings),
            validation_metrics=replay,
        )
        out["heavy_context_rebuilds"] += 1
        ctx = engine._ctx
        if ctx is None or ctx.previous is None:
            continue
        if not has_selling_campaign(ctx):
            continue

        out["candidate_events"] += 1
        proxy = _bar_proxy(bar)
        previous_proxy = _bar_proxy(metrics.iloc[index - 1])

        mandatory = (
            has_selling_campaign(ctx),
            is_bearish_bar(proxy),
            is_very_high_volume(proxy),
            is_above_average_spread(proxy),
        )
        if not all(mandatory):
            out["semantic_failures"] += 1
            continue

        out["bearish_bar"] += int(is_bearish_bar(proxy))
        out["very_high_volume"] += int(is_very_high_volume(proxy))
        out["above_average_spread"] += int(is_above_average_spread(proxy))
        out["wide_spread"] += int(has_strong_spread(proxy))
        out["strong_close"] += int(is_strong_close(proxy))
        out["volume_increasing"] += int(volume_increasing(proxy, previous_proxy))

    return out


def main() -> None:
    failures = []
    results = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(_audit_symbol, s): s for s in SYMBOLS}
        for future, symbol in futures.items():
            try:
                results.append(future.result())
            except Exception as exc:
                failures.append({"symbol": symbol, "error": repr(exc)})

    totals = {
        key: sum(item[key] for item in results)
        for key in (
            "candidate_events", "semantic_failures", "bearish_bar",
            "very_high_volume", "above_average_spread", "wide_spread",
            "strong_close", "volume_increasing", "heavy_context_rebuilds",
        )
    }

    print("SELLING CLIMAX SEMANTIC QUALITY AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": len(results),
        **totals,
        "failures": failures,
        "status": "PASS" if not failures and totals["semantic_failures"] == 0 else "FAIL",
    })
    print("SELLING CLIMAX SEMANTIC QUALITY BY_SYMBOL")
    for item in sorted(results, key=lambda x: x["symbol"]):
        print(item)


if __name__ == "__main__":
    main()
