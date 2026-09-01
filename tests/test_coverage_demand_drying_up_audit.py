from __future__ import annotations

from types import SimpleNamespace

import pytest

from coverage_demand_drying_up_audit import (
    summarize_by_symbol,
    summarize_by_symbol_context,
    stable_symbol_counts,
)


def _pair(symbol: str, state: str, direction: str, horizon: int, delta: float):
    return SimpleNamespace(
        target=SimpleNamespace(
            symbol=symbol,
            state=state,
            direction=direction,
            horizon=horizon,
            forward_return=delta + 0.01,
        ),
        control=SimpleNamespace(forward_return=0.01),
    )


def test_symbol_summary_groups_by_symbol_and_horizon() -> None:
    rows = summarize_by_symbol([
        _pair("AAA.NS", "healthy", "bullish", 3, 0.02),
        _pair("AAA.NS", "healthy", "bullish", 3, -0.01),
        _pair("BBB.NS", "healthy", "bearish", 5, -0.03),
    ])

    assert rows[0] == {
        "symbol": "AAA.NS",
        "horizon": 3,
        "pairs": 2,
        "mean_delta": pytest.approx(0.005),
        "positive": 1,
    }
    assert rows[1]["symbol"] == "BBB.NS"


def test_symbol_context_summary_preserves_context() -> None:
    rows = summarize_by_symbol_context([
        _pair("AAA.NS", "healthy", "bullish", 3, 0.02),
        _pair("AAA.NS", "correcting", "bullish", 3, -0.04),
    ])

    assert len(rows) == 2
    assert rows[0]["state"] == "correcting"
    assert rows[0]["direction"] == "bullish"
    assert rows[0]["mean_delta"] == pytest.approx(-0.04)


def test_stable_symbol_counts_uses_minimum_cases() -> None:
    rows = [
        {"symbol": "AAA.NS", "horizon": 3, "pairs": 3},
        {"symbol": "AAA.NS", "horizon": 5, "pairs": 2},
        {"symbol": "BBB.NS", "horizon": 3, "pairs": 4},
    ]
    assert stable_symbol_counts(rows, min_cases=3) == {
        ("AAA.NS", 3): 1,
        ("BBB.NS", 3): 1,
    }


def test_empty_pairs_return_empty() -> None:
    assert summarize_by_symbol([]) == []
    assert summarize_by_symbol_context([]) == []
