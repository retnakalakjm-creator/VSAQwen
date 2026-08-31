from __future__ import annotations

from dataclasses import dataclass

import config


@dataclass(frozen=True, slots=True)
class BoundaryRequirements:
    """Derived dependencies used to define a future incremental boundary."""

    metric_seed_bars: int
    structural_swing_count: int
    trend_swing_count: int
    trend_state_swing_count: int
    swing_confirmation_bars: int
    vsa_lookback_bars: int
    actionable_vsa_age: int


def _requirements() -> BoundaryRequirements:
    return BoundaryRequirements(
        metric_seed_bars=config.LOOKBACK_PERIOD,
        structural_swing_count=config.STRUCTURE_LOOKBACK,
        trend_swing_count=config.TREND_RECENT_SWINGS,
        trend_state_swing_count=config.TREND_STATE_LOOKBACK,
        swing_confirmation_bars=config.MIN_SWING_CONFIRMATION_BARS,
        vsa_lookback_bars=10,
        actionable_vsa_age=3,
    )


def test_incremental_dependencies_are_explicit() -> None:
    requirements = _requirements()

    assert requirements.metric_seed_bars == 20
    assert requirements.structural_swing_count == 20
    assert requirements.trend_swing_count == 8
    assert requirements.trend_state_swing_count == 4
    assert requirements.swing_confirmation_bars == 2
    assert requirements.vsa_lookback_bars == 10
    assert requirements.actionable_vsa_age == 3


def test_structural_boundary_is_swing_based_not_fixed_bar_count() -> None:
    requirements = _requirements()

    assert requirements.structural_swing_count == config.STRUCTURE_LOOKBACK
    assert requirements.metric_seed_bars == config.LOOKBACK_PERIOD
    assert requirements.structural_swing_count > requirements.trend_swing_count
    assert requirements.structural_swing_count > requirements.trend_state_swing_count
