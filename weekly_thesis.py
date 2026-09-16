from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum, auto

from models import (
    Evidence,
    EvidenceDirection,
    StructuralPattern,
    TrendDirection,
    TrendState,
)
from weekly_behavior import WeeklyBehaviorState
from weekly_behavior_evolution import (
    WeeklyBehaviorEvolution,
    WeeklyContradictionState,
)
from weekly_setup import WeeklyPriceZone


class ShadowWeeklyThesisState(StrEnum):
    """Read-only weekly thesis states used only by the WF4 shadow path."""

    NO_THESIS = auto()

    BULLISH_DEVELOPING = auto()
    BULLISH_SUPPORTED = auto()
    BULLISH_CHALLENGED = auto()
    BULLISH_INVALIDATION_EVIDENCE = auto()

    BEARISH_DEVELOPING = auto()
    BEARISH_SUPPORTED = auto()
    BEARISH_CHALLENGED = auto()
    BEARISH_INVALIDATION_EVIDENCE = auto()


class ShadowWeeklyThesisBasis(StrEnum):
    """Observable reason the shadow thesis has its current state."""

    NO_DIRECTIONAL_REFERENCE = auto()
    DIRECTIONAL_REFERENCE_ONLY = auto()
    ALIGNED_BEHAVIOR_PRESENT = auto()
    MEANINGFUL_CONTRADICTION = auto()
    CAMPAIGN_WEAKENING = auto()
    STRUCTURAL_INVALIDATION_EVIDENCE = auto()


@dataclass(frozen=True, slots=True)
class ShadowWeeklyThesis:
    """Immutable, non-actionable weekly thesis assembled from WF2/WF3 output.

    WF4 deliberately does not create a production ``WeeklySetup`` and does not
    replace ``PatternQualification``.  It is a causal comparison object for
    replay/audit work in later weekly-foundation milestones.
    """

    symbol: str
    week: str | None
    bar_index: int

    state: ShadowWeeklyThesisState
    basis: ShadowWeeklyThesisBasis
    direction: EvidenceDirection
    contradiction_state: WeeklyContradictionState

    trend_direction: TrendDirection
    trend_state: TrendState
    structural_pattern: StructuralPattern
    current_structural_direction: EvidenceDirection

    supporting_evidence: tuple[Evidence, ...] = ()
    opposing_evidence: tuple[Evidence, ...] = ()
    current_supporting_evidence: tuple[Evidence, ...] = ()
    current_opposing_evidence: tuple[Evidence, ...] = ()

    support_zone: WeeklyPriceZone | None = None
    resistance_zone: WeeklyPriceZone | None = None

    professional_strength: float = 0.0
    professional_weakness: float = 0.0
    professional_net_strength: float = 0.0
    professional_net_pressure: float = 0.0
    professional_confidence: float = 0.0

    @property
    def is_actionable(self) -> bool:
        """WF4 has no production authority."""

        return False

    @property
    def has_directional_thesis(self) -> bool:
        return self.direction in {
            EvidenceDirection.BULLISH,
            EvidenceDirection.BEARISH,
        }

    @property
    def is_challenged(self) -> bool:
        return self.state in {
            ShadowWeeklyThesisState.BULLISH_CHALLENGED,
            ShadowWeeklyThesisState.BEARISH_CHALLENGED,
        }

    @property
    def has_invalidation_evidence(self) -> bool:
        return self.state in {
            ShadowWeeklyThesisState.BULLISH_INVALIDATION_EVIDENCE,
            ShadowWeeklyThesisState.BEARISH_INVALIDATION_EVIDENCE,
        }


