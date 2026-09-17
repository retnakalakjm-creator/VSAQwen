from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum, auto
from statistics import mean, median

from models import EvidenceDirection
from weekly_behavior import WeeklyBehaviorState, WeeklyBehaviorStateBuilder
from weekly_behavior_evolution import WeeklyBehaviorEvolution, WeeklyBehaviorEvolutionEngine
from weekly_decision_audit import WeeklyDecisionGateAuditRecord
from weekly_replay_comparison import (
    DirectionalForwardOutcome,
    WeeklyReplayComparisonEngine,
    WeeklyReplayPriceBar,
)
from weekly_thesis import ShadowWeeklyThesis, ShadowWeeklyThesisBuilder, ShadowWeeklyThesisState


class WeeklyCounterfactualPolicy(StrEnum):
    """Read-only candidate-suppression policies evaluated by WF7A.

    These are counterfactual audit policies only.  They do not alter scanner
    qualification, actionability, ranking, WeeklySetup, alerts, or orders.
    """

    STRUCTURAL_INVALIDATION_ONLY = auto()
    MATERIAL_CONTRADICTION = auto()
    MATERIAL_CONTRADICTION_OR_OPPOSITE_SUPPORT = auto()
    REQUIRE_SAME_DIRECTION_SHADOW_SUPPORT = auto()


class WeeklyCounterfactualPartition(StrEnum):
    ALL = auto()
    UNSPLIT = auto()
    IN_SAMPLE = auto()
    OUT_OF_SAMPLE = auto()


class WeeklyCounterfactualDisposition(StrEnum):
    RETAIN = auto()
    SUPPRESS = auto()


class WeeklyCounterfactualReason(StrEnum):
    NONE = auto()
    STRUCTURAL_INVALIDATION = auto()
    CAMPAIGN_CHALLENGED = auto()
    OPPOSITE_SUPPORTED_THESIS = auto()
    SHADOW_SUPPORT_MISSING = auto()


@dataclass(frozen=True, slots=True)
class WeeklyActionabilityCounterfactualInput:
    """One symbol's causal weekly audit history and matching completed prices."""

    symbol: str
    audits: tuple[WeeklyDecisionGateAuditRecord, ...]
    prices: tuple[WeeklyReplayPriceBar, ...]
    out_of_sample_start_bar_index: int | None = None


@dataclass(frozen=True, slots=True)
class WeeklyActionabilityCounterfactualObservation:
    """One legacy-actionable week under one counterfactual suppression policy."""

    symbol: str
    week: str | None
    bar_index: int
    policy: WeeklyCounterfactualPolicy
    partition: WeeklyCounterfactualPartition

    legacy_direction: EvidenceDirection
    shadow_state: ShadowWeeklyThesisState
    shadow_direction: EvidenceDirection

    disposition: WeeklyCounterfactualDisposition
    reasons: tuple[WeeklyCounterfactualReason, ...]
    outcomes: tuple[DirectionalForwardOutcome, ...]

    @property
    def suppressed(self) -> bool:
        return self.disposition is WeeklyCounterfactualDisposition.SUPPRESS


@dataclass(frozen=True, slots=True)
class WeeklyCounterfactualCohortMetrics:
    observation_count: int
    complete_outcome_count: int
    mean_close_return_pct: float | None
    median_close_return_pct: float | None
    mean_mfe_pct: float | None
    mean_mae_pct: float | None
    positive_close_return_count: int
    non_positive_close_return_count: int


@dataclass(frozen=True, slots=True)
class WeeklyCounterfactualSummary:
    policy: WeeklyCounterfactualPolicy
    horizon_weeks: int
    partition: WeeklyCounterfactualPartition

    baseline: WeeklyCounterfactualCohortMetrics
    retained: WeeklyCounterfactualCohortMetrics
    suppressed: WeeklyCounterfactualCohortMetrics

    retained_minus_baseline_mean_close_pct: float | None
    retained_minus_suppressed_mean_close_pct: float | None
    retained_minus_suppressed_mean_mfe_pct: float | None
    retained_minus_suppressed_mean_mae_pct: float | None


@dataclass(frozen=True, slots=True)
class WeeklyCounterfactualLeaveOneSymbolOut:
    policy: WeeklyCounterfactualPolicy
    horizon_weeks: int
    held_out_symbol: str

    held_out_retained: WeeklyCounterfactualCohortMetrics
    held_out_suppressed: WeeklyCounterfactualCohortMetrics
    held_out_retained_minus_suppressed_mean_close_pct: float | None

    other_symbols_retained: WeeklyCounterfactualCohortMetrics
    other_symbols_suppressed: WeeklyCounterfactualCohortMetrics
    other_symbols_retained_minus_suppressed_mean_close_pct: float | None


