"""
Audit the currently implemented event-specific weight components.

This is diagnostic-only: it does not change WeightCalculator behaviour.
Pass an already-built BackgroundContext to ``audit_weight_components``
from an existing replay/debug workflow.
"""

from __future__ import annotations

from models import BackgroundContext

from evidence.weight import WeightCalculator


def audit_weight_components(
    ctx: BackgroundContext,
    *,
    shakeout_quality: float = 1.0,
) -> None:
    """Print the exact components used by current event-specific weights."""

    shakeout_environment = (
        0.30
        if ctx.is_bearish_environment()
        else 0.00
    )
    shakeout_trend = WeightCalculator._shakeout_trend_adjustment(
        ctx.trend.direction,
        ctx.trend.state,
    )
    shakeout_structure = WeightCalculator._directional_structure_adjustment(
        expected_bullish=True,
        progression=ctx.structural_pattern,
    )

    shakeout_stopping = 0.0
    evaluation = ctx.latest_professional_evaluation
    if evaluation is not None:
        shakeout_stopping = WeightCalculator._stopping_adjustment(
            evaluation.smart_money.stopping_volume,
        )

    shakeout_pre_quality = max(
        0.50,
        min(
            2.00,
            1.00
            + shakeout_environment
            + shakeout_trend
            + shakeout_structure
            + shakeout_stopping,
        ),
    )

    shakeout_final = max(
        0.00,
        min(
            2.00,
            shakeout_pre_quality * shakeout_quality,
        ),
    )

    supply_trend = WeightCalculator._supply_coming_in_trend_adjustment(
        ctx.trend.direction,
        ctx.trend.state,
    )
    supply_structure = WeightCalculator._directional_structure_adjustment(
        expected_bullish=False,
        progression=ctx.structural_pattern,
    )

    supply_final = max(
        0.50,
        min(
            2.00,
            1.00 + supply_trend + supply_structure,
        ),
    )

    print(
        "EVENT SPECIFIC WEIGHT AUDIT",
        {
            "shakeout": {
                "environment": shakeout_environment,
                "trend": shakeout_trend,
                "structure": shakeout_structure,
                "stopping": shakeout_stopping,
                "pre_quality_weight": shakeout_pre_quality,
                "quality": shakeout_quality,
                "final_weight": shakeout_final,
            },
            "supply_coming_in": {
                "environment": 0.0,
                "trend": supply_trend,
                "structure": supply_structure,
                "final_weight": supply_final,
            },
        },
    )
