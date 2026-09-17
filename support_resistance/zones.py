from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol

from models import Swing, SwingType
from weekly_setup import WeeklyPriceZone


class StructuralSwingLike(Protocol):
    """Minimal structural-swing surface required by zone derivation."""

    swing: Swing
    is_failed: bool


@dataclass(frozen=True, slots=True)
class WeeklyStructuralZone:
    """Read-only zone derived from confirmed structural swing prices."""

    zone: WeeklyPriceZone
    source_type: SwingType
    source_weeks: tuple[str, ...]
    source_prices: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class WeeklyStructuralZones:
    """Latest support and resistance zones known at one weekly bar."""

    support: WeeklyStructuralZone | None = None
    resistance: WeeklyStructuralZone | None = None


def _zone_from_swings(swings: tuple[Swing, ...], swing_type: SwingType) -> WeeklyStructuralZone | None:
    matching = tuple(swing for swing in swings if swing.type is swing_type)
    if not matching:
        return None

    latest = tuple(
        sorted(
            matching,
            key=lambda swing: (swing.confirmation_index, swing.bar_index),
        )[-2:]
    )
    prices = tuple(swing.price for swing in latest)
    return WeeklyStructuralZone(
        zone=WeeklyPriceZone(lower=min(prices), upper=max(prices)),
        source_type=swing_type,
        source_weeks=tuple(swing.week_beginning for swing in latest),
        source_prices=prices,
    )


def derive_weekly_structural_zones(
    structural_swings: Iterable[StructuralSwingLike],
    *,
    as_of_bar_index: int | None = None,
) -> WeeklyStructuralZones:
    """Derive read-only weekly support/resistance zones point-in-time.

    Only confirmed, non-failed structural swings are eligible. When
    ``as_of_bar_index`` is supplied, a swing is visible only when its
    confirmation bar is at or before that index, preventing future structural
    confirmation from leaking backward into historical/replay evaluation.

    The latest two LOW structural swings define support and the latest two HIGH
    structural swings define resistance. With only one eligible swing, the zone
    is a zero-width level at that price. No score, rank, actionability, setup
    lifecycle, or production state is modified here.
    """

    if as_of_bar_index is not None and as_of_bar_index < 0:
        raise ValueError("as_of_bar_index cannot be negative")

    eligible: list[Swing] = []
    for structural in structural_swings:
        if structural.is_failed:
            continue
        swing = structural.swing
        if as_of_bar_index is not None and swing.confirmation_index > as_of_bar_index:
            continue
        eligible.append(swing)

    ordered = tuple(
        sorted(
            eligible,
            key=lambda swing: (swing.confirmation_index, swing.bar_index),
        )
    )
    return WeeklyStructuralZones(
        support=_zone_from_swings(ordered, SwingType.LOW),
        resistance=_zone_from_swings(ordered, SwingType.HIGH),
    )


__all__ = [
    "StructuralSwingLike",
    "WeeklyStructuralZone",
    "WeeklyStructuralZones",
    "derive_weekly_structural_zones",
]
