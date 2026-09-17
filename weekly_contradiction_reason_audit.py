from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum, auto
from statistics import mean, median

from models import EvidenceDirection
from weekly_actionability_counterfactual import (
    WeeklyActionabilityCounterfactualObservation,
    WeeklyActionabilityCounterfactualReport,
    WeeklyCounterfactualPartition,
    WeeklyCounterfactualPolicy,
    WeeklyCounterfactualReason,
)
from weekly_replay_comparison import DirectionalForwardOutcome
from weekly_thesis import ShadowWeeklyThesisState


class WeeklyContradictionReasonClass(StrEnum):
    """Exclusive WF7B reason classes for legacy-actionable observations."""

    SAME_DIRECTION_SUPPORTED = auto()
    CAMPAIGN_CHALLENGED = auto()
    OPPOSITE_SUPPORTED_THESIS = auto()
    STRUCTURAL_INVALIDATION = auto()
    SHADOW_SUPPORT_MISSING = auto()


class WeeklyContradictionSampleUnit(StrEnum):
    """Whether a cohort uses every eligible bar or only episode starts."""

    BAR = auto()
    EPISODE_START = auto()


@dataclass(frozen=True, slots=True)
class WeeklyContradictionReasonObservation:
    """One unique legacy-actionable week classified by its dominant shadow reason."""

    symbol: str
    week: str | None
    bar_index: int
    partition: WeeklyCounterfactualPartition
    legacy_direction: EvidenceDirection
    shadow_state: ShadowWeeklyThesisState
    shadow_direction: EvidenceDirection
    reason_class: WeeklyContradictionReasonClass
    source_reasons: tuple[WeeklyCounterfactualReason, ...]
    episode_id: int
    episode_start: bool
    episode_length_so_far: int
    outcomes: tuple[DirectionalForwardOutcome, ...]


@dataclass(frozen=True, slots=True)
class WeeklyContradictionReasonMetrics:
    observation_count: int
    complete_outcome_count: int
    mean_close_return_pct: float | None
    median_close_return_pct: float | None
    mean_mfe_pct: float | None
    mean_mae_pct: float | None
    positive_close_return_count: int
    non_positive_close_return_count: int


@dataclass(frozen=True, slots=True)
class WeeklyContradictionReasonSummary:
    reason_class: WeeklyContradictionReasonClass
    sample_unit: WeeklyContradictionSampleUnit
    horizon_weeks: int
    partition: WeeklyCounterfactualPartition
    metrics: WeeklyContradictionReasonMetrics


@dataclass(frozen=True, slots=True)
class WeeklyContradictionReasonLeaveOneSymbolOut:
    reason_class: WeeklyContradictionReasonClass
    sample_unit: WeeklyContradictionSampleUnit
    horizon_weeks: int
    held_out_symbol: str
    held_out: WeeklyContradictionReasonMetrics
    other_symbols: WeeklyContradictionReasonMetrics
    held_out_minus_other_mean_close_pct: float | None


@dataclass(frozen=True, slots=True)
class WeeklyContradictionReasonAuditReport:
    """WF7B audit report. It has no production authority."""

    symbols: tuple[str, ...]
    horizons_weeks: tuple[int, ...]
    observations: tuple[WeeklyContradictionReasonObservation, ...]
    summaries: tuple[WeeklyContradictionReasonSummary, ...]
    leave_one_symbol_out: tuple[WeeklyContradictionReasonLeaveOneSymbolOut, ...]

    @property
    def is_actionable(self) -> bool:
        return False


