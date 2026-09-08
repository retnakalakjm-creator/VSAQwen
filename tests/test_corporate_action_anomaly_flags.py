import pandas as pd

from engine.columns import (
    COL_CORPORATE_ACTION_ANOMALY,
    COL_PRICE_ANOMALY,
    COL_PRICE_GAP_RATIO,
    COL_VOLUME_ANOMALY,
)
from metrics_engine import MetricsEngine


def _weekly_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "week_beginning": ["2026-01-02", "2026-01-09", "2026-01-16"],
            "open": [100.0, 65.0, 66.0],
            "high": [105.0, 67.0, 70.0],
            "low": [95.0, 63.0, 64.0],
            "close": [100.0, 66.0, 69.0],
            "volume": [1_000, 1_100, 1_200],
        }
    )


def test_large_price_gap_flags_potential_corporate_action() -> None:
    metrics = MetricsEngine().calculate(_weekly_frame())

    assert metrics.loc[0, COL_PRICE_GAP_RATIO] == 0.0
    assert metrics.loc[1, COL_PRICE_GAP_RATIO] == 0.35
    assert bool(metrics.loc[0, COL_PRICE_ANOMALY]) is False
    assert bool(metrics.loc[1, COL_PRICE_ANOMALY]) is True
    assert bool(metrics.loc[1, COL_CORPORATE_ACTION_ANOMALY]) is True


def test_normal_bars_do_not_set_volume_anomaly_by_default() -> None:
    metrics = MetricsEngine().calculate(_weekly_frame())

    assert bool(metrics.loc[2, COL_VOLUME_ANOMALY]) is False
    assert bool(metrics.loc[2, COL_CORPORATE_ACTION_ANOMALY]) is False


def test_invalid_ohlc_relationship_flags_price_anomaly() -> None:
    frame = _weekly_frame()
    frame.loc[2, "high"] = 60.0

    metrics = MetricsEngine().calculate(frame)

    assert bool(metrics.loc[2, COL_PRICE_ANOMALY]) is True
    assert bool(metrics.loc[2, COL_CORPORATE_ACTION_ANOMALY]) is True
