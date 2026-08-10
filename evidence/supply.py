"""
Professional VSA Swing Scanner

Supply Evidence Collector

Collects all supply-side background evidence.
"""

from __future__ import annotations

from .campaign import has_buying_campaign

from .rules import (
    closes_lower, closes_lower_than_previous, has_strong_spread, is_above_average_spread, is_bullish_bar, is_confirmed_uptrend, is_down_bar, 
    is_high_volume, is_low_volume, is_narrow_spread, 
    is_up_bar, is_very_high_volume, is_weak_close, is_wide_spread, makes_higher_high, 
    spread_increasing, volume_decreasing, volume_increasing,
)
from .helpers import (
    EvidenceCollector,
    add_evidence,
    evaluate_detector,
    requirement,
    requirements_passed,
)
from models import (
    BackgroundContext,    
    Evidence,
    EvidenceCategory,
    EvidenceCode,
    EvidenceDirection,
    
)

# -------------------------------------------------------------------------
# Public API
# -------------------------------------------------------------------------

def collect_supply(
    ctx: BackgroundContext,
) -> list[Evidence]:
    """
    Collect supply-side evidence from the recent
    background bars.
    """

    evidence: list[Evidence] = []

    # Skip index 0 because it has no previous bar.
    for i in range(1, len(ctx.bars)):

        bar_ctx = ctx.with_current(i)

        evidence.extend(
            _collect_buying_climax(bar_ctx)
        )

        evidence.extend(
            _collect_supply_coming_in(bar_ctx)
        )

        evidence.extend(
            _collect_hidden_supply(bar_ctx)
        )

        evidence.extend(
            _collect_increasing_supply(bar_ctx)
        )

        evidence.extend(
            _collect_supply_drying_up(bar_ctx)
        )

        evidence.extend(
            _collect_upthrust(bar_ctx)
        )

        evidence.extend(
            _collect_no_demand(bar_ctx)
        )

        # evidence.extend(
        #     _collect_supply_absorption(bar_ctx)
        # )
        #
        # evidence.extend(
        #     _collect_high_volume_supply(bar_ctx)
        # )
        #
        # evidence.extend(
        #     _collect_wide_spread_supply(bar_ctx)
        # )

    return evidence


# -------------------------------------------------------------------------
# Buying Climax
# -------------------------------------------------------------------------
def _collect_buying_climax(
    ctx: BackgroundContext,
) -> list[Evidence]:

    evidence: list[Evidence] = []

    bar = ctx.current
    previous = ctx.previous   

    # --------------------------------------------------
    # Requirements
    # --------------------------------------------------

    requirements = (

        requirement(
            name="Buying Campaign",
            passed=has_buying_campaign(ctx),
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

    )

    if not requirements_passed(requirements):
        return evidence
    
    
    # --------------------------------------------------
    # Confirmations
    # --------------------------------------------------

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
            passed=volume_increasing(
                bar,
                previous,
            ),
        ),

    )

    # --------------------------------------------------
    # Evidence
    # --------------------------------------------------

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
) -> list[Evidence]:

    evidence: list[Evidence] = []

    bar = ctx.current
    previous = ctx.previous

    requirements = (
        requirement(
            name="Buying Campaign",
            passed=has_buying_campaign(ctx),
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
            passed=volume_increasing(
                bar,
                previous,
            ),
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
            passed=volume_decreasing(
                bar,
                previous,
            ),
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
# Uptrust 
# -------------------------------------------------------------------------
def _collect_upthrust(
    ctx: BackgroundContext,
) -> list[Evidence]:

    evidence: list[Evidence] = []

    bar = ctx.current
    previous = ctx.previous

    requirements = (

        requirement(
            name="Buying Campaign",
            passed=has_buying_campaign(ctx),
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
            name="Lower Close Than Previous",
            passed=closes_lower_than_previous(
                bar,
                previous,
            ),
        ),

    )
    # print(
    #     "UPTHRUST CREATED",
    #     {
    #         "bar_index": ctx.current.bar_index,
    #         "code": EvidenceCode.UPTHRUST,
    #     },
    # )
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