from __future__ import annotations

from models import (
    ProfessionalProgression,
    StructuralPattern,
    StructuralSwing,
    VSAContext,
)

from market_structure.progression import determine_professional_progression


def build_vsa_context(
    trend,
    structural_pattern: StructuralPattern,
    structural_swings: tuple[StructuralSwing, ...],
) -> VSAContext:
    """Build context from independent structural inputs only."""

    latest = structural_swings[-1] if structural_swings else None
    evaluation = latest.evaluation if latest is not None else None

    professional_score = (
        float(evaluation.professional.overall)
        if evaluation is not None
        else None
    )

    stopping_volume = (
        float(evaluation.smart_money.stopping_volume)
        if evaluation is not None
        else None
    )

    climactic_volume = (
        float(evaluation.smart_money.climactic_volume)
        if evaluation is not None
        else None
    )

    return VSAContext(
        trend_direction=trend.direction,
        trend_state=trend.state,
        trend_strength=float(trend.strength),
        trend_confidence=float(trend.confidence),
        structural_pattern=structural_pattern,
        professional_progression=determine_professional_progression(
            structural_swings,
        ),
        professional_score=professional_score,
        stopping_volume=stopping_volume,
        climactic_volume=climactic_volume,
    )


