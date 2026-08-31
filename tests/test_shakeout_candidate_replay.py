from __future__ import annotations

from types import SimpleNamespace

from evidence.campaign import has_selling_campaign
from evidence.campaign_snapshot import CampaignSnapshot
from evidence.demand import _candidate_campaign_snapshot, _candidate_trend_direction
from evidence.engine import EvidenceEngine
from metrics_engine import MetricsEngine
from models import Direction, TrendDirection
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
        actual = _candidate_trend_direction(
            TrendAnalyzer()._classify_swings(list(ctx.structural_swings)),
            candidate_index,
        )
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

    classified = TrendAnalyzer()._classify_swings(list(ctx.structural_swings))
    first_confirmation = min(
        swing.swing.confirmation_index
        for swing in full_trend.structure.structural_swings
    )

    if first_confirmation > 0:
        assert _candidate_trend_direction(
            classified,
            first_confirmation - 1,
        ) is TrendDirection.UNKNOWN


def test_candidate_campaign_snapshot_matches_prefix_replay() -> None:
    metrics = MetricsEngine().calculate(_bars())
    full_trend = TrendAnalyzer().analyze(metrics)
    engine = EvidenceEngine()
    engine._reset(
        metrics=metrics,
        trend=full_trend,
        structural_swings=tuple(full_trend.structure.structural_swings),
        validation_metrics=metrics,
    )
    ctx = engine._ctx
    assert ctx is not None

    classified = TrendAnalyzer()._classify_swings(list(ctx.structural_swings))
    lookback = 21
    start = max(1, len(metrics) - lookback)

    for candidate_index in range(start, len(metrics)):
        replay_metrics = metrics.iloc[: candidate_index + 1].copy()
        replay_trend = TrendAnalyzer().analyze(replay_metrics)
        replay_engine = EvidenceEngine()
        replay_engine._reset(
            metrics=replay_metrics,
            trend=replay_trend,
            structural_swings=tuple(replay_trend.structure.structural_swings),
            validation_metrics=replay_metrics,
        )
        replay_ctx = replay_engine._ctx
        assert replay_ctx is not None

        expected = has_selling_campaign(replay_ctx)
        snapshot = _candidate_campaign_snapshot(
            ctx,
            metrics,
            candidate_index,
            classified,
        )
        assert isinstance(snapshot, CampaignSnapshot)
        actual = snapshot.has_selling_campaign()
        assert actual == expected, (
            candidate_index,
            expected,
            actual,
        )
