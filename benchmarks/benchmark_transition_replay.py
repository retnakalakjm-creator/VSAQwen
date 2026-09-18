"""Deterministic offline benchmark for the optimized transition scanner path.

This benchmark is intentionally separate from pytest timing assertions. It compares
current transition replay against the legacy point-in-time ScannerEngine on the
same synthetic weekly metrics and also measures one-new-bar update paths.

Examples
--------
    python benchmarks/benchmark_transition_replay.py
    python benchmarks/benchmark_transition_replay.py --bars 192 --repeats 7
    python benchmarks/benchmark_transition_replay.py --output-dir benchmarks/results
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from engine.columns import COL_CLOSE, COL_HIGH, COL_LOW, COL_OPEN, COL_VOLUME, COL_WEEK
from historical_scanner import HistoricalScannerRunner
from metrics_engine import MetricsEngine
from scanner import ScannerCandidate, ScannerEngine
from scanner_transition import ScannerTransitionEngine
from scanner_transition_resume import ScannerTransitionResumeAdapter
from scanner_transition_snapshot import ScannerTransitionSnapshotAdapter


@dataclass(frozen=True, slots=True)
class TimingStats:
    repeats: int
    min_seconds: float
    median_seconds: float
    mean_seconds: float
    max_seconds: float


@dataclass(frozen=True, slots=True)
class TransitionBenchmarkResult:
    bars: int
    candidate_count: int
    legacy_full_replay: TimingStats
    transition_full_replay: TimingStats
    transition_one_new_bar: TimingStats
    durable_resume_one_new_bar: TimingStats
    full_replay_speedup: float
    one_new_bar_vs_legacy_full_speedup: float


def make_metrics(size: int = 192, *, seed: int = 20260918) -> pd.DataFrame:
    """Build deterministic weekly OHLCV with repeated directional reversals."""

    if size <= ScannerEngine.MIN_REPLAY_BARS + 2:
        raise ValueError(
            f"size must be > {ScannerEngine.MIN_REPLAY_BARS + 2}"
        )

    rng = np.random.default_rng(seed)
    index = np.arange(size, dtype=float)

    trend = 100.0 + index * 0.16
    cycle = 6.0 * np.sin(index / 5.5) + 2.8 * np.sin(index / 2.9)
    noise = rng.normal(0.0, 0.35, size)
    close = np.maximum(trend + cycle + noise, 5.0)

    open_ = close + rng.normal(0.0, 0.45, size)
    half_range = 0.8 + rng.uniform(0.15, 1.25, size)
    high = np.maximum(open_, close) + half_range
    low = np.maximum(np.minimum(open_, close) - half_range, 0.01)
    volume = (
        1_000_000.0
        + 180_000.0 * np.sin(index / 4.1)
        + rng.normal(0.0, 55_000.0, size)
    )
    volume = np.maximum(volume, 25_000.0)

    raw = pd.DataFrame(
        {
            COL_WEEK: [
                value.strftime("%Y-%m-%d")
                for value in pd.date_range(
                    "2023-01-02",
                    periods=size,
                    freq="W-MON",
                )
            ],
            COL_OPEN: open_,
            COL_HIGH: high,
            COL_LOW: low,
            COL_CLOSE: close,
            COL_VOLUME: volume,
        }
    )
    return MetricsEngine().calculate(raw)


def candidate_signature(candidate: ScannerCandidate) -> tuple[object, ...]:
    """Stable semantic signature used before benchmark timings are accepted."""

    qualification = candidate.qualification_result
    return (
        candidate.bar_index,
        candidate.week,
        candidate.actionable,
        getattr(candidate.qualification, "value", candidate.qualification),
        candidate.reason,
        candidate.scoring_bar_index,
        candidate.scoring_evidence_age,
        candidate.signal_bar_index,
        candidate.signal_week,
        candidate.execution_bar_index,
        candidate.execution_week,
        candidate.execution_available,
        round(float(candidate.ranking_score), 12),
        round(float(candidate.net_strength), 12),
        round(float(candidate.net_pressure), 12),
        round(float(candidate.confidence), 12),
        getattr(qualification.qualification, "value", qualification.qualification),
        qualification.is_actionable_evidence,
        qualification.reason,
        tuple(getattr(item.code, "value", item.code) for item in candidate.qualifying_evidence),
        tuple(getattr(item.code, "value", item.code) for item in candidate.scoring_evidence),
    )


def assert_full_replay_parity(metrics: pd.DataFrame) -> int:
    """Require exact legacy-vs-transition candidate semantics before timing."""

    legacy = ScannerEngine().scan(metrics)
    transition = HistoricalScannerRunner().scan(metrics)

    legacy_signatures = tuple(candidate_signature(item) for item in legacy)
    transition_signatures = tuple(candidate_signature(item) for item in transition)
    if legacy_signatures != transition_signatures:
        raise AssertionError("legacy and transition full replay candidates differ")

    return len(legacy)


def _time_call(fn, *, repeats: int, warmups: int) -> TimingStats:
    if repeats <= 0:
        raise ValueError("repeats must be positive")
    if warmups < 0:
        raise ValueError("warmups must be >= 0")

    for _ in range(warmups):
        fn()

    durations: list[float] = []
    for _ in range(repeats):
        started = time.perf_counter()
        fn()
        durations.append(time.perf_counter() - started)

    return TimingStats(
        repeats=repeats,
        min_seconds=min(durations),
        median_seconds=statistics.median(durations),
        mean_seconds=statistics.fmean(durations),
        max_seconds=max(durations),
    )


def run_benchmark(
    *,
    bars: int = 192,
    repeats: int = 5,
    warmups: int = 1,
    seed: int = 20260918,
) -> TransitionBenchmarkResult:
    metrics = make_metrics(bars, seed=seed)
    candidate_count = assert_full_replay_parity(metrics)

    target_index = len(metrics) - 1
    checkpoint_index = target_index - 1

    transition = ScannerTransitionEngine()
    checkpoint_state, _ = transition.run_to_index(metrics, checkpoint_index)

    durable_state = ScannerTransitionSnapshotAdapter().snapshot(
        metrics,
        target_index=checkpoint_index,
        symbol="BENCH.NS",
        timeframe="1wk",
    )

    legacy_full = _time_call(
        lambda: ScannerEngine().scan(metrics),
        repeats=repeats,
        warmups=warmups,
    )
    transition_full = _time_call(
        lambda: HistoricalScannerRunner().scan(metrics),
        repeats=repeats,
        warmups=warmups,
    )
    one_new_bar = _time_call(
        lambda: ScannerTransitionEngine().run_to_index(
            metrics,
            target_index,
            state=checkpoint_state,
        ),
        repeats=repeats,
        warmups=warmups,
    )
    durable_resume = _time_call(
        lambda: ScannerTransitionResumeAdapter().resume_latest(
            metrics,
            durable_state,
        ),
        repeats=repeats,
        warmups=warmups,
    )

    transition_latest = ScannerTransitionEngine().run_to_index(
        metrics,
        target_index,
        state=checkpoint_state,
    )[1].candidate
    durable_latest = ScannerTransitionResumeAdapter().resume_latest(
        metrics,
        durable_state,
    )
    legacy_latest = ScannerEngine().scan_to_index(metrics, target_index)

    expected = candidate_signature(legacy_latest)
    if candidate_signature(transition_latest) != expected:
        raise AssertionError("one-new-bar transition candidate differs from legacy")
    if candidate_signature(durable_latest) != expected:
        raise AssertionError("durable one-new-bar resume candidate differs from legacy")

    full_speedup = (
        legacy_full.median_seconds / transition_full.median_seconds
        if transition_full.median_seconds > 0.0
        else float("inf")
    )
    one_bar_speedup = (
        legacy_full.median_seconds / one_new_bar.median_seconds
        if one_new_bar.median_seconds > 0.0
        else float("inf")
    )

    return TransitionBenchmarkResult(
        bars=len(metrics),
        candidate_count=candidate_count,
        legacy_full_replay=legacy_full,
        transition_full_replay=transition_full,
        transition_one_new_bar=one_new_bar,
        durable_resume_one_new_bar=durable_resume,
        full_replay_speedup=full_speedup,
        one_new_bar_vs_legacy_full_speedup=one_bar_speedup,
    )


def _print_result(result: TransitionBenchmarkResult) -> None:
    def ms(stats: TimingStats) -> float:
        return stats.median_seconds * 1000.0

    print(f"bars={result.bars}")
    print(f"candidate_count={result.candidate_count}")
    print(f"legacy_full_replay_median_ms={ms(result.legacy_full_replay):.3f}")
    print(f"transition_full_replay_median_ms={ms(result.transition_full_replay):.3f}")
    print(f"transition_one_new_bar_median_ms={ms(result.transition_one_new_bar):.3f}")
    print(f"durable_resume_one_new_bar_median_ms={ms(result.durable_resume_one_new_bar):.3f}")
    print(f"full_replay_speedup={result.full_replay_speedup:.3f}x")
    print(
        "one_new_bar_vs_legacy_full_speedup="
        f"{result.one_new_bar_vs_legacy_full_speedup:.3f}x"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark transition replay and one-new-bar scanner updates."
    )
    parser.add_argument("--bars", type=int, default=192)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--seed", type=int, default=20260918)
    parser.add_argument("--output-dir", type=Path, default=Path("benchmarks") / "results")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_benchmark(
        bars=args.bars,
        repeats=args.repeats,
        warmups=args.warmups,
        seed=args.seed,
    )
    _print_result(result)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    path = args.output_dir / f"transition_replay_{timestamp}.json"
    path.write_text(
        json.dumps(asdict(result), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
