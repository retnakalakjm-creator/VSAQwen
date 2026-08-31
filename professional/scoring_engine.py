from __future__ import annotations

import pandas as pd

import config
from model import (
    ProfessionalScore,
    ProfessionalScoreResult,
)
from model.evidence_result_model import EvidenceResult
from models import BackgroundContext, Evidence, EvidenceCategory, EvidenceCode, TrendDirection, TrendState
from trend import TrendResult


class ProfessionalScoringEngine:

    def calculate(
        self,
        trend: TrendResult,
        evidence: EvidenceResult,
    ) -> ProfessionalScoreResult:
        trend_score = self._score_trend(trend)
        supply_score = self._score_supply(evidence)
        demand_score = self._score_demand(evidence)
        effort_score = self._score_effort(evidence)

        strength_score = self._score_strength(
            trend_score,
            demand_score,
            supply_score,
            effort_score,
        )

        weakness_score = self._score_weakness(
            trend_score,
            demand_score,
            supply_score,
            effort_score,
        )

        confidence = self._measure_confidence(
            ProfessionalScore(
                trend=trend_score,
                supply=supply_score,
                demand=demand_score,
                effort=effort_score,
                strength=strength_score,
                weakness=weakness_score,
                confidence=0.0,
            )
        )
        confidence = self._apply_increasing_demand_gate(
            confidence=confidence,
            trend=trend,
            evidence=evidence,
        )

        scores = ProfessionalScore(
            trend=trend_score,
            supply=supply_score,
            demand=demand_score,
            effort=effort_score,
            strength=strength_score,
            weakness=weakness_score,
            confidence=confidence,
        )

        return ProfessionalScoreResult(
            scores=scores,
            evidence=evidence.evidence,
        )

    @staticmethod
    def _apply_increasing_demand_gate(
        *,
        confidence: float,
        trend: TrendResult,
        evidence: EvidenceResult,
    ) -> float:
        """
        Keep INCREASING_DEMAND as confirmation evidence, but do not let it
        upgrade actionability outside a healthy uptrend when it is the only
        bullish VSA evidence.

        INCREASING_DEMAND is intentionally absent from the professional demand
        weight map, so demand/supply pressure must not be used as an additional
        gate for this confirmation-only event.
        """
        bullish_codes = frozenset({
            EvidenceCode.STOPPING_VOLUME,
            EvidenceCode.DEMAND_COMING_IN,
            EvidenceCode.INCREASING_DEMAND,
            EvidenceCode.HIDDEN_DEMAND,
            EvidenceCode.DEMAND_DRYING_UP,
            EvidenceCode.NO_SUPPLY,
            EvidenceCode.SPRING,
            EvidenceCode.TEST,
            EvidenceCode.SELLING_CLIMAX,
            EvidenceCode.SHAKEOUT,
        })
        bearish_codes = frozenset({
            EvidenceCode.BUYING_CLIMAX,
            EvidenceCode.SUPPLY_COMING_IN,
            EvidenceCode.INCREASING_SUPPLY,
            EvidenceCode.HIDDEN_SUPPLY,
            EvidenceCode.SUPPLY_HIGH_VOLUME,
            EvidenceCode.SUPPLY_WIDE_SPREAD,
            EvidenceCode.SUPPLY_ABSORPTION,
            EvidenceCode.UPTHRUST,
            EvidenceCode.NO_DEMAND,
        })

        codes = {item.code for item in evidence.evidence}
        bullish = codes & bullish_codes
        bearish = codes & bearish_codes
        only_increasing_demand = bullish == {EvidenceCode.INCREASING_DEMAND}

        if not only_increasing_demand:
            return confidence
        if bearish:
            return 0.0
        if trend.structure.direction != TrendDirection.UP:
            return 0.0
        if trend.structure.state != TrendState.HEALTHY:
            return 0.0

        return confidence

    @staticmethod
    def _score_trend(
        trend: TrendResult,
    ) -> float:
        """
        Convert the TrendResult into a normalized
        professional trend score.
        """
        structure = trend.structure

        if structure.direction in (
            TrendDirection.UNKNOWN,
            TrendDirection.RANGE,
        ):
            return 0.0

        score = (
            config.TREND_SCORE_WEIGHT * structure.strength
            + config.STATE_SCORE_WEIGHT * config.TREND_STATE_SCORES[structure.state]
            + config.CONFIDENCE_SCORE_WEIGHT * structure.confidence
        )

        return max(0.0, min(score, 1.0))

    @staticmethod
    def _score_evidence(
        evidence: tuple[Evidence, ...],
        category: EvidenceCategory,
        weights: dict[EvidenceCode, float],
    ) -> float:
        """
        Calculate a normalized score for a single EvidenceCategory.

        Only evidence belonging to the requested category contributes to the score.
        """
        score = 0.0

        for item in evidence:
            if item.category != category:
                continue
            score += weights.get(item.code, 0.0)

        return min(score, 1.0)

    @staticmethod
    def _score_supply(
        result: EvidenceResult,
    ) -> float:
        """Calculate professional supply pressure."""
        return ProfessionalScoringEngine._score_evidence(
            result.evidence,
            EvidenceCategory.SUPPLY,
            config.SUPPLY_EVIDENCE_WEIGHTS,
        )

    @staticmethod
    def _score_demand(
        result: EvidenceResult,
    ) -> float:
        """Calculate professional demand pressure."""
        return ProfessionalScoringEngine._score_evidence(
            result.evidence,
            EvidenceCategory.DEMAND,
            config.DEMAND_EVIDENCE_WEIGHTS,
        )

    @staticmethod
    def _score_effort(
        result: EvidenceResult,
    ) -> float:
        """Calculate professional effort."""
        return ProfessionalScoringEngine._score_evidence(
            result.evidence,
            EvidenceCategory.EFFORT,
            config.EFFORT_EVIDENCE_WEIGHTS,
        )

    @staticmethod
    def _score_strength(
        trend_score: float,
        demand_score: float,
        supply_score: float,
        effort_score: float,
    ) -> float:
        """
        Calculate overall professional strength.

        Strength increases when:

            • Trend is healthy
            • Demand exceeds supply
            • Effort confirms the move
        """
        demand_advantage = max(
            demand_score - supply_score,
            0.0,
        )

        score = (
            config.STRENGTH_TREND_WEIGHT * trend_score
            + config.STRENGTH_DEMAND_WEIGHT * demand_advantage
            + config.STRENGTH_EFFORT_WEIGHT * effort_score
        )

        return max(
            0.0,
            min(score, 1.0),
        )

    @staticmethod
    def _score_weakness(
        trend_score: float,
        demand_score: float,
        supply_score: float,
        effort_score: float,
    ) -> float:
        """
        Calculate overall professional weakness.

        Weakness increases when:

            • Trend is weak
            • Supply exceeds demand
            • Effort does not support the move
        """
        supply_advantage = max(
            supply_score - demand_score,
            0.0,
        )

        weak_trend = 1.0 - trend_score
        weak_effort = 1.0 - effort_score

        score = (
            config.WEAKNESS_TREND_WEIGHT * weak_trend
            + config.WEAKNESS_SUPPLY_WEIGHT * supply_advantage
            + config.WEAKNESS_EFFORT_WEIGHT * weak_effort
        )

        return max(
            0.0,
            min(score, 1.0),
        )

    @staticmethod
    def _measure_confidence(
        score: ProfessionalScore,
    ) -> float:
        """
        Measure confidence in the professional assessment.

        Confidence measures how consistent the evidence is,
        not whether the market is bullish or bearish.
        """
        trend_component = (
            score.trend
            * config.PROFESSIONAL_CONFIDENCE_TREND_WEIGHT
        )

        agreement_component = (
            abs(score.demand - score.supply)
            * config.PROFESSIONAL_CONFIDENCE_AGREEMENT_WEIGHT
        )

        effort_component = (
            score.effort
            * config.PROFESSIONAL_CONFIDENCE_EFFORT_WEIGHT
        )

        confidence = (
            trend_component
            + agreement_component
            + effort_component
        )

        return max(
            0.0,
            min(confidence, 1.0),
        )
