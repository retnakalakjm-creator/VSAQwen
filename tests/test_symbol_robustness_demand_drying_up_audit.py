from __future__ import annotations

from types import SimpleNamespace

import pytest

from symbol_robustness_demand_drying_up_audit import (
    leave_one_symbol_out,
    summarize_symbol_robustness,
)


def _pair(symbol: str, horizon: int, target: float, control: float):
    return SimpleNamespace(
        target=SimpleNamespace(
            symbol=symbol,
            horizon=horizon,
            forward_return=target,
        ),
        control=SimpleNamespace(forward_return=control),
    )


def test_symbol_robustness_filters_small_buckets() -> None:
    pairs = [
        _pair("A", 3, 0.00, 0.02),
        _pair("A", 3, -0.02, 0.00),
        _pair("A", 3, -0.03, 0.00),
        _pair("B", 3, -0.10, 0.00),
    ]
    rows = summarize_symbol_robustness(pairs, iterations=100, min_cases=3)
    assert [(r["symbol"], r["horizon"]) for r in rows] == [("A", 3)]
    assert rows[0]["observed_delta"] == pytest.approx(-0.0233333333)


def test_leave_one_symbol_out_preserves_horizon() -> None:
    pairs = [
        _pair("A", 3, 0.03, 0.01),
        _pair("B", 3, -0.03, 0.01),
        _pair("A", 5, 0.02, 0.01),
        _pair("B", 5, 0.04, 0.01),
    ]
    rows = leave_one_symbol_out(pairs)
    a3 = next(r for r in rows if r["excluded_symbol"] == "A" and r["horizon"] == 3)
    assert a3["pairs"] == 1
    assert a3["mean_delta"] == pytest.approx(-0.04)
