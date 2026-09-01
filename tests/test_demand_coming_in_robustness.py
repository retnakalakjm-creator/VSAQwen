from __future__ import annotations

import pytest

from matched_demand_coming_in_audit import MatchedPair
from robustness_demand_coming_in_audit import bootstrap_delta, summarize


def _pair(horizon: int, target: float, control: float) -> MatchedPair:
    class Case:
        def __init__(self, value: float) -> None:
            self.forward_return = value
            self.horizon = horizon

    return MatchedPair(
        target=Case(target),
        control=Case(control),
        score_gap=0.0,
        pressure_gap=0.0,
        age_gap=0,
    )


def test_bootstrap_delta_matches_observed_mean() -> None:
    pairs = [_pair(3, 0.03, 0.01), _pair(3, 0.00, 0.01), _pair(3, 0.04, 0.02)]
    observed, low, high = bootstrap_delta(pairs, iterations=500)
    assert observed == pytest.approx((0.02 - 0.01 + 0.02) / 3)
    assert low <= observed <= high


def test_bootstrap_delta_rejects_empty_pairs() -> None:
    with pytest.raises(ValueError):
        bootstrap_delta([])


def test_bootstrap_delta_rejects_invalid_iterations() -> None:
    with pytest.raises(ValueError):
        bootstrap_delta([_pair(3, 0.02, 0.01)], iterations=0)


def test_summarize_returns_all_required_horizons() -> None:
    pairs = [_pair(3, 0.03, 0.01), _pair(5, 0.04, 0.01), _pair(10, 0.05, 0.01)]
    rows = summarize(pairs, iterations=200)
    assert [row["horizon"] for row in rows] == [3, 5, 10]


def test_runner_uses_5000_bootstrap_default() -> None:
    from pathlib import Path
    source = Path(__file__).with_name("run_demand_coming_in_robustness.py").read_text(encoding="utf-8")
    assert "default=5000" in source
