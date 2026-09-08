"""
Professional VSA Swing Scanner

Metrics Engine

Produces all quantitative market metrics required by the
Trend Engine, Background Engine and Pattern Engine.

No VSA interpretation is performed here.
"""

from __future__ import annotations

import pandas as pd

from classifiers import (
    classify_close_position,
    classify_direction,
    classify_spread,
    classify_volume,
)
from engine.columns import (
    COL_AVG_VOLUME, COL_HIGH, COL_LOW, COL_SPREAD, COL_CLOSE,
    COL_OPEN, COL_BODY, COL_SPREAD_RATIO, COL_STD_SPREAD, COL_STD_VOLUME, COL_VOLUME,
    COL_VOLUME_RATIO, COL_SPREAD_PERCENTILE,
    COL_VOLUME_PERCENTILE, COL_SPREAD_CLASS, COL_VOLUME_CLASS,
    COL_DIRECTION, COL_CLOSE_POSITION,
    COL_UPPER_SHADOW, COL_LOWER_SHADOW,
    COL_CLOSE_RATIO, COL_PRICE_CHANGE,
    COL_PRICE_CHANGE_PCT, COL_PREV_CLOSE, COL_AVG_SPREAD,
    COL_PREV_HIGH, COL_PREV_LOW, COL_WEEK,
    COL_PRICE_GAP_RATIO, COL_PRICE_ANOMALY, COL_VOLUME_ANOMALY,
    COL_CORPORATE_ACTION_ANOMALY,
)

import config
from models import ClosePosition, Direction, SpreadClass, VolumeClass
from stats_utils import (
    historical_percentile_rank,
    rolling_mean,
    rolling_std,
)

DEFAULT_CORPORATE_ACTION_PRICE_GAP_RATIO = 0.35
DEFAULT_CORPORATE_ACTION_VOLUME_RATIO = 5.0


