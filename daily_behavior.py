from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum, auto

from models import Evidence, EvidenceCode, EvidenceDirection
from weekly_setup import WeeklySetupDirection


class DailyBehaviorDimension(StrEnum):
    """Direction-relative daily behavior observed from VSA evidence.

    These are behavioral dimensions, not mandatory textbook patterns. Named VSA
    events contribute evidence to a dimension, but no individual event is
    required for the dimension model to exist.
    """

    OPPOSING_PRESSURE_RECEDING = auto()
    ALIGNED_PRESSURE_EMERGING = auto()
    REJECTION_OF_OPPOSING_MOVE = auto()
    EFFORT_RESULT_ALIGNMENT = auto()
    ABSORPTION = auto()
    STRUCTURAL_ALIGNMENT = auto()
    CONTINUATION_ALIGNMENT = auto()


@dataclass(frozen=True, slots=True)
class DailyBehaviorObservation:
    dimension: DailyBehaviorDimension
    evidence: tuple[Evidence, ...]


@dataclass(frozen=True, slots=True)
class DailyBehaviorSnapshot:
    """Read-only, point-in-time behavior snapshot for one daily bar.

    The snapshot intentionally has no trigger, score, ranking, or execution
    authority. It only states which behavior dimensions are supported by recent
    evidence relative to the armed weekly direction.
    """

    daily_bar_index: int
    lookback_bars: int
    weekly_direction: WeeklySetupDirection
    observed_evidence: tuple[Evidence, ...]
    observations: tuple[DailyBehaviorObservation, ...]

    @property
    def dimensions(self) -> tuple[DailyBehaviorDimension, ...]:
        return tuple(item.dimension for item in self.observations)

    @property
    def is_actionable(self) -> bool:
        return False

    def evidence_for(
        self,
        dimension: DailyBehaviorDimension,
    ) -> tuple[Evidence, ...]:
        for item in self.observations:
            if item.dimension is dimension:
                return item.evidence
        return ()


_BULLISH_CODES: dict[DailyBehaviorDimension, frozenset[EvidenceCode]] = {
    DailyBehaviorDimension.OPPOSING_PRESSURE_RECEDING: frozenset(
        {
            EvidenceCode.SUPPLY_DRYING_UP,
            EvidenceCode.NO_SUPPLY,
            EvidenceCode.TEST,
        }
    ),
    DailyBehaviorDimension.ALIGNED_PRESSURE_EMERGING: frozenset(
        {
            EvidenceCode.DEMAND_COMING_IN,
            EvidenceCode.INCREASING_DEMAND,
            EvidenceCode.HIDDEN_DEMAND,
        }
    ),
    DailyBehaviorDimension.REJECTION_OF_OPPOSING_MOVE: frozenset(
        {
            EvidenceCode.STOPPING_VOLUME,
            EvidenceCode.SELLING_CLIMAX,
            EvidenceCode.SHAKEOUT,
            EvidenceCode.SPRING,
        }
    ),
    DailyBehaviorDimension.EFFORT_RESULT_ALIGNMENT: frozenset(
        {
            EvidenceCode.RESULT_GT_EFFORT,
            EvidenceCode.EFFORT_RESULT,
        }
    ),
    DailyBehaviorDimension.ABSORPTION: frozenset(
        {
            EvidenceCode.ABSORPTION,
            EvidenceCode.SUPPLY_ABSORPTION,
        }
    ),
    DailyBehaviorDimension.STRUCTURAL_ALIGNMENT: frozenset(
        {EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING}
    ),
    DailyBehaviorDimension.CONTINUATION_ALIGNMENT: frozenset(
        {
            EvidenceCode.STRONG_UPTREND,
            EvidenceCode.REACCUMULATION,
            EvidenceCode.MARKUP,
        }
    ),
}

