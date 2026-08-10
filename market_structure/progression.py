from __future__ import annotations

import config

from models import ClassifiedSwing, ProfessionalProgression, StructuralPattern, SwingLabel, StructuralSwing


def determine_structural_pattern(
    swings: tuple[ClassifiedSwing, ...],
) -> StructuralPattern:
    if len(swings) < 3:
        return StructuralPattern.UNKNOWN

    recent = swings[-3:]
    labels = tuple(
        classified_swing.label
        for classified_swing in recent
        if classified_swing.label is not None
    )

    if len(labels) < 3:
        return StructuralPattern.UNKNOWN

    if labels in (
        (SwingLabel.HH, SwingLabel.HL, SwingLabel.HH),
        (SwingLabel.HL, SwingLabel.HH, SwingLabel.HL),
    ):
        return StructuralPattern.IMPROVING

    if labels in (
        (SwingLabel.LH, SwingLabel.LL, SwingLabel.LH),
        (SwingLabel.LL, SwingLabel.LH, SwingLabel.LL),
    ):
        return StructuralPattern.WEAKENING

    if SwingLabel.LL in labels and SwingLabel.HH in labels:
        return StructuralPattern.BREAKING

    return StructuralPattern.STABLE


def calculate_professional_progression(
    structural_swings: tuple[StructuralSwing, ...],
) -> tuple[ProfessionalProgression, float | None]:
    scores = [
        float(swing.evaluation.professional.overall)
        for swing in structural_swings
    ]

    if len(scores) < 6:
        return ProfessionalProgression.UNKNOWN, None

    window = min(5, len(scores) // 2)
    older = scores[-(window * 2):-window]
    recent = scores[-window:]

    difference = (
        _weighted_average(recent)
        - _weighted_average(older)
    )

    if difference >= config.PROGRESSION_NEUTRAL_MARGIN:
        return ProfessionalProgression.IMPROVING, difference

    if difference <= -config.PROGRESSION_NEUTRAL_MARGIN:
        return ProfessionalProgression.WEAKENING, difference

    return ProfessionalProgression.STABLE, difference


def determine_professional_progression(
    structural_swings: tuple[StructuralSwing, ...],
) -> ProfessionalProgression:
    progression, _ = calculate_professional_progression(structural_swings)
    return progression

def _weighted_average(values: list[float]) -> float:
    if not values:
        return 0.0

    weights = range(1, len(values) + 1)
    return sum(
        value * weight
        for value, weight in zip(values, weights)
    ) / sum(weights)