class MetricsEngine:
    """Computes all quantitative market metrics."""

    def __init__(self) -> None:
        self._df: pd.DataFrame | None = None

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        self._reset(df)
        self._create_basic_metrics()
        self._create_rolling_statistics()
        self._create_anomaly_flags()
        self._create_percentiles()
        self._create_classifications()
        result = self._df
        self._clean()
        assert result is not None
        return result

    def _reset(self, df: pd.DataFrame) -> None:
        self._df = df.copy(deep=True)

    def _create_basic_metrics(self) -> None:
        assert self._df is not None
        df = self._df
        df[COL_SPREAD] = df[COL_HIGH] - df[COL_LOW]
        df[COL_BODY] = (df[COL_CLOSE] - df[COL_OPEN]).abs()
        df[COL_UPPER_SHADOW] = df[COL_HIGH] - df[[COL_OPEN, COL_CLOSE]].max(axis=1)
        df[COL_LOWER_SHADOW] = df[[COL_OPEN, COL_CLOSE]].min(axis=1) - df[COL_LOW]
        spread = df[COL_SPREAD].replace(0.0, pd.NA)
        df[COL_CLOSE_RATIO] = (((df[COL_CLOSE] - df[COL_LOW]) / spread).infer_objects(copy=False)).fillna(0.5)
        df[COL_CLOSE_RATIO] = df[COL_CLOSE_RATIO].clip(0.0, 1.0)
        previous_columns = (COL_HIGH, COL_LOW, COL_CLOSE, COL_SPREAD)
        for column in previous_columns:
            df[f"prev_{column}"] = df[column].shift(1)
        df[COL_PRICE_CHANGE] = df[COL_CLOSE] - df[COL_PREV_CLOSE]
        prev_close = df[COL_PREV_CLOSE].replace(0.0, pd.NA)
        df[COL_PRICE_CHANGE_PCT] = ((df[COL_PRICE_CHANGE] / prev_close) * 100.0).fillna(0.0)
        df[COL_PRICE_GAP_RATIO] = ((df[COL_OPEN] - prev_close).abs() / prev_close).fillna(0.0)
        self._df = df

    def _create_rolling_statistics(self) -> None:
        assert self._df is not None
        df = self._df
        df[COL_AVG_VOLUME] = rolling_mean(df[COL_VOLUME], config.LOOKBACK_PERIOD)
        df[COL_AVG_SPREAD] = rolling_mean(df[COL_SPREAD], config.LOOKBACK_PERIOD)
        df[COL_STD_VOLUME] = rolling_std(df[COL_VOLUME], config.LOOKBACK_PERIOD)
        df[COL_STD_SPREAD] = rolling_std(df[COL_SPREAD], config.LOOKBACK_PERIOD)
        avg_volume = df[COL_AVG_VOLUME].replace(0.0, pd.NA)
        df[COL_VOLUME_RATIO] = (df[COL_VOLUME] / avg_volume).fillna(0.0)
        avg_spread = df[COL_AVG_SPREAD].replace(0.0, pd.NA)
        df[COL_SPREAD_RATIO] = (df[COL_SPREAD] / avg_spread).fillna(0.0)
        self._df = df

    def _create_anomaly_flags(self) -> None:
        """Flag suspicious OHLCV rows without changing scanner scoring.

        These flags are intentionally conservative. A flagged row is not proof of
        a split, bonus issue, bad tick, or market halt; it is a warning that VSA
        evidence near the row should be reviewed before acting on it.
        """
        assert self._df is not None
        df = self._df
        price_gap_threshold = getattr(
            config,
            "CORPORATE_ACTION_PRICE_GAP_RATIO",
            DEFAULT_CORPORATE_ACTION_PRICE_GAP_RATIO,
        )
        volume_threshold = getattr(
            config,
            "CORPORATE_ACTION_VOLUME_RATIO",
            DEFAULT_CORPORATE_ACTION_VOLUME_RATIO,
        )

        invalid_ohlc = (
            (df[COL_OPEN] <= 0.0)
            | (df[COL_HIGH] <= 0.0)
            | (df[COL_LOW] <= 0.0)
            | (df[COL_CLOSE] <= 0.0)
            | (df[COL_VOLUME] < 0.0)
            | (df[COL_HIGH] < df[[COL_OPEN, COL_CLOSE]].max(axis=1))
            | (df[COL_LOW] > df[[COL_OPEN, COL_CLOSE]].min(axis=1))
        )
        extreme_price_gap = df[COL_PRICE_GAP_RATIO] >= price_gap_threshold
        extreme_volume = df[COL_VOLUME_RATIO] >= volume_threshold

        df[COL_PRICE_ANOMALY] = (invalid_ohlc | extreme_price_gap).fillna(False)
        df[COL_VOLUME_ANOMALY] = extreme_volume.fillna(False)
        df[COL_CORPORATE_ACTION_ANOMALY] = (
            df[COL_PRICE_ANOMALY] | df[COL_VOLUME_ANOMALY]
        ).fillna(False)
        self._df = df

    def _create_percentiles(self) -> None:
        assert self._df is not None
        df = self._df
        df[COL_SPREAD_PERCENTILE] = historical_percentile_rank(df[COL_SPREAD_RATIO], config.LOOKBACK_PERIOD)
        df[COL_VOLUME_PERCENTILE] = historical_percentile_rank(df[COL_VOLUME_RATIO], config.LOOKBACK_PERIOD)
        self._df = df

    def _create_classifications(self) -> None:
        assert self._df is not None
        df = self._df
        df[COL_SPREAD_CLASS] = [classify_spread(percentile) for percentile in df[COL_SPREAD_PERCENTILE]]
        df[COL_VOLUME_CLASS] = [classify_volume(percentile) for percentile in df[COL_VOLUME_PERCENTILE]]
        df[COL_DIRECTION] = [classify_direction(open_, close) for open_, close in zip(df[COL_OPEN], df[COL_CLOSE])]
        df[COL_CLOSE_POSITION] = [classify_close_position(ratio) for ratio in df[COL_CLOSE_RATIO]]
        self._df = df

    def _clean(self) -> None:
        self._df = None
