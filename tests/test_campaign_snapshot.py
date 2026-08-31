from __future__ import annotations

from types import SimpleNamespace

from evidence.campaign import has_buying_campaign, has_selling_campaign
from evidence.campaign_snapshot import CampaignSnapshot
from models import Direction, SwingType, TrendDirection, TrendState


def _bar(direction: Direction, close: float, close_position: int) -> SimpleNamespace:
    return SimpleNamespace(
        direction=direction,
        close_price=close,
        close_position=close_position,
    )


def _structural_swing(
    swing_type: SwingType,
    score: float,
    amplitude: float,
) -> SimpleNamespace:
    return SimpleNamespace(
        swing=SimpleNamespace(type=swing_type),
        evaluation=SimpleNamespace(
            smart_money=SimpleNamespace(overall=score),
            structure=SimpleNamespace(
                snapshot=SimpleNamespace(
                    current_spread_adjusted_amplitude=amplitude,
                )
            ),
        ),
    )


def _context(
    *,
    trend: TrendDirection,
    bars: tuple[SimpleNamespace, ...],
    structural_swings: tuple[SimpleNamespace, ...],
) -> SimpleNamespace:
    return SimpleNamespace(
        trend=SimpleNamespace(direction=trend, state=TrendState.HEALTHY),
        bars=bars,
        structural_swings=structural_swings,
    )


def test_campaign_snapshot_matches_campaign_predicates() -> None:
    bars = tuple(
        _bar(Direction.UP, 100.0 + i, 4)
        for i in range(6)
    )
    structural = (
        _structural_swing(SwingType.HIGH, 0.80, 1.0),
        _structural_swing(SwingType.HIGH, 0.90, 1.2),
        _structural_swing(SwingType.LOW, 0.70, 1.0),
        _structural_swing(SwingType.LOW, 0.60, 0.8),
    )
    ctx = _context(
        trend=TrendDirection.UP,
        bars=bars,
        structural_swings=structural,
    )

    snapshot = CampaignSnapshot.from_context(ctx)

    assert snapshot.has_buying_campaign() == has_buying_campaign(ctx)
    assert snapshot.has_selling_campaign() == has_selling_campaign(ctx)


def test_serialized_campaign_snapshot_preserves_results() -> None:
    snapshot = CampaignSnapshot(
        recent_up_bars=5,
        recent_down_bars=1,
        recent_higher_closes=5,
        recent_lower_closes=0,
        recent_strong_closes=5,
        recent_weak_closes=0,
        trend_direction=TrendDirection.UP,
        high_scores=(0.80, 0.90),
        high_amplitudes=(1.00, 1.20),
        low_scores=(0.70, 0.60),
        low_amplitudes=(1.00, 0.80),
    )

    restored = CampaignSnapshot.from_dict(snapshot.to_dict())

    assert restored == snapshot
    assert restored.has_buying_campaign() == snapshot.has_buying_campaign()
    assert restored.has_selling_campaign() == snapshot.has_selling_campaign()
