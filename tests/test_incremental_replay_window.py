from __future__ import annotations

import pandas as pd
import pytest

from data import METRIC_REPLAY_SEED_BARS, incremental_replay_window
from models import SwingSearchState, SwingType
from scanner_state import CandidateState, ConfirmedSwingState, ScannerState


def _weekly(size: int = 100) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "week_beginning": [f"2025-W{i + 1:03d}" for i in range(size)],
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.0,
            "volume": 1000.0,
        }
    )


def _state() -> ScannerState:
    return ScannerState(
        schema_version=2,
        symbol="TEST.NS",
        timeframe="1w",
        last_closed_bar="2025-W080",
        search_state=SwingSearchState.TRACKING_LOW,
        candidate=CandidateState(
            bar_key="2025-W080",
            type=SwingType.LOW,
            price=98.0,
        ),
        confirmed_swings=(
            ConfirmedSwingState(
                pivot_bar_key="2025-W055",
                confirmation_bar_key="2025-W058",
                type=SwingType.HIGH,
                price=110.0,
            ),
            ConfirmedSwingState(
                pivot_bar_key="2025-W070",
                confirmation_bar_key="2025-W073",
                type=SwingType.LOW,
                price=101.0,
            ),
        ),
    )


def test_replay_window_preserves_state_and_metric_seed() -> None:
    weekly = _weekly()
    window = incremental_replay_window(weekly, _state())

    earliest_required_index = 54  # 2025-W055 is the 55th row.
    expected_start = max(0, earliest_required_index - METRIC_REPLAY_SEED_BARS)

    assert str(window.iloc[0]["week_beginning"]) == str(
        weekly.iloc[expected_start]["week_beginning"]
    )
    assert str(window.iloc[-1]["week_beginning"]) == "2025-W100"


def test_replay_window_rejects_missing_state_identity() -> None:
    weekly = _weekly().iloc[:79].reset_index(drop=True)

    with pytest.raises(ValueError, match="State identities not present"):
        incremental_replay_window(weekly, _state())


def test_replay_window_rejects_duplicate_bar_identity() -> None:
    weekly = _weekly()
    weekly.loc[10, "week_beginning"] = weekly.loc[9, "week_beginning"]

    with pytest.raises(ValueError, match="Duplicate weekly bar identity"):
        incremental_replay_window(weekly, _state())