class WeeklyContradictionReasonAuditEngine:
    """Decompose WF7A conflicts into exclusive reasons and episode starts.

    WF7A deliberately repeats each legacy-actionable week once per counterfactual
    policy. WF7B takes one policy-independent copy, classifies the underlying
    reason with explicit precedence, and then reports both bar-level and
    episode-start cohorts. It does not select a production suppression rule.
    """

    _SOURCE_POLICY = WeeklyCounterfactualPolicy.STRUCTURAL_INVALIDATION_ONLY
    _SUPPORTED_STATES = frozenset(
        {
            ShadowWeeklyThesisState.BULLISH_SUPPORTED,
            ShadowWeeklyThesisState.BEARISH_SUPPORTED,
        }
    )

    @staticmethod
    def _opposite(direction: EvidenceDirection) -> EvidenceDirection:
        if direction is EvidenceDirection.BULLISH:
            return EvidenceDirection.BEARISH
        if direction is EvidenceDirection.BEARISH:
            return EvidenceDirection.BULLISH
        return EvidenceDirection.NEUTRAL

    @classmethod
    def _reason_class(
        cls,
        item: WeeklyActionabilityCounterfactualObservation,
    ) -> WeeklyContradictionReasonClass:
        reasons = frozenset(item.reasons)

        # Strongest observable contradiction wins. This precedence is an audit
        # taxonomy only; it is not a production severity score.
        if WeeklyCounterfactualReason.STRUCTURAL_INVALIDATION in reasons:
            return WeeklyContradictionReasonClass.STRUCTURAL_INVALIDATION
        if WeeklyCounterfactualReason.OPPOSITE_SUPPORTED_THESIS in reasons:
            return WeeklyContradictionReasonClass.OPPOSITE_SUPPORTED_THESIS
        if WeeklyCounterfactualReason.CAMPAIGN_CHALLENGED in reasons:
            return WeeklyContradictionReasonClass.CAMPAIGN_CHALLENGED

        if (
            item.shadow_direction is item.legacy_direction
            and item.shadow_state in cls._SUPPORTED_STATES
        ):
            return WeeklyContradictionReasonClass.SAME_DIRECTION_SUPPORTED

        return WeeklyContradictionReasonClass.SHADOW_SUPPORT_MISSING

    @classmethod
    def _unique_source_observations(
        cls,
        report: WeeklyActionabilityCounterfactualReport,
    ) -> tuple[WeeklyActionabilityCounterfactualObservation, ...]:
        source = tuple(
            item for item in report.observations if item.policy is cls._SOURCE_POLICY
        )
        expected = len(report.observations) // len(WeeklyCounterfactualPolicy)
        if len(report.observations) % len(WeeklyCounterfactualPolicy) != 0:
            raise ValueError("WF7A observations are not balanced across policies")
        if len(source) != expected:
            raise ValueError("WF7A source policy does not cover every unique observation")
        return tuple(sorted(source, key=lambda item: (item.symbol, item.bar_index)))

    @classmethod
    def _classify_with_episodes(
        cls,
        items: Sequence[WeeklyActionabilityCounterfactualObservation],
    ) -> tuple[WeeklyContradictionReasonObservation, ...]:
        result: list[WeeklyContradictionReasonObservation] = []
        next_episode_id = 1
        previous_symbol: str | None = None
        previous_index: int | None = None
        previous_direction = EvidenceDirection.NEUTRAL
        previous_reason: WeeklyContradictionReasonClass | None = None
        current_episode_id = 0
        current_episode_length = 0

        for item in items:
            reason = cls._reason_class(item)
            continues = (
                item.symbol == previous_symbol
                and previous_index is not None
                and item.bar_index == previous_index + 1
                and item.legacy_direction is previous_direction
                and reason is previous_reason
            )
            if continues:
                episode_start = False
                current_episode_length += 1
            else:
                episode_start = True
                current_episode_id = next_episode_id
                next_episode_id += 1
                current_episode_length = 1

            result.append(
                WeeklyContradictionReasonObservation(
                    symbol=item.symbol,
                    week=item.week,
                    bar_index=item.bar_index,
                    partition=item.partition,
                    legacy_direction=item.legacy_direction,
                    shadow_state=item.shadow_state,
                    shadow_direction=item.shadow_direction,
                    reason_class=reason,
                    source_reasons=item.reasons,
                    episode_id=current_episode_id,
                    episode_start=episode_start,
                    episode_length_so_far=current_episode_length,
                    outcomes=item.outcomes,
                )
            )
            previous_symbol = item.symbol
            previous_index = item.bar_index
            previous_direction = item.legacy_direction
            previous_reason = reason

        return tuple(result)

    @staticmethod
    def _outcome_for_horizon(
        item: WeeklyContradictionReasonObservation,
        horizon: int,
    ) -> DirectionalForwardOutcome | None:
        return next(
            (outcome for outcome in item.outcomes if outcome.horizon_weeks == horizon),
            None,
        )

    @classmethod
    def _metrics(
        cls,
        observations: Sequence[WeeklyContradictionReasonObservation],
        horizon: int,
    ) -> WeeklyContradictionReasonMetrics:
        items = tuple(observations)
        complete = tuple(
            outcome
            for item in items
            if (outcome := cls._outcome_for_horizon(item, horizon)) is not None
            and outcome.complete
            and outcome.close_return_pct is not None
            and outcome.maximum_favorable_excursion_pct is not None
            and outcome.maximum_adverse_excursion_pct is not None
        )
        closes = tuple(item.close_return_pct for item in complete if item.close_return_pct is not None)
        mfes = tuple(
            item.maximum_favorable_excursion_pct
            for item in complete
            if item.maximum_favorable_excursion_pct is not None
        )
        maes = tuple(
            item.maximum_adverse_excursion_pct
            for item in complete
            if item.maximum_adverse_excursion_pct is not None
        )
        return WeeklyContradictionReasonMetrics(
            observation_count=len(items),
            complete_outcome_count=len(complete),
            mean_close_return_pct=mean(closes) if closes else None,
            median_close_return_pct=median(closes) if closes else None,
            mean_mfe_pct=mean(mfes) if mfes else None,
            mean_mae_pct=mean(maes) if maes else None,
            positive_close_return_count=sum(value > 0.0 for value in closes),
            non_positive_close_return_count=sum(value <= 0.0 for value in closes),
        )

    @staticmethod
    def _delta(left: float | None, right: float | None) -> float | None:
        if left is None or right is None:
            return None
        return left - right

    @classmethod
    def audit(
        cls,
        *,
        counterfactual_report: WeeklyActionabilityCounterfactualReport,
    ) -> WeeklyContradictionReasonAuditReport:
        if not counterfactual_report.observations:
            raise ValueError("WF7B requires WF7A observations")

        source = cls._unique_source_observations(counterfactual_report)
        observations = cls._classify_with_episodes(source)
        horizons = tuple(counterfactual_report.horizons_weeks)
        symbols = tuple(sorted(counterfactual_report.symbols))

        available_partitions = {item.partition for item in observations}
        partitions = [WeeklyCounterfactualPartition.ALL]
        if WeeklyCounterfactualPartition.UNSPLIT in available_partitions:
            partitions.append(WeeklyCounterfactualPartition.UNSPLIT)
        if WeeklyCounterfactualPartition.IN_SAMPLE in available_partitions:
            partitions.append(WeeklyCounterfactualPartition.IN_SAMPLE)
        if WeeklyCounterfactualPartition.OUT_OF_SAMPLE in available_partitions:
            partitions.append(WeeklyCounterfactualPartition.OUT_OF_SAMPLE)

        summaries: list[WeeklyContradictionReasonSummary] = []
        for reason in WeeklyContradictionReasonClass:
            for unit in WeeklyContradictionSampleUnit:
                for horizon in horizons:
                    for partition in partitions:
                        cohort = tuple(
                            item
                            for item in observations
                            if item.reason_class is reason
                            and (
                                partition is WeeklyCounterfactualPartition.ALL
                                or item.partition is partition
                            )
                            and (
                                unit is WeeklyContradictionSampleUnit.BAR
                                or item.episode_start
                            )
                        )
                        summaries.append(
                            WeeklyContradictionReasonSummary(
                                reason_class=reason,
                                sample_unit=unit,
                                horizon_weeks=horizon,
                                partition=partition,
                                metrics=cls._metrics(cohort, horizon),
                            )
                        )

        leave_one_symbol_out: list[WeeklyContradictionReasonLeaveOneSymbolOut] = []
        for reason in WeeklyContradictionReasonClass:
            for unit in WeeklyContradictionSampleUnit:
                base = tuple(
                    item
                    for item in observations
                    if item.reason_class is reason
                    and (
                        unit is WeeklyContradictionSampleUnit.BAR
                        or item.episode_start
                    )
                )
                for horizon in horizons:
                    for symbol in symbols:
                        held_out = tuple(item for item in base if item.symbol == symbol)
                        others = tuple(item for item in base if item.symbol != symbol)
                        held_metrics = cls._metrics(held_out, horizon)
                        other_metrics = cls._metrics(others, horizon)
                        leave_one_symbol_out.append(
                            WeeklyContradictionReasonLeaveOneSymbolOut(
                                reason_class=reason,
                                sample_unit=unit,
                                horizon_weeks=horizon,
                                held_out_symbol=symbol,
                                held_out=held_metrics,
                                other_symbols=other_metrics,
                                held_out_minus_other_mean_close_pct=cls._delta(
                                    held_metrics.mean_close_return_pct,
                                    other_metrics.mean_close_return_pct,
                                ),
                            )
                        )

        return WeeklyContradictionReasonAuditReport(
            symbols=symbols,
            horizons_weeks=horizons,
            observations=observations,
            summaries=tuple(summaries),
            leave_one_symbol_out=tuple(leave_one_symbol_out),
        )


__all__ = [
    "WeeklyContradictionReasonAuditEngine",
    "WeeklyContradictionReasonAuditReport",
    "WeeklyContradictionReasonClass",
    "WeeklyContradictionReasonLeaveOneSymbolOut",
    "WeeklyContradictionReasonMetrics",
    "WeeklyContradictionReasonObservation",
    "WeeklyContradictionReasonSummary",
    "WeeklyContradictionSampleUnit",
]
