from __future__ import annotations

import pytest

from background.qualification import PatternQualification
from weekly_setup import (
    WeeklyPriceZone,
    WeeklySetup,
    WeeklySetupDirection,
    WeeklySetupStatus,
    build_weekly_setup_id,
)


def _bullish_setup(**overrides) -> WeeklySetup:
    values = {
        "setup_id": "LT.NS:2026-03-02:bullish",
        "symbol": "LT.NS",
        "direction": WeeklySetupDirection.BULLISH,
        "signal_week": "2026-03-02",
        "qualification": PatternQualification.PERSISTENT_BULLISH,
        "weekly_confidence": 0.82,
        "weekly_net_strength": 1.25,
        "weekly_net_pressure": 0.74,
        "support_zone": WeeklyPriceZone(3200.0, 3250.0),
        "resistance_zone": WeeklyPriceZone(3475.0, 3520.0),
        "invalidation_level": 3175.0,
    }
    values.update(overrides)
    return WeeklySetup(**values)


def test_weekly_setup_starts_armed_and_is_immutable() -> None:
    setup = _bullish_setup()

    assert setup.status is WeeklySetupStatus.ARMED
    assert setup.is_armed
    assert not setup.is_terminal

    with pytest.raises(AttributeError):
        setup.status = WeeklySetupStatus.TRIGGERED  # type: ignore[misc]


def test_weekly_setup_direction_must_match_persistent_qualification() -> None:
    with pytest.raises(ValueError, match="direction must match"):
        _bullish_setup(qualification=PatternQualification.PERSISTENT_BEARISH)

    with pytest.raises(ValueError, match="direction must match"):
        _bullish_setup(qualification=PatternQualification.UNQUALIFIED)


def test_weekly_setup_can_transition_from_armed_to_terminal_state() -> None:
    setup = _bullish_setup()

    triggered = setup.transition_to(WeeklySetupStatus.TRIGGERED)

    assert setup.status is WeeklySetupStatus.ARMED
    assert triggered.status is WeeklySetupStatus.TRIGGERED
    assert triggered.is_terminal
    assert not triggered.is_armed


@pytest.mark.parametrize(
    "status",
    (
        WeeklySetupStatus.TRIGGERED,
        WeeklySetupStatus.INVALIDATED,
        WeeklySetupStatus.EXPIRED,
    ),
)
def test_terminal_weekly_setup_cannot_be_rewritten(status: WeeklySetupStatus) -> None:
    setup = _bullish_setup().transition_to(status)

    assert setup.transition_to(status) is setup
    with pytest.raises(ValueError, match="cannot transition terminal weekly setup"):
        setup.transition_to(
            WeeklySetupStatus.INVALIDATED
            if status is not WeeklySetupStatus.INVALIDATED
            else WeeklySetupStatus.TRIGGERED
        )


def test_weekly_price_zone_requires_ordered_finite_bounds() -> None:
    with pytest.raises(ValueError, match="lower bound"):
        WeeklyPriceZone(101.0, 100.0)

    with pytest.raises(ValueError, match="finite"):
        WeeklyPriceZone(float("nan"), 100.0)


def test_build_weekly_setup_id_is_stable_and_normalized() -> None:
    assert (
        build_weekly_setup_id(
            " lt.ns ",
            "2026-03-02",
            WeeklySetupDirection.BULLISH,
        )
        == "LT.NS:2026-03-02:bullish"
    )


def test_bearish_setup_accepts_bearish_persistent_qualification() -> None:
    setup = _bullish_setup(
        setup_id="ABC.NS:2026-03-02:bearish",
        symbol="ABC.NS",
        direction=WeeklySetupDirection.BEARISH,
        qualification=PatternQualification.PERSISTENT_BEARISH,
        weekly_net_strength=-0.9,
        weekly_net_pressure=-1.1,
    )

    assert setup.direction is WeeklySetupDirection.BEARISH
    assert setup.qualification is PatternQualification.PERSISTENT_BEARISH
