from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from data import daily_to_weekly
from metrics_engine import MetricsEngine
from scanner import ScannerEngine, TrendAnalyzer, EvidenceEngine


def old_scan_actionable(engine: ScannerEngine, metrics: pd.DataFrame):
    """Exact pre-optimization scan_actionable behavior from 356883e."""
    if len(metrics) <= engine.MIN_REPLAY_BARS:
        return []

    target_index = len(metrics) - 1
    history = []
    current_trend = None
    current_evidence = None

    for index in range(engine.MIN_REPLAY_BARS, target_index + 1):
        replay = metrics.iloc[: index + 1].copy()
        trend = TrendAnalyzer().analyze(replay)
        structural_swings = list(trend.structure.structural_swings)
        evidence = EvidenceEngine().collect(
            metrics=replay,
            trend=trend,
            structural_swings=structural_swings,
        )
        history.append(evidence)
        current_trend = trend
        current_evidence = evidence

    assert current_trend is not None
    assert current_evidence is not None

    candidate = engine.evaluate(
        trend=current_trend,
        evidence=current_evidence,
        history=history,
        bar_index=target_index,
        week=engine._week_at(metrics, target_index),
    )
    return [candidate] if candidate.actionable else []


def new_scan_actionable(engine: ScannerEngine, metrics: pd.DataFrame):
    return engine.scan_actionable(metrics)


def timed(fn, engine, metrics, repeats):
    best = float("inf")
    result = None
    for _ in range(repeats):
        start = time.perf_counter()
        result = fn(engine, metrics)
        best = min(best, time.perf_counter() - start)
    return result, best


def candidate_signature(candidates):
    return [
        (
            c.bar_index,
            c.week,
            str(c.qualification),
            c.actionable,
            c.net_strength,
            c.net_pressure,
            c.confidence,
            c.target_bar_evidence_codes,
            c.scoring_evidence_codes,
            c.scoring_bar_index,
            c.scoring_evidence_age,
            c.used_fallback_evidence,
        )
        for c in candidates
    ]


def make_daily(size: int) -> pd.DataFrame:
    end = pd.Timestamp("2025-12-31")
    start = end - pd.to_timedelta(size - 1, unit="D")
    if start < pd.Timestamp.min:
        raise ValueError("--size is too large for pandas datetime64[ns] range")
    index = pd.date_range(start=start, periods=size, freq="D")

    rng = np.random.default_rng(42)
    log_returns = rng.normal(0.0, 0.01, size)
    close = 100.0 * np.exp(np.cumsum(log_returns))
    spread = rng.uniform(0.1, 2.0, size)
    frame = pd.DataFrame(
        {
            "open": close * np.exp(rng.normal(0.0, 0.003, size)),
            "high": close + spread,
            "low": np.maximum(close - spread, 0.01),
            "close": close,
            "volume": rng.integers(1_000, 100_000, size),
        },
        index=index,
    )
    frame.index.name = "date"
    return frame


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", type=int, default=5000)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()

    if args.size < ScannerEngine.MIN_REPLAY_BARS:
        parser.error(f"--size must be >= {ScannerEngine.MIN_REPLAY_BARS}")
    if args.repeats <= 0:
        parser.error("--repeats must be greater than zero")

    daily = make_daily(args.size)
    weekly = daily_to_weekly(daily)
    metrics = MetricsEngine().calculate(weekly)
    engine = ScannerEngine()

    old_result, old_time = timed(old_scan_actionable, engine, metrics, args.repeats)
    new_result, new_time = timed(new_scan_actionable, engine, metrics, args.repeats)

    if candidate_signature(old_result) != candidate_signature(new_result):
        raise AssertionError("latest-bar decision mismatch between old and new implementations")

    print(f"daily_size={args.size:,}")
    print(f"weekly_size={len(weekly):,}")
    print(f"repeats={args.repeats}")
    print(f"old_best_seconds={old_time:.6f}")
    print(f"optimized_best_seconds={new_time:.6f}")
    print(f"speedup={old_time / new_time:.2f}x")
    print("equivalence=PASS")


if __name__ == "__main__":
    main()
