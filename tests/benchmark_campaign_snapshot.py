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


def _build_context() -> SimpleNamespace:
    bars = tuple(
        _bar(
            Direction.UP if i % 3 else Direction.DOWN,
            100.0 + i * 0.7,
            4 if i % 4 else 1,
        )
        for i in range(500)
    )
    structural = tuple(
        _structural_swing(
            SwingType.HIGH if i % 2 == 0 else SwingType.LOW,
            0.55 + (i % 5) * 0.08,
            0.8 + (i % 4) * 0.2,
        )
        for i in range(40)
    )
    return SimpleNamespace(
        trend=SimpleNamespace(
            direction=TrendDirection.UP,
            state=TrendState.HEALTHY,
        ),
        bars=bars,
        structural_swings=structural,
    )


def main() -> None:
    ctx = _build_context()
    snapshot = CampaignSnapshot.from_context(ctx)

    expected = (
        has_buying_campaign(ctx),
        has_selling_campaign(ctx),
    )
    actual = (
        snapshot.has_buying_campaign(),
        snapshot.has_selling_campaign(),
    )
    assert actual == expected, (expected, actual)

    rounds = 200

    legacy = []
    for _ in range(rounds):
        start = perf_counter()
        has_buying_campaign(ctx)
        has_selling_campaign(ctx)
        legacy.append(perf_counter() - start)

    snapshot_times = []
    for _ in range(rounds):
        start = perf_counter()
        snapshot.has_buying_campaign()
        snapshot.has_selling_campaign()
        snapshot_times.append(perf_counter() - start)

    legacy_median = median(legacy)
    snapshot_median = median(snapshot_times)
    speedup = legacy_median / snapshot_median if snapshot_median else float("inf")

    print(f"legacy median:   {legacy_median:.9f}s")
    print(f"snapshot median: {snapshot_median:.9f}s")
    print(f"speedup:         {speedup:.2f}x")


if __name__ == "__main__":
    main()
