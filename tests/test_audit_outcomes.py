import math

import pandas as pd
import pytest

from audit.outcomes import (
    OutcomeSide,
    compute_forward_outcome,
    compute_forward_outcomes,
    normalize_outcome_side,
)
from models import EvidenceDirection


def _bars() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "close": [100.0, 102.0, 105.0, 101.0, 108.0, 104.0],
            "high": [101.0, 103.0, 106.0, 102.0, 110.0, 105.0],
            "low": [99.0, 101.0, 104.0, 100.0, 107.0, 103.0],
        }
    )


def test_forward_outcome_uses_next_bar_execution_and_requested_horizon() -> None:
    outcome = compute_forward_outcome(
        _bars(),
        signal_bar_index=0,
        horizon_bars=3,
        side=OutcomeSide.LONG,
    )

    assert outcome is not None
    assert outcome.signal_bar_index == 0
    assert outcome.execution_bar_index == 1
    assert outcome.exit_bar_index == 4
    assert outcome.entry_price == 102.0
    assert outcome.exit_price == 108.0
    assert outcome.complete is True
    assert outcome.bars_available == 3
    assert outcome.raw_return == pytest.approx(108.0 / 102.0 - 1.0)
    assert outcome.favorable_return == pytest.approx(outcome.raw_return)
    assert outcome.mfe == pytest.approx(110.0 / 102.0 - 1.0)
    assert outcome.mae == pytest.approx(100.0 / 102.0 - 1.0)


def test_bearish_outcome_converts_down_move_to_favorable_return() -> None:
    outcome = compute_forward_outcome(
        _bars(),
        signal_bar_index=1,
        horizon_bars=2,
        side=EvidenceDirection.BEARISH,
    )

    assert outcome is not None
    assert outcome.execution_bar_index == 2
    assert outcome.exit_bar_index == 4
    assert outcome.raw_return == pytest.approx(108.0 / 105.0 - 1.0)
    assert outcome.favorable_return == pytest.approx(-(108.0 / 105.0 - 1.0))
    assert outcome.mfe == pytest.approx(105.0 / 100.0 - 1.0)
    assert outcome.mae == pytest.approx(min(105.0 / 110.0 - 1.0, 0.0))


def test_latest_signal_without_execution_bar_is_not_scored() -> None:
    assert compute_forward_outcome(
        _bars(),
        signal_bar_index=5,
        horizon_bars=1,
        side="bullish",
    ) is None


def test_partial_horizon_is_retained_but_marked_incomplete() -> None:
    outcome = compute_forward_outcome(
        _bars(),
        signal_bar_index=3,
        horizon_bars=4,
        side="long",
    )

    assert outcome is not None
    assert outcome.execution_bar_index == 4
    assert outcome.exit_bar_index == 5
    assert outcome.bars_available == 1
    assert outcome.complete is False


def test_invalid_inputs_raise_clear_errors() -> None:
    with pytest.raises(ValueError, match="horizon_bars"):
        compute_forward_outcome(_bars(), signal_bar_index=0, horizon_bars=0, side="long")

    with pytest.raises(IndexError, match="signal_bar_index"):
        compute_forward_outcome(_bars(), signal_bar_index=-1, horizon_bars=1, side="long")

    with pytest.raises(ValueError, match="Missing required price columns"):
        compute_forward_outcome(
            pd.DataFrame({"close": [1.0, 2.0]}),
            signal_bar_index=0,
            horizon_bars=1,
            side="long",
        )


def test_direction_normalization_accepts_scanner_values() -> None:
    assert normalize_outcome_side(EvidenceDirection.BULLISH) is OutcomeSide.LONG
    assert normalize_outcome_side(EvidenceDirection.BEARISH) is OutcomeSide.SHORT
    assert normalize_outcome_side(EvidenceDirection.NEUTRAL) is OutcomeSide.NEUTRAL
    assert normalize_outcome_side(1) is OutcomeSide.LONG
    assert normalize_outcome_side(-1) is OutcomeSide.SHORT
    assert normalize_outcome_side("buy") is OutcomeSide.LONG
    assert normalize_outcome_side("sell") is OutcomeSide.SHORT
    assert normalize_outcome_side("flat") is OutcomeSide.NEUTRAL

    with pytest.raises(ValueError, match="Unsupported outcome side"):
        normalize_outcome_side("sideways-but-not-supported")


def test_batch_outcomes_preserve_signal_then_horizon_order() -> None:
    outcomes = compute_forward_outcomes(
        _bars(),
        signal_bar_indices=[0, 4, 1],
        horizons=[1, 2],
        side="long",
    )

    # Signal 4 has an execution bar but no future bar after execution; both
    # requested horizons are retained as incomplete zero-bar outcomes.
    assert [
        (item.signal_bar_index, item.horizon_bars, item.execution_bar_index)
        for item in outcomes
    ] == [
        (0, 1, 1),
        (0, 2, 1),
        (4, 1, 5),
        (4, 2, 5),
        (1, 1, 2),
        (1, 2, 2),
    ]
    assert math.isfinite(outcomes[0].raw_return)
