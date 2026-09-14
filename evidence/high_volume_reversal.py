"""High Volume Reversal read-only evidence collector."""

from __future__ import annotations

from enum import StrEnum

from evidence.helpers import EvidenceCollector, requirement, requirements_passed
from evidence.rules import closes_middle, is_high_volume, is_strong_close, makes_lower_low
from models import (
    BackgroundContext,
    Direction,
    Evidence,
    EvidenceCategory,
    EvidenceDirection,
)


class HighVolumeReversalCode(StrEnum):
    """Read-only detector code exposed through evidence APIs."""

    HIGH_VOLUME_REVERSAL = "high_volume_reversal"


HIGH_VOLUME_REVERSAL_CODE = HighVolumeReversalCode.HIGH_VOLUME_REVERSAL


def collect_high_volume_reversal(ctx: BackgroundContext) -> list[Evidence]:
    """Collect bullish High Volume Reversal evidence point-in-time.

    The detector is intentionally production-visible but read-only. It emits a
    same-bar observation for historical audit/API/frontend visibility while its
    scanner integration excludes the code from scoring, ranking, qualification,
    actionability, alerts, and orders.
    """
    evidence: list[Evidence] = []
    bar = ctx.current
    previous = getattr(ctx, "previous", None)

    if not _has_high_volume_reversal_context(bar, previous):
        return evidence

    requirements = (
        requirement(name="High Volume", passed=is_high_volume(bar)),
        requirement(name="Lower Low", passed=makes_lower_low(bar, previous)),
        requirement(name="Close Off Low", passed=_closes_off_low(bar)),
        requirement(name="Reversal Recovery", passed=_has_reversal_recovery(bar)),
    )

    if not requirements_passed(requirements):
        return evidence

    evidence.append(
        Evidence(
            code=HIGH_VOLUME_REVERSAL_CODE,
            category=EvidenceCategory.DEMAND,
            direction=EvidenceDirection.BULLISH,
            strength=0.85,
            quality=1.0,
            weight=0.0,
            observation="High Volume Reversal",
            description=(
                "High volume pushed price to a lower low, but the bar recovered "
                "off the low enough to indicate possible bullish reversal demand. "
                "Scoring remains disabled pending ranking validation."
            ),
            bar_index=bar.bar_index,
            week_beginning=bar.week_beginning,
        )
    )
    return evidence


def _has_high_volume_reversal_context(bar, previous) -> bool:
    if previous is None:
        return False
    return all(
        hasattr(obj, attr)
        for obj, attr in (
            (bar, "volume"),
            (bar, "close_position"),
            (bar, "close_ratio"),
            (bar, "direction"),
            (bar, "low"),
            (bar, "bar_index"),
            (bar, "week_beginning"),
            (previous, "low"),
        )
    )


def _closes_off_low(bar) -> bool:
    return float(getattr(bar, "close_ratio", 0.5)) >= 0.35


def _has_reversal_recovery(bar) -> bool:
    return (
        closes_middle(bar)
        or is_strong_close(bar)
        or float(getattr(bar, "close_ratio", 0.5)) >= 0.45
        or (
            getattr(bar, "direction", None) == Direction.UP
            and float(getattr(bar, "close_ratio", 0.5)) >= 0.35
        )
    )


__all__ = [
    "EvidenceCollector",
    "HIGH_VOLUME_REVERSAL_CODE",
    "HighVolumeReversalCode",
    "collect_high_volume_reversal",
]
