from __future__ import annotations

import pandas as pd

import config
from engine.columns import (
    COL_AVG_SPREAD,
    COL_CLOSE,
    COL_HIGH,
    COL_LOW,
    COL_OPEN,
    COL_VOLUME,
    COL_WEEK,
)
from market_structure.swing_engine import SwingEngine
from tests.incremental_equivalence_harness import (
    compare_state,
    compare_swing_sequences,
    run_equivalence_case,
    snapshot_after_prefix,
)


def _metrics() -> pd.DataFrame:
    weeks = [f"W{i:03d}" for i in range(60)]
    highs = [100.0 + (i % 7) for i in range(60)]
    lows = [98.0 + (i % 7) for i in range(60)]
    closes = [(highs[i] + lows[i]) / 2 for i in range(60)]
    return pd.DataFrame(
        {
            COL_HIGH: highs,
            COL_LOW: lows,
            COL_OPEN: closes,
            COL_CLOSE: closes,
            COL_VOLUME: [1000.0 + i for i in range(60)],
            COL_WEEK: weeks,
            COL_AVG_SPREAD: [2.0] * 60,
        }
    )


def test_snapshot_retains_only_structural_lookback() -> None:
    metrics = _metrics()
    engine = SwingEngine()
    engine.calculate(metrics)
    state = engine.snapshot_state("TEST", "weekly")

    assert len(state.confirmed_swings) <= config.STRUCTURE_LOOKBACK


def test_snapshot_state_round_trip_is_stable() -> None:
    metrics = _metrics()
    state = snapshot_after_prefix(
        metrics,
        symbol="TEST",
        timeframe="weekly",
        split_index=40,
    )
    assert compare_state(state, type(state).from_dict(state.to_dict()))


def test_checkpoint_continuation_matches_full_history() -> None:
    metrics = _metrics()
    result = run_equivalence_case(
        metrics,
        symbol="TEST",
        timeframe="weekly",
        split_index=40,
    )
    assert result.equivalent
    assert result.equal_swings
    assert result.equal_state


def test_swing_sequence_comparison_uses_stable_identity() -> None:
    metrics = _metrics()
    engine = SwingEngine()
    swings = engine.calculate(metrics)
    assert compare_swing_sequences(
        swings,
        tuple(swings),
        full_metrics=metrics,
        incremental_metrics=metrics,
    )
