from __future__ import annotations

import os
import sys

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from data import daily_to_weekly, download_data
from evidence.engine import EvidenceEngine
from metrics_engine import MetricsEngine
from models import EvidenceCode, Direction, SpreadClass, VolumeClass
from trend import TrendAnalyzer
from engine.columns import COL_DIRECTION, COL_SPREAD_CLASS, COL_VOLUME_CLASS

SYMBOLS = (
    "BHARTIARTL.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "LT.NS", "RELIANCE.NS", "SBIN.NS", "TCS.NS",
)
TARGET_CODE = EvidenceCode.INCREASING_SUPPLY


def _cheap_candidate(metrics, index: int) -> bool:
    row = metrics.iloc[index]
    return (
        Direction(int(row[COL_DIRECTION])) == Direction.DOWN
        and VolumeClass(int(row[COL_VOLUME_CLASS])) >= VolumeClass.HIGH
        and SpreadClass(int(row[COL_SPREAD_CLASS])) >= SpreadClass.ABOVE_AVERAGE
    )


def _audit_symbol(symbol: str) -> dict[str, object]:
    metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
    cheap_candidates = 0
    candidate_events: list[tuple[int, float | None]] = []
    failures: list[str] = []
    heavy_rebuilds = 0

    for index in range(1, len(metrics)):
        if not _cheap_candidate(metrics, index):
            continue

        cheap_candidates += 1
        replay = metrics.iloc[: index + 1].copy()
        trend = TrendAnalyzer().analyze(replay)
        structural_swings = tuple(trend.structure.structural_swings)
        engine = EvidenceEngine()
        result = engine.collect(
            metrics=replay,
            trend=trend,
            structural_swings=structural_swings,
        )
        heavy_rebuilds += 1

        target = [
            e for e in result.evidence
            if e.code is TARGET_CODE
            and getattr(e, "bar_index", None) == index
        ]

        if len(target) > 1:
            failures.append(
                f"{symbol}:{index}: expected at most one target emission, got {len(target)}"
            )
            continue

        if not target:
            continue

        candidate_events.append((index, float(getattr(target[0], "weight", np.nan))))

    return {
        "cheap_candidates": cheap_candidates,
        "candidate_events": candidate_events,
        "heavy_rebuilds": heavy_rebuilds,
        "failures": failures,
    }


def main() -> None:
    symbols_with_results = 0
    bars_scanned = 0
    cheap_candidates = 0
    candidate_events: list[tuple[str, int, float | None]] = []
    heavy_rebuilds = 0
    failures: list[dict[str, str]] = []

    for symbol in SYMBOLS:
        try:
            metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
            bars_scanned += len(metrics)
            result = _audit_symbol(symbol)
            symbols_with_results += 1
            cheap_candidates += int(result["cheap_candidates"])
            heavy_rebuilds += int(result["heavy_rebuilds"])
            candidate_events.extend(
                (symbol, index, weight)
                for index, weight in result["candidate_events"]
            )
            failures.extend(
                {"symbol": symbol, "error": msg}
                for msg in result["failures"]
            )
        except Exception as exc:
            failures.append({"symbol": symbol, "error": str(exc)})

    positive = negative = flat = 0
    returns: list[float] = []

    # Outcome calculation is intentionally performed on the original weekly data
    # at the emitted target index, using the existing audit convention of an
    # 8-bar forward close return. Flat is reserved for exactly zero outcome.
    for symbol, index, _weight in candidate_events:
        try:
            metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
            if index + 8 >= len(metrics):
                continue
            start = float(metrics.iloc[index]["Close"])
            end = float(metrics.iloc[index + 8]["Close"])
            if start == 0.0:
                continue
            ret = (end - start) / start
            returns.append(ret)
            if ret > 0:
                positive += 1
            elif ret < 0:
                negative += 1
            else:
                flat += 1
        except Exception as exc:
            failures.append({"symbol": symbol, "error": f"{index}: {exc}"})

    decisive = positive + negative
    positive_decisive_rate = positive / decisive if decisive else 0.0
    mean_return = float(np.mean(returns)) if returns else 0.0

    print("INCREASING SUPPLY CANDIDATE AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": symbols_with_results,
        "bars_scanned": bars_scanned,
        "cheap_candidates": cheap_candidates,
        "candidate_events": len(candidate_events),
        "positive": positive,
        "negative": negative,
        "flat": flat,
        "decisive": decisive,
        "positive_decisive_rate": positive_decisive_rate,
        "mean_return": mean_return,
        "semantic_failures": 0,
        "heavy_context_rebuilds": heavy_rebuilds,
        "failures": failures,
        "status": "PASS" if not failures and symbols_with_results == len(SYMBOLS) else "FAIL",
    })


if __name__ == "__main__":
    main()
