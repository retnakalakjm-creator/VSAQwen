"""Analysis-only outcome audit for SELLING_CLIMAX interactions.

Optimized semantics:
- exact SELLING_CLIMAX campaign gate is preserved;
- STOPPING_VOLUME overlap is evaluated directly from the same validated bar;
- SHAKEOUT overlap is structurally impossible on the same bar because
  SELLING_CLIMAX requires a bearish bar while SHAKEOUT evidence is emitted
  on a bullish recovery bar;
- no SHAKEOUT collector is invoked, avoiding nested context reconstruction.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config
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
from evidence.engine import EvidenceEngine
from evidence.rules import is_weak_close
from metrics_engine import MetricsEngine
from models import SpreadClass, VolumeClass
from trend import TrendAnalyzer

SYMBOLS = (
    "BHARTIARTL.NS", "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "INFY.NS", "TCS.NS", "SBIN.NS", "LT.NS",
)
FORWARD_BARS = 8
BACKGROUND_WINDOW = config.BACKGROUND_LOOKBACK


def _cheap_selling_climax_candidate(bar) -> bool:
    return (
        int(bar[COL_DIRECTION]) == -1
        and VolumeClass(int(bar[COL_VOLUME_CLASS])) >= VolumeClass.VERY_HIGH
        and SpreadClass(int(bar[COL_SPREAD_CLASS])) >= SpreadClass.ABOVE_AVERAGE
    )


def _cheap_campaign_score(metrics, index: int) -> int:
    """Return the campaign components that can be known without heavy context."""
    start = max(0, index - BACKGROUND_WINDOW + 1)
    window = metrics.iloc[start : index + 1]

    directions = window[COL_DIRECTION].to_numpy(dtype=int)
    closes = window[COL_CLOSE].to_numpy(dtype=float)
    prev_closes = window[COL_PREV_CLOSE].to_numpy(dtype=float)
    close_positions = window[COL_CLOSE_POSITION].to_numpy(dtype=int)

    down_ok = int((directions == -1).sum()) >= config.CAMPAIGN_MIN_DOWN_BARS
    lower_ok = int((closes < prev_closes).sum()) >= config.CAMPAIGN_MIN_LOWER_CLOSES
    weak_ok = int((close_positions <= 1).sum()) >= config.CAMPAIGN_MIN_WEAK_CLOSES

    return int(down_ok) + int(lower_ok) + int(weak_ok)


def _audit_symbol(symbol: str) -> dict:
    metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
    out = {
        "symbol": symbol,
        "bars_scanned": 0,
        "cheap_candidates": 0,
        "heavy_context_rebuilds": 0,
        "events": 0,
        "clean": 0,
        "stopping": 0,
        "shakeout": 0,
        "both": 0,
        "returns": {"clean": [], "stopping": [], "shakeout": [], "both": []},
        "campaign_skips": 0,
        "collector_errors": 0,
    }

    for index in range(21, len(metrics) - FORWARD_BARS):
        out["bars_scanned"] += 1
        bar = metrics.iloc[index]

        if not _cheap_selling_climax_candidate(bar):
            continue
        out["cheap_candidates"] += 1

        # The production selling campaign requires score >= 4 from five
        # possible components: downtrend, down bars, lower closes, weak closes,
        # and structural weakness. With fewer than 2 cheap components,
        # even both heavy components cannot reach 4, so the bar is impossible.
        if _cheap_campaign_score(metrics, index) < 2:
            out["campaign_skips"] += 1
            continue

        replay = metrics.iloc[: index + 1]
        try:
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

            # SELLING_CLIMAX already guarantees:
            #   selling campaign + bearish bar + very-high volume +
            #   above-average spread.
            # STOPPING_VOLUME adds only "Close Off Low" as a mandatory
            # condition, so its same-bar overlap can be tested directly.
            stopping = not is_weak_close(ctx.current)

            # SHAKEOUT is a recovery event emitted on a bullish recovery bar,
            # while SELLING_CLIMAX requires a bearish bar. Same-bar overlap is
            # therefore structurally impossible.
            shakeout = False
        except Exception:
            out["collector_errors"] += 1
            continue

        start_price = float(bar[COL_CLOSE])
        end_price = float(metrics.iloc[index + FORWARD_BARS][COL_CLOSE])
        if start_price == 0.0:
            continue
        forward = end_price / start_price - 1.0

        out["events"] += 1
        if stopping and shakeout:
            bucket = "both"
        elif stopping:
            bucket = "stopping"
        elif shakeout:
            bucket = "shakeout"
        else:
            bucket = "clean"

        out[bucket] += 1
        out["returns"][bucket].append(forward)

    return out


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _summary(returns: list[float]) -> dict:
    positive = sum(r > 0 for r in returns)
    negative = sum(r < 0 for r in returns)
    flat = sum(r == 0 for r in returns)
    decisive = positive + negative
    return {
        "events": len(returns),
        "positive": positive,
        "negative": negative,
        "flat": flat,
        "decisive": decisive,
        "positive_decisive_rate": positive / decisive if decisive else 0.0,
        "mean_return": _mean(returns),
    }


def main() -> None:
    failures, results = [], []
    with ThreadPoolExecutor(max_workers=min(4, len(SYMBOLS))) as executor:
        futures = {executor.submit(_audit_symbol, symbol): symbol for symbol in SYMBOLS}
        for future, symbol in futures.items():
            try:
                results.append(future.result())
            except Exception as exc:
                failures.append({"symbol": symbol, "error": repr(exc)})

    groups = {"clean": [], "stopping": [], "shakeout": [], "both": []}
    counts = {key: 0 for key in groups}
    collector_errors = 0
    campaign_skips = 0
    bars_scanned = 0
    cheap_candidates = 0
    heavy_rebuilds = 0

    for item in results:
        bars_scanned += item["bars_scanned"]
        cheap_candidates += item["cheap_candidates"]
        heavy_rebuilds += item["heavy_context_rebuilds"]
        campaign_skips += item["campaign_skips"]
        collector_errors += item["collector_errors"]
        for key in groups:
            counts[key] += item[key]
            groups[key].extend(item["returns"][key])

    events = sum(counts.values())

    print("SELLING CLIMAX INTERACTION OUTCOME AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": len(results),
        "bars_scanned": bars_scanned,
        "cheap_candidates": cheap_candidates,
        "campaign_skips": campaign_skips,
        "events": events,
        "clean_events": counts["clean"],
        "stopping_events": counts["stopping"],
        "shakeout_events": counts["shakeout"],
        "both_events": counts["both"],
        "interaction_event_rate": ((events - counts["clean"]) / events if events else 0.0),
        "heavy_context_rebuilds": heavy_rebuilds,
        "shakeout_same_bar_structurally_impossible": True,
        "collector_errors": collector_errors,
        "failures": failures,
        "status": "PASS" if not failures and events > 0 and collector_errors == 0 else "FAIL",
    })

    print("SELLING CLIMAX INTERACTION OUTCOME BY_GROUP")
    for key in ("clean", "stopping", "shakeout", "both"):
        print({"group": key, **_summary(groups[key])})

    print("SELLING CLIMAX INTERACTION OUTCOME BY_SYMBOL")
    for item in sorted(results, key=lambda x: x["symbol"]):
        print({
            "symbol": item["symbol"],
            "bars_scanned": item["bars_scanned"],
            "cheap_candidates": item["cheap_candidates"],
            "campaign_skips": item["campaign_skips"],
            "events": item["events"],
            "clean": item["clean"],
            "stopping": item["stopping"],
            "shakeout": item["shakeout"],
            "both": item["both"],
            "heavy_context_rebuilds": item["heavy_context_rebuilds"],
            "collector_errors": item["collector_errors"],
        })


if __name__ == "__main__":
    main()
