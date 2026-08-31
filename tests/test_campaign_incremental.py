from __future__ import annotations

from types import SimpleNamespace

from evidence.campaign import has_buying_campaign, has_selling_campaign
from evidence.campaign_incremental import evaluate_campaigns
from evidence.campaign_snapshot import CampaignSnapshot
from models import Direction, SwingType, TrendDirection, TrendState


def _bar(direction: Direction, close: float, close_position: int) -> SimpleNamespace:
    return SimpleNamespace(
        direction=direction,
        close_price=close,
        close_position=close_position,
    )


def _swing(swing_type: SwingType, score: float, amplitude: float) -> SimpleNamespace:
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


def _context() -> SimpleNamespace:
    bars = tuple(_bar(Direction.UP, 100.0 + i, 4) for i in range(6))
    return SimpleNamespace(
        trend=SimpleNamespace(direction=TrendDirection.UP, state=TrendState.HEALTHY),
        bars=bars,
        structural_swings=(
            _swing(SwingType.HIGH, 0.80, 1.0),
            _swing(SwingType.HIGH, 0.90, 1.2),
            _swing(SwingType.LOW, 0.70, 1.0),
            _swing(SwingType.LOW, 0.60, 0.8),
        ),
    )


def test_default_path_matches_existing_campaign_api() -> None:
    ctx = _context()
    assert evaluate_campaigns(ctx) == (
        has_buying_campaign(ctx),
        has_selling_campaign(ctx),
    )


def test_snapshot_path_uses_persisted_state() -> None:
    ctx = _context()
    snapshot = CampaignSnapshot.from_context(ctx)
    unrelated = SimpleNamespace()

    assert evaluate_campaigns(unrelated, snapshot=snapshot) == (
        snapshot.has_buying_campaign(),
        snapshot.has_selling_campaign(),
    )
