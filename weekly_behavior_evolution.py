from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum, auto

from models import (
    Evidence,
    EvidenceCode,
    EvidenceDirection,
    StructuralPattern,
    TrendState,
)
from weekly_behavior import WeeklyBehaviorState


_PROGRESSION_CODES = frozenset(
    {
        EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING,
        EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING,
    }
)


class WeeklyContradictionState(StrEnum):
    """Read-only description of opposition to an established weekly direction."""

    NONE = auto()
    MINOR = auto()
    MEANINGFUL = auto()
    CAMPAIGN_WEAKENING = auto()
    STRUCTURAL_INVALIDATION_EVIDENCE = auto()


@dataclass(frozen=True, slots=True)
class WeeklyBehaviorEvolution:
    """Point-in-time evolution view over a sequence of WF2 behavior states.

    WF3 does not create or mutate a weekly thesis. It preserves the latest
    previously-established structural direction as the comparison reference and
    describes how the current completed week relates to that reference.
    """

    symbol: str
    week: str | None
    bar_index: int
    observed_state_count: int

    reference_direction: EvidenceDirection
    current_structural_direction: EvidenceDirection
    contradiction_state: WeeklyContradictionState

    current_aligned_evidence: tuple[Evidence, ...] = ()
    current_opposing_evidence: tuple[Evidence, ...] = ()
    consecutive_opposing_weeks: int = 0

    professional_pressure_opposes_reference: bool = False
    opposing_progression_present: bool = False
    structural_pattern_opposes_reference: bool = False
    structural_weakening_present: bool = False
    structural_direction_changed: bool = False

    @property
    def has_contradiction(self) -> bool:
        return self.contradiction_state is not WeeklyContradictionState.NONE

    @property
    def is_actionable(self) -> bool:
        """WF3 remains shadow/read-only and has no production authority."""

        return False


