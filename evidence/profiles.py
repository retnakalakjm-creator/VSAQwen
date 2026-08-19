from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from collections.abc import Mapping, ValuesView

from models import (
    EvidenceCode,
    EvidenceCategory,
    EvidenceDirection,
)

@dataclass(slots=True, frozen=True)
class EvidenceProfile:
    """
    Immutable metadata describing an Evidence type.
    """

    code: EvidenceCode

    category: EvidenceCategory

    direction: EvidenceDirection

    strength: float

    weight: float

    priority: int

    observation: str

    description: str


@dataclass(slots=True, frozen=True)
class EvidenceRegistry:
    """
    Immutable registry of Evidence profiles.
    """

    profiles: Mapping[
        EvidenceCode,
        EvidenceProfile,
    ]

    def __getitem__(
        self,
        code: EvidenceCode,
    ) -> EvidenceProfile:

        return self.profiles[code]

    def __contains__(
        self,
        code: EvidenceCode,
    ) -> bool:

        return code in self.profiles

    def values(
        self,
    ) -> ValuesView[EvidenceProfile]:

        return self.profiles.values()

    def get(
        self,
        code: EvidenceCode,
    ) -> EvidenceProfile | None:

        return self.profiles.get(code)
   
    def __len__(
        self,
    ) -> int:
        return len(self.profiles)
    

# ----------------------------------------------------------
# Supply Profiles
# ----------------------------------------------------------
BUYING_CLIMAX = EvidenceProfile(
    code=EvidenceCode.BUYING_CLIMAX,
    category=EvidenceCategory.SUPPLY,
    direction=EvidenceDirection.BEARISH,
    strength=0.95,
    weight=1.00,
    priority=100,
    observation="Buying Climax",
    description="Professional distribution after an extended advance.",
)

SUPPLY_COMING_IN = EvidenceProfile(
    code=EvidenceCode.SUPPLY_COMING_IN,
    category=EvidenceCategory.SUPPLY,
    direction=EvidenceDirection.BEARISH,
    strength=0.80,
    weight=1.00,
    priority=80,
    observation="Supply Coming In",
    description=(
        "Professional selling pressure entering the market."
    ),
)

HIDDEN_SUPPLY = EvidenceProfile(

    code=EvidenceCode.HIDDEN_SUPPLY,

    category=EvidenceCategory.SUPPLY,

    direction=EvidenceDirection.BEARISH,

    strength=0.70,

    weight=0.75,

    priority=60,

    observation="Hidden Supply",

    description=(
        "Selling pressure hidden inside the current bar."
    ),
)

INCREASING_SUPPLY = EvidenceProfile(

    code=EvidenceCode.INCREASING_SUPPLY,
    category=EvidenceCategory.SUPPLY,
    direction=EvidenceDirection.BEARISH,
    strength=0.80,
    weight=0.85,
    priority=75,
    observation="Increasing Supply",
    description=(
        "Selling pressure is increasing across recent bars."
    ),
)

SUPPLY_DRYING_UP = EvidenceProfile(

    code=EvidenceCode.SUPPLY_DRYING_UP,
    category=EvidenceCategory.SUPPLY,
    direction=EvidenceDirection.BULLISH,
    strength=0.85,
    weight=0.90,
    priority=90,
    observation="Supply Drying Up",
    description=(
        "Selling pressure has diminished significantly."
    ),
)

SUPPLY_HIGH_VOLUME = EvidenceProfile(

    code=EvidenceCode.SUPPLY_HIGH_VOLUME,
    category=EvidenceCategory.SUPPLY,
    direction=EvidenceDirection.BEARISH,
    strength=0.70,
    weight=0.70,
    priority=50,
    observation="High Volume Supply",
    description=(
        "Supply is entering the market on elevated volume."
    ),
)

SUPPLY_WIDE_SPREAD = EvidenceProfile(

    code=EvidenceCode.SUPPLY_WIDE_SPREAD,
    category=EvidenceCategory.SUPPLY,
    direction=EvidenceDirection.BEARISH,
    strength=0.70,
    weight=0.70,
    priority=45,
    observation="Wide Spread Supply",
    description=(
        "Wide spread reflects aggressive professional selling."
    ),
)

SUPPLY_ABSORPTION = EvidenceProfile(

    code=EvidenceCode.SUPPLY_ABSORPTION,
    category=EvidenceCategory.SUPPLY,
    direction=EvidenceDirection.BULLISH,
    strength=0.90,
    weight=0.95,
    priority=95,
    observation="Supply Absorption",
    description=(
        "Professional money is absorbing available supply."
    ),
)

UPTHRUST = EvidenceProfile(
    code=EvidenceCode.UPTHRUST,
    category=EvidenceCategory.SUPPLY,
    direction=EvidenceDirection.BEARISH,
    strength=0.82,
    weight=1.0,
    priority=80,
    observation="Upthrust",
    description="An upward price move that fails and closes weak, indicating supply.",
)

