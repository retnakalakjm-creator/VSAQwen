from __future__ import annotations

from dataclasses import dataclass

from models import Evidence


@dataclass(slots=True, frozen=True)
class ProfessionalScore:

    trend: float

    supply: float

    demand: float

    effort: float

    strength: float #Computed by the Wyckoff Engine."""

    weakness: float  #Computed by the Wyckoff Engine."""

    confidence: float

    @property
    def net_pressure(self) -> float:
        """
        Positive = Demand dominates.

        Negative = Supply dominates.
        """

        return self.demand - self.supply


    @property
    def net_strength(self) -> float:
        """
        Positive = Professional strength dominates.

        Negative = Professional weakness dominates.
        """

        return self.strength - self.weakness

    @property
    def is_bullish(self) -> bool:
        return self.net_pressure > 0.0


    @property
    def is_bearish(self) -> bool:
        return self.net_pressure < 0.0


    @property
    def is_strong(self) -> bool:
        return self.net_strength > 0.0

    @property
    def is_weak(self) -> bool:
        return self.net_strength < 0.0


    @property
    def is_high_confidence(self) -> bool:
        return self.confidence >= 0.70




@dataclass(slots=True, frozen=True)
class ProfessionalScoreResult:

    scores: ProfessionalScore

    evidence: tuple[Evidence, ...]

    @property
    def trend(self) -> float:
        return self.scores.trend

    @property
    def supply(self) -> float:
        return self.scores.supply

    @property
    def demand(self) -> float:
        return self.scores.demand

    @property
    def effort(self) -> float:
        return self.scores.effort

    @property
    def strength(self) -> float:
        return self.scores.strength

    @property
    def weakness(self) -> float:
        return self.scores.weakness

    @property
    def confidence(self) -> float:
        return self.scores.confidence

    @property
    def is_bullish(self) -> bool:
        return self.scores.is_bullish

    @property
    def is_bearish(self) -> bool:
        return self.scores.is_bearish

    @property
    def is_strong(self) -> bool:
        return self.scores.is_strong

    @property
    def is_weak(self) -> bool:
        return self.scores.is_weak

    @property
    def is_high_confidence(self) -> bool:
        return self.scores.is_high_confidence

    @property
    def has_evidence(self) -> bool:
        return bool(self.evidence)

    @property
    def evidence_count(self) -> int:
        return len(self.evidence)