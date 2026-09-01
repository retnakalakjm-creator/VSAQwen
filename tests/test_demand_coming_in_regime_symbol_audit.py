from __future__ import annotations

from coverage_demand_coming_in_audit import summarize_by_symbol, stable_symbol_counts


class Obj:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class Pair:
    def __init__(self, target_return, control_return, **target_kwargs):
        self.target = Obj(forward_return=target_return, **target_kwargs)
        self.control = Obj(forward_return=control_return)


def test_summarize_by_symbol_filters_to_significant_regimes() -> None:
    pairs = [
        Pair(0.05, 0.01, symbol="A", state="correcting", direction="bullish", horizon=3),
        Pair(0.01, 0.02, symbol="A", state="healthy", direction="bullish", horizon=3),
        Pair(0.03, 0.01, symbol="B", state="healthy", direction="bearish", horizon=10),
    ]
    rows = summarize_by_symbol(pairs)
    assert {(r["symbol"], r["state"], r["direction"], r["horizon"]) for r in rows} == {
        ("A", "correcting", "bullish", 3),
        ("B", "healthy", "bearish", 10),
    }


def test_summarize_by_symbol_computes_delta_and_positive_count() -> None:
    rows = summarize_by_symbol([
        Pair(0.05, 0.01, symbol="A", state="correcting", direction="bullish", horizon=3),
        Pair(0.00, 0.02, symbol="A", state="correcting", direction="bullish", horizon=3),
    ])
    assert rows[0]["pairs"] == 2
    assert rows[0]["mean_delta"] == 0.01
    assert rows[0]["positive"] == 1


def test_stable_symbol_counts_uses_minimum_case_threshold() -> None:
    rows = [
        {"symbol": "A", "state": "correcting", "direction": "bullish", "horizon": 3, "pairs": 3},
        {"symbol": "A", "state": "correcting", "direction": "bullish", "horizon": 5, "pairs": 3},
        {"symbol": "B", "state": "healthy", "direction": "bearish", "horizon": 10, "pairs": 2},
    ]
    counts = stable_symbol_counts(rows, min_cases=3)
    assert counts[("A", "correcting", "bullish")] == 2
    assert ("B", "healthy", "bearish") not in counts
