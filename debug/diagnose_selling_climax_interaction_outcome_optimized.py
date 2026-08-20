"""Analysis-only outcome audit for SELLING_CLIMAX interactions."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from engine.columns import COL_CLOSE, COL_DIRECTION, COL_SPREAD_CLASS, COL_VOLUME_CLASS
from evidence.campaign import has_selling_campaign
from evidence.demand import _collect_shakeout, _collect_stopping_volume
from evidence.engine import EvidenceEngine
from metrics_engine import MetricsEngine
from models import EvidenceCode, SpreadClass, VolumeClass
from trend import TrendAnalyzer

SYMBOLS = (
    "BHARTIARTL.NS", "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "INFY.NS", "TCS.NS", "SBIN.NS", "LT.NS",
)
FORWARD_BARS = 8


def _candidate(bar) -> bool:
    return (
        int(bar[COL_DIRECTION]) == -1
        and VolumeClass(int(bar[COL_VOLUME_CLASS])) >= VolumeClass.VERY_HIGH
        and SpreadClass(int(bar[COL_SPREAD_CLASS])) >= SpreadClass.ABOVE_AVERAGE
    )


def _audit_symbol(symbol: str) -> dict:
    metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
    out = {
        "symbol": symbol,
        "events": 0,
        "clean": 0,
        "stopping": 0,
        "shakeout": 0,
        "both": 0,
        "returns": {"clean": [], "stopping": [], "shakeout": [], "both": []},
        "heavy_context_rebuilds": 0,
    }

    for index in range(21, len(metrics) - FORWARD_BARS):
        bar = metrics.iloc[index]
        previous = metrics.iloc[index - 1]
        if not _candidate(bar):
            continue

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

        # Reuse the validated production collector semantics at the current bar.
        stopping = bool(_collect_stopping_volume(ctx))
        shakeout = bool(_collect_shakeout(ctx))

        start = float(bar[COL_CLOSE])
        end = float(metrics.iloc[index + FORWARD_BARS][COL_CLOSE])
        if start == 0.0:
            continue
        forward = end / start - 1.0

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


def _summary(events: int, returns: list[float]) -> dict:
    positive = sum(r > 0 for r in returns)
    negative = sum(r < 0 for r in returns)
    flat = sum(r == 0 for r in returns)
    decisive = positive + negative
    return {
        "events": events,
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
        futures = {executor.submit(_audit_symbol, s): s for s in SYMBOLS}
        for future, symbol in futures.items():
            try:
                results.append(future.result())
            except Exception as exc:
                failures.append({"symbol": symbol, "error": repr(exc)})

    groups = {"clean": [], "stopping": [], "shakeout": [], "both": []}
    counts = {k: 0 for k in groups}
    for item in results:
        for key in groups:
            counts[key] += item[key]
            groups[key].extend(item["returns"][key])

    events = sum(counts.values())
    print("SELLING CLIMAX INTERACTION OUTCOME AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": len(results),
        "events": events,
        "clean_events": counts["clean"],
        "stopping_events": counts["stopping"],
        "shakeout_events": counts["shakeout"],
        "both_events": counts["both"],
        "interaction_event_rate": ((events - counts["clean"]) / events if events else 0.0),
        "heavy_context_rebuilds": sum(x["heavy_context_rebuilds"] for x in results),
        "failures": failures,
        "status": "PASS" if not failures else "FAIL",
    })
    print("SELLING CLIMAX INTERACTION OUTCOME BY_GROUP")
    for key in ("clean", "stopping", "shakeout", "both"):
        print({"group": key, **_summary(counts[key], groups[key])})

    print("SELLING CLIMAX INTERACTION OUTCOME BY_SYMBOL")
    for item in sorted(results, key=lambda x: x["symbol"]):
        print({
            "symbol": item["symbol"],
            "events": item["events"],
            "clean": item["clean"],
            "stopping": item["stopping"],
            "shakeout": item["shakeout"],
            "both": item["both"],
        })


if __name__ == "__main__":
    main()
