from __future__ import annotations

from dataclasses import dataclass

from stratified_demand_coming_in_audit import summarize


@dataclass(frozen=True, slots=True)
class Case:
    state: str
    direction: str
    horizon: int
    forward_return: float


@dataclass(frozen=True, slots=True)
class Pair:
    target: Case
    control: Case


def test_summarize_stratifies_by_state_direction_and_horizon() -> None:
    rows = summarize([
        Pair(Case("healthy", "bullish", 3, 0.04), Case("healthy", "bullish", 3, 0.01)),
        Pair(Case("healthy", "bullish", 3, 0.00), Case("healthy", "bullish", 3, 0.01)),
        Pair(Case("correcting", "bullish", 5, 0.02), Case("correcting", "bullish", 5, 0.00)),
    ])

    assert len(rows) == 2
    assert rows[0]["state"] == "correcting"
    assert rows[1]["state"] == "healthy"
    assert rows[1]["direction"] == "bullish"
    assert rows[1]["horizon"] == 3
    assert rows[1]["pairs"] == 2
    assert rows[1]["positive"] == 1


def test_summarize_empty_pairs() -> None:
    assert summarize([]) == []