@dataclass(frozen=True, slots=True)
class WeeklyActionabilityCounterfactualReport:
    """WF7A audit report.  It deliberately carries no production authority."""

    symbols: tuple[str, ...]
    horizons_weeks: tuple[int, ...]
    observations: tuple[WeeklyActionabilityCounterfactualObservation, ...]
    summaries: tuple[WeeklyCounterfactualSummary, ...]
    leave_one_symbol_out: tuple[WeeklyCounterfactualLeaveOneSymbolOut, ...]

    @property
    def is_actionable(self) -> bool:
        return False


class WeeklyActionabilityCounterfactualEngine:
    """Test suppression of legacy-actionable weeks using shadow contradiction.

    WF7A intentionally does not create a new production decision.  It asks a
    narrower historical question: if legacy qualification remained unchanged,
    would withholding legacy-actionable weeks under transparent shadow conflict
    policies have separated stronger from weaker forward outcomes?
    """

    DEFAULT_HORIZONS = WeeklyReplayComparisonEngine.DEFAULT_HORIZONS

    _SUPPORTED_STATES = frozenset(
        {
            ShadowWeeklyThesisState.BULLISH_SUPPORTED,
            ShadowWeeklyThesisState.BEARISH_SUPPORTED,
        }
    )
    _CHALLENGED_STATES = frozenset(
        {
            ShadowWeeklyThesisState.BULLISH_CHALLENGED,
            ShadowWeeklyThesisState.BEARISH_CHALLENGED,
        }
    )
    _INVALIDATION_STATES = frozenset(
        {
            ShadowWeeklyThesisState.BULLISH_INVALIDATION_EVIDENCE,
            ShadowWeeklyThesisState.BEARISH_INVALIDATION_EVIDENCE,
        }
    )

    @staticmethod
    def _validate(
        datasets: Sequence[WeeklyActionabilityCounterfactualInput],
        horizons_weeks: Sequence[int],
    ) -> tuple[tuple[WeeklyActionabilityCounterfactualInput, ...], tuple[int, ...]]:
        items = tuple(datasets)
        if not items:
            raise ValueError("at least one counterfactual dataset is required")

        horizons = tuple(sorted(set(int(item) for item in horizons_weeks)))
        if not horizons or any(item <= 0 for item in horizons):
            raise ValueError("forward horizons must contain positive week counts")

        seen: set[str] = set()
        for dataset in items:
            symbol = dataset.symbol.strip().upper()
            if not symbol:
                raise ValueError("dataset symbol cannot be empty")
            if symbol in seen:
                raise ValueError("counterfactual datasets require unique symbols")
            seen.add(symbol)

            if not dataset.audits:
                raise ValueError(f"{symbol}: audit history cannot be empty")
            if len(dataset.audits) != len(dataset.prices):
                raise ValueError(f"{symbol}: audit and price histories must have equal length")
            if (
                dataset.out_of_sample_start_bar_index is not None
                and dataset.out_of_sample_start_bar_index < 0
            ):
                raise ValueError("out_of_sample_start_bar_index cannot be negative")

            previous: int | None = None
            for audit, price in zip(dataset.audits, dataset.prices):
                if audit.symbol != symbol:
                    raise ValueError(f"{symbol}: audit symbol does not match dataset symbol")
                if audit.bar_index is None:
                    raise ValueError(f"{symbol}: audit bar_index is required")
                if previous is not None and audit.bar_index <= previous:
                    raise ValueError(f"{symbol}: audit history must be strictly increasing")
                if price.bar_index != audit.bar_index or price.week != audit.week:
                    raise ValueError(f"{symbol}: price identity must match audit identity")
                previous = audit.bar_index

        return items, horizons

    @staticmethod
    def _partition(
        bar_index: int,
        out_of_sample_start_bar_index: int | None,
    ) -> WeeklyCounterfactualPartition:
        if out_of_sample_start_bar_index is None:
            return WeeklyCounterfactualPartition.UNSPLIT
        if bar_index >= out_of_sample_start_bar_index:
            return WeeklyCounterfactualPartition.OUT_OF_SAMPLE
        return WeeklyCounterfactualPartition.IN_SAMPLE

    @staticmethod
    def _legacy_direction(audit: WeeklyDecisionGateAuditRecord) -> EvidenceDirection:
        qualification = str(audit.legacy_qualification)
        if qualification.endswith("persistent_bullish"):
            return EvidenceDirection.BULLISH
        if qualification.endswith("persistent_bearish"):
            return EvidenceDirection.BEARISH
        return EvidenceDirection.NEUTRAL

    @classmethod
    def _reasons(
        cls,
        *,
        legacy_direction: EvidenceDirection,
        thesis: ShadowWeeklyThesis,
    ) -> tuple[WeeklyCounterfactualReason, ...]:
        reasons: list[WeeklyCounterfactualReason] = []

        if (
            thesis.direction is legacy_direction
            and thesis.state in cls._INVALIDATION_STATES
        ):
            reasons.append(WeeklyCounterfactualReason.STRUCTURAL_INVALIDATION)

        if (
            thesis.direction is legacy_direction
            and thesis.state in cls._CHALLENGED_STATES
        ):
            reasons.append(WeeklyCounterfactualReason.CAMPAIGN_CHALLENGED)

        if (
            thesis.direction not in {EvidenceDirection.NEUTRAL, legacy_direction}
            and thesis.state in cls._SUPPORTED_STATES
        ):
            reasons.append(WeeklyCounterfactualReason.OPPOSITE_SUPPORTED_THESIS)

        if not (
            thesis.direction is legacy_direction
            and thesis.state in cls._SUPPORTED_STATES
        ):
            reasons.append(WeeklyCounterfactualReason.SHADOW_SUPPORT_MISSING)

        return tuple(reasons) if reasons else (WeeklyCounterfactualReason.NONE,)

    @staticmethod
    def _suppressed(
        policy: WeeklyCounterfactualPolicy,
        reasons: tuple[WeeklyCounterfactualReason, ...],
    ) -> bool:
        reason_set = frozenset(reasons)
        if policy is WeeklyCounterfactualPolicy.STRUCTURAL_INVALIDATION_ONLY:
            return WeeklyCounterfactualReason.STRUCTURAL_INVALIDATION in reason_set
        if policy is WeeklyCounterfactualPolicy.MATERIAL_CONTRADICTION:
            return bool(
                reason_set
                & {
                    WeeklyCounterfactualReason.STRUCTURAL_INVALIDATION,
                    WeeklyCounterfactualReason.CAMPAIGN_CHALLENGED,
                }
            )
        if policy is WeeklyCounterfactualPolicy.MATERIAL_CONTRADICTION_OR_OPPOSITE_SUPPORT:
            return bool(
                reason_set
                & {
                    WeeklyCounterfactualReason.STRUCTURAL_INVALIDATION,
                    WeeklyCounterfactualReason.CAMPAIGN_CHALLENGED,
                    WeeklyCounterfactualReason.OPPOSITE_SUPPORTED_THESIS,
                }
            )
        if policy is WeeklyCounterfactualPolicy.REQUIRE_SAME_DIRECTION_SHADOW_SUPPORT:
            return WeeklyCounterfactualReason.SHADOW_SUPPORT_MISSING in reason_set
        raise ValueError(f"unsupported counterfactual policy: {policy}")

    @classmethod
    def _observations_for_dataset(
        cls,
        dataset: WeeklyActionabilityCounterfactualInput,
        horizons: tuple[int, ...],
    ) -> tuple[WeeklyActionabilityCounterfactualObservation, ...]:
        audits = tuple(dataset.audits)
        prices = tuple(dataset.prices)
        replay = WeeklyReplayComparisonEngine.compare(
            audits=audits,
            prices=prices,
            horizons_weeks=horizons,
        )
        replay_by_index = {item.bar_index: item for item in replay.records}

        behaviors: list[WeeklyBehaviorState] = []
        evolutions: list[WeeklyBehaviorEvolution] = []
        theses: list[ShadowWeeklyThesis] = []
        for audit in audits:
            behavior = WeeklyBehaviorStateBuilder.from_audit(audit)
            behaviors.append(behavior)
            evolution = WeeklyBehaviorEvolutionEngine.evaluate(behaviors)
            evolutions.append(evolution)
            theses.append(
                ShadowWeeklyThesisBuilder.build(
                    behavior=behavior,
                    evolution=evolution,
                )
            )

        observations: list[WeeklyActionabilityCounterfactualObservation] = []
        for audit, thesis in zip(audits, theses):
            if not audit.legacy_actionable:
                continue
            assert audit.bar_index is not None
            legacy_direction = cls._legacy_direction(audit)
            if legacy_direction is EvidenceDirection.NEUTRAL:
                raise ValueError("legacy-actionable audit must have a directional qualification")

            replay_record = replay_by_index[audit.bar_index]
            reasons = cls._reasons(
                legacy_direction=legacy_direction,
                thesis=thesis,
            )
            partition = cls._partition(
                audit.bar_index,
                dataset.out_of_sample_start_bar_index,
            )
            for policy in WeeklyCounterfactualPolicy:
                suppressed = cls._suppressed(policy, reasons)
                observations.append(
                    WeeklyActionabilityCounterfactualObservation(
                        symbol=audit.symbol,
                        week=audit.week,
                        bar_index=audit.bar_index,
                        policy=policy,
                        partition=partition,
                        legacy_direction=legacy_direction,
                        shadow_state=thesis.state,
                        shadow_direction=thesis.direction,
                        disposition=(
                            WeeklyCounterfactualDisposition.SUPPRESS
                            if suppressed
                            else WeeklyCounterfactualDisposition.RETAIN
                        ),
                        reasons=reasons,
                        outcomes=replay_record.legacy_forward_outcomes,
                    )
                )
        return tuple(observations)

    @staticmethod
    def _outcome_for_horizon(
        observation: WeeklyActionabilityCounterfactualObservation,
        horizon: int,
    ) -> DirectionalForwardOutcome | None:
        return next(
            (item for item in observation.outcomes if item.horizon_weeks == horizon),
            None,
        )

    @classmethod
    def _cohort_metrics(
        cls,
        observations: Sequence[WeeklyActionabilityCounterfactualObservation],
        horizon: int,
    ) -> WeeklyCounterfactualCohortMetrics:
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
        close_values = tuple(item.close_return_pct for item in complete if item.close_return_pct is not None)
        mfe_values = tuple(
            item.maximum_favorable_excursion_pct
            for item in complete
            if item.maximum_favorable_excursion_pct is not None
        )
        mae_values = tuple(
            item.maximum_adverse_excursion_pct
            for item in complete
            if item.maximum_adverse_excursion_pct is not None
        )
        return WeeklyCounterfactualCohortMetrics(
            observation_count=len(items),
            complete_outcome_count=len(complete),
            mean_close_return_pct=mean(close_values) if close_values else None,
            median_close_return_pct=median(close_values) if close_values else None,
            mean_mfe_pct=mean(mfe_values) if mfe_values else None,
            mean_mae_pct=mean(mae_values) if mae_values else None,
            positive_close_return_count=sum(value > 0.0 for value in close_values),
            non_positive_close_return_count=sum(value <= 0.0 for value in close_values),
        )

    @staticmethod
    def _delta(left: float | None, right: float | None) -> float | None:
        if left is None or right is None:
            return None
        return left - right

    @classmethod
    def _summary(
        cls,
        observations: tuple[WeeklyActionabilityCounterfactualObservation, ...],
        *,
        policy: WeeklyCounterfactualPolicy,
        horizon: int,
        partition: WeeklyCounterfactualPartition,
    ) -> WeeklyCounterfactualSummary:
        policy_items = tuple(
            item
            for item in observations
            if item.policy is policy
            and (
                partition is WeeklyCounterfactualPartition.ALL
                or item.partition is partition
            )
        )
        retained_items = tuple(
            item for item in policy_items if item.disposition is WeeklyCounterfactualDisposition.RETAIN
        )
        suppressed_items = tuple(
            item for item in policy_items if item.disposition is WeeklyCounterfactualDisposition.SUPPRESS
        )

        baseline = cls._cohort_metrics(policy_items, horizon)
        retained = cls._cohort_metrics(retained_items, horizon)
        suppressed = cls._cohort_metrics(suppressed_items, horizon)
        return WeeklyCounterfactualSummary(
            policy=policy,
            horizon_weeks=horizon,
            partition=partition,
            baseline=baseline,
            retained=retained,
            suppressed=suppressed,
            retained_minus_baseline_mean_close_pct=cls._delta(
                retained.mean_close_return_pct,
                baseline.mean_close_return_pct,
            ),
            retained_minus_suppressed_mean_close_pct=cls._delta(
                retained.mean_close_return_pct,
                suppressed.mean_close_return_pct,
            ),
            retained_minus_suppressed_mean_mfe_pct=cls._delta(
                retained.mean_mfe_pct,
                suppressed.mean_mfe_pct,
            ),
            retained_minus_suppressed_mean_mae_pct=cls._delta(
                retained.mean_mae_pct,
                suppressed.mean_mae_pct,
            ),
        )

    @classmethod
    def _summaries(
        cls,
        observations: tuple[WeeklyActionabilityCounterfactualObservation, ...],
        horizons: tuple[int, ...],
    ) -> tuple[WeeklyCounterfactualSummary, ...]:
        partitions = [WeeklyCounterfactualPartition.ALL]
        for partition in (
            WeeklyCounterfactualPartition.UNSPLIT,
            WeeklyCounterfactualPartition.IN_SAMPLE,
            WeeklyCounterfactualPartition.OUT_OF_SAMPLE,
        ):
            if any(item.partition is partition for item in observations):
                partitions.append(partition)

        return tuple(
            cls._summary(
                observations,
                policy=policy,
                horizon=horizon,
                partition=partition,
            )
            for policy in WeeklyCounterfactualPolicy
            for horizon in horizons
            for partition in partitions
        )

    @classmethod
    def _leave_one_symbol_out(
        cls,
        observations: tuple[WeeklyActionabilityCounterfactualObservation, ...],
        horizons: tuple[int, ...],
    ) -> tuple[WeeklyCounterfactualLeaveOneSymbolOut, ...]:
        symbols = tuple(sorted({item.symbol for item in observations}))
        if len(symbols) < 2:
            return ()

        result: list[WeeklyCounterfactualLeaveOneSymbolOut] = []
        for policy in WeeklyCounterfactualPolicy:
            policy_items = tuple(item for item in observations if item.policy is policy)
            for horizon in horizons:
                for held_out_symbol in symbols:
                    held = tuple(item for item in policy_items if item.symbol == held_out_symbol)
                    other = tuple(item for item in policy_items if item.symbol != held_out_symbol)
                    if not held or not other:
                        continue
                    held_retained = cls._cohort_metrics(
                        tuple(item for item in held if not item.suppressed),
                        horizon,
                    )
                    held_suppressed = cls._cohort_metrics(
                        tuple(item for item in held if item.suppressed),
                        horizon,
                    )
                    other_retained = cls._cohort_metrics(
                        tuple(item for item in other if not item.suppressed),
                        horizon,
                    )
                    other_suppressed = cls._cohort_metrics(
                        tuple(item for item in other if item.suppressed),
                        horizon,
                    )
                    result.append(
                        WeeklyCounterfactualLeaveOneSymbolOut(
                            policy=policy,
                            horizon_weeks=horizon,
                            held_out_symbol=held_out_symbol,
                            held_out_retained=held_retained,
                            held_out_suppressed=held_suppressed,
                            held_out_retained_minus_suppressed_mean_close_pct=cls._delta(
                                held_retained.mean_close_return_pct,
                                held_suppressed.mean_close_return_pct,
                            ),
                            other_symbols_retained=other_retained,
                            other_symbols_suppressed=other_suppressed,
                            other_symbols_retained_minus_suppressed_mean_close_pct=cls._delta(
                                other_retained.mean_close_return_pct,
                                other_suppressed.mean_close_return_pct,
                            ),
                        )
                    )
        return tuple(result)

    @classmethod
    def audit(
        cls,
        *,
        datasets: Sequence[WeeklyActionabilityCounterfactualInput],
        horizons_weeks: Sequence[int] = DEFAULT_HORIZONS,
    ) -> WeeklyActionabilityCounterfactualReport:
        items, horizons = cls._validate(datasets, horizons_weeks)
        observations = tuple(
            observation
            for dataset in items
            for observation in cls._observations_for_dataset(dataset, horizons)
        )
        return WeeklyActionabilityCounterfactualReport(
            symbols=tuple(sorted(item.symbol.strip().upper() for item in items)),
            horizons_weeks=horizons,
            observations=observations,
            summaries=cls._summaries(observations, horizons),
            leave_one_symbol_out=cls._leave_one_symbol_out(observations, horizons),
        )


__all__ = [
    "WeeklyActionabilityCounterfactualEngine",
    "WeeklyActionabilityCounterfactualInput",
    "WeeklyActionabilityCounterfactualObservation",
    "WeeklyActionabilityCounterfactualReport",
    "WeeklyCounterfactualCohortMetrics",
    "WeeklyCounterfactualDisposition",
    "WeeklyCounterfactualLeaveOneSymbolOut",
    "WeeklyCounterfactualPartition",
    "WeeklyCounterfactualPolicy",
    "WeeklyCounterfactualReason",
    "WeeklyCounterfactualSummary",
]
