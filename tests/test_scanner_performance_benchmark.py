import pytest

from benchmarks.benchmark_scanner_performance import _select_symbols


def test_select_symbols_requires_large_universe_without_repeat() -> None:
    with pytest.raises(ValueError, match="Need at least 3 unique symbols"):
        _select_symbols(["SRF.NS"], count=3, allow_repeat=False)


def test_select_symbols_can_repeat_for_smoke_tests() -> None:
    assert _select_symbols(["SRF.NS", "TCS.NS"], count=5, allow_repeat=True) == [
        "SRF.NS",
        "TCS.NS",
        "SRF.NS",
        "TCS.NS",
        "SRF.NS",
    ]


def test_select_symbols_preserves_first_n_symbols() -> None:
    assert _select_symbols(
        ["SRF.NS", "TCS.NS", "INFY.NS"],
        count=2,
        allow_repeat=False,
    ) == ["SRF.NS", "TCS.NS"]
