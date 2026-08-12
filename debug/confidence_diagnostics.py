from __future__ import annotations

from model import ProfessionalScore
import config


def confidence_components(score: ProfessionalScore) -> dict[str, float]:
    """Expose the existing confidence calculation as diagnostic components."""
    trend_component = (
        score.trend * config.PROFESSIONAL_CONFIDENCE_TREND_WEIGHT
    )
    agreement_component = (
        abs(score.demand - score.supply)
        * config.PROFESSIONAL_CONFIDENCE_AGREEMENT_WEIGHT
    )
    effort_component = (
        score.effort * config.PROFESSIONAL_CONFIDENCE_EFFORT_WEIGHT
    )

    confidence = max(
        0.0,
        min(
            trend_component + agreement_component + effort_component,
            1.0,
        ),
    )

    return {
        "trend_component": trend_component,
        "agreement_component": agreement_component,
        "effort_component": effort_component,
        "confidence": confidence,
    }


def score_inputs(score: ProfessionalScore) -> dict[str, float]:
    """Return the exact normalized inputs consumed by confidence scoring."""
    return {
        "trend": score.trend,
        "demand": score.demand,
        "supply": score.supply,
        "effort": score.effort,
        "strength": score.strength,
        "weakness": score.weakness,
        "net_strength": score.net_strength,
        "net_pressure": score.net_pressure,
        "confidence": score.confidence,
    }
