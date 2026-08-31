from __future__ import annotations

from types import SimpleNamespace

from evidence.demand import _candidate_trend_direction
from metrics_engine import MetricsEngine
from models import Direction
from trend import TrendAnalyzer

from tests.test_incremental_trend import _bars


def _bar_contexts(metrics):
    bars = []
    for index, row in metrics.iterrows():
        bars.append(
            SimpleNamespace(
                bar_index=int(index),
                direction=Direction.UP if float(row["close"]) >= float(row["open"]) else Direction.DOWN,
                close_price=float(row["close"]),
                close_position=3,
            )
        )
    return tuple(bars)


def test_candidate_trend_direction_matches_prefix_replay() -> None:
    metrics = MetricsEngine().calculate(_bars())
    full_trend = TrendAnalyzer().analyze(metrics)
    ctx = SimpleNamespace(
        bars=_bar_contexts(metrics),
        structural_swings=full_trend.structure.structural_swings,
    )

    for candidate_index in range(1, len(metrics)):
        expected = TrendAnalyzer().analyze(
            metrics.iloc[: candidate_index + 1].copy()
        ).direction
        actual = _candidate_trend_direction(ctx, candidate_index)
        assert actual == expected, (
            candidate_index,
            expected,
            actual,
        )


def test_candidate_trend_direction_is_unknown_before_first_confirmed_swing() -> None:
    metrics = MetricsEngine().calculate(_bars())
    full_trend = TrendAnalyzer().analyze(metrics)
    ctx = SimpleNamespace(
        bars=_bar_contexts(metrics),
        structural_swings=full_trend.structure.structural_swings,
    )

    first_confirmation = min(
        swing.swing.confirmation_index
        for swing in full_trend.structure.structural_swings
    )

    if first_confirmation > 0:
        assert _candidate_trend_direction(ctx, first_confirmation - 1).name == "UNKNOWN"
