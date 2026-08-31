from __future__ import annotations

from models import BackgroundContext, Evidence, EvidenceCode
from evidence.helpers import evaluate_detector, requirement
from evidence.rules import is_above_average_spread, is_bullish_bar, is_high_volume, is_strong_close


def collect_demand_coming_in(ctx: BackgroundContext) -> list[Evidence]:
    """
    Detect the initial audit definition of DEMAND_COMING_IN.

    Mandatory VSA observations:
    - bullish/up bar
    - high volume
    - above-average spread
    - strong close in the upper part of the range

    This detector is intentionally audit-first. Its presence does not
    establish a professional scoring weight or actionability rule.
    """
    evidence: list[Evidence] = []
    bar = ctx.current

    requirements = (
        requirement(name="Bullish Bar", passed=is_bullish_bar(bar)),
        requirement(name="High Volume", passed=is_high_volume(bar)),
        requirement(
            name="Above Average Spread",
            passed=is_above_average_spread(bar),
        ),
        requirement(name="Strong Close", passed=is_strong_close(bar)),
    )

    evaluate_detector(
        evidence=evidence,
        ctx=ctx,
        code=EvidenceCode.DEMAND_COMING_IN,
        requirements=requirements,
    )
    return evidence


__all__ = ["collect_demand_coming_in"]
