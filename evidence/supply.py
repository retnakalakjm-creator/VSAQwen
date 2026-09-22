"""
Professional VSA Swing Scanner

Supply Evidence Collector

Collects all supply-side background evidence.
"""

from __future__ import annotations

from .campaign import has_buying_campaign
from .campaign_snapshot import CampaignSnapshot

from .rules import (
    closes_lower,
    has_strong_spread,
    is_above_average_spread,
    is_bullish_bar,
    is_down_bar,
    is_high_volume,
    is_low_volume,
    is_narrow_spread,
    is_up_bar,
    is_very_high_volume,
    is_weak_close,
    spread_increasing,
    volume_decreasing,
    volume_increasing,
)
from .helpers import (
    add_evidence,
    evaluate_detector,
    requirement,
    requirements_passed,
)
from models import (
    BackgroundContext,
    ClosePosition,
    Evidence,
    EvidenceCode,
    StructuralSwing,
    SwingType,
)

# -------------------------------------------------------------------------
# Public API
# -------------------------------------------------------------------------

def collect_supply(
    ctx: BackgroundContext,
) -> list[Evidence]:
    """Collect supply-side evidence for the current point-in-time bar only."""

    campaign_snapshot = CampaignSnapshot.from_context(ctx)
    evidence: list[Evidence] = []

    evidence.extend(_collect_buying_climax(ctx, campaign_snapshot))
    evidence.extend(_collect_supply_coming_in(ctx, campaign_snapshot))
    evidence.extend(_collect_hidden_supply(ctx))
    evidence.extend(_collect_increasing_supply(ctx))
    evidence.extend(_collect_supply_drying_up(ctx))
    evidence.extend(_collect_upthrust(ctx))
    evidence.extend(_collect_no_demand(ctx))

    return evidence

# -------------------------------------------------------------------------
# Buying Climax
# -------------------------------------------------------------------------
def _collect_buying_climax(
    ctx: BackgroundContext,
    campaign_snapshot: CampaignSnapshot | None = None,
) -> list[Evidence]:
    """Detect climactic buying effort without strong high-price acceptance."""

    evidence: list[Evidence] = []

    bar = ctx.current
    previous = ctx.previous
    snapshot = campaign_snapshot or CampaignSnapshot.from_context(ctx)

    requirements = (
        requirement(
            name="Buying Campaign",
            passed=snapshot.has_buying_campaign(),
        ),
        requirement(
            name="Bullish Bar",
            passed=is_bullish_bar(bar),
        ),
        requirement(
            name="Very High Volume",
            passed=is_very_high_volume(bar),
        ),
        requirement(
            name="Above Average Spread",
            passed=is_above_average_spread(bar),
        ),
        requirement(
            name="Non-Strong High Acceptance",
            passed=bar.close_position
            not in (ClosePosition.UPPER, ClosePosition.ON_HIGH),
        ),
    )

    if not requirements_passed(requirements):
        return evidence

    confirmations = (
        requirement(
            name="Wide Spread",
            passed=has_strong_spread(bar),
        ),
        requirement(
            name="Weak Close",
            passed=is_weak_close(bar),
        ),
        requirement(
            name="Increasing Volume",
            passed=volume_increasing(bar, previous),
        ),
    )

    evaluate_detector(
        evidence=evidence,
        ctx=ctx,
        code=EvidenceCode.BUYING_CLIMAX,
        requirements=requirements,
        confirmations=confirmations,
    )

    return evidence


# -------------------------------------------------------------------------
# Supply Coming In
# -------------------------------------------------------------------------
def _collect_supply_coming_in(
    ctx: BackgroundContext,
    campaign_snapshot: CampaignSnapshot | None = None,
) -> list[Evidence]:

    evidence: list[Evidence] = []

    bar = ctx.current
    previous = ctx.previous
    snapshot = campaign_snapshot or CampaignSnapshot.from_context(ctx)

    requirements = (
        requirement(
            name="Buying Campaign",
            passed=snapshot.has_buying_campaign(),
        ),
        requirement(
            name="Down Bar",
            passed=is_down_bar(bar),
        ),
        requirement(
            name="High Volume",
            passed=is_high_volume(bar),
        ),
        requirement(
            name="Above Average Spread",
            passed=is_above_average_spread(bar),
        ),
        requirement(
            name="Weak Close",
            passed=is_weak_close(bar),
        ),
        requirement(
            name="Volume Increasing",
            passed=volume_increasing(bar, previous),
        ),
    )

    evaluate_detector(
        evidence=evidence,
        ctx=ctx,
        code=EvidenceCode.SUPPLY_COMING_IN,
        requirements=requirements,
    )

    return evidence


# -------------------------------------------------------------------------
# Hidden Supply
# -------------------------------------------------------------------------
def _collect_hidden_supply(
    ctx: BackgroundContext,
) -> list[Evidence]:

    evidence: list[Evidence] = []
    bar = ctx.current

    if (
        is_up_bar(bar)
        and is_high_volume(bar)
        and closes_lower(bar)
    ):
        add_evidence(
            evidence=evidence,
            ctx=ctx,
            code=EvidenceCode.HIDDEN_SUPPLY,
        )

    return evidence

