from models import Evidence, EvidenceCode, EvidenceDirection, EvidenceScore


def score_evidence(
    evidence: list[Evidence],
) -> EvidenceScore:
    
    supply = 0.0
    demand = 0.0
    professional = 0.0
    
    for item in evidence:

        score = item.strength * item.weight

        if item.direction == EvidenceDirection.BULLISH:
            demand += score

        elif item.direction == EvidenceDirection.BEARISH:
            supply += score

        if item.code in (
            EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING,
            EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING,
        ):
            professional += score
            
    return EvidenceScore(
        supply=supply,
        demand=demand,
        professional=professional,
    )        