_BEARISH_CODES: dict[DailyBehaviorDimension, frozenset[EvidenceCode]] = {
    DailyBehaviorDimension.OPPOSING_PRESSURE_RECEDING: frozenset(
        {
            EvidenceCode.DEMAND_DRYING_UP,
            EvidenceCode.NO_DEMAND,
        }
    ),
    DailyBehaviorDimension.ALIGNED_PRESSURE_EMERGING: frozenset(
        {
            EvidenceCode.SUPPLY_COMING_IN,
            EvidenceCode.INCREASING_SUPPLY,
            EvidenceCode.HIDDEN_SUPPLY,
        }
    ),
    DailyBehaviorDimension.REJECTION_OF_OPPOSING_MOVE: frozenset(
        {
            EvidenceCode.BUYING_CLIMAX,
            EvidenceCode.UPTHRUST,
        }
    ),
    DailyBehaviorDimension.EFFORT_RESULT_ALIGNMENT: frozenset(
        {
            EvidenceCode.RESULT_GT_EFFORT,
            EvidenceCode.EFFORT_RESULT,
        }
    ),
    DailyBehaviorDimension.ABSORPTION: frozenset({EvidenceCode.ABSORPTION}),
    DailyBehaviorDimension.STRUCTURAL_ALIGNMENT: frozenset(
        {EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING}
    ),
    DailyBehaviorDimension.CONTINUATION_ALIGNMENT: frozenset(
        {
            EvidenceCode.STRONG_DOWNTREND,
            EvidenceCode.REDISTRIBUTION,
            EvidenceCode.MARKDOWN,
        }
    ),
}


def daily_behavior_dimensions_for_code(
    code: EvidenceCode,
) -> tuple[
    tuple[WeeklySetupDirection, DailyBehaviorDimension],
    ...,
]:
    """Return every direction-relative behavior mapping for one evidence code.

    This is a read-only introspection helper for audit/reporting. It does not
    evaluate evidence, change detector behavior, or create actionability.
    """

    mappings: list[
        tuple[WeeklySetupDirection, DailyBehaviorDimension]
    ] = []
    for weekly_direction, code_map in (
        (WeeklySetupDirection.BULLISH, _BULLISH_CODES),
        (WeeklySetupDirection.BEARISH, _BEARISH_CODES),
    ):
        for dimension in DailyBehaviorDimension:
            if code in code_map[dimension]:
                mappings.append((weekly_direction, dimension))
    return tuple(mappings)


def evaluate_daily_behavior(
    *,
    weekly_direction: WeeklySetupDirection,
    daily_bar_index: int,
    evidence: Iterable[Evidence],
    lookback_bars: int = 5,
) -> DailyBehaviorSnapshot:
    """Summarize recent VSA evidence as direction-relative market behavior.

    Only bars in the closed interval
    ``[daily_bar_index - lookback_bars + 1, daily_bar_index]`` are admitted.
    Future evidence is therefore impossible to consume accidentally.

    Evidence must also agree with the weekly thesis direction. A contrary daily
    event remains useful to the F1 observation layer, but it does not become a
    positive behavior dimension here and cannot reverse the weekly thesis.
    """

    if daily_bar_index < 0:
        raise ValueError("daily_bar_index cannot be negative")
    if lookback_bars <= 0:
        raise ValueError("lookback_bars must be positive")

    first_index = max(0, daily_bar_index - lookback_bars + 1)
    recent = tuple(
        sorted(
            (
                item
                for item in evidence
                if first_index <= item.bar_index <= daily_bar_index
            ),
            key=lambda item: (item.bar_index, str(item.code)),
        )
    )

    aligned_direction = (
        EvidenceDirection.BULLISH
        if weekly_direction is WeeklySetupDirection.BULLISH
        else EvidenceDirection.BEARISH
    )
    code_map = (
        _BULLISH_CODES
        if weekly_direction is WeeklySetupDirection.BULLISH
        else _BEARISH_CODES
    )

    aligned = tuple(item for item in recent if item.direction == aligned_direction)
    observations: list[DailyBehaviorObservation] = []
    for dimension in DailyBehaviorDimension:
        allowed_codes = code_map[dimension]
        supporting = tuple(item for item in aligned if item.code in allowed_codes)
        if supporting:
            observations.append(
                DailyBehaviorObservation(
                    dimension=dimension,
                    evidence=supporting,
                )
            )

    return DailyBehaviorSnapshot(
        daily_bar_index=daily_bar_index,
        lookback_bars=lookback_bars,
        weekly_direction=weekly_direction,
        observed_evidence=recent,
        observations=tuple(observations),
    )


__all__ = [
    "DailyBehaviorDimension",
    "DailyBehaviorObservation",
    "DailyBehaviorSnapshot",
    "daily_behavior_dimensions_for_code",
    "evaluate_daily_behavior",
]
