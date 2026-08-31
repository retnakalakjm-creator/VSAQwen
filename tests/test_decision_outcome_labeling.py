import pandas as pd
import pytest

from decision_outcome_labeling import label_outcome


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "High": [100.0, 105.0, 108.0, 103.0, 112.0, 115.0],
            "Low": [98.0, 99.0, 101.0, 100.0, 102.0, 110.0],
            "Close": [99.0, 104.0, 106.0, 102.0, 110.0, 114.0],
        }
    )


def test_bullish_outcome_uses_only_future_bars() -> None:
    outcome = label_outcome(_frame(), signal_index=1, direction=1, horizon=3)

    assert outcome.complete is True
    assert outcome.entry_close == 104.0
    assert outcome.exit_close == 110.0
    assert outcome.forward_return == pytest.approx(110.0 / 104.0 - 1.0)
    assert outcome.maximum_favorable_excursion == pytest.approx(112.0 / 104.0 - 1.0)
    assert outcome.maximum_adverse_excursion == pytest.approx(1.0 - 100.0 / 104.0)


def test_bearish_outcome_reverses_favorable_and_adverse_excursion() -> None:
    outcome = label_outcome(_frame(), signal_index=1, direction=-1, horizon=3)

    assert outcome.complete is True
    assert outcome.forward_return == pytest.approx(1.0 - 110.0 / 104.0)
    assert outcome.maximum_favorable_excursion == pytest.approx(1.0 - 100.0 / 104.0)
    assert outcome.maximum_adverse_excursion == pytest.approx(112.0 / 104.0 - 1.0)


def test_incomplete_horizon_is_not_labeled() -> None:
    outcome = label_outcome(_frame(), signal_index=4, direction=1, horizon=3)

    assert outcome.complete is False
    assert outcome.forward_return is None
    assert outcome.maximum_favorable_excursion is None
    assert outcome.maximum_adverse_excursion is None


def test_invalid_arguments_fail() -> None:
    with pytest.raises(ValueError):
        label_outcome(_frame(), signal_index=1, direction=0, horizon=3)
    with pytest.raises(ValueError):
        label_outcome(_frame(), signal_index=1, direction=1, horizon=0)
    with pytest.raises(IndexError):
        label_outcome(_frame(), signal_index=99, direction=1, horizon=3)
