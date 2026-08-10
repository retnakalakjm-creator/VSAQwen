"""
Background scoring engine.

Converts collected VSA/Wyckoff evidence into a
professional market background assessment.
"""

from __future__ import annotations

from statistics import fmean
from model.evidence_result_model import EvidenceResult
import config
from models import (    
    Evidence,
    EvidenceCategory,
    EvidenceCode,
    MarketBias,
    WyckoffPhase,
)


# -------------------------------------------------------------------------
# Public API
# -------------------------------------------------------------------------

# def score_background(
#     evidence: list[Evidence],
# ) -> EvidenceResult:
#     """
#     Convert collected evidence into a professional
#     market background assessment.
#     """

#     bias = _score_bias(evidence)

#     phase = _score_phase(evidence)

#     confidence = _score_confidence(evidence)

#     return EvidenceResult(
#         bias=bias,
#         phase=phase,
#         confidence=confidence,
#         evidence=tuple(evidence),
#     )


# -------------------------------------------------------------------------
# Bias
# -------------------------------------------------------------------------

def _score_bias(
    evidence: list[Evidence],
) -> MarketBias:
    """
    Determine the overall Smart Money bias.
    """

    bullish = 0.0
    bearish = 0.0

    for item in evidence:

        score = item.weight * item.strength

        # ------------------------------
        # Bullish evidence
        # ------------------------------

        if item.code in (
            EvidenceCode.STOPPING_VOLUME,
            EvidenceCode.DEMAND_COMING_IN,
            EvidenceCode.INCREASING_DEMAND,
            EvidenceCode.HIDDEN_DEMAND,
            EvidenceCode.DEMAND_DRYING_UP,
            EvidenceCode.STRONG_UPTREND,
            EvidenceCode.WEAK_UPTREND,
            EvidenceCode.ACCUMULATION,
            EvidenceCode.REACCUMULATION,
            EvidenceCode.MARKUP,
        ):
            bullish += score

        # ------------------------------
        # Bearish evidence
        # ------------------------------

        elif item.code in (
            EvidenceCode.BUYING_CLIMAX,
            EvidenceCode.SUPPLY_COMING_IN,
            EvidenceCode.INCREASING_SUPPLY,
            EvidenceCode.HIDDEN_SUPPLY,
            EvidenceCode.SUPPLY_DRYING_UP,
            EvidenceCode.STRONG_DOWNTREND,
            EvidenceCode.WEAK_DOWNTREND,
            EvidenceCode.DISTRIBUTION,
            EvidenceCode.REDISTRIBUTION,
            EvidenceCode.MARKDOWN,
        ):
            bearish += score

    difference = bullish - bearish

    if difference > config.BACKGROUND_BIAS_MARGIN:
        return MarketBias.BULLISH

    if difference < -config.BACKGROUND_BIAS_MARGIN:
        return MarketBias.BEARISH

    return MarketBias.NEUTRAL


# -------------------------------------------------------------------------
# Wyckoff Phase
# -------------------------------------------------------------------------

def _score_phase(
    evidence: list[Evidence],
) -> WyckoffPhase:
    """
    Determine the dominant Wyckoff phase.

    This is intentionally simple for now.
    The Phase Engine will later replace this.
    """

    phase_weights: dict[WyckoffPhase, float] = {
        WyckoffPhase.ACCUMULATION: 0.0,
        WyckoffPhase.REACCUMULATION: 0.0,
        WyckoffPhase.MARKUP: 0.0,
        WyckoffPhase.DISTRIBUTION: 0.0,
        WyckoffPhase.REDISTRIBUTION: 0.0,
        WyckoffPhase.MARKDOWN: 0.0,
    }

    mapping = {
        EvidenceCode.ACCUMULATION: WyckoffPhase.ACCUMULATION,
        EvidenceCode.REACCUMULATION: WyckoffPhase.REACCUMULATION,
        EvidenceCode.MARKUP: WyckoffPhase.MARKUP,
        EvidenceCode.DISTRIBUTION: WyckoffPhase.DISTRIBUTION,
        EvidenceCode.REDISTRIBUTION: WyckoffPhase.REDISTRIBUTION,
        EvidenceCode.MARKDOWN: WyckoffPhase.MARKDOWN,
    }

    for item in evidence:

        phase = mapping.get(item.code)

        if phase is None:
            continue

        phase_weights[phase] += (
            item.weight * item.strength
        )

    if not any(phase_weights.values()):
        return WyckoffPhase.UNKNOWN

    return max(
        phase_weights,
        key=phase_weights.get,
    )


# -------------------------------------------------------------------------
# Confidence
# -------------------------------------------------------------------------

def _score_confidence(
    evidence: list[Evidence],
) -> float:
    """
    Confidence of the background assessment.
    """

    if not evidence:
        return 0.0

    confidence = fmean(
        item.strength
        for item in evidence
    )

    confidence = max(
        0.0,
        min(1.0, confidence),
    )

    return round(confidence, 3)