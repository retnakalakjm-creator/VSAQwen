from __future__ import annotations

import pytest

from stratified_demand_coming_in_robustness import bootstrap_bucket, summarize


class Case:
    def __init__(self, state: str, direction: str, horizon: int, value: float) -> None:
        self.state = state
        self.direction = direction
        self.horizon = horizon
        self.forward_return = value


class Pair:
    def __init__(self, target: Case, control: Case) -> None:
        self.target = target
        self.control = control


def _pair(state: str, direction: str, horizon: int, target: float, control: float) -> Pair:
    return Pair(
        Case(state, direction, horizon, target),
        Case(state, direction, horizon, control),
    )


def test_bootstrap_bucket_matches_observed_mean() -> None:
    pairs = [
        _pair("healthy", "bullish", 3, 0.03, 0.01),
        _pair("healthy", "bullish", 3, 0.00, 0.01),
        _pair("healthy", "bullish", 3, 0.04, 0.02),
    ]
    observed, low, high, positive = bootstrap_bucket(pairs, iterations=500)
    assert observed == pytest.approx((0.02 - 0.01 + 0.02) / 3)
    assert low <= observed <= high
    assert positive == 2


def test_bootstrap_bucket_rejects_empty_input() -> None:
    with pytest.raises(ValueError):
        bootstrap_bucket([])


def test_bootstrap_bucket_rejects_invalid_iterations() -> None:
    with pytest.raises(ValueError):
        bootstrap_bucket([_pair("healthy", "bullish", 3, 0.02, 0.01)], iterations=0)


def test_summarize_groups_state_direction_and_horizon() -> None:
    pairs = [
        _pair("healthy", "bullish", 3, 0.03, 0.01),
        _pair("healthy", "bullish", 3, 0.02, 0.01),
        _pair("healthy", "bearish", 3, 0.01, 0.00),
        _pair("healthy", "bearish", 5, 0.02, 0.00),
    ]
    rows = summarize(pairs, iterations=200)
    keys = [(r["state"], r["direction"], r["horizon"]) for r in rows]
    assert keys == [
        ("healthy", "bearish", 3),
        ("healthy", "bearish", 5),
        ("healthy", "bullish", 3),
    ]


def test_summarize_reports_confidence_interval() -> None:
    pairs = [_pair("healthy", "bearish", 10, 0.05, 0.01)]
    row = summarize(pairs, iterations=200)[0]
    assert row["pairs"] == 1
    assert row["ci_low"] == pytest.approx(0.04)
    assert row["ci_high"] == pytest.approx(0.04)
