from dataclasses import dataclass

import pytest

from models import Swing, SwingType
from support_resistance.zones import derive_weekly_structural_zones


@dataclass(frozen=True, slots=True)
class StructuralFixture:
    swing: Swing
    is_failed: bool = False


def _structural(
    swing_type: SwingType,
    price: float,
    bar_index: int,
    confirmation_index: int,
    week: str,
    *,
    failed: bool = False,
) -> StructuralFixture:
    return StructuralFixture(
        swing=Swing(
            type=swing_type,
            price=price,
            bar_index=bar_index,
            confirmation_index=confirmation_index,
            week_beginning=week,
        ),
        is_failed=failed,
    )


def test_latest_two_lows_and_highs_define_weekly_zones() -> None:
    zones = derive_weekly_structural_zones(
        (
            _structural(SwingType.LOW, 90.0, 1, 3, "2026-01-05"),
            _structural(SwingType.HIGH, 120.0, 4, 6, "2026-01-26"),
            _structural(SwingType.LOW, 96.0, 7, 9, "2026-02-16"),
            _structural(SwingType.HIGH, 128.0, 10, 12, "2026-03-09"),
            _structural(SwingType.LOW, 101.0, 13, 15, "2026-03-30"),
            _structural(SwingType.HIGH, 132.0, 16, 18, "2026-04-20"),
        )
    )

    assert zones.support is not None
    assert zones.support.zone.lower == 96.0
    assert zones.support.zone.upper == 101.0
    assert zones.support.source_weeks == ("2026-02-16", "2026-03-30")

    assert zones.resistance is not None
    assert zones.resistance.zone.lower == 128.0
    assert zones.resistance.zone.upper == 132.0
    assert zones.resistance.source_weeks == ("2026-03-09", "2026-04-20")


def test_as_of_bar_index_excludes_not_yet_confirmed_future_swing() -> None:
    zones = derive_weekly_structural_zones(
        (
            _structural(SwingType.LOW, 94.0, 1, 3, "2026-01-05"),
            _structural(SwingType.LOW, 99.0, 6, 8, "2026-02-09"),
            _structural(SwingType.LOW, 105.0, 10, 14, "2026-03-09"),
        ),
        as_of_bar_index=10,
    )

    assert zones.support is not None
    assert zones.support.zone.lower == 94.0
    assert zones.support.zone.upper == 99.0
    assert zones.support.source_prices == (94.0, 99.0)


def test_failed_structural_swings_do_not_define_zones() -> None:
    zones = derive_weekly_structural_zones(
        (
            _structural(SwingType.HIGH, 120.0, 1, 3, "2026-01-05"),
            _structural(SwingType.HIGH, 150.0, 5, 7, "2026-02-02", failed=True),
            _structural(SwingType.HIGH, 126.0, 9, 11, "2026-03-02"),
        )
    )

    assert zones.resistance is not None
    assert zones.resistance.zone.lower == 120.0
    assert zones.resistance.zone.upper == 126.0
    assert zones.resistance.source_prices == (120.0, 126.0)


def test_single_structural_swing_is_exposed_as_zero_width_level() -> None:
    zones = derive_weekly_structural_zones(
        (_structural(SwingType.LOW, 88.5, 2, 4, "2026-01-12"),)
    )

    assert zones.support is not None
    assert zones.support.zone.lower == 88.5
    assert zones.support.zone.upper == 88.5
    assert zones.resistance is None


def test_empty_structural_history_returns_no_zones() -> None:
    zones = derive_weekly_structural_zones(())

    assert zones.support is None
    assert zones.resistance is None


def test_negative_as_of_bar_index_is_rejected() -> None:
    with pytest.raises(ValueError, match="as_of_bar_index"):
        derive_weekly_structural_zones((), as_of_bar_index=-1)