class ShadowWeeklyThesisBuilder:
    """Combine WF2 behavior and WF3 evolution into a read-only thesis.

    No synthetic score, vote count, expiry or actionability threshold is added.
    The builder preserves the WF3 structural reference as thesis direction and
    only labels the directly observable support/contradiction state around it.
    """

    @staticmethod
    def _opposite(direction: EvidenceDirection) -> EvidenceDirection:
        if direction is EvidenceDirection.BULLISH:
            return EvidenceDirection.BEARISH
        if direction is EvidenceDirection.BEARISH:
            return EvidenceDirection.BULLISH
        return EvidenceDirection.NEUTRAL

    @staticmethod
    def _validate(
        behavior: WeeklyBehaviorState,
        evolution: WeeklyBehaviorEvolution,
    ) -> None:
        if behavior.symbol != evolution.symbol:
            raise ValueError("behavior and evolution symbol must match")
        if behavior.bar_index is None:
            raise ValueError("shadow weekly thesis requires behavior bar_index")
        if behavior.bar_index != evolution.bar_index:
            raise ValueError("behavior and evolution bar_index must match")
        if behavior.week != evolution.week:
            raise ValueError("behavior and evolution week must match")

    @staticmethod
    def _state_for(
        direction: EvidenceDirection,
        *,
        developing: bool = False,
        challenged: bool = False,
        invalidation: bool = False,
    ) -> ShadowWeeklyThesisState:
        if direction is EvidenceDirection.BULLISH:
            if invalidation:
                return ShadowWeeklyThesisState.BULLISH_INVALIDATION_EVIDENCE
            if challenged:
                return ShadowWeeklyThesisState.BULLISH_CHALLENGED
            if developing:
                return ShadowWeeklyThesisState.BULLISH_DEVELOPING
            return ShadowWeeklyThesisState.BULLISH_SUPPORTED

        if direction is EvidenceDirection.BEARISH:
            if invalidation:
                return ShadowWeeklyThesisState.BEARISH_INVALIDATION_EVIDENCE
            if challenged:
                return ShadowWeeklyThesisState.BEARISH_CHALLENGED
            if developing:
                return ShadowWeeklyThesisState.BEARISH_DEVELOPING
            return ShadowWeeklyThesisState.BEARISH_SUPPORTED

        return ShadowWeeklyThesisState.NO_THESIS

    @classmethod
    def build(
        cls,
        *,
        behavior: WeeklyBehaviorState,
        evolution: WeeklyBehaviorEvolution,
    ) -> ShadowWeeklyThesis:
        cls._validate(behavior, evolution)
        assert behavior.bar_index is not None

        direction = evolution.reference_direction
        if direction is EvidenceDirection.NEUTRAL:
            return ShadowWeeklyThesis(
                symbol=behavior.symbol,
                week=behavior.week,
                bar_index=behavior.bar_index,
                state=ShadowWeeklyThesisState.NO_THESIS,
                basis=ShadowWeeklyThesisBasis.NO_DIRECTIONAL_REFERENCE,
                direction=EvidenceDirection.NEUTRAL,
                contradiction_state=evolution.contradiction_state,
                trend_direction=behavior.trend_direction,
                trend_state=behavior.trend_state,
                structural_pattern=behavior.structural_pattern,
                current_structural_direction=evolution.current_structural_direction,
                support_zone=behavior.support_zone,
                resistance_zone=behavior.resistance_zone,
                professional_strength=behavior.professional_strength,
                professional_weakness=behavior.professional_weakness,
                professional_net_strength=behavior.professional_net_strength,
                professional_net_pressure=behavior.professional_net_pressure,
                professional_confidence=behavior.professional_confidence,
            )

        opposite = cls._opposite(direction)
        supporting = tuple(
            item for item in behavior.recent_evidence if item.direction is direction
        )
        opposing = tuple(
            item for item in behavior.recent_evidence if item.direction is opposite
        )

        contradiction = evolution.contradiction_state
        if contradiction is WeeklyContradictionState.STRUCTURAL_INVALIDATION_EVIDENCE:
            state = cls._state_for(direction, invalidation=True)
            basis = ShadowWeeklyThesisBasis.STRUCTURAL_INVALIDATION_EVIDENCE
        elif contradiction is WeeklyContradictionState.CAMPAIGN_WEAKENING:
            state = cls._state_for(direction, challenged=True)
            basis = ShadowWeeklyThesisBasis.CAMPAIGN_WEAKENING
        elif contradiction is WeeklyContradictionState.MEANINGFUL:
            state = cls._state_for(direction, challenged=True)
            basis = ShadowWeeklyThesisBasis.MEANINGFUL_CONTRADICTION
        elif supporting:
            # A MINOR contradiction remains visible in contradiction_state, but
            # one contrary week does not automatically demote an otherwise
            # supported structural campaign into a challenged/reversed thesis.
            state = cls._state_for(direction)
            basis = ShadowWeeklyThesisBasis.ALIGNED_BEHAVIOR_PRESENT
        else:
            state = cls._state_for(direction, developing=True)
            basis = ShadowWeeklyThesisBasis.DIRECTIONAL_REFERENCE_ONLY

        return ShadowWeeklyThesis(
            symbol=behavior.symbol,
            week=behavior.week,
            bar_index=behavior.bar_index,
            state=state,
            basis=basis,
            direction=direction,
            contradiction_state=contradiction,
            trend_direction=behavior.trend_direction,
            trend_state=behavior.trend_state,
            structural_pattern=behavior.structural_pattern,
            current_structural_direction=evolution.current_structural_direction,
            supporting_evidence=supporting,
            opposing_evidence=opposing,
            current_supporting_evidence=evolution.current_aligned_evidence,
            current_opposing_evidence=evolution.current_opposing_evidence,
            support_zone=behavior.support_zone,
            resistance_zone=behavior.resistance_zone,
            professional_strength=behavior.professional_strength,
            professional_weakness=behavior.professional_weakness,
            professional_net_strength=behavior.professional_net_strength,
            professional_net_pressure=behavior.professional_net_pressure,
            professional_confidence=behavior.professional_confidence,
        )


__all__ = [
    "ShadowWeeklyThesis",
    "ShadowWeeklyThesisBasis",
    "ShadowWeeklyThesisBuilder",
    "ShadowWeeklyThesisState",
]
