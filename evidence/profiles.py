from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from collections.abc import Mapping, ValuesView

from models import EvidenceCode, EvidenceCategory, EvidenceDirection

@dataclass(slots=True, frozen=True)
class EvidenceProfile:
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
    profiles: Mapping[EvidenceCode, EvidenceProfile]
    def __getitem__(self, code: EvidenceCode) -> EvidenceProfile:
        return self.profiles[code]
    def __contains__(self, code: EvidenceCode) -> bool:
        return code in self.profiles
    def values(self) -> ValuesView[EvidenceProfile]:
        return self.profiles.values()
    def get(self, code: EvidenceCode) -> EvidenceProfile | None:
        return self.profiles.get(code)
    def __len__(self) -> int:
        return len(self.profiles)

BUYING_CLIMAX = EvidenceProfile(EvidenceCode.BUYING_CLIMAX, EvidenceCategory.SUPPLY, EvidenceDirection.BEARISH, 0.95, 1.00, 100, "Buying Climax", "Professional distribution after an extended advance.")
SUPPLY_COMING_IN = EvidenceProfile(EvidenceCode.SUPPLY_COMING_IN, EvidenceCategory.SUPPLY, EvidenceDirection.BEARISH, 0.80, 1.00, 80, "Supply Coming In", "Professional selling pressure entering the market.")
HIDDEN_SUPPLY = EvidenceProfile(EvidenceCode.HIDDEN_SUPPLY, EvidenceCategory.SUPPLY, EvidenceDirection.BEARISH, 0.70, 0.75, 60, "Hidden Supply", "Selling pressure hidden inside the current bar.")
INCREASING_SUPPLY = EvidenceProfile(EvidenceCode.INCREASING_SUPPLY, EvidenceCategory.SUPPLY, EvidenceDirection.BEARISH, 0.80, 0.85, 75, "Increasing Supply", "Selling pressure is increasing across recent bars.")
SUPPLY_DRYING_UP = EvidenceProfile(EvidenceCode.SUPPLY_DRYING_UP, EvidenceCategory.SUPPLY, EvidenceDirection.BULLISH, 0.85, 0.90, 90, "Supply Drying Up", "Selling pressure has diminished significantly.")
SUPPLY_HIGH_VOLUME = EvidenceProfile(EvidenceCode.SUPPLY_HIGH_VOLUME, EvidenceCategory.SUPPLY, EvidenceDirection.BEARISH, 0.70, 0.70, 50, "High Volume Supply", "Supply is entering the market on elevated volume.")
SUPPLY_WIDE_SPREAD = EvidenceProfile(EvidenceCode.SUPPLY_WIDE_SPREAD, EvidenceCategory.SUPPLY, EvidenceDirection.BEARISH, 0.70, 0.70, 45, "Wide Spread Supply", "Wide spread reflects aggressive professional selling.")
SUPPLY_ABSORPTION = EvidenceProfile(EvidenceCode.SUPPLY_ABSORPTION, EvidenceCategory.SUPPLY, EvidenceDirection.BULLISH, 0.90, 0.95, 95, "Supply Absorption", "Professional money is absorbing available supply.")
UPTHRUST = EvidenceProfile(EvidenceCode.UPTHRUST, EvidenceCategory.SUPPLY, EvidenceDirection.BEARISH, 0.82, 1.0, 80, "Upthrust", "An upward price move that fails and closes weak, indicating supply.")
NO_DEMAND = EvidenceProfile(EvidenceCode.NO_DEMAND, EvidenceCategory.SUPPLY, EvidenceDirection.BEARISH, 0.73, 1.0, 60, "No Demand", "An advance showing insufficient buying interest.")
SUPPLY_PROFILES = (BUYING_CLIMAX, SUPPLY_COMING_IN, HIDDEN_SUPPLY, INCREASING_SUPPLY, SUPPLY_DRYING_UP, SUPPLY_HIGH_VOLUME, SUPPLY_WIDE_SPREAD, SUPPLY_ABSORPTION, UPTHRUST, NO_DEMAND)