class WeeklyBehaviorEvolutionEngine:
    """Describe weekly behavior evolution without scoring or thesis promotion."""

    @staticmethod
    def _opposite(direction: EvidenceDirection) -> EvidenceDirection:
        if direction is EvidenceDirection.BULLISH:
            return EvidenceDirection.BEARISH
        if direction is EvidenceDirection.BEARISH:
            return EvidenceDirection.BULLISH
        return EvidenceDirection.NEUTRAL

    @staticmethod
    def _validate(states: Sequence[WeeklyBehaviorState]) -> tuple[WeeklyBehaviorState, ...]:
        history = tuple(states)
        if not history:
            raise ValueError("at least one weekly behavior state is required")

        symbol = history[0].symbol
        previous_index: int | None = None
        for state in history:
            if state.symbol != symbol:
                raise ValueError("all weekly behavior states must have the same symbol")
            if state.bar_index is None:
                raise ValueError("weekly behavior evolution requires bar_index")
            if previous_index is not None and state.bar_index <= previous_index:
                raise ValueError("weekly behavior states must be strictly increasing by bar_index")
            previous_index = state.bar_index

        return history

    @staticmethod
    def _reference_direction(history: tuple[WeeklyBehaviorState, ...]) -> EvidenceDirection:
        # Compare the current week against the most recent structural direction
        # that was already established before it. If there is no prior
        # directional state, use the current structural direction as the initial
        # observation reference. This avoids inventing direction in RANGE or
        # UNKNOWN while allowing a structural direction change to remain visible
        # as an explicit event.
        for state in reversed(history[:-1]):
            if state.structural_reference_direction is not EvidenceDirection.NEUTRAL:
                return state.structural_reference_direction
        return history[-1].structural_reference_direction

    @staticmethod
    def _current_directional_evidence(
        state: WeeklyBehaviorState,
        direction: EvidenceDirection,
    ) -> tuple[Evidence, ...]:
        if direction is EvidenceDirection.NEUTRAL:
            return ()
        return tuple(item for item in state.current_evidence if item.direction is direction)

    @classmethod
    def _consecutive_opposing_weeks(
        cls,
        history: tuple[WeeklyBehaviorState, ...],
        reference: EvidenceDirection,
    ) -> int:
        opposite = cls._opposite(reference)
        if opposite is EvidenceDirection.NEUTRAL:
            return 0

        count = 0
        for state in reversed(history):
            if any(item.direction is opposite for item in state.current_evidence):
                count += 1
                continue
            break
        return count

    @staticmethod
    def _structural_pattern_opposes_reference(
        pattern: StructuralPattern,
        reference: EvidenceDirection,
    ) -> bool:
        if pattern is StructuralPattern.BREAKING:
            return True
        if reference is EvidenceDirection.BULLISH:
            return pattern is StructuralPattern.WEAKENING
        if reference is EvidenceDirection.BEARISH:
            return pattern is StructuralPattern.IMPROVING
        return False

    @classmethod
    def evaluate(
        cls,
        states: Sequence[WeeklyBehaviorState],
    ) -> WeeklyBehaviorEvolution:
        history = cls._validate(states)
        current = history[-1]
        assert current.bar_index is not None

        reference = cls._reference_direction(history)
        current_structural = current.structural_reference_direction

        if reference is EvidenceDirection.NEUTRAL:
            return WeeklyBehaviorEvolution(
                symbol=current.symbol,
                week=current.week,
                bar_index=current.bar_index,
                observed_state_count=len(history),
                reference_direction=reference,
                current_structural_direction=current_structural,
                contradiction_state=WeeklyContradictionState.NONE,
            )

        opposite = cls._opposite(reference)
        aligned_current = cls._current_directional_evidence(current, reference)
        opposing_current = cls._current_directional_evidence(current, opposite)
        consecutive_opposition = cls._consecutive_opposing_weeks(history, reference)

        pressure_opposes = (
            current.professional_net_pressure < 0.0
            if reference is EvidenceDirection.BULLISH
            else current.professional_net_pressure > 0.0
        )

        opposing_progression = any(
            item.code in _PROGRESSION_CODES
            and item.direction is opposite
            and item.bar_index == current.bar_index
            for item in current.progression_evidence
        )

        structural_direction_changed = (
            current_structural is not EvidenceDirection.NEUTRAL
            and current_structural is opposite
        )
        pattern_opposes = cls._structural_pattern_opposes_reference(
            current.structural_pattern,
            reference,
        )

        structural_weakening = (
            current.trend_state in {TrendState.EXHAUSTED, TrendState.REVERSING}
            or pattern_opposes
            or opposing_progression
        )

        structural_invalidation = structural_direction_changed or (
            current.trend_state is TrendState.REVERSING and opposing_progression
        )

        if structural_invalidation:
            contradiction = WeeklyContradictionState.STRUCTURAL_INVALIDATION_EVIDENCE
        elif structural_weakening:
            contradiction = WeeklyContradictionState.CAMPAIGN_WEAKENING
        elif opposing_current and (
            consecutive_opposition >= 2 or pressure_opposes
        ):
            contradiction = WeeklyContradictionState.MEANINGFUL
        elif opposing_current:
            contradiction = WeeklyContradictionState.MINOR
        else:
            contradiction = WeeklyContradictionState.NONE

        return WeeklyBehaviorEvolution(
            symbol=current.symbol,
            week=current.week,
            bar_index=current.bar_index,
            observed_state_count=len(history),
            reference_direction=reference,
            current_structural_direction=current_structural,
            contradiction_state=contradiction,
            current_aligned_evidence=aligned_current,
            current_opposing_evidence=opposing_current,
            consecutive_opposing_weeks=consecutive_opposition,
            professional_pressure_opposes_reference=pressure_opposes,
            opposing_progression_present=opposing_progression,
            structural_pattern_opposes_reference=pattern_opposes,
            structural_weakening_present=structural_weakening,
            structural_direction_changed=structural_direction_changed,
        )


__all__ = [
    "WeeklyBehaviorEvolution",
    "WeeklyBehaviorEvolutionEngine",
    "WeeklyContradictionState",
]
