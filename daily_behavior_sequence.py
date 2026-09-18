from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from daily_behavior import (
    DailyBehaviorDimension,
    evaluate_daily_behavior,
)
from models import Evidence
from weekly_setup import WeeklySetupDirection


@dataclass(frozen=True, slots=True)
class DailyBehaviorSequenceStep:
    """Behavior dimensions observed on one exact daily bar."""

    bar_index: int
    dimensions: tuple[DailyBehaviorDimension, ...]
    evidence: tuple[Evidence, ...]


@dataclass(frozen=True, slots=True)
class DailyBehaviorSequence:
    """Read-only temporal audit of daily behavior across a bounded bar window.

    This object preserves ordering only. It does not assign a score, confidence,
    trigger, ranking, execution price, or actionability.
    """

    weekly_direction: WeeklySetupDirection
    start_bar_index: int
    end_bar_index: int
    lookback_bars: int
    steps: tuple[DailyBehaviorSequenceStep, ...]

    @property
    def dimensions(self) -> tuple[DailyBehaviorDimension, ...]:
        """Return observed dimensions once each in stable enum order."""

        return tuple(
            dimension
            for dimension in DailyBehaviorDimension
            if any(dimension in step.dimensions for step in self.steps)
        )

    @property
    def is_actionable(self) -> bool:
        return False

    def bar_indices_for(
        self,
        dimension: DailyBehaviorDimension,
    ) -> tuple[int, ...]:
        return tuple(
            step.bar_index
            for step in self.steps
            if dimension in step.dimensions
        )

    def first_bar_for(
        self,
        dimension: DailyBehaviorDimension,
    ) -> int | None:
        indices = self.bar_indices_for(dimension)
        return None if not indices else indices[0]

    def last_bar_for(
        self,
        dimension: DailyBehaviorDimension,
    ) -> int | None:
        indices = self.bar_indices_for(dimension)
        return None if not indices else indices[-1]


def evaluate_daily_behavior_sequence(
    *,
    weekly_direction: WeeklySetupDirection,
    daily_bar_index: int,
    evidence: Iterable[Evidence],
    lookback_bars: int = 5,
) -> DailyBehaviorSequence:
    """Preserve the temporal order of supported daily behavior dimensions.

    Each bar is evaluated independently with the existing daily-behavior mapping
    and a one-bar evidence window. This prevents older context from being
    re-attributed to later bars while keeping the exact existing behavior-code
    semantics.

    Bars with no supported aligned behavior are omitted from steps. They are
    still represented implicitly by the sequence start/end indices.
    """

    if daily_bar_index < 0:
        raise ValueError("daily_bar_index cannot be negative")
    if lookback_bars <= 0:
        raise ValueError("lookback_bars must be positive")

    first_index = max(0, daily_bar_index - lookback_bars + 1)
    evidence_items = tuple(evidence)
    steps: list[DailyBehaviorSequenceStep] = []

    for bar_index in range(first_index, daily_bar_index + 1):
        snapshot = evaluate_daily_behavior(
            weekly_direction=weekly_direction,
            daily_bar_index=bar_index,
            evidence=evidence_items,
            lookback_bars=1,
        )
        if not snapshot.dimensions:
            continue

        supporting: list[Evidence] = []
        for observation in snapshot.observations:
            for item in observation.evidence:
                if item not in supporting:
                    supporting.append(item)

        steps.append(
            DailyBehaviorSequenceStep(
                bar_index=bar_index,
                dimensions=snapshot.dimensions,
                evidence=tuple(supporting),
            )
        )

    return DailyBehaviorSequence(
        weekly_direction=weekly_direction,
        start_bar_index=first_index,
        end_bar_index=daily_bar_index,
        lookback_bars=lookback_bars,
        steps=tuple(steps),
    )


__all__ = [
    "DailyBehaviorSequence",
    "DailyBehaviorSequenceStep",
    "evaluate_daily_behavior_sequence",
]
