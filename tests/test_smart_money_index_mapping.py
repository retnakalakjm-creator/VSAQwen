from __future__ import annotations

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
from models import Swing, SwingType


def _metrics() -> pd.DataFrame:
    return pd.DataFrame(
        {
            COL_OPEN: [10.0, 20.0, 30.0, 40.0],
            COL_HIGH: [12.0, 22.0, 32.0, 42.0],
            COL_LOW: [9.0, 18.0, 27.0, 36.0],
            COL_CLOSE: [11.8, 20.2, 31.8, 40.2],
            COL_VOLUME: [100.0, 250.0, 700.0, 140.0],
            COL_SPREAD: [2.0, 4.0, 5.0, 6.0],
            COL_AVG_VOLUME: [100.0, 100.0, 100.0, 100.0],
            COL_AVG_SPREAD: [2.0, 2.0, 2.0, 2.0],
        }
    )


def test_batch_smart_money_preserves_requested_index_order() -> None:
    scorer = ProfessionalScorer()
    arrays = scorer._metric_arrays(_metrics())
    indices = (3, 1, 0, 2)

    scores = scorer.smart_money_scores_batch(
        arrays,
        indices,
        include_components=True,
    )

    for score, index in zip(scores, indices):
        scalar = scorer._smart_money.score_values(
            bar_count=2 if index > 0 else 1,
            open_value=float(arrays[0][index]),
            low_value=float(arrays[2][index]),
            close_value=float(arrays[3][index]),
            spread_value=float(arrays[5][index]),
            avg_spread=float(arrays[7][index]),
            volume_value=float(arrays[4][index]),
            avg_volume=float(arrays[6][index]),
            include_components=True,
        )
        assert score == scalar


def test_smart_money_scores_batch_returns_one_score_per_input_index() -> None:
    scorer = ProfessionalScorer()
    arrays = scorer._metric_arrays(_metrics())
    indices = (0, 3, 1, 3, 2)

    scores = scorer.smart_money_scores_batch(arrays, indices)

    assert len(scores) == len(indices)
    assert scores[1] == scores[3]


def test_swing_metric_indices_are_the_batch_mapping_contract() -> None:
    scorer = ProfessionalScorer()
    metrics = _metrics()
    swings = (
        Swing(
            type=SwingType.HIGH,
            price=12.0,
            bar_index=0,
            confirmation_index=1,
            week_beginning="2025-01-01",
            metrics_index=3,
        ),
        Swing(
            type=SwingType.LOW,
            price=18.0,
            bar_index=1,
            confirmation_index=2,
            week_beginning="2025-01-02",
            metrics_index=1,
        ),
        Swing(
            type=SwingType.HIGH,
            price=32.0,
            bar_index=2,
            confirmation_index=3,
            week_beginning="2025-01-03",
            metrics_index=0,
        ),
    )

    arrays = scorer._metric_arrays(metrics)
    indices = tuple(swing.metrics_index for swing in swings)
    scores = scorer.smart_money_scores_batch(arrays, indices)

    expected = tuple(
        scorer._smart_money.score_values(
            bar_count=2 if swing.metrics_index > 0 else 1,
            open_value=float(metrics.loc[swing.metrics_index, COL_OPEN]),
            low_value=float(metrics.loc[swing.metrics_index, COL_LOW]),
            close_value=float(metrics.loc[swing.metrics_index, COL_CLOSE]),
            spread_value=float(metrics.loc[swing.metrics_index, COL_SPREAD]),
            avg_spread=float(metrics.loc[swing.metrics_index, COL_AVG_SPREAD]),
            volume_value=float(metrics.loc[swing.metrics_index, COL_VOLUME]),
            avg_volume=float(metrics.loc[swing.metrics_index, COL_AVG_VOLUME]),
        ).overall
        for swing in swings
    )

    assert tuple(score.overall for score in scores) == expected


def test_batch_smart_money_is_invariant_to_future_metric_changes() -> None:
    scorer = ProfessionalScorer()
    metrics = _metrics()
    arrays = scorer._metric_arrays(metrics)
    indices = (1, 2)
    baseline = scorer.smart_money_scores_batch(arrays, indices)

    future_changed = metrics.copy()
    future_changed.loc[3, COL_OPEN] = 999.0
    future_changed.loc[3, COL_LOW] = 1.0
    future_changed.loc[3, COL_CLOSE] = 998.0
    future_changed.loc[3, COL_SPREAD] = 500.0
    future_changed.loc[3, COL_AVG_SPREAD] = 0.01
    future_changed.loc[3, COL_VOLUME] = 999_999.0
    future_changed.loc[3, COL_AVG_VOLUME] = 1.0

    changed_arrays = scorer._metric_arrays(future_changed)
    changed = scorer.smart_money_scores_batch(changed_arrays, indices)

    assert changed == baseline


def test_batch_smart_money_is_invariant_to_unrequested_metric_rows() -> None:
    scorer = ProfessionalScorer()
    metrics = _metrics()
    indices = (0, 2)
    baseline = scorer.smart_money_scores_batch(
        scorer._metric_arrays(metrics),
        indices,
    )

    unrelated_changed = metrics.copy()
    unrelated_changed.loc[1, COL_OPEN] = 888.0
    unrelated_changed.loc[1, COL_LOW] = 2.0
    unrelated_changed.loc[1, COL_CLOSE] = 887.0
    unrelated_changed.loc[1, COL_SPREAD] = 400.0
    unrelated_changed.loc[1, COL_AVG_SPREAD] = 0.02
    unrelated_changed.loc[1, COL_VOLUME] = 888_888.0
    unrelated_changed.loc[1, COL_AVG_VOLUME] = 1.0

    changed = scorer.smart_money_scores_batch(
        scorer._metric_arrays(unrelated_changed),
        indices,
    )

    assert changed == baseline
