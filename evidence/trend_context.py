"""
Trend evidence collector.

Converts TrendStructure into professional
background evidence.
"""

from __future__ import annotations

import config
from models import (
    BackgroundContext,
    Evidence,
    EvidenceCategory,
    EvidenceCode,
    TrendDirection,
    TrendResult,
    TrendState,
)


# -------------------------------------------------------------------------
# Public API
# -------------------------------------------------------------------------

def collect_trend(
    ctx: BackgroundContext,
) -> list[Evidence]:
    """
    Collect trend evidence.
    """

    evidence: list[Evidence] = []

    _detect_strong_uptrend(ctx, evidence)

    _detect_weak_uptrend(ctx, evidence)

    _detect_strong_downtrend(ctx, evidence)

    _detect_weak_downtrend(ctx, evidence)

    _detect_sideways_market(ctx, evidence)

    return evidence


# -------------------------------------------------------------------------
# Strong Uptrend
# -------------------------------------------------------------------------

def _detect_strong_uptrend(
    ctx: BackgroundContext,    
    evidence: list[Evidence],
) -> None:

    trend = ctx.trend

    if trend.direction != TrendDirection.UP:
        return

    if trend.state != TrendState.HEALTHY:
        return

    evidence.append(
        Evidence(
            category=EvidenceCategory.TREND,
            code=EvidenceCode.STRONG_UPTREND,
            strength=trend.confidence,
            weight=config.TREND_STRONG_WEIGHT,
            observation=(
                "Healthy uptrend with a consistent "
                "sequence of higher highs and higher lows."
            ),
        )
    )


# -------------------------------------------------------------------------
# Weak Uptrend
# -------------------------------------------------------------------------

def _detect_weak_uptrend(
    ctx: BackgroundContext,
    evidence: list[Evidence],
) -> None:

    trend = ctx.trend

    if trend.direction != TrendDirection.UP:
        return

    if trend.state not in (
        TrendState.DEVELOPING,
        TrendState.CORRECTING,
    ):
        return

    evidence.append(
        Evidence(
            category=EvidenceCategory.TREND,
            code=EvidenceCode.WEAK_UPTREND,
            strength=trend.confidence,
            weight=config.TREND_WEAK_WEIGHT,
            observation=(
                "Uptrend remains intact but is "
                "developing or correcting."
            ),
        )
    )


# -------------------------------------------------------------------------
# Strong Downtrend
# -------------------------------------------------------------------------

def _detect_strong_downtrend(
    ctx: BackgroundContext,
    evidence: list[Evidence],
) -> None:

    trend = ctx.trend

    if trend.direction != TrendDirection.DOWN:
        return

    if trend.state != TrendState.HEALTHY:
        return

    evidence.append(
        Evidence(
            category=EvidenceCategory.TREND,
            code=EvidenceCode.STRONG_DOWNTREND,
            strength=trend.confidence,
            weight=config.TREND_STRONG_WEIGHT,
            observation=(
                "Healthy downtrend with a consistent "
                "sequence of lower highs and lower lows."
            ),
        )
    )


# -------------------------------------------------------------------------
# Weak Downtrend
# -------------------------------------------------------------------------

def _detect_weak_downtrend(
    ctx: BackgroundContext,
    evidence: list[Evidence],
) -> None:

    trend = ctx.trend

    if trend.direction != TrendDirection.DOWN:
        return

    if trend.state not in (
        TrendState.DEVELOPING,
        TrendState.CORRECTING,
    ):
        return

    evidence.append(
        Evidence(
            category=EvidenceCategory.TREND,
            code=EvidenceCode.WEAK_DOWNTREND,
            strength=trend.confidence,
            weight=config.TREND_WEAK_WEIGHT,
            observation=(
                "Downtrend remains intact but is "
                "developing or correcting."
            ),
        )
    )


# -------------------------------------------------------------------------
# Sideways Market
# -------------------------------------------------------------------------

def _detect_sideways_market(
    ctx: BackgroundContext,
    evidence: list[Evidence],
) -> None:

    trend = ctx.trend

    if trend.direction != TrendDirection.RANGE:
        return

    evidence.append(
        Evidence(
            category=EvidenceCategory.TREND,
            code=EvidenceCode.SIDEWAYS_MARKET,
            strength=1.0,
            weight=config.TREND_RANGE_WEIGHT,
            observation=(
                "Market is currently range-bound with "
                "no dominant trend structure."
            ),
        )
    )