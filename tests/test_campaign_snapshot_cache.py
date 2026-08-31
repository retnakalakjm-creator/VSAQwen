from types import SimpleNamespace

from evidence.campaign_snapshot import CampaignSnapshot
from models import TrendDirection


def _context():
    bar_a = SimpleNamespace(
        close_price=100.0,
        direction=1,
        close_position=3,
    )
    bar_b = SimpleNamespace(
        close_price=101.0,
        direction=1,
        close_position=2,
    )
    trend = SimpleNamespace(direction=TrendDirection.UP)
    return SimpleNamespace(
        bars=(bar_a, bar_b),
        trend=trend,
        structural_swings=(),
    )


def test_campaign_snapshot_reused_for_same_context():
    ctx = _context()

    first = CampaignSnapshot.from_context(ctx)
    second = CampaignSnapshot.from_context(ctx)

    assert first is second


def test_campaign_snapshot_cache_isolated_by_context_identity():
    first_ctx = _context()
    second_ctx = _context()

    first = CampaignSnapshot.from_context(first_ctx)
    second = CampaignSnapshot.from_context(second_ctx)

    assert first is not second
    assert first == second
