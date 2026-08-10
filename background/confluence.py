import config
from models import Evidence, EvidenceCode, EvidenceScore


def apply_confluence(
    score: EvidenceScore,
    evidence: list[Evidence],
) -> EvidenceScore:    
    
    supply = score.supply
    demand = score.demand
    professional = score.professional
    
    codes = {
        item.code
        for item in evidence
    } 
    
    if (
        EvidenceCode.SUPPLY_DRYING_UP in codes
        and
        EvidenceCode.TEST in codes
    ):
        demand += config.CONFLUENCE_BONUS
        print(
            "Confluence:",
            "SUPPLY_DRYING_UP + TEST",
            "+0.30 Demand",
        )
        
    if (
        EvidenceCode.NO_SUPPLY in codes
        and
        EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING in codes
    ):
        demand += config.CONFLUENCE_BONUS 
        print(
            "Confluence:",
            "NO_SUPPLY + STRUCTURAL_PROGRESSION_IMPROVING",
            "+0.30 Demand",
        )
        
    if (
        EvidenceCode.INCREASING_SUPPLY in codes
        and
        EvidenceCode.UPTHRUST in codes
    ):
        supply += config.CONFLUENCE_BONUS
        print(
            "Confluence:",
            "INCREASING_SUPPLY + UPTHRUST",
            "+0.30 Supply",
        )
        
    if (
        EvidenceCode.NO_DEMAND in codes
        and
        EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING in codes
    ):
        supply += config.CONFLUENCE_BONUS        
        print(
            "Confluence:",
            "NO_DEMAND + STRUCTURAL_PROGRESSION_WEAKENING",
            "+0.30 Supply",
        )   
    
    return EvidenceScore(
        supply=supply,
        demand=demand,
        professional=professional,
    )        