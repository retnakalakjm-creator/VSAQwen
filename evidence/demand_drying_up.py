from __future__ import annotations

from models import BackgroundContext, Evidence, EvidenceCode
from evidence.helpers import evaluate_detector, requirement, requirements_passed
from evidence.rules import is_low_volume, is_narrow_spread, is_up_bar


def collect_demand_drying_up(ctx: BackgroundContext) -> list[Evidence]:
    """Detect demand drying up from weak participation on an up bar."""
    evidence: list[Evidence] = []
    bar = ctx.current
    requirements = (
        requirement(name="Up Bar", passed=is_up_bar(bar)),
        requirement(name="Low Volume", passed=is_low_volume(bar)),
        requirement(name="Narrow Spread", passed=is_narrow_spread(bar)),
    )

    if not requirements_passed(requirements):
        return evidence

    evaluate_detector(
        evidence=evidence,
        ctx=ctx,
        code=EvidenceCode.DEMAND_DRYING_UP,
        requirements=requirements,
    )
    return evidence


__all__ = ["collect_demand_drying_up"]