NO_DEMAND = EvidenceProfile(
    code=EvidenceCode.NO_DEMAND,
    category=EvidenceCategory.SUPPLY,
    direction=EvidenceDirection.BEARISH,
    strength=0.73,
    weight=1.0,
    priority=60,
    observation="No Demand",
    description="An advance showing insufficient buying interest.",
)

SUPPLY_PROFILES: tuple[EvidenceProfile, ...] = (

    BUYING_CLIMAX,

    SUPPLY_COMING_IN,

    HIDDEN_SUPPLY,

    INCREASING_SUPPLY,

    SUPPLY_DRYING_UP,

    SUPPLY_HIGH_VOLUME,

    SUPPLY_WIDE_SPREAD,

    SUPPLY_ABSORPTION,

    UPTHRUST,

    NO_DEMAND,
)

# ----------------------------------------------------------
# Demand Profiles 
# ----------------------------------------------------------

STOPPING_VOLUME = EvidenceProfile(
    code=EvidenceCode.STOPPING_VOLUME,
    category=EvidenceCategory.DEMAND,
    direction=EvidenceDirection.BULLISH,
    strength=0.90,
    weight=1.00,
    priority=95,
    observation="Stopping Volume",
    description=(
        "Heavy selling effort after a decline with evidence of "
        "professional demand capable of absorbing supply."
    ),
)

DEMAND_COMING_IN = EvidenceProfile(
    code=EvidenceCode.DEMAND_COMING_IN,
    category=EvidenceCategory.DEMAND,
    direction=EvidenceDirection.BULLISH,
    strength=0.90,
    weight=1.00,
    priority=85,
    observation="Demand Coming In",
    description=(
        "Bullish effort/result evidence suggesting demand is entering the market."
    ),
)

SELLING_CLIMAX = EvidenceProfile(
    code=EvidenceCode.SELLING_CLIMAX,
    category=EvidenceCategory.DEMAND,
    direction=EvidenceDirection.BULLISH,
    strength=0.95,
    weight=1.0,
    priority=100,
    observation="Selling Climax",
    description="Climactic selling that may indicate exhaustion and professional absorption.",
)

NO_SUPPLY = EvidenceProfile(
    code=EvidenceCode.NO_SUPPLY,
    category=EvidenceCategory.DEMAND,
    direction=EvidenceDirection.BULLISH,
    strength=0.80,
    weight=1.0,
    priority=70,
    observation="No Supply",
    description="A decline occurring with insufficient selling pressure.",
)

TEST = EvidenceProfile(
    code=EvidenceCode.TEST,
    category=EvidenceCategory.DEMAND,
    direction=EvidenceDirection.BULLISH,    
    strength=0.85,
    weight=1.0,
    priority=80,
    observation="Test",
    description="A low-volume test of available supply.",
)

SHAKEOUT = EvidenceProfile(
    code=EvidenceCode.SHAKEOUT,
    category=EvidenceCategory.DEMAND,
    direction=EvidenceDirection.BULLISH,
    strength=0.90,
    weight=1.0,
    priority=90,
    observation="Shakeout",
    description="A sharp downward move that is rejected and shows absorption of selling.",
)

DEMAND_PROFILES: tuple[EvidenceProfile, ...] = (

    STOPPING_VOLUME,

    DEMAND_COMING_IN,

    SELLING_CLIMAX,

    NO_SUPPLY,

    TEST,

    SHAKEOUT,    
)

# ----------------------------------------------------------
# Effort Profiles
# ----------------------------------------------------------

# ----------------------------------------------------------
# Trend Profiles
# ----------------------------------------------------------

# ----------------------------------------------------------
# Phase Profiles
# ----------------------------------------------------------

# ----------------------------------------------------------
# ALL Profiles
# ----------------------------------------------------------
ALL_PROFILES = SUPPLY_PROFILES + DEMAND_PROFILES

#Later Purpose
""" ALL_PROFILES = (

    SUPPLY_PROFILES

    + DEMAND_PROFILES

    + EFFORT_PROFILES

    + TREND_PROFILES

    + PHASE_PROFILES
) """


def _validate_profiles(
    profiles: tuple[
        EvidenceProfile,
        ...
    ],
) -> None:
    """
    Validate the Evidence profile registry.
    """

    seen: set[EvidenceCode] = set()

    for profile in profiles:

        if profile.code in seen:

            raise ValueError(
                f"Duplicate EvidenceCode: {profile.code}"
            )

        seen.add(profile.code)


_validate_profiles(
    ALL_PROFILES
)


EVIDENCE_REGISTRY = EvidenceRegistry(

    profiles=MappingProxyType({

        profile.code: profile

        for profile in ALL_PROFILES

    })
)


__all__ = [

    "EvidenceProfile",

    "EvidenceRegistry",

    "SUPPLY_PROFILES",

    "DEMAND_PROFILES",

    "ALL_PROFILES",

    "EVIDENCE_REGISTRY",
]