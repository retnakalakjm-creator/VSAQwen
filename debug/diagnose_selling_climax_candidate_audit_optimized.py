"""Analysis-only candidate audit for the existing SELLING_CLIMAX detector definition.

The detector semantics remain unchanged. The audit avoids rebuilding the full
TrendAnalyzer/EvidenceEngine context for bars that cannot possibly satisfy the
existing selling-campaign requirement.
"""
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
    is_strong_close,
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
    """Count the three campaign components that are cheap to evaluate.

    Production campaign scoring has five components:
      - confirmed downtrend        [heavy]
      - down bars >= threshold     [cheap]
      - lower closes >= threshold  [cheap]
      - weak closes >= threshold   [cheap]
      - structural weakness        [heavy]

    Required score is 4. With only three cheap components available, a cheap
    score of 0-1 can never qualify; scores 2-3 require the exact heavy context.
    """
    start = max(0, index - BACKGROUND_WINDOW + 1)
    window = metrics.iloc[start : index + 1]

    down_ok = (
        int((window[COL_DIRECTION].to_numpy(dtype=int) == -1).sum())
        >= config.CAMPAIGN_MIN_DOWN_BARS
    )

    lower_ok = (
        int(
            (
                window[COL_CLOSE].to_numpy(dtype=float)
                < window[COL_PREV_CLOSE].to_numpy(dtype=float)
            ).sum()
        )
        >= config.CAMPAIGN_MIN_LOWER_CLOSES
    )

    weak_ok = (
        int((window[COL_CLOSE_POSITION].to_numpy(dtype=int) <= 1).sum())
        >= config.CAMPAIGN_MIN_WEAK_CLOSES
    )

    return int(down_ok) + int(lower_ok) + int(weak_ok)


class _BarPlaceholder:
    """Minimal BarContext-compatible object for already-qualified bars."""
    __slots__ = ("direction", "volume", "spread", "close_position")

    def __init__(self, row):
        self.direction = Direction(int(row[COL_DIRECTION]))
        self.volume = VolumeClass(int(row[COL_VOLUME_CLASS]))
        self.spread = SpreadClass(int(row[COL_SPREAD_CLASS]))
        self.close_position = ClosePosition(int(row[COL_CLOSE_POSITION]))


def _audit_symbol(symbol: str) -> dict:
    metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))

    out = {
        "symbol": symbol,
        "bars_scanned": 0,
        "cheap_candidates": 0,
        "heavy_context_rebuilds": 0,
        "campaign_candidates_after_context": 0,
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
        out["bars_scanned"] += 1
        bar = metrics.iloc[index]

        # Exact cheap mandatory SELLING_CLIMAX conditions.
        if int(bar[COL_DIRECTION]) != -1:
            continue
        if VolumeClass(int(bar[COL_VOLUME_CLASS])) < VolumeClass.VERY_HIGH:
            continue
        if SpreadClass(int(bar[COL_SPREAD_CLASS])) < SpreadClass.ABOVE_AVERAGE:
            continue

        out["cheap_candidates"] += 1
        cheap_score = _cheap_campaign_score(metrics, index)

        # If fewer than 2 of the 3 cheap campaign components pass, even both
        # heavy components together cannot reach CAMPAIGN_REQUIRED_SCORE=4.
        if cheap_score < 2:
            continue

        # Exact campaign evaluation only for bars where qualification remains
        # mathematically possible.
        from trend import TrendAnalyzer
        from evidence.engine import EvidenceEngine

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
        out["heavy_context_rebuilds"] += 1

        if ctx is None or ctx.previous is None:
            continue
        if not has_selling_campaign(ctx):
            continue

        out["campaign_candidates_after_context"] += 1
        out["candidate_events"] += 1

        current_bar = ctx.current
        previous_bar = ctx.previous
        out["wide_spread"] += int(has_strong_spread(current_bar))
        out["strong_close"] += int(is_strong_close(current_bar))
        out["volume_increasing"] += int(
            volume_increasing(current_bar, previous_bar)
        )

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
        futures = {
            executor.submit(_audit_symbol, symbol): symbol
            for symbol in SYMBOLS
        }
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
    bars_scanned = sum(x["bars_scanned"] for x in results)
    cheap_candidates = sum(x["cheap_candidates"] for x in results)
    heavy_rebuilds = sum(x["heavy_context_rebuilds"] for x in results)
    campaign_candidates = sum(
        x["campaign_candidates_after_context"] for x in results
    )

    print("SELLING CLIMAX CANDIDATE AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": len(results),
        "bars_scanned": bars_scanned,
        "cheap_candidates": cheap_candidates,
        "heavy_context_rebuilds": heavy_rebuilds,
        "campaign_candidates_after_context": campaign_candidates,
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
            result["positive"] / result["decisive"]
            if result["decisive"]
            else 0.0
        )
        print(result)


if __name__ == "__main__":
    main()
