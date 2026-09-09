from __future__ import annotations

import pandas as pd
import pytest

from engine.columns import (
    COL_CLOSE,
    COL_CLOSE_RATIO,
    COL_OPEN,
    COL_PRICE_CHANGE_PCT,
    COL_SPREAD_RATIO,
    COL_VOLUME_RATIO,
    COL_WEEK,
)
from weekly_bar_interpreter import (
    MAX_WEEKLY_BAR_READING_LOOKBACK,
    build_weekly_bar_readings,
)


def _metrics_frame(rows: int = 16) -> pd.DataFrame:
    weeks = pd.date_range("2026-05-18", periods=rows, freq="W-MON")
    data = []
    for index, week in enumerate(weeks):
        data.append(
            {
                COL_WEEK: week,
                COL_OPEN: 100.0 + index,
                COL_CLOSE: 104.0 + index,
                COL_SPREAD_RATIO: 1.25,
                COL_VOLUME_RATIO: 1.20,
                COL_CLOSE_RATIO: 0.78,
                COL_PRICE_CHANGE_PCT: 2.0,
            }
        )
    return pd.DataFrame(data)


def test_build_weekly_bar_readings_returns_requested_tail_window() -> None:
    readings = build_weekly_bar_readings(_metrics_frame(), lookback=10)

    assert len(readings) == 10
    assert readings[0].week == "2026-06-29 00:00:00"
    assert readings[-1].week == "2026-08-31 00:00:00"
    assert set(readings[0].to_dict()) == {"week", "professional_reading"}
    assert "Sign of Strength" in readings[-1].professional_reading
    assert "Bias: Bullish." in readings[-1].professional_reading


def test_build_weekly_bar_readings_interprets_low_effort_decline_as_no_supply_style() -> None:
    metrics = _metrics_frame(rows=2)
    metrics.loc[1, COL_OPEN] = 110.0
    metrics.loc[1, COL_CLOSE] = 105.0
    metrics.loc[1, COL_SPREAD_RATIO] = 0.70
    metrics.loc[1, COL_VOLUME_RATIO] = 0.60
    metrics.loc[1, COL_CLOSE_RATIO] = 0.30

    reading = build_weekly_bar_readings(metrics, lookback=1)[0]

    assert "without strong selling effort" in reading.professional_reading
    assert "Bias: Neutral to Mildly Bullish." in reading.professional_reading


@pytest.mark.parametrize("lookback", [0, -1, MAX_WEEKLY_BAR_READING_LOOKBACK + 1])
def test_build_weekly_bar_readings_rejects_invalid_lookback(lookback: int) -> None:
    with pytest.raises(ValueError):
        build_weekly_bar_readings(_metrics_frame(), lookback=lookback)