STOPPING_VOLUME = EvidenceProfile(EvidenceCode.STOPPING_VOLUME, EvidenceCategory.DEMAND, EvidenceDirection.BULLISH, 0.90, 1.00, 95, "Stopping Volume", "Heavy selling effort after a decline with evidence of professional demand capable of absorbing supply.")
DEMAND_COMING_IN = EvidenceProfile(EvidenceCode.DEMAND_COMING_IN, EvidenceCategory.DEMAND, EvidenceDirection.BULLISH, 0.90, 1.00, 85, "Demand Coming In", "Bullish effort/result evidence suggesting demand is entering the market.")
INCREASING_DEMAND = EvidenceProfile(EvidenceCode.INCREASING_DEMAND, EvidenceCategory.DEMAND, EvidenceDirection.BULLISH, 0.90, 0.85, 85, "Increasing Demand", "Bullish effort/result evidence showing increasing demand pressure.")
DEMAND_DRYING_UP = EvidenceProfile(EvidenceCode.DEMAND_DRYING_UP, EvidenceCategory.DEMAND, EvidenceDirection.BEARISH, 0.80, 0.0, 55, "Demand Drying Up", "Buying effort has diminished significantly; retain as audit/context evidence until separately validated.")
SELLING_CLIMAX = EvidenceProfile(EvidenceCode.SELLING_CLIMAX, EvidenceCategory.DEMAND, EvidenceDirection.BULLISH, 0.95, 0.38, 100, "Selling Climax", "Climactic selling that may indicate exhaustion and professional absorption.")
NO_SUPPLY = EvidenceProfile(EvidenceCode.NO_SUPPLY, EvidenceCategory.DEMAND, EvidenceDirection.BULLISH, 0.80, 1.0, 70, "No Supply", "A decline occurring with insufficient selling pressure.")
TEST = EvidenceProfile(EvidenceCode.TEST, EvidenceCategory.DEMAND, EvidenceDirection.BULLISH, 0.85, 1.0, 80, "Test", "A low-volume test of available supply.")
SHAKEOUT = EvidenceProfile(EvidenceCode.SHAKEOUT, EvidenceCategory.DEMAND, EvidenceDirection.BULLISH, 0.90, 1.0, 90, "Shakeout", "A sharp downward move that is rejected and shows absorption of selling.")
DEMAND_PROFILES = (STOPPING_VOLUME, DEMAND_COMING_IN, INCREASING_DEMAND, DEMAND_DRYING_UP, SELLING_CLIMAX, NO_SUPPLY, TEST, SHAKEOUT)

# Effort/Result profiles are contextual only. Weight remains zero until a separate
# production decision establishes an evidence contribution.
EFFORT_GT_RESULT = EvidenceProfile(EvidenceCode.EFFORT_GT_RESULT, EvidenceCategory.EFFORT, EvidenceDirection.NEUTRAL, 0.50, 0.0, 40, "Effort exceeds result", "Elevated effort produced comparatively limited result; interpret with directional and event context.")
RESULT_GT_EFFORT = EvidenceProfile(EvidenceCode.RESULT_GT_EFFORT, EvidenceCategory.EFFORT, EvidenceDirection.NEUTRAL, 0.50, 0.0, 40, "Result exceeds effort", "Price result is comparatively strong for the observed effort; interpret with directional and event context.")
ABSORPTION = EvidenceProfile(EvidenceCode.ABSORPTION, EvidenceCategory.EFFORT, EvidenceDirection.NEUTRAL, 0.50, 0.0, 45, "Absorption candidate", "High effort with limited result may indicate absorption; directional/contextual evidence is required.")
EFFORT_PROFILES = (EFFORT_GT_RESULT, RESULT_GT_EFFORT, ABSORPTION)

ALL_PROFILES = SUPPLY_PROFILES + DEMAND_PROFILES + EFFORT_PROFILES

def _validate_profiles(profiles: tuple[EvidenceProfile, ...]) -> None:
    seen: set[EvidenceCode] = set()
    for profile in profiles:
        if profile.code in seen:
            raise ValueError(f"Duplicate EvidenceCode: {profile.code}")
        seen.add(profile.code)

_validate_profiles(ALL_PROFILES)
EVIDENCE_REGISTRY = EvidenceRegistry(MappingProxyType({profile.code: profile for profile in ALL_PROFILES}))

__all__ = ["EvidenceProfile", "EvidenceRegistry", "SUPPLY_PROFILES", "DEMAND_PROFILES", "EFFORT_PROFILES", "ALL_PROFILES", "EVIDENCE_REGISTRY"]
