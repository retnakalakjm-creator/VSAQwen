
from background.evidence_score import score_evidence
from background.confluence import apply_confluence
from model.evidence_result_model import EvidenceResult
from models import (
    BackgroundAssessment,
    BackgroundBias,
    Evidence,
    EvidenceCategory,
    EvidenceCode,
    StructuralBackground,
    StructuralSwing,
)

class StructuralBackgroundAnalyzer:

    def analyze(
        self,
        evidence: EvidenceResult,        
    ) -> BackgroundAssessment:

        
        score = score_evidence(
            list(evidence.evidence),
        )
        
        score = apply_confluence(
            score,
            list(evidence.evidence),
        )
        # supply = self._measure_supply(
        #     evidence,
        # )
        supply = score.supply
        
        # demand = self._measure_demand(
        #     evidence,
        # )
        demand = score.demand
        
        # professional = self._measure_professional(
        #     evidence,
        # )
        professional = score.professional

        print()

        print("Evidence Score")

        print("---------------------")

        print(f"Supply       : {score.supply:.2f}")

        print(f"Demand       : {score.demand:.2f}")

        print(f"Professional : {score.professional:.2f}")
        
        # overall = (
        #     supply
        #     + demand
        #     + professional
        # ) / 3
        net_pressure  = demand - supply
        maximum = max(
            demand + supply,
            1.0,
        )
        overall = (
            net_pressure / maximum + 1.0
        ) / 2.0
        
        bias = self._determine_bias(
            supply=supply,
            demand=demand,
            professional=professional,
        )

        total = supply + demand

        if total <= 0.0:
            confidence = 0.0
        else:
            confidence = abs(demand - supply) / total    

        confidence *= (
            0.75 + professional * 0.25
        )
        confidence = max(
            0.0,
            min(confidence, 1.0),
        )
        
        background_evidence: list[Evidence] = []

        for item in evidence.evidence:

            if item.category in (
                EvidenceCategory.SUPPLY,
                EvidenceCategory.DEMAND,
                EvidenceCategory.TREND,
            ):
                background_evidence.append(item)
       
       
        summary = self._build_summary(
            supply=supply,
            demand=demand,
            professional=professional,
            bias=bias,
        )
        return BackgroundAssessment(
            supply=supply,
            demand=demand,
            professional=professional,
            overall=overall,
            bias=bias,
            confidence=confidence,
            evidence=tuple(background_evidence),
            summary=summary,
        )


    def _measure_supply(
        self,
        evidence: EvidenceResult,
    ) -> float:

        total = 0.0

        for item in evidence.evidence:

            if item.category != EvidenceCategory.SUPPLY:
                continue

            total += item.strength * item.weight

        return min(
            total,
            1.0,
        )


    def _measure_demand(
        self,
        evidence: EvidenceResult,
    ) -> float:

        total = 0.0

        for item in evidence.evidence:

            if item.category != EvidenceCategory.DEMAND:
                continue

            total += item.strength * item.weight

        return min(
            total,
            1.0,
        )


    def _measure_professional(
        self,
        evidence: EvidenceResult,
    ) -> float:

        score = 0.5

        for item in evidence.evidence:

            if (
                item.code
                == EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING
            ):

                score += 0.5 * item.strength

            elif (
                item.code
                == EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING
            ):

                score -= 0.5 * item.strength

        return max(
            0.0,
            min(
                score,
                1.0,
            ),
        )



    def _determine_bias(
        self,
        *,
        supply: float,
        demand: float,
        professional: float,
    ) -> BackgroundBias:

        bearish = (
            supply * 0.50
            + (1.0 - demand) * 0.25
            + (1.0 - professional) * 0.25
        )

        bullish = (
            demand * 0.50
            + professional * 0.25
            + (1.0 - supply) * 0.25
        )

        difference = bullish - bearish

        if difference >= 0.50:
            return BackgroundBias.VERY_BULLISH

        if difference >= 0.15:
            return BackgroundBias.BULLISH

        if difference <= -0.50:
            return BackgroundBias.VERY_BEARISH

        if difference <= -0.15:
            return BackgroundBias.BEARISH

        return BackgroundBias.NEUTRAL    
    

    def _build_summary(
        self,
        *,
        supply: float,
        demand: float,
        professional: float,
        bias: BackgroundBias,
    ) -> str:

        if bias == BackgroundBias.VERY_BEARISH:

            return (
                "Supply is dominant, demand is weak and "
                "professional participation is deteriorating."
            )

        if bias == BackgroundBias.BEARISH:

            return (
                "Supply currently outweighs demand. "
                "Background favours weakness."
            )

        if bias == BackgroundBias.NEUTRAL:

            return (
                "Background is balanced. "
                "No clear professional advantage."
            )

        if bias == BackgroundBias.BULLISH:

            return (
                "Demand exceeds supply. "
                "Professional participation is improving."
            )

        return (
            "Demand is dominant with strong professional "
            "participation."
        )    
            
    
    def _average(
        self,
        values: list[float],
    ) -> float:

        if not values:
            return 0.0

        return sum(values) / len(values)        