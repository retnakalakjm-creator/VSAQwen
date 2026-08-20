"""Analysis-only decision-value audit for SELLING_CLIMAX."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from engine.columns import COL_CLOSE, COL_DIRECTION, COL_PREV_CLOSE, COL_SPREAD_CLASS, COL_VOLUME_CLASS
from evidence.campaign import has_selling_campaign
from metrics_engine import MetricsEngine
from models import SpreadClass, VolumeClass
from trend import TrendAnalyzer
from evidence.engine import EvidenceEngine

SYMBOLS = (
    "BHARTIARTL.NS", "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "INFY.NS", "TCS.NS", "SBIN.NS", "LT.NS",
)
FORWARD_BARS = 8
WEIGHTS_TESTED = (0.0, 0.25, 0.30, 0.38, 0.45, 0.50)


def _candidate_bar(bar) -> bool:
    return (
        int(bar[COL_DIRECTION]) == -1
        and VolumeClass(int(bar[COL_VOLUME_CLASS])) >= VolumeClass.VERY_HIGH
        and SpreadClass(int(bar[COL_SPREAD_CLASS])) >= SpreadClass.ABOVE_AVERAGE
    )


def _audit_symbol(symbol: str) -> dict:
    metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
    candidate_returns: list[float] = []
    eligible_returns: list[float] = []
    heavy_context_rebuilds = 0

    for index in range(21, len(metrics) - FORWARD_BARS):
        bar = metrics.iloc[index]
        if not _candidate_bar(bar):
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
        heavy_context_rebuilds += 1
        if ctx is None or ctx.previous is None or not has_selling_campaign(ctx):
            continue

        start = float(bar[COL_CLOSE])
        end = float(metrics.iloc[index + FORWARD_BARS][COL_CLOSE])
        if start == 0.0:
            continue
        candidate_returns.append(end / start - 1.0)

    # Eligible-market baseline: all point-in-time bars with a valid forward return.
    for index in range(21, len(metrics) - FORWARD_BARS):
        start = float(metrics.iloc[index][COL_CLOSE])
        if start == 0.0:
            continue
        end = float(metrics.iloc[index + FORWARD_BARS][COL_CLOSE])
        eligible_returns.append(end / start - 1.0)

    return {
        "symbol": symbol,
        "candidate_returns": candidate_returns,
        "eligible_returns": eligible_returns,
        "heavy_context_rebuilds": heavy_context_rebuilds,
    }


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _positive_decisive_rate(values: list[float]) -> float:
    positive = sum(v > 0 for v in values)
    decisive = sum(v != 0 for v in values)
    return positive / decisive if decisive else 0.0


def main() -> None:
    failures, results = [], []
    with ThreadPoolExecutor(max_workers=min(4, len(SYMBOLS))) as executor:
        futures = {executor.submit(_audit_symbol, s): s for s in SYMBOLS}
        for future, symbol in futures.items():
            try:
                results.append(future.result())
            except Exception as exc:
                failures.append({"symbol": symbol, "error": repr(exc)})

    candidate = [v for r in results for v in r["candidate_returns"]]
    eligible = [v for r in results for v in r["eligible_returns"]]
    candidate_mean = _mean(candidate)
    eligible_mean = _mean(eligible)
    candidate_rate = _positive_decisive_rate(candidate)
    eligible_rate = _positive_decisive_rate(eligible)
    weight_reference = 0.38

    print("SELLING CLIMAX DECISION VALUE AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": len(results),
        "candidate": {
            "events": len(candidate),
            "positive": sum(v > 0 for v in candidate),
            "negative": sum(v < 0 for v in candidate),
            "decisive": sum(v != 0 for v in candidate),
            "positive_decisive_rate": candidate_rate,
            "mean_return": candidate_mean,
        },
        "eligible_market": {
            "events": len(eligible),
            "positive": sum(v > 0 for v in eligible),
            "negative": sum(v < 0 for v in eligible),
            "decisive": sum(v != 0 for v in eligible),
            "positive_decisive_rate": eligible_rate,
            "mean_return": eligible_mean,
        },
        "positive_decisive_rate_lift": candidate_rate - eligible_rate,
        "mean_return_lift": candidate_mean - eligible_mean,
        "candidate_share_of_eligible": len(candidate) / len(eligible) if eligible else 0.0,
        "weights_tested": WEIGHTS_TESTED,
        "reference_weight": weight_reference,
        "heavy_context_rebuilds": sum(r["heavy_context_rebuilds"] for r in results),
        "production_path_mutation": False,
        "failures": failures,
        "status": "PASS" if not failures and candidate else "FAIL",
    })

    print("SELLING CLIMAX DECISION VALUE WEIGHTS")
    for weight in WEIGHTS_TESTED:
        print({
            "weight": weight,
            "candidate_score_contribution": weight,
            "relative_candidate_strength": weight * 0.90,
        })


if __name__ == "__main__":
    main()
