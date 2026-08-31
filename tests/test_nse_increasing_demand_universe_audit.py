from __future__ import annotations

from run_nse_increasing_demand_universe_audit import SYMBOLS


def test_universe_has_expected_size() -> None:
    assert len(SYMBOLS) == 30
    assert len(set(SYMBOLS)) == 30


def test_universe_contains_existing_reference_symbols() -> None:
    assert {"RELIANCE.NS", "TCS.NS", "INFY.NS"}.issubset(SYMBOLS)
