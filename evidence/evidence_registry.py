
from models import (
    Evidence,
    EvidenceCode,
    EvidenceCategory,
    EvidenceDefinition,
    EvidenceDirection,
)

EVIDENCE_LIBRARY = {

    EvidenceCode.NO_DEMAND:

        EvidenceDefinition(

            category=EvidenceCategory.DEMAND,

            direction=EvidenceDirection.BEARISH,

            strength=0.70,

            weight=1.00,

            observation="No Demand",

            description="No demand detected.",

        ),

    EvidenceCode.NO_SUPPLY:

        EvidenceDefinition(

            category=EvidenceCategory.SUPPLY,

            direction=EvidenceDirection.BULLISH,

            strength=0.70,

            weight=1.00,

            observation="No Supply",

            description="No supply detected.",

        ),
     
    EvidenceCode.TEST:
        
        EvidenceDefinition(
        
            category=EvidenceCategory.DEMAND,
        
            direction=EvidenceDirection.BULLISH,
        
            strength=0.90,
        
            weight=1.30,
        
            observation="Successful Test",
        
            description="Professional test of supply.",
        
        ),    

    EvidenceCode.STOPPING_VOLUME:

        EvidenceDefinition(

            category=EvidenceCategory.DEMAND,

            direction=EvidenceDirection.BULLISH,

            strength=0.90,

            weight=1.00,

            observation="Stopping Volume",

            description="Heavy selling effort showing evidence of absorption and possible stopping of the decline.",

        ),

    EvidenceCode.DEMAND_COMING_IN:

        EvidenceDefinition(

            category=EvidenceCategory.DEMAND,

            direction=EvidenceDirection.BULLISH,

            strength=0.90,

            weight=1.00,

            observation="Demand Coming In",

            description="Bullish effort/result evidence suggesting demand is entering the market.",

        ),

    EvidenceCode.UPTHRUST:
        
        EvidenceDefinition(
        
            category=EvidenceCategory.SUPPLY,
        
            direction=EvidenceDirection.BEARISH,
        
            strength=0.90,
        
            weight=1.30,
        
            observation="Upthrust",
        
            description="Professional selling after attempted breakout.",
        
        ),  
    
}


def build_evidence(
    code: EvidenceCode,
    *,
    bar_index: int,
    week_beginning: str,
    strength: float | None = None,
    weight: float | None = None,
) -> Evidence:

    definition = EVIDENCE_LIBRARY[code]

    strength_value = (
        definition.strength
        if strength is None
        else strength
    )
        
    return Evidence(
        code=code,
        category=definition.category,
        direction=definition.direction,
        strength=strength_value,
        weight=weight,
        observation=definition.observation,
        description=definition.description,
        bar_index=bar_index,
        week_beginning=week_beginning,
    )