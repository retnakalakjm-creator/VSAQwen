from types import SimpleNamespace

import pytest

from robustness_hidden_demand_audit import bootstrap_delta, summarize


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


def test_summarize_classifies_robust_direction() -> None:
    pairs = [
        pair(3, 0.04, 0.00),
        pair(3, 0.05, 0.00),
        pair(3, 0.03, 0.00),
    ]
    rows = summarize(pairs, iterations=1000)
    row = next(item for item in rows if item["horizon"] == 3)
    assert row["observed_delta"] == pytest.approx(0.04)
    assert row["robust"] == "positive"
