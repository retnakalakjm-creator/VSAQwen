from types import SimpleNamespace

import pytest

from robustness_demand_drying_up_audit import bootstrap_delta, summarize


def pair(horizon: int, target: float, control: float):
    return SimpleNamespace(
        target=SimpleNamespace(horizon=horizon, forward_return=target),
        control=SimpleNamespace(forward_return=control),
    )


def test_bootstrap_delta_uses_paired_target_control_difference() -> None:
    pairs = [pair(3, 0.02, 0.01), pair(3, 0.04, 0.01)]
    observed, low, high = bootstrap_delta(pairs, iterations=1000)
    assert observed == pytest.approx(0.02)
    assert low <= observed <= high


def test_bootstrap_delta_rejects_empty_pairs() -> None:
    with pytest.raises(ValueError, match="pairs must not be empty"):
        bootstrap_delta([], iterations=10)


def test_bootstrap_delta_rejects_non_positive_iterations() -> None:
    pairs = [pair(3, 0.01, 0.0)]
    with pytest.raises(ValueError, match="iterations must be greater than zero"):
        bootstrap_delta(pairs, iterations=0)


def test_summarize_splits_pairs_by_horizon() -> None:
    pairs = [
        pair(3, 0.01, 0.0),
        pair(3, 0.03, 0.0),
        pair(5, -0.01, 0.0),
    ]
    rows = summarize(pairs, iterations=1000)
    by_horizon = {row["horizon"]: row for row in rows}
    assert by_horizon[3]["pairs"] == 2
    assert by_horizon[5]["pairs"] == 1
    assert by_horizon[3]["observed_delta"] == pytest.approx(0.02)
    assert by_horizon[5]["observed_delta"] == pytest.approx(-0.01)
