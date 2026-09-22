"""Analysis-only forward outcomes for daily behavior sequences.

This module attaches the existing next-bar-execution audit outcome contract to
fresh DailyBehaviorSequence observations. It has no production authority.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from statistics import mean, median

import pandas as pd

from audit.outcomes import ForwardOutcome, compute_forward_outcome
from daily_behavior import DailyBehaviorDimension
from daily_behavior_sequence import DailyBehaviorSequence
from models import EvidenceCode
from weekly_setup import WeeklySetupDirection


@dataclass(frozen=True, slots=True)
class DailyBehaviorSequenceStepSignature:
    """Relative temporal identity for one observed coarse behavior step."""

    offset_from_signal: int
    dimensions: tuple[DailyBehaviorDimension, ...]


@dataclass(frozen=True, slots=True)
class DailyBehaviorSequenceEvidenceStepSignature:
    """Relative temporal identity preserving exact supporting evidence codes."""

    offset_from_signal: int
    evidence_codes: tuple[EvidenceCode, ...]


@dataclass(frozen=True, slots=True)
class DailyBehaviorSequenceOutcomeObservation:
    """One read-only sequence observation at one forward horizon."""

    signal_bar_index: int
    weekly_direction: WeeklySetupDirection
    lookback_bars: int
    signature: tuple[DailyBehaviorSequenceStepSignature, ...]
    horizon_bars: int
    outcome: ForwardOutcome | None

    @property
    def outcome_available(self) -> bool:
        return self.outcome is not None

    @property
    def complete(self) -> bool:
        return self.outcome is not None and self.outcome.complete

    @property
    def is_actionable(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class DailyBehaviorSequenceOutcomeSummary:
    """Descriptive cohort metrics for one exact sequence signature/horizon."""

    weekly_direction: WeeklySetupDirection
    signature: tuple[DailyBehaviorSequenceStepSignature, ...]
    horizon_bars: int
    observation_count: int
    outcome_available_count: int
    complete_outcome_count: int
    mean_favorable_return: float | None
    median_favorable_return: float | None
    mean_mfe: float | None
    mean_mae: float | None

    @property
    def is_actionable(self) -> bool:
        return False


def daily_behavior_sequence_signature(
    sequence: DailyBehaviorSequence,
) -> tuple[DailyBehaviorSequenceStepSignature, ...]:
    """Return an absolute-date-independent sequence identity."""

    return tuple(
        DailyBehaviorSequenceStepSignature(
            offset_from_signal=step.bar_index - sequence.end_bar_index,
            dimensions=step.dimensions,
        )
        for step in sequence.steps
    )


def daily_behavior_sequence_evidence_signature(
    sequence: DailyBehaviorSequence,
) -> tuple[DailyBehaviorSequenceEvidenceStepSignature, ...]:
    """Return exact supporting-code identity without changing coarse grouping.

    The existing dimension signature remains the outcome-study grouping key.
    This second identity preserves named-event provenance so audits can measure
    where multiple distinct evidence narratives collapse into the same coarse
    behavior sequence.
    """

    return tuple(
        DailyBehaviorSequenceEvidenceStepSignature(
            offset_from_signal=step.bar_index - sequence.end_bar_index,
            evidence_codes=tuple(
                sorted(
                    {item.code for item in step.evidence},
                    key=lambda code: str(getattr(code, "value", code)),
                )
            ),
        )
        for step in sequence.steps
    )


def sequence_has_fresh_behavior(sequence: DailyBehaviorSequence) -> bool:
    """Return whether the target bar itself contributed supported behavior."""

    return any(
        step.bar_index == sequence.end_bar_index
        for step in sequence.steps
    )


def _outcome_side(direction: WeeklySetupDirection) -> str:
    if direction is WeeklySetupDirection.BULLISH:
        return "long"
    return "short"


def build_daily_behavior_sequence_outcomes(
    bars: pd.DataFrame,
    *,
    sequence: DailyBehaviorSequence,
    horizons: Iterable[int] = (1, 3, 5),
) -> tuple[DailyBehaviorSequenceOutcomeObservation, ...]:
    """Attach causal forward outcomes to one fresh sequence observation.

    A sequence is eligible only when its end bar contains fresh supported
    behavior. If the latest supported step occurred on an older bar, returning
    no observations prevents retrospectively scoring returns that began before
    the sequence was observed at the requested target bar.

    Latest signals with no next execution bar are retained with outcome=None.
    """

    normalized_horizons = tuple(sorted(set(int(item) for item in horizons)))
    if not normalized_horizons or any(item <= 0 for item in normalized_horizons):
        raise ValueError("horizons must contain positive bar counts")
    if sequence.end_bar_index < 0 or sequence.end_bar_index >= len(bars):
        raise IndexError("sequence end_bar_index is outside bars")
    if not sequence_has_fresh_behavior(sequence):
        return ()

    signature = daily_behavior_sequence_signature(sequence)
    side = _outcome_side(sequence.weekly_direction)
    observations: list[DailyBehaviorSequenceOutcomeObservation] = []

    for horizon_bars in normalized_horizons:
        outcome = compute_forward_outcome(
            bars,
            signal_bar_index=sequence.end_bar_index,
            horizon_bars=horizon_bars,
            side=side,
        )
        observations.append(
            DailyBehaviorSequenceOutcomeObservation(
                signal_bar_index=sequence.end_bar_index,
                weekly_direction=sequence.weekly_direction,
                lookback_bars=sequence.lookback_bars,
                signature=signature,
                horizon_bars=horizon_bars,
                outcome=outcome,
            )
        )

    return tuple(observations)


def summarize_daily_behavior_sequence_outcomes(
    observations: Iterable[DailyBehaviorSequenceOutcomeObservation],
) -> tuple[DailyBehaviorSequenceOutcomeSummary, ...]:
    """Aggregate exact sequence signatures without ranking or promotion."""

    groups: dict[
        tuple[
            WeeklySetupDirection,
            tuple[DailyBehaviorSequenceStepSignature, ...],
            int,
        ],
        list[DailyBehaviorSequenceOutcomeObservation],
    ] = defaultdict(list)

    for observation in observations:
        key = (
            observation.weekly_direction,
            observation.signature,
            observation.horizon_bars,
        )
        groups[key].append(observation)

    summaries: list[DailyBehaviorSequenceOutcomeSummary] = []
    for (direction, signature, horizon_bars), group in groups.items():
        available = [item.outcome for item in group if item.outcome is not None]
        complete = [item for item in available if item.complete]

        favorable = [item.favorable_return for item in complete]
        mfe = [item.mfe for item in complete]
        mae = [item.mae for item in complete]

        summaries.append(
            DailyBehaviorSequenceOutcomeSummary(
                weekly_direction=direction,
                signature=signature,
                horizon_bars=horizon_bars,
                observation_count=len(group),
                outcome_available_count=len(available),
                complete_outcome_count=len(complete),
                mean_favorable_return=None if not favorable else mean(favorable),
                median_favorable_return=(
                    None if not favorable else median(favorable)
                ),
                mean_mfe=None if not mfe else mean(mfe),
                mean_mae=None if not mae else mean(mae),
            )
        )

    return tuple(
        sorted(
            summaries,
            key=lambda item: (
                item.weekly_direction.value,
                item.horizon_bars,
                tuple(
                    (
                        step.offset_from_signal,
                        tuple(dimension.value for dimension in step.dimensions),
                    )
                    for step in item.signature
                ),
            ),
        )
    )


__all__ = [
    "DailyBehaviorSequenceEvidenceStepSignature",
    "DailyBehaviorSequenceOutcomeObservation",
    "DailyBehaviorSequenceOutcomeSummary",
    "DailyBehaviorSequenceStepSignature",
    "build_daily_behavior_sequence_outcomes",
    "daily_behavior_sequence_evidence_signature",
    "daily_behavior_sequence_signature",
    "sequence_has_fresh_behavior",
    "summarize_daily_behavior_sequence_outcomes",
]
