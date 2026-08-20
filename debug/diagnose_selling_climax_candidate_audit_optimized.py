"""Analysis-only candidate audit for the existing SELLING_CLIMAX detector definition."""
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
    COL_DIRECTION,
    COL_SPREAD_CLASS,
    COL_VOLUME_CLASS,
)
from evidence.campaign import has_selling_campaign
from evidence.rules import is_bearish_bar, is_strong_close, has_strong_spread, is_very_high_volume, volume_increasing
from metrics_engine import MetricsEngine
from models import SpreadClass, VolumeClass

SYMBOLS = (
    "BHARTIARTL.NS", "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "INFY.NS", "TCS.NS", "SBIN.NS", "LT.NS",
)
FORWARD_BARS = 8


def _candidate(bar, previous, ctx) -> bool:
    # Exact mandatory conditions from evidence/demand.py::_collect_selling_climax.
    return (
        has_selling_campaign(ctx)
        and is_bearish_bar(bar)
        and is_very_high_volume(bar)
        and (
            is_above_average_spread(bar)
        )
    )


def is_above_average_spread(bar) -> bool:
    return SpreadClass(int(bar[COL_SPREAD_CLASS])) >= SpreadClass.ABOVE_AVERAGE


def _audit_symbol(symbol: str) -> dict:
    metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
    from trend import TrendAnalyzer
    from evidence.engine import EvidenceEngine

    out = {
        "symbol": symbol,
        "candidate_events": 0,
        "positive": 0,
        "negative": 0,
        "flat": 0,
        "decisive": 0,
        "returns": [],
        "wide_spread": 0,
        "strong_close": 0,
        "volume_increasing": 0,
    }

    for index in range(21, len(metrics) - FORWARD_BARS):
        replay = metrics.iloc[: index + 1]
        trend = TrendAnalyzer().analyze(replay)
        engine = EvidenceEngine()
        engine._reset(
            metrics=replay,
            trend=trend,
            structural_swings=tuple(trend.structure.structural_swings),
            validation_metrics=replay,
        )
        ctx = engine._ctx
        if ctx is None or ctx.previous is None:
            continue
        bar = metrics.iloc[index]
        previous = metrics.iloc[index - 1]
        if not _candidate(bar, previous, ctx):
            continue

        out["candidate_events"] += 1
        out["wide_spread"] += int(has_strong_spread(bar))
        out["strong_close"] += int(is_strong_close(bar))
        out["volume_increasing"] += int(volume_increasing(bar, previous))

        start = float(bar[COL_CLOSE])
        end = float(metrics.iloc[index + FORWARD_BARS][COL_CLOSE])
        if start == 0.0:
            continue
        forward = end / start - 1.0
        out["returns"].append(forward)
        if forward > 0:
            out["positive"] += 1
        elif forward < 0:
            out["negative"] += 1
        else:
            out["flat"] += 1

    out["decisive"] = out["positive"] + out["negative"]
    return out


def _mean(values):
    return sum(values) / len(values) if values else 0.0


def main() -> None:
    failures = []
    results = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(_audit_symbol, symbol): symbol for symbol in SYMBOLS}
        for future, symbol in futures.items():
            try:
                results.append(future.result())
            except Exception as exc:
                failures.append({"symbol": symbol, "error": repr(exc)})

    candidate = sum(x["candidate_events"] for x in results)
    positive = sum(x["positive"] for x in results)
    negative = sum(x["negative"] for x in results)
    flat = sum(x["flat"] for x in results)
    decisive = positive + negative
    returns = [r for x in results for r in x["returns"]]
    wide = sum(x["wide_spread"] for x in results)
    strong = sum(x["strong_close"] for x in results)
    increasing = sum(x["volume_increasing"] for x in results)

    print("SELLING CLIMAX CANDIDATE AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": len(results),
        "candidate_events": candidate,
        "positive": positive,
        "negative": negative,
        "flat": flat,
        "decisive": decisive,
        "positive_decisive_rate": positive / decisive if decisive else 0.0,
        "mean_return": _mean(returns),
        "wide_spread": wide,
        "strong_close": strong,
        "volume_increasing": increasing,
        "failures": failures,
        "status": "PASS" if not failures else "FAIL",
    })
    print("SELLING CLIMAX CANDIDATE BY_SYMBOL")
    for result in sorted(results, key=lambda x: x["symbol"]):
        result = dict(result)
        result.pop("returns", None)
        result["positive_decisive_rate"] = (
            result["positive"] / result["decisive"] if result["decisive"] else 0.0
        )
        print(result)


if __name__ == "__main__":
    main()
