from debug.confidence_diagnostics import confidence_components
from model import ProfessionalScore
import config


def test_confidence_components_match_existing_formula() -> None:
    score = ProfessionalScore(
        trend=0.50,
        supply=0.70,
        demand=0.10,
        effort=0.25,
        strength=0.0,
        weakness=0.0,
        confidence=0.0,
    )

    result = confidence_components(score)

    expected_trend = 0.50 * config.PROFESSIONAL_CONFIDENCE_TREND_WEIGHT
    expected_agreement = (
        abs(0.10 - 0.70)
        * config.PROFESSIONAL_CONFIDENCE_AGREEMENT_WEIGHT
    )
    expected_effort = 0.25 * config.PROFESSIONAL_CONFIDENCE_EFFORT_WEIGHT
    expected_confidence = max(
        0.0,
        min(
            expected_trend + expected_agreement + expected_effort,
            1.0,
        ),
    )

    assert result["trend_component"] == expected_trend
    assert result["agreement_component"] == expected_agreement
    assert result["effort_component"] == expected_effort
    assert result["confidence"] == expected_confidence


def test_confidence_components_sum_to_confidence_when_not_capped() -> None:
    score = ProfessionalScore(
        trend=0.40,
        supply=0.20,
        demand=0.50,
        effort=0.30,
        strength=0.0,
        weakness=0.0,
        confidence=0.0,
    )

    result = confidence_components(score)

    components = (
        result["trend_component"]
        + result["agreement_component"]
        + result["effort_component"]
    )

    assert components <= 1.0
    assert result["confidence"] == components


def test_confidence_diagnostics_preserves_direction_neutrality() -> None:
    bullish = ProfessionalScore(
        trend=0.50,
        supply=0.10,
        demand=0.70,
        effort=0.20,
        strength=0.0,
        weakness=0.0,
        confidence=0.0,
    )
    bearish = ProfessionalScore(
        trend=0.50,
        supply=0.70,
        demand=0.10,
        effort=0.20,
        strength=0.0,
        weakness=0.0,
        confidence=0.0,
    )

    assert confidence_components(bullish)["confidence"] == confidence_components(
        bearish
    )["confidence"]
