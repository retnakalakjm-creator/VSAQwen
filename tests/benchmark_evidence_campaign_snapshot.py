from __future__ import annotations

import sys
from pathlib import Path
from statistics import median
from time import perf_counter
from types import SimpleNamespace

# Allow direct execution from the repository's tests directory.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import evidence.demand as demand
import evidence.supply as supply
from evidence.campaign import has_buying_campaign, has_selling_campaign
from evidence.campaign_snapshot import CampaignSnapshot
from models import SwingType, TrendDirection, TrendState

ROUNDS = 100


def _bar(i: int) -> SimpleNamespace:
    return SimpleNamespace(
        direction=1 if i % 3 else -1,
        close_price=100.0 + i * 0.7,
        close_position=4 if i % 4 else 1,
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
    bars = tuple(_bar(i) for i in range(500))
    structural = tuple(
        _swing(
            SwingType.HIGH if i % 2 == 0 else SwingType.LOW,
            0.55 + (i % 5) * 0.08,
            0.8 + (i % 4) * 0.2,
        )
        for i in range(40)
    )

    ctx = SimpleNamespace(
        trend=SimpleNamespace(
            direction=TrendDirection.UP,
            state=TrendState.HEALTHY,
        ),
        bars=bars,
        structural_swings=structural,
        current=bars[-1],
        previous=bars[-2],
    )

    def with_current(index: int) -> SimpleNamespace:
        return SimpleNamespace(
            current=bars[index],
            previous=bars[index - 1] if index else None,
            bars=bars,
            trend=ctx.trend,
            structural_swings=structural,
        )

    ctx.with_current = with_current
    return ctx


class _LegacyCampaignAdapter:
    def __init__(self, ctx: SimpleNamespace) -> None:
        self._ctx = ctx

    def has_buying_campaign(self) -> bool:
        return has_buying_campaign(self._ctx)

    def has_selling_campaign(self) -> bool:
        return has_selling_campaign(self._ctx)


def _patch_non_campaign_detectors() -> None:
    supply._collect_supply_coming_in = lambda _ctx: []
    supply._collect_hidden_supply = lambda _ctx: []
    supply._collect_increasing_supply = lambda _ctx: []
    supply._collect_supply_drying_up = lambda _ctx: []
    supply._collect_no_demand = lambda _ctx: []

    demand._collect_increasing_demand = lambda _ctx: []
    demand._collect_shakeout = lambda **_kwargs: []
    demand._collect_no_supply = lambda _ctx: []

    supply.evaluate_detector = lambda **_kwargs: None
    demand.evaluate_detector = lambda **_kwargs: None
    supply.requirements_passed = lambda _requirements: True
    demand.requirements_passed = lambda _requirements: True

    supply.is_bullish_bar = lambda _bar: True
    supply.is_very_high_volume = lambda _bar: True
    supply.is_above_average_spread = lambda _bar: True
    supply.has_strong_spread = lambda _bar: True
    supply.is_weak_close = lambda _bar: True
    supply.volume_increasing = lambda _bar, _previous: True

    demand.is_bearish_bar = lambda _bar: True
    demand.is_high_volume = lambda _bar: True
    demand.is_above_average_spread = lambda _bar: True
    demand.is_weak_close = lambda _bar: False
    demand.is_very_high_volume = lambda _bar: True
    demand.has_strong_spread = lambda _bar: True
    demand.volume_increasing = lambda _bar, _previous: True
    demand.makes_higher_low = lambda _bar, _previous: True
    demand.is_strong_close = lambda _bar: True
    demand.is_low_volume = lambda _bar: True
    demand.is_narrow_spread = lambda _bar: True
    demand.is_confirmed_downtrend = lambda _trend: False
    demand._recent_structural_weakness = lambda _ctx: False
    demand.volume_decreasing = lambda _bar, _previous: True


def _legacy_collect_supply(ctx: SimpleNamespace) -> list:
    evidence = []
    for i in range(1, len(ctx.bars)):
        bar_ctx = ctx.with_current(i)
        snapshot = _LegacyCampaignAdapter(bar_ctx)
        evidence.extend(supply._collect_buying_climax(bar_ctx, snapshot))
        evidence.extend(supply._collect_upthrust(bar_ctx, snapshot))
    return evidence


def _legacy_collect_demand(ctx: SimpleNamespace) -> list:
    evidence = []
    for i in range(1, len(ctx.bars)):
        bar_ctx = ctx.with_current(i)
        snapshot = _LegacyCampaignAdapter(bar_ctx)
        evidence.extend(demand._collect_stopping_volume(bar_ctx, snapshot))
        evidence.extend(demand._collect_selling_climax(bar_ctx, snapshot))
        evidence.extend(demand._collect_test(bar_ctx, snapshot))
    return evidence


def _snapshot_collect(ctx: SimpleNamespace) -> list:
    evidence = []
    snapshot = CampaignSnapshot.from_context(ctx)
    for i in range(1, len(ctx.bars)):
        bar_ctx = ctx.with_current(i)
        evidence.extend(supply._collect_buying_climax(bar_ctx, snapshot))
        evidence.extend(supply._collect_upthrust(bar_ctx, snapshot))
        evidence.extend(demand._collect_stopping_volume(bar_ctx, snapshot))
        evidence.extend(demand._collect_selling_climax(bar_ctx, snapshot))
        evidence.extend(demand._collect_test(bar_ctx, snapshot))
    return evidence


def main() -> None:
    _patch_non_campaign_detectors()
    ctx = _context()

    legacy_expected = _legacy_collect_supply(ctx) + _legacy_collect_demand(ctx)
    snapshot_expected = _snapshot_collect(ctx)
    assert legacy_expected == snapshot_expected, "legacy and snapshot paths differ"

    legacy_times = []
    for _ in range(ROUNDS):
        start = perf_counter()
        _legacy_collect_supply(ctx)
        _legacy_collect_demand(ctx)
        legacy_times.append(perf_counter() - start)

    snapshot_times = []
    for _ in range(ROUNDS):
        start = perf_counter()
        _snapshot_collect(ctx)
        snapshot_times.append(perf_counter() - start)

    legacy_median = median(legacy_times)
    snapshot_median = median(snapshot_times)
    speedup = legacy_median / snapshot_median if snapshot_median else float("inf")

    print(f"legacy-equivalent median: {legacy_median:.9f}s")
    print(f"snapshot median:          {snapshot_median:.9f}s")
    print(f"speedup:                   {speedup:.2f}x")


if __name__ == "__main__":
    main()
