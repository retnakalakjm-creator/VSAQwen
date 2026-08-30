from types import SimpleNamespace

import pandas as pd

from engine.columns import (
    COL_AVG_SPREAD,
    COL_AVG_VOLUME,
    COL_CLOSE,
    COL_HIGH,
    COL_LOW,
    COL_OPEN,
    COL_SPREAD,
    COL_VOLUME,
)
from market_structure.professional_scorer import ProfessionalScorer


def _metrics() -> pd.DataFrame:
    return pd.DataFrame(
        {
            COL_OPEN: [10.0, 11.0, 12.0, 13.0],
            COL_HIGH: [11.0, 12.0, 13.0, 14.0],
            COL_LOW: [9.0, 10.0, 11.0, 12.0],
            COL_CLOSE: [10.5, 11.5, 12.5, 13.5],
            COL_VOLUME: [100.0, 110.0, 120.0, 130.0],
            COL_SPREAD: [1.0, 1.1, 1.2, 1.3],
            COL_AVG_VOLUME: [95.0, 105.0, 115.0, 125.0],
            COL_AVG_SPREAD: [0.9, 1.0, 1.1, 1.2],
        }
    )


def test_metric_arrays_returns_expected_columns_and_reuses_cache() -> None:
    scorer = ProfessionalScorer()
    metrics = _metrics()

    first = scorer._metric_arrays(metrics)
    second = scorer._metric_arrays(metrics)

    assert len(first) == 8
    assert all(a is b for a, b in zip(first, second))
    assert first[0][3] == 13.0
    assert first[7][3] == 1.2


def test_metric_arrays_refreshes_for_a_different_dataframe() -> None:
    scorer = ProfessionalScorer()
    first_metrics = _metrics()
    second_metrics = _metrics().copy()
    second_metrics.loc[3, COL_CLOSE] = 99.0

    first = scorer._metric_arrays(first_metrics)
    second = scorer._metric_arrays(second_metrics)

    assert first[3] is not second[3]
    assert first[3][3] == 13.5
    assert second[3][3] == 99.0


def test_metric_snapshot_uses_cached_array_values() -> None:
    scorer = ProfessionalScorer()
    metrics = _metrics()
    swing = SimpleNamespace(metrics_index=2)

    snapshot = scorer._metric_snapshot(metrics, swing)

    assert snapshot.volume == 120.0
    assert snapshot.spread == 1.2
    assert snapshot.avg_volume == 115.0
    assert snapshot.avg_spread == 1.1


def test_smart_money_snapshot_uses_requested_lookback() -> None:
    scorer = ProfessionalScorer()
    metrics = _metrics()
    swing = SimpleNamespace(metrics_index=3)

    snapshot = scorer._smart_money_snapshot(metrics, swing, lookback=3)

    assert len(snapshot.bars) == 3
    assert [bar.close for bar in snapshot.bars] == [11.5, 12.5, 13.5]
    assert [bar.volume for bar in snapshot.bars] == [110.0, 120.0, 130.0]


def test_smart_money_batch_matches_scalar_scoring() -> None:
    scorer = ProfessionalScorer()
    metrics = _metrics()
    arrays = scorer._metric_arrays(metrics)
    (
        open_values,
        _high_values,
        low_values,
        close_values,
        volume_values,
        spread_values,
        avg_volume_values,
        avg_spread_values,
    ) = arrays

    indices = [0, 1, 2, 3]
    batch_scores = scorer._smart_money.score_values_batch(
        open_values=open_values,
        low_values=low_values,
        close_values=close_values,
        spread_values=spread_values,
        avg_spread_values=avg_spread_values,
        volume_values=volume_values,
        avg_volume_values=avg_volume_values,
        indices=indices,
        include_components=True,
    )

    scalar_scores = tuple(
        scorer._smart_money.score_values(
            bar_count=2 if index > 0 else 1,
            open_value=float(open_values[index]),
            low_value=float(low_values[index]),
            close_value=float(close_values[index]),
            spread_value=float(spread_values[index]),
            avg_spread=float(avg_spread_values[index]),
            volume_value=float(volume_values[index]),
            avg_volume=float(avg_volume_values[index]),
            include_components=True,
        )
        for index in indices
    )

    for batch, scalar in zip(batch_scores, scalar_scores):
        assert batch.stopping_volume == scalar.stopping_volume
        assert batch.stopping_breakdown == scalar.stopping_breakdown
        assert batch.climactic_volume == scalar.climactic_volume
        assert batch.climactic_breakdown == scalar.climactic_breakdown
        assert batch.overall == scalar.overall
