from __future__ import annotations

from evidence.helpers import EvidenceCollector, evaluate_detector, requirement, requirements_passed
from evidence.rules import (
    is_above_average_spread,
    is_bearish_bar,
    is_high_volume,
    is_strong_close,
    makes_lower_low,
)
from models import BackgroundContext, Evidence, EvidenceCode


def collect_absorption(ctx: BackgroundContext) -> list[Evidence]:
    """Collect the canonical point-in-time ABSORPTION observation."""
    evidence: list[Evidence] = []
    bar = ctx.current
    previous = ctx.previous

    requirements = (
        requirement(name="Bearish Bar", passed=is_bearish_bar(bar)),
        requirement(name="High Volume", passed=is_high_volume(bar)),
        requirement(
            name="Above Average Spread",
            passed=is_above_average_spread(bar),
        ),
        requirement(name="Upper Close", passed=is_strong_close(bar)),
        requirement(
            name="Lower Low",
            passed=previous is not None and makes_lower_low(bar, previous),
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


__all__ = ["collect_absorption"]
