"""
Effort vs Result evidence collector.
"""

from __future__ import annotations

import config
from .rules import (
    closes_lower, closes_middle, is_above_average_spread, is_down_bar, 
    is_high_volume, is_low_volume, is_narrow_spread, is_neutral_close, is_strong_close, 
    is_up_bar, is_very_high_volume, is_weak_close, is_wide_spread, 
    spread_increasing, volume_increasing,
)
from models import (
    BackgroundContext,
    Evidence,
    EvidenceCategory,
    EvidenceCode,
)

from .helpers import (
    EvidenceCollector,
    add_evidence,
)


# -------------------------------------------------------------------------
# Public API
# -------------------------------------------------------------------------

def collect_effort(
    ctx: BackgroundContext,
) -> list[Evidence]:
    """
    Collect Effort vs Result evidence.
    """

    evidence: list[Evidence] = []

    _detect_effort_greater_than_result(
        ctx,
        evidence,
    )

    _detect_result_greater_than_effort(
        ctx,
        evidence,
    )

    _detect_absorption(
        ctx,
        evidence,
    )

    return evidence

# -------------------------------------------------------------------------
# Exceptional Effort
# -------------------------------------------------------------------------



# -------------------------------------------------------------------------
# Exceptional Result
# -------------------------------------------------------------------------



# -------------------------------------------------------------------------
# Effort > Result
# -------------------------------------------------------------------------

def _detect_effort_greater_than_result(
    ctx: BackgroundContext,
    evidence: list[Evidence],
) -> None:
    """
    Large effort producing little result.
    """

    last = ctx.current

    if not is_high_volume(last):
        return

    if not is_narrow_spread(last):
        return

    if not (
        is_weak_close(last)
        or is_neutral_close(last)
    ):
        return

    evidence.append(
        Evidence(
            category=EvidenceCategory.EFFORT,
            code=EvidenceCode.EFFORT_GT_RESULT,
            strength=1.0,
            weight=config.EFFORT_MAJOR_WEIGHT,
            observation=(
                "High effort produced little price progress."
            ),
        )
    )
    


# -------------------------------------------------------------------------
# Result > Effort
# -------------------------------------------------------------------------
def _detect_result_greater_than_effort(
    ctx: BackgroundContext,
    evidence: list[Evidence],
) -> None:
    """
    Good result produced with little effort.
    """

    last = ctx.current

    if not is_low_volume(last):
        return

    if not is_wide_spread(last):
        return

    if not is_strong_close(last):
        return

    evidence.append(
        Evidence(
            category=EvidenceCategory.EFFORT,
            code=EvidenceCode.RESULT_GT_EFFORT,
            strength=1.0,
            weight=config.EFFORT_MINOR_WEIGHT,
            observation=(
                "Strong price progress achieved with relatively little effort."
            ),
        )
    )
    

# -------------------------------------------------------------------------
# Climactic Action
# -------------------------------------------------------------------------




# -------------------------------------------------------------------------
# Absorption
# -------------------------------------------------------------------------
def _detect_absorption(
    ctx: BackgroundContext,
    evidence: list[Evidence],
) -> None:
    """
    Detect professional absorption.
    """

    last = ctx.current

    if not is_high_volume(last):
        return

    if not is_narrow_spread(last):
        return

    if not is_neutral_close(last):
        return

    evidence.append(
        Evidence(
            category=EvidenceCategory.EFFORT,
            code=EvidenceCode.ABSORPTION,
            strength=1.0,
            weight=config.ABSORPTION_WEIGHT,
            observation=(
                "High volume with limited price movement suggests professional absorption."
            ),
        )
    )
    

            