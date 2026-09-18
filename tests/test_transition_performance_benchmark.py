from __future__ import annotations

from benchmarks.benchmark_transition_replay import (
    assert_full_replay_parity,
    candidate_signature,
    make_metrics,
    run_benchmark,
)
from scanner import ScannerEngine
from scanner_transition import ScannerTransitionEngine


def test_transition_benchmark_fixture_preserves_full_replay_semantics() -> None:
    metrics = make_metrics(48, seed=7)

    assert assert_full_replay_parity(metrics) == len(metrics) - ScannerEngine.MIN_REPLAY_BARS


def test_one_new_bar_transition_matches_legacy_on_benchmark_fixture() -> None:
    metrics = make_metrics(48, seed=11)
    target_index = len(metrics) - 1
    checkpoint_index = target_index - 1

    transition = ScannerTransitionEngine()
    state, _ = transition.run_to_index(metrics, checkpoint_index)
    candidate = transition.run_to_index(
        metrics,
        target_index,
        state=state,
    )[1].candidate
    legacy = ScannerEngine().scan_to_index(metrics, target_index)

    assert candidate_signature(candidate) == candidate_signature(legacy)


def test_benchmark_reports_positive_timings_without_machine_speed_threshold() -> None:
    result = run_benchmark(
        bars=40,
        repeats=1,
        warmups=0,
        seed=23,
    )

    assert result.bars == 40
    assert result.candidate_count == 40 - ScannerEngine.MIN_REPLAY_BARS
    assert result.legacy_full_replay.median_seconds > 0.0
    assert result.transition_full_replay.median_seconds > 0.0
    assert result.transition_one_new_bar.median_seconds > 0.0
    assert result.durable_resume_one_new_bar.median_seconds > 0.0
    assert result.full_replay_speedup > 0.0
    assert result.one_new_bar_vs_legacy_full_speedup > 0.0
