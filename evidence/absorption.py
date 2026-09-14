from __future__ import annotations

from evidence.helpers import EvidenceCollector, evaluate_detector, requirement, requirements_passed
from evidence.rules import (
    closes_middle,
    is_above_average_spread,
    is_bearish_bar,
    is_high_volume,
    is_strong_close,
    makes_lower_low,
)
from models import BackgroundContext, Evidence, EvidenceCode


def collect_absorption(ctx: BackgroundContext) -> list[Evidence]:
    """Collect the canonical point-in-time ABSORPTION observation.

    ABSORPTION is production-visible read-only evidence. It can appear in API,
    CLI, and frontend evidence views, but its registry weight remains zero and
    scanner scoring/ranking/actionability continue to exclude it.
    """
    evidence: list[Evidence] = []
    bar = ctx.current
    previous = getattr(ctx, "previous", None)

    if not _has_absorption_context(bar, previous):
        return evidence

    requirements = (
        requirement(name="Bearish Bar", passed=is_bearish_bar(bar)),
        requirement(name="High Volume", passed=is_high_volume(bar)),
        requirement(
            name="Lower Low",
            passed=makes_lower_low(bar, previous),
        ),
        requirement(
            name="Close Midpoint Or Better",
            passed=closes_middle(bar) or is_strong_close(bar),
        ),
        requirement(
            name="Absorptive Spread Or Recovery",
            passed=is_above_average_spread(bar) or _recovered_from_low(bar),
        ),
    )

    if not requirements_passed(requirements):
        return evidence

    evaluate_detector(
        evidence=evidence,
        ctx=ctx,
        code=EvidenceCode.ABSORPTION,
        requirements=requirements,
    )
    return evidence


def _has_absorption_context(bar, previous) -> bool:
    if previous is None:
        return False
    return all(
        hasattr(obj, attr)
        for obj, attr in (
            (bar, "direction"),
            (bar, "low"),
            (previous, "low"),
        )
    )


def _recovered_from_low(bar) -> bool:
    return float(getattr(bar, "close_ratio", 0.5)) >= 0.45


__all__ = ["collect_absorption"]
