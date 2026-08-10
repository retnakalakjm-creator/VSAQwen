"""
Professional Wyckoff Engine.
"""


import config
from model.evidence_result_model import EvidenceResult
from model.score_model import ProfessionalScore, ProfessionalScoreResult
from models import TrendResult
from wyckoff.wyckoff_model import MarketBias, WyckoffEvent, WyckoffPhase, WyckoffResult


class WyckoffEngine:
    """
    Professional Wyckoff interpretation engine.

    Consumes:

        TrendResult

        EvidenceResult

        ProfessionalScoreResult

    Produces:

        WyckoffResult
    """

    @staticmethod
    def _clamp(value: float) -> float:
        """
        Clamp a score to the range [0.0, 1.0].
        """
        return max(
            0.0,
            min(value, 1.0),
        )
    
    
    def analyze(
        self,
        trend: TrendResult,
        evidence: EvidenceResult,
        score: ProfessionalScoreResult,
    ) -> WyckoffResult:

        phase = self._detect_phase(
            trend,
            evidence,
            score,
        )

        events = self._detect_events(
            trend,
            evidence,
            score,
        )

        bias = self._determine_bias(
            phase,
            events,
        )

        confidence = self._measure_confidence(
            phase,
            events,
            score,
        )

        summary = self._build_summary(
            phase,
            events,
            bias,
            confidence,
        )

        return WyckoffResult(
            phase=phase,
            events=events,
            bias=bias,
            confidence=confidence,
            summary=summary,
        )
          
    
    def _detect_phase(
        self,
        trend: TrendResult,
        evidence: EvidenceResult,
        score: ProfessionalScoreResult,
    ) -> WyckoffPhase:
        """
        Determine the dominant Wyckoff phase.
        """

        if self._is_accumulation(
            trend,
            evidence,
            score,
        ):
            return WyckoffPhase.ACCUMULATION

        if self._is_reaccumulation(
            trend,
            evidence,
            score,
        ):
            return WyckoffPhase.REACCUMULATION

        # Markup
        
        
        if self._is_distribution(
            trend,
            evidence,
            score,
        ):
            return WyckoffPhase.DISTRIBUTION

        # Redistribution
        # ↓
        # Markdown
        
        
        return WyckoffPhase.UNKNOWN
    
    
    def _is_accumulation(
        self,
        trend: TrendResult,
        evidence: EvidenceResult,
        score: ProfessionalScoreResult,
    ) -> bool:
        """
        Determine whether the current market structure is
        consistent with Wyckoff accumulation.
        """

        if not self._trend_supports_accumulation(trend):
            return False

        if not self._background_supports_accumulation(evidence):
            return False

        if not self._professional_demand_present(score):
            return False

        return True
             
    
    def _trend_supports_accumulation(
        self,
        trend: TrendResult,
    ) -> bool:
        """
        Accumulation should not occur during a confirmed
        bearish trend.
        """

        return not trend.structure.is_downtrend
        
    def _trend_supports_reaccumulation(
        self,
        trend: TrendResult,
    ) -> bool:
        """
        Reaccumulation should occur within
        an established uptrend.
        """

        return trend.structure.is_uptrend
    
    
    def _background_supports_accumulation(
            self,
            evidence: EvidenceResult,
        ) -> bool:
            """
            Background evidence should already indicate
            professional accumulation.
            """
    
            if not evidence.has_demand:
                return False
    
            if evidence.has_supply:
                return False
    
            if evidence.has_weakness:
                return False
    
            return True
    
    def _background_supports_reaccumulation(
        self,
        evidence: EvidenceResult,
    ) -> bool:
        """
        Background evidence should already indicate
        professional reaccumulation.
        """

        if not evidence.has_demand:
            return False

        if evidence.has_supply:
            return False

        if evidence.has_weakness:
            return False

        return True
    
    def _is_reaccumulation(
            self,
            trend: TrendResult,
            evidence: EvidenceResult,
            score: ProfessionalScoreResult,
        ) -> bool:
            """
            Determine whether the current market structure
            is consistent with Wyckoff reaccumulation.
            """
    
            if not self._trend_supports_reaccumulation(trend):
                return False
    
            if not self._background_supports_reaccumulation(evidence):
                return False
    
            if not self._professional_reaccumulation_present(score):
                return False
    
            return True
    
    
    
    def _professional_demand_present(
        self,
        score: ProfessionalScoreResult,
    ) -> bool:
        """
        Professional demand must dominate supply before
        accumulation can be recognised.
        """

        professional = score.scores

        if professional.demand <= professional.supply:
            return False

        if professional.strength <= professional.weakness:
            return False

        if professional.confidence < config.WYCKOFF_MIN_CONFIDENCE:
            return False

        return True
    
    
    def _professional_reaccumulation_present(
        self,
        score: ProfessionalScoreResult,
    ) -> bool:
        """
        Professional demand must continue to
        dominate supply.
        """

        professional = score.scores

        if professional.demand <= professional.supply:
            return False

        if professional.strength <= professional.weakness:
            return False

        if professional.confidence < config.WYCKOFF_MIN_CONFIDENCE:
            return False

        return True
    
   
   
   
   
    def _is_distribution(
        self,
        trend: TrendResult,
        evidence: EvidenceResult,
        score: ProfessionalScoreResult,
    ) -> bool:
        """
        Determine whether the current market structure is
        consistent with Wyckoff distribution.
        """

        if not self._trend_supports_distribution(trend):
            return False

        if not self._background_supports_distribution(evidence):
            return False

        if not self._professional_supply_present(score):
            return False

        return True
    
    def _trend_supports_distribution(
        self,
        trend: TrendResult,
    ) -> bool:
        """
        Distribution should not occur during a confirmed
        bullish trend.
        """

        return not trend.structure.is_uptrend
    
    
    def _background_supports_distribution(
        self,
        evidence: EvidenceResult,
    ) -> bool:

        if not evidence.has_supply:
            return False

        if evidence.has_demand:
            return False

        if evidence.has_strength:
            return False

        return True
        
    
    def _professional_supply_present(
        self,
        score: ProfessionalScoreResult,
    ) -> bool:
        """
        Professional supply must dominate demand before
        distribution can be recognised.
        """

        professional = score.scores

        if professional.supply <= professional.demand:
            return False

        if professional.weakness <= professional.strength:
            return False

        if professional.confidence < config.WYCKOFF_MIN_CONFIDENCE:
            return False

        return True
    
    
    
    
    
    def _detect_events(
        self,
        trend: TrendResult,
        evidence: EvidenceResult,
        score: ProfessionalScoreResult,
    ) -> tuple[WyckoffEvent, ...]:
        """
        Detect Wyckoff events.

        Placeholder until event detection
        is implemented.
        """

        return ()
    
    def _determine_bias(
        self,
        phase: WyckoffPhase,
        events: tuple[WyckoffEvent, ...],
    ) -> MarketBias:

        if phase in (
            WyckoffPhase.ACCUMULATION,
            WyckoffPhase.REACCUMULATION,
            WyckoffPhase.MARKUP,
        ):
            return MarketBias.BULLISH

        if phase in (
            WyckoffPhase.DISTRIBUTION,
            WyckoffPhase.REDISTRIBUTION,
            WyckoffPhase.MARKDOWN,
        ):
            return MarketBias.BEARISH

        return MarketBias.NEUTRAL
    
    
    
    def _measure_confidence(
        self,
        phase: WyckoffPhase,
        events: tuple[WyckoffEvent, ...],
        score: ProfessionalScoreResult,
    ) -> float:

        confidence = score.scores.confidence

        if phase == WyckoffPhase.UNKNOWN:
            confidence *= config.WYCKOFF_UNKNOWN_PHASE_PENALTY

        if events:
            confidence += config.WYCKOFF_EVENT_CONFIDENCE_BONUS

        return self._clamp(confidence)
    
    def _build_summary(
        self,
        phase: WyckoffPhase,
        events: tuple[WyckoffEvent, ...],
        bias: MarketBias,
        confidence: float,
    ) -> str:
        """
        Build a concise professional summary.
        """

        return (
            f"{phase.name.title()} | "
            f"{bias.name.title()} | "
            f"Confidence: {confidence:.2f}"
        )
    
    