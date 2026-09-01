from __future__ import annotations

from types import SimpleNamespace

import pytest

from conditional_demand_drying_up_audit import (
    context_case_counts,
    summarize_by_context,
    summarize_context_set,
)


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


def test_context_set_filters_exact_state_direction_horizon() -> None:
    contexts = frozenset({("healthy", "bearish", 3)})
    pairs = [
        _pair("healthy", "bearish", 3, -0.04),
        _pair("healthy", "bullish", 3, 0.05),
        _pair("healthy", "bearish", 5, -0.02),
    ]
    rows = summarize_context_set(pairs, contexts, iterations=100, min_cases=1)
    assert rows[0]["horizon"] == 3
    assert rows[0]["pairs"] == 1
    assert rows[0]["observed_delta"] == pytest.approx(-0.04)


def test_context_set_respects_minimum_cases() -> None:
    contexts = frozenset({("healthy", "bearish", 3)})
    pairs = [_pair("healthy", "bearish", 3, -0.04)]
    assert summarize_context_set(pairs, contexts, min_cases=2) == []


def test_context_summary_groups_state_direction_and_horizon() -> None:
    pairs = [
        _pair("healthy", "bearish", 3, -0.02),
        _pair("healthy", "bearish", 3, -0.04),
    ]
    rows = summarize_by_context(pairs, iterations=100, min_cases=1)
    assert rows[0]["state"] == "healthy"
    assert rows[0]["direction"] == "bearish"
    assert rows[0]["horizon"] == 3
    assert rows[0]["observed_delta"] == pytest.approx(-0.03)


def test_context_case_counts() -> None:
    contexts = frozenset({("healthy", "bearish", 3), ("healthy", "bullish", 5)})
    pairs = [
        _pair("healthy", "bearish", 3, -0.02),
        _pair("healthy", "bullish", 5, -0.01),
        _pair("healthy", "bearish", 3, 0.01),
    ]
    assert context_case_counts(pairs, contexts) == {3: 2, 5: 1, 10: 0}
