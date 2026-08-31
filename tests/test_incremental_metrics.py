from __future__ import annotations

import numpy as np
import pandas as pd

import config
from engine.columns import (
    COL_AVG_SPREAD,
    COL_AVG_VOLUME,
    COL_BODY,
    COL_CLOSE,
    COL_CLOSE_POSITION,
    COL_CLOSE_RATIO,
    COL_DIRECTION,
    COL_HIGH,
    COL_LOW,
    COL_LOWER_SHADOW,
    COL_OPEN,
    COL_PRICE_CHANGE,
    COL_PRICE_CHANGE_PCT,
    COL_PREV_CLOSE,
    COL_PREV_HIGH,
    COL_PREV_LOW,
    COL_SPREAD,
    COL_SPREAD_CLASS,
    COL_SPREAD_PERCENTILE,
    COL_SPREAD_RATIO,
    COL_STD_SPREAD,
    COL_STD_VOLUME,
    COL_UPPER_SHADOW,
    COL_VOLUME,
    COL_VOLUME_CLASS,
    COL_VOLUME_PERCENTILE,
    COL_VOLUME_RATIO,
    COL_WEEK,
)
from metrics_engine import MetricsEngine


def _bars(size: int = 100) -> pd.DataFrame:
    index = np.arange(size, dtype=float)
    close = 100.0 + np.sin(index / 3.0) * 4.0 + index * 0.12
    spread = 1.0 + (index % 5) * 0.15
    volume = 1000.0 + (index % 7) * 75.0 + index * 2.0

    return pd.DataFrame(
        {
            COL_WEEK: [f"2025-W{i + 1:02d}" for i in range(size)],
            COL_OPEN: close - 0.25,
            COL_HIGH: close + spread / 2.0,
            COL_LOW: close - spread / 2.0,
            COL_CLOSE: close,
            COL_VOLUME: volume,
        }
    )


_METRIC_COLUMNS = (
    COL_SPREAD,
    COL_BODY,
    COL_UPPER_SHADOW,
    COL_LOWER_SHADOW,
    COL_CLOSE_RATIO,
    COL_PREV_HIGH,
    COL_PREV_LOW,
    COL_PREV_CLOSE,
    COL_PRICE_CHANGE,
    COL_PRICE_CHANGE_PCT,
    COL_AVG_VOLUME,
    COL_AVG_SPREAD,
    COL_STD_VOLUME,
    COL_STD_SPREAD,
    COL_VOLUME_RATIO,
    COL_SPREAD_RATIO,
    COL_SPREAD_PERCENTILE,
    COL_VOLUME_PERCENTILE,
    COL_SPREAD_CLASS,
    COL_VOLUME_CLASS,
    COL_DIRECTION,
    COL_CLOSE_POSITION,
)


def test_seeded_metrics_match_full_history_after_seed_boundary() -> None:
    bars = _bars()
    full = MetricsEngine().calculate(bars)

    split = 50
    seed = config.LOOKBACK_PERIOD * 2
    seeded_input = bars.iloc[split - seed :].reset_index(drop=True)
    seeded = MetricsEngine().calculate(seeded_input)

    expected = full.iloc[split:].reset_index(drop=True)
    actual = seeded.iloc[seed:].reset_index(drop=True)

    for column in _METRIC_COLUMNS:
        expected_values = expected[column].reset_index(drop=True)
        actual_values = actual[column].reset_index(drop=True)

        if pd.api.types.is_numeric_dtype(expected_values):
            try:
                np.testing.assert_allclose(
                    actual_values.to_numpy(dtype=float),
                    expected_values.to_numpy(dtype=float),
                    equal_nan=True,
                )
            except AssertionError as exc:
                diff = ~np.isclose(
                    actual_values.to_numpy(dtype=float),
                    expected_values.to_numpy(dtype=float),
                    equal_nan=True,
                )
                first = int(np.flatnonzero(diff)[0])
                raise AssertionError(
                    f"Metric continuity mismatch: column={column!r}, "
                    f"relative_row={first}, expected="
                    f"{expected_values.iloc[first]!r}, actual="
                    f"{actual_values.iloc[first]!r}"
                ) from exc
        else:
            assert actual_values.tolist() == expected_values.tolist(), (
                f"Metric continuity mismatch: column={column!r}"
            )


def test_metric_raw_seed_requirement_accounts_for_nested_rolling() -> None:
    assert config.LOOKBACK_PERIOD == 20
    assert config.LOOKBACK_PERIOD * 2 == 40
