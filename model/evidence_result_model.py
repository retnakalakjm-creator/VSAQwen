from __future__ import annotations

from dataclasses import dataclass

from models import BackgroundContext, EvidenceCategory, EvidenceCode, EvidenceDirection
from models import Evidence



@dataclass(slots=True, frozen=True)
class EvidenceResult:
    """
    Immutable output of the Evidence Engine.

    Provides convenient query helpers over the
    collected evidence while preserving the
    underlying immutable evidence tuple.
    """

    context: BackgroundContext

    evidence: tuple[Evidence, ...]

    # ---------------------------------------------------------
    # Observation
    # ---------------------------------------------------------

    @property
    def observation(self) -> str:
        """
        Combined professional observations.
        """

        return "\n".join(

            item.observation

            for item in self.evidence

        )

    # ---------------------------------------------------------
    # Category Views
    # ---------------------------------------------------------

    @property
    def supply(self) -> tuple[Evidence, ...]:

        return tuple(

            e

            for e in self.evidence

            if e.category == EvidenceCategory.SUPPLY

        )

    @property
    def demand(self) -> tuple[Evidence, ...]:

        return tuple(

            e

            for e in self.evidence

            if e.category == EvidenceCategory.DEMAND

        )

    @property
    def strength_evidence(self) -> tuple[Evidence, ...]:
        return tuple(
            e
            for e in self.evidence
            if e.direction == EvidenceDirection.BULLISH
        )


    @property
    def weakness_evidence(self) -> tuple[Evidence, ...]:
        return tuple(
            e
            for e in self.evidence
            if e.direction == EvidenceDirection.BEARISH
        )

    @property
    def trend(self) -> tuple[Evidence, ...]:

        return tuple(

            e

            for e in self.evidence

            if e.category == EvidenceCategory.TREND

        )

    # ---------------------------------------------------------
    # Convenience Flags
    # ---------------------------------------------------------

    @property
    def has_supply(self) -> bool:

        return bool(self.supply)

    @property
    def has_demand(self) -> bool:

        return bool(self.demand)

    @property
    def has_strength(self) -> bool:

        return bool(self.strength_evidence)

    @property
    def has_weakness(self) -> bool:

        return bool(self.weakness_evidence)

    @property
    def has_trend(self) -> bool:

        return bool(self.trend)

    @property
    def is_empty(self) -> bool:

        return not self.evidence

    @property
    def count(self) -> int:

        return len(self.evidence)

    # ---------------------------------------------------------
    # Query Helpers
    # ---------------------------------------------------------

    def by_category(
        self,
        category: EvidenceCategory,
    ) -> tuple[Evidence, ...]:

        return tuple(

            e

            for e in self.evidence

            if e.category == category

        )

    def by_code(
        self,
        code: EvidenceCode,
    ) -> tuple[Evidence, ...]:

        return tuple(

            e

            for e in self.evidence

            if e.code == code

        )