# -------------------------------------------------------------------------
# Wide Spread Supply
# -------------------------------------------------------------------------


# -------------------------------------------------------------------------
# Increasing Supply
# -------------------------------------------------------------------------
def _collect_increasing_supply(
    ctx: BackgroundContext,
) -> list[Evidence]:

    evidence: list[Evidence] = []

    if not ctx.has_previous:
        return evidence

    current = ctx.current
    previous = ctx.previous

    if (
        is_down_bar(current)
        and volume_increasing(current, previous)
        and spread_increasing(current, previous)
    ):
        add_evidence(
            evidence=evidence,
            ctx=ctx,
            code=EvidenceCode.INCREASING_SUPPLY,
        )

    return evidence


# -------------------------------------------------------------------------
# Supply Drying Up
# -------------------------------------------------------------------------
def _collect_supply_drying_up(
    ctx: BackgroundContext,
) -> list[Evidence]:

    evidence: list[Evidence] = []
    bar = ctx.current

    if (
        is_down_bar(bar)
        and is_low_volume(bar)
        and is_narrow_spread(bar)
    ):
        add_evidence(
            evidence=evidence,
            ctx=ctx,
            code=EvidenceCode.SUPPLY_DRYING_UP,
        )

    return evidence

# -------------------------------------------------------------------------
# Supply Absorption
# -------------------------------------------------------------------------


# -------------------------------------------------------------------------
# No Demand
# -------------------------------------------------------------------------
def _collect_no_demand(
    ctx: BackgroundContext,
) -> list[Evidence]:

    evidence: list[Evidence] = []

    bar = ctx.current
    previous = ctx.previous

    requirements = (
        requirement(
            name="Bullish Environment",
            passed=ctx.is_bullish_environment(),
        ),
        requirement(
            name="Bullish Bar",
            passed=is_bullish_bar(bar),
        ),
        requirement(
            name="Low Volume",
            passed=is_low_volume(bar),
        ),
        requirement(
            name="Narrow Spread",
            passed=is_narrow_spread(bar),
        ),
    )

    if not requirements_passed(requirements):
        return evidence

    confirmations = (
        requirement(
            name="Volume Decreasing",
            passed=volume_decreasing(bar, previous),
        ),
        requirement(
            name="Weak Close",
            passed=is_weak_close(bar),
        ),
    )

    evaluate_detector(
        evidence=evidence,
        ctx=ctx,
        code=EvidenceCode.NO_DEMAND,
        requirements=requirements,
        confirmations=confirmations,
    )

    return evidence


# -------------------------------------------------------------------------
# Upthrust
# -------------------------------------------------------------------------
def _latest_confirmed_structural_high(
    ctx: BackgroundContext,
) -> StructuralSwing | None:
    """Return the latest structural high already visible at the current bar."""

    eligible = (
        item
        for item in ctx.structural_swings
        if item.swing.type is SwingType.HIGH
        and item.swing.confirmation_index <= ctx.current.bar_index
        and item.swing.bar_index < ctx.current.bar_index
    )
    return max(
        eligible,
        key=lambda item: (
            item.swing.confirmation_index,
            item.swing.bar_index,
        ),
        default=None,
    )


def _collect_upthrust(
    ctx: BackgroundContext,
) -> list[Evidence]:
    """Detect rejection after a probe above confirmed structural resistance."""

    evidence: list[Evidence] = []
    bar = ctx.current

    structural_high = _latest_confirmed_structural_high(ctx)
    structural_high_price = (
        None
        if structural_high is None
        else float(structural_high.swing.price)
    )

    requirements = (
        requirement(
            name="Confirmed Structural High",
            passed=structural_high_price is not None,
        ),
        requirement(
            name="Probe Above Structural High",
            passed=(
                structural_high_price is not None
                and float(bar.high) > structural_high_price
            ),
        ),
        requirement(
            name="Failed Acceptance Above Structural High",
            passed=(
                structural_high_price is not None
                and float(bar.close_price) <= structural_high_price
            ),
        ),
    )

    if not requirements_passed(requirements):
        return evidence

    confirmations = (
        requirement(
            name="Weak Close",
            passed=is_weak_close(bar),
        ),
        requirement(
            name="Very High Volume",
            passed=is_very_high_volume(bar),
        ),
        requirement(
            name="Above Average Spread",
            passed=is_above_average_spread(bar),
        ),
    )

    evaluate_detector(
        evidence=evidence,
        ctx=ctx,
        code=EvidenceCode.UPTHRUST,
        requirements=requirements,
        confirmations=confirmations,
    )

    return evidence


# ==========================================================
# Public API
# ==========================================================
__all__ = [
    "collect_supply",
]
