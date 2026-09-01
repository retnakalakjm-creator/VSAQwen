from __future__ import annotations

from types import SimpleNamespace

import pytest

from stratified_demand_drying_up_audit import summarize


def _pair(state: str, direction: str, horizon: int, delta: float):
    return SimpleNamespace(
        target=SimpleNamespace(
            state=state,
            direction=direction,
            horizon=horizon,
            forward_return=delta + 0.01,
        ),
        control=SimpleNamespace(forward_return=0.01),
    )


def test_stratified_summary_groups_by_state_direction_and_horizon() -> None:
    rows = summarize([
        _pair("healthy", "bullish", 3, 0.02),
        _pair("healthy", "bullish", 3, -0.01),
        _pair("correcting", "bullish", 5, -0.03),
    ])

    assert rows[0] == {
        "state": "correcting",
        "direction": "bullish",
        "horizon": 5,
        "pairs": 1,
        "positive": 0,
        "mean_delta": pytest.approx(-0.03),
    }
    assert rows[1] == {
        "state": "healthy",
        "direction": "bullish",
        "horizon": 3,
        "pairs": 2,
        "positive": 1,
        "mean_delta": pytest.approx(0.005),
    }


def test_empty_pairs_return_empty_summary() -> None:
    assert summarize([]) == []
