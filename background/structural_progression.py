from __future__ import annotations

import config

from models import (
    BackgroundContext,
    Evidence,
    EvidenceCategory,
    EvidenceCode,
    EvidenceDirection,
)
from market_structure.progression import calculate_professional_progression


def collect_structural_progression(
    ctx: BackgroundContext,
) -> list[Evidence]:
    """
    Emit professional structural progression only when a new
    structural swing has been confirmed on the current bar.

    Structural progression is a change in swing quality between
    structural campaigns. It is therefore an event, not a state
    that should be re-emitted on every subsequent bar while the
    same structural swing set remains unchanged.
    """

    structural_swings = ctx.structural_swings

    if not structural_swings:
        return []

    latest_confirmation = structural_swings[-1].swing.confirmation_index

    # The progression calculation is based on the current set of
    # confirmed structural swings. Do not emit the same progression
    # again on bars after the latest structural swing confirmation.
    if ctx.current.bar_index != latest_confirmation:
        return []

    progression, difference = calculate_professional_progression(
        structural_swings,
    )

    if difference is None:
        return []

    strength = min(abs(difference) * 5, 1.0)

    if difference >= config.PROGRESSION_NEUTRAL_MARGIN:
        return [
            Evidence(
                code=EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING,
                category=EvidenceCategory.TREND,
                direction=EvidenceDirection.BULLISH,
                strength=strength,
                weight=1.0,
                observation="Professional structural progression improving",
                description=(
                    "Recent structural swing quality is stronger "
                    "than the previous campaign."
                ),
                bar_index=ctx.current.bar_index,
                week_beginning=str(ctx.current.week_beginning),
            )
        ]

    if difference <= -config.PROGRESSION_NEUTRAL_MARGIN:
        return [
            Evidence(
                code=EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING,
                category=EvidenceCategory.TREND,
                direction=EvidenceDirection.BEARISH,
                strength=strength,
                weight=1.0,
                observation="Professional structural progression weakening",
                description=(
                    "Recent structural swing quality is weaker "
                    "than the previous campaign."
                ),
                bar_index=ctx.current.bar_index,
                week_beginning=str(ctx.current.week_beginning),
            )
        ]

    return []
