from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from statistics import mean, median

from models import EvidenceDirection
from weekly_actionability_counterfactual import WeeklyCounterfactualPartition
from weekly_contradiction_reason_audit import (
    WeeklyContradictionReasonAuditReport,
    WeeklyContradictionReasonClass,
)
from weekly_replay_comparison import DirectionalForwardOutcome


@dataclass(frozen=True, slots=True)
class WeeklyOppositeRegime:
    """Legacy weekly regime attached to one frozen actionable observation."""

    trend_direction: object
    trend_state: object
    structural_pattern: object


@dataclass(frozen=True, slots=True)
class WeeklyOppositeSupportedObservation:
    """One WF7B episode start enriched with its legacy weekly regime."""

    symbol: str
    week: str | None
    bar_index: int
    partition: WeeklyCounterfactualPartition
    legacy_direction: EvidenceDirection
    shadow_direction: EvidenceDirection
    reason_class: WeeklyContradictionReasonClass
    episode_id: int
    regime: WeeklyOppositeRegime
    outcomes: tuple[DirectionalForwardOutcome, ...]

    @property
    def is_opposite_supported(self) -> bool:
        return self.reason_class is WeeklyContradictionReasonClass.OPPOSITE_SUPPORTED_THESIS


@dataclass(frozen=True, slots=True)
class WeeklyOppositeMetrics:
    observation_count: int
    complete_outcome_count: int
    mean_close_return_pct: float | None
    median_close_return_pct: float | None
    mean_mfe_pct: float | None
    mean_mae_pct: float | None
    positive_close_return_count: int
    non_positive_close_return_count: int


@dataclass(frozen=True, slots=True)
class WeeklyOppositeRegimeSummary:
    horizon_weeks: int
    partition: WeeklyCounterfactualPartition
    legacy_direction: EvidenceDirection
    trend_direction: object
    trend_state: object
    structural_pattern: object
    metrics: WeeklyOppositeMetrics


@dataclass(frozen=True, slots=True)
class WeeklyOppositeSymbolBalancedSummary:
    horizon_weeks: int
    partition: WeeklyCounterfactualPartition
    legacy_direction: EvidenceDirection
    symbol_count: int
    observation_count: int
    complete_outcome_count: int
    equal_weight_mean_close_return_pct: float | None
    equal_weight_mean_mfe_pct: float | None
    equal_weight_mean_mae_pct: float | None


@dataclass(frozen=True, slots=True)
class WeeklyOppositeMatchedPair:
    treatment: WeeklyOppositeSupportedObservation
    control: WeeklyOppositeSupportedObservation
    bar_distance: int


@dataclass(frozen=True, slots=True)
class WeeklyOppositeMatchedSummary:
    horizon_weeks: int
    partition: WeeklyCounterfactualPartition
    legacy_direction: EvidenceDirection
    pair_count: int
    complete_pair_count: int
    symbol_count: int
    treatment_mean_close_return_pct: float | None
    control_mean_close_return_pct: float | None
    mean_paired_close_delta_pct: float | None
    median_paired_close_delta_pct: float | None
    symbol_balanced_mean_paired_close_delta_pct: float | None
    treatment_mean_mfe_pct: float | None
    control_mean_mfe_pct: float | None
    mean_paired_mfe_delta_pct: float | None
    treatment_mean_mae_pct: float | None
    control_mean_mae_pct: float | None
    mean_paired_mae_delta_pct: float | None
    positive_paired_close_delta_count: int
    non_positive_paired_close_delta_count: int


@dataclass(frozen=True, slots=True)
class WeeklyOppositeSupportedThesisAuditReport:
    symbols: tuple[str, ...]
    horizons_weeks: tuple[int, ...]
    observations: tuple[WeeklyOppositeSupportedObservation, ...]
    regime_summaries: tuple[WeeklyOppositeRegimeSummary, ...]
    symbol_balanced_summaries: tuple[WeeklyOppositeSymbolBalancedSummary, ...]
    matched_pairs: tuple[WeeklyOppositeMatchedPair, ...]
    matched_summaries: tuple[WeeklyOppositeMatchedSummary, ...]
    unmatched_treatments: tuple[WeeklyOppositeSupportedObservation, ...]

    @property
    def is_actionable(self) -> bool:
        return False


class WeeklyOppositeSupportedThesisAuditEngine:
    """WF7C1 audit of opposite-supported weekly thesis episodes.

    Only WF7B episode starts are used. Treatments are
    ``OPPOSITE_SUPPORTED_THESIS`` episodes. Exact matched controls are selected
    from ``SAME_DIRECTION_SUPPORTED`` and ``SHADOW_SUPPORT_MISSING`` episodes
    with the same symbol, partition, legacy direction, trend direction, trend
    state, and structural pattern. Matching is retrospective research only and
    never feeds production qualification or actionability.
    """

    _CONTROL_REASONS = frozenset(
        {
            WeeklyContradictionReasonClass.SAME_DIRECTION_SUPPORTED,
            WeeklyContradictionReasonClass.SHADOW_SUPPORT_MISSING,
        }
    )

    @staticmethod
    def _enum_key(value: object) -> str:
        return str(getattr(value, "value", value))

    @classmethod
    def _match_key(
        cls,
        item: WeeklyOppositeSupportedObservation,
    ) -> tuple[str, str, str, str, str, str]:
        return (
            item.symbol,
            cls._enum_key(item.partition),
            cls._enum_key(item.legacy_direction),
            cls._enum_key(item.regime.trend_direction),
            cls._enum_key(item.regime.trend_state),
            cls._enum_key(item.regime.structural_pattern),
        )

    @staticmethod
    def _outcome_for_horizon(
        item: WeeklyOppositeSupportedObservation,
        horizon: int,
    ) -> DirectionalForwardOutcome | None:
        return next(
            (outcome for outcome in item.outcomes if outcome.horizon_weeks == horizon),
            None,
        )

    @classmethod
    def _complete_outcome(
        cls,
        item: WeeklyOppositeSupportedObservation,
        horizon: int,
    ) -> DirectionalForwardOutcome | None:
        outcome = cls._outcome_for_horizon(item, horizon)
        if (
            outcome is None
            or not outcome.complete
            or outcome.close_return_pct is None
            or outcome.maximum_favorable_excursion_pct is None
            or outcome.maximum_adverse_excursion_pct is None
        ):
            return None
        return outcome

    @classmethod
    def _metrics(
        cls,
        observations: Sequence[WeeklyOppositeSupportedObservation],
        horizon: int,
    ) -> WeeklyOppositeMetrics:
        items = tuple(observations)
        complete = tuple(
            outcome
            for item in items
            if (outcome := cls._complete_outcome(item, horizon)) is not None
        )
        closes = tuple(float(item.close_return_pct) for item in complete)
        mfes = tuple(float(item.maximum_favorable_excursion_pct) for item in complete)
        maes = tuple(float(item.maximum_adverse_excursion_pct) for item in complete)
        return WeeklyOppositeMetrics(
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
    def _partitions(
        observations: Sequence[WeeklyOppositeSupportedObservation],
    ) -> tuple[WeeklyCounterfactualPartition, ...]:
        available = {item.partition for item in observations}
        result = [WeeklyCounterfactualPartition.ALL]
        for partition in (
            WeeklyCounterfactualPartition.UNSPLIT,
            WeeklyCounterfactualPartition.IN_SAMPLE,
            WeeklyCounterfactualPartition.OUT_OF_SAMPLE,
        ):
            if partition in available:
                result.append(partition)
        return tuple(result)

    @staticmethod
    def _in_partition(
        item: WeeklyOppositeSupportedObservation,
        partition: WeeklyCounterfactualPartition,
    ) -> bool:
        return partition is WeeklyCounterfactualPartition.ALL or item.partition is partition

    @classmethod
    def _enrich_episode_starts(
        cls,
        reason_report: WeeklyContradictionReasonAuditReport,
        regimes: Mapping[tuple[str, int], WeeklyOppositeRegime],
    ) -> tuple[WeeklyOppositeSupportedObservation, ...]:
        result: list[WeeklyOppositeSupportedObservation] = []
        for item in reason_report.observations:
            if not item.episode_start:
                continue
            key = (item.symbol, item.bar_index)
            if key not in regimes:
                raise ValueError(
                    "missing weekly regime for episode-start observation: "
                    f"{item.symbol}@{item.bar_index}"
                )
            result.append(
                WeeklyOppositeSupportedObservation(
                    symbol=item.symbol,
                    week=item.week,
                    bar_index=item.bar_index,
                    partition=item.partition,
                    legacy_direction=item.legacy_direction,
                    shadow_direction=item.shadow_direction,
                    reason_class=item.reason_class,
                    episode_id=item.episode_id,
                    regime=regimes[key],
                    outcomes=item.outcomes,
                )
            )
        return tuple(sorted(result, key=lambda item: (item.symbol, item.bar_index)))

    @classmethod
    def _match_controls(
        cls,
        observations: Sequence[WeeklyOppositeSupportedObservation],
    ) -> tuple[
        tuple[WeeklyOppositeMatchedPair, ...],
        tuple[WeeklyOppositeSupportedObservation, ...],
    ]:
        treatments = tuple(item for item in observations if item.is_opposite_supported)
        controls_by_key: dict[
            tuple[str, str, str, str, str, str],
            list[WeeklyOppositeSupportedObservation],
        ] = {}
        for item in observations:
            if item.reason_class not in cls._CONTROL_REASONS:
                continue
            controls_by_key.setdefault(cls._match_key(item), []).append(item)

        for controls in controls_by_key.values():
            controls.sort(key=lambda item: item.bar_index)

        used_controls: set[tuple[str, int]] = set()
        pairs: list[WeeklyOppositeMatchedPair] = []
        unmatched: list[WeeklyOppositeSupportedObservation] = []
        for treatment in treatments:
            candidates = tuple(
                item
                for item in controls_by_key.get(cls._match_key(treatment), ())
                if (item.symbol, item.bar_index) not in used_controls
            )
            if not candidates:
                unmatched.append(treatment)
                continue
            control = min(
                candidates,
                key=lambda item: (
                    abs(item.bar_index - treatment.bar_index),
                    item.bar_index,
                    item.episode_id,
                ),
            )
            used_controls.add((control.symbol, control.bar_index))
            pairs.append(
                WeeklyOppositeMatchedPair(
                    treatment=treatment,
                    control=control,
                    bar_distance=abs(control.bar_index - treatment.bar_index),
                )
            )
        return tuple(pairs), tuple(unmatched)

    @classmethod
    def _symbol_balanced_summary(
        cls,
        treatments: Sequence[WeeklyOppositeSupportedObservation],
        *,
        horizon: int,
        partition: WeeklyCounterfactualPartition,
        legacy_direction: EvidenceDirection,
    ) -> WeeklyOppositeSymbolBalancedSummary:
        cohort = tuple(
            item
            for item in treatments
            if item.legacy_direction is legacy_direction
            and cls._in_partition(item, partition)
        )
        by_symbol: dict[str, list[WeeklyOppositeSupportedObservation]] = {}
        for item in cohort:
            by_symbol.setdefault(item.symbol, []).append(item)

        symbol_close_means: list[float] = []
        symbol_mfe_means: list[float] = []
        symbol_mae_means: list[float] = []
        complete_count = 0
        symbols_with_complete = 0
        for symbol_items in by_symbol.values():
            metrics = cls._metrics(symbol_items, horizon)
            complete_count += metrics.complete_outcome_count
            if metrics.mean_close_return_pct is None:
                continue
            symbols_with_complete += 1
            symbol_close_means.append(metrics.mean_close_return_pct)
            assert metrics.mean_mfe_pct is not None
            assert metrics.mean_mae_pct is not None
            symbol_mfe_means.append(metrics.mean_mfe_pct)
            symbol_mae_means.append(metrics.mean_mae_pct)

        return WeeklyOppositeSymbolBalancedSummary(
            horizon_weeks=horizon,
            partition=partition,
            legacy_direction=legacy_direction,
            symbol_count=symbols_with_complete,
            observation_count=len(cohort),
            complete_outcome_count=complete_count,
            equal_weight_mean_close_return_pct=(
                mean(symbol_close_means) if symbol_close_means else None
            ),
            equal_weight_mean_mfe_pct=(
                mean(symbol_mfe_means) if symbol_mfe_means else None
            ),
            equal_weight_mean_mae_pct=(
                mean(symbol_mae_means) if symbol_mae_means else None
            ),
        )

    @classmethod
    def _matched_summary(
        cls,
        pairs: Sequence[WeeklyOppositeMatchedPair],
        *,
        horizon: int,
        partition: WeeklyCounterfactualPartition,
        legacy_direction: EvidenceDirection,
    ) -> WeeklyOppositeMatchedSummary:
        cohort = tuple(
            pair
            for pair in pairs
            if pair.treatment.legacy_direction is legacy_direction
            and cls._in_partition(pair.treatment, partition)
        )
        complete: list[
            tuple[
                WeeklyOppositeMatchedPair,
                DirectionalForwardOutcome,
                DirectionalForwardOutcome,
            ]
        ] = []
        for pair in cohort:
            treatment_outcome = cls._complete_outcome(pair.treatment, horizon)
            control_outcome = cls._complete_outcome(pair.control, horizon)
            if treatment_outcome is None or control_outcome is None:
                continue
            complete.append((pair, treatment_outcome, control_outcome))

        treatment_close = [float(item[1].close_return_pct) for item in complete]
        control_close = [float(item[2].close_return_pct) for item in complete]
        close_deltas = [
            float(treatment.close_return_pct) - float(control.close_return_pct)
            for _, treatment, control in complete
        ]
        treatment_mfe = [
            float(item[1].maximum_favorable_excursion_pct) for item in complete
        ]
        control_mfe = [
            float(item[2].maximum_favorable_excursion_pct) for item in complete
        ]
        mfe_deltas = [
            float(treatment.maximum_favorable_excursion_pct)
            - float(control.maximum_favorable_excursion_pct)
            for _, treatment, control in complete
        ]
        treatment_mae = [
            float(item[1].maximum_adverse_excursion_pct) for item in complete
        ]
        control_mae = [
            float(item[2].maximum_adverse_excursion_pct) for item in complete
        ]
        mae_deltas = [
            float(treatment.maximum_adverse_excursion_pct)
            - float(control.maximum_adverse_excursion_pct)
            for _, treatment, control in complete
        ]

        deltas_by_symbol: dict[str, list[float]] = {}
        for (pair, _, _), delta in zip(complete, close_deltas):
            deltas_by_symbol.setdefault(pair.treatment.symbol, []).append(delta)
        symbol_means = [mean(values) for values in deltas_by_symbol.values()]

        return WeeklyOppositeMatchedSummary(
            horizon_weeks=horizon,
            partition=partition,
            legacy_direction=legacy_direction,
            pair_count=len(cohort),
            complete_pair_count=len(complete),
            symbol_count=len(symbol_means),
            treatment_mean_close_return_pct=mean(treatment_close) if treatment_close else None,
            control_mean_close_return_pct=mean(control_close) if control_close else None,
            mean_paired_close_delta_pct=mean(close_deltas) if close_deltas else None,
            median_paired_close_delta_pct=median(close_deltas) if close_deltas else None,
            symbol_balanced_mean_paired_close_delta_pct=(
                mean(symbol_means) if symbol_means else None
            ),
            treatment_mean_mfe_pct=mean(treatment_mfe) if treatment_mfe else None,
            control_mean_mfe_pct=mean(control_mfe) if control_mfe else None,
            mean_paired_mfe_delta_pct=mean(mfe_deltas) if mfe_deltas else None,
            treatment_mean_mae_pct=mean(treatment_mae) if treatment_mae else None,
            control_mean_mae_pct=mean(control_mae) if control_mae else None,
            mean_paired_mae_delta_pct=mean(mae_deltas) if mae_deltas else None,
            positive_paired_close_delta_count=sum(value > 0.0 for value in close_deltas),
            non_positive_paired_close_delta_count=sum(value <= 0.0 for value in close_deltas),
        )

    @classmethod
    def audit(
        cls,
        *,
        reason_report: WeeklyContradictionReasonAuditReport,
        regimes: Mapping[tuple[str, int], WeeklyOppositeRegime],
    ) -> WeeklyOppositeSupportedThesisAuditReport:
        if not reason_report.observations:
            raise ValueError("WF7C1 requires WF7B observations")

        observations = cls._enrich_episode_starts(reason_report, regimes)
        treatments = tuple(item for item in observations if item.is_opposite_supported)
        if not treatments:
            raise ValueError("WF7C1 requires at least one opposite-supported episode start")

        pairs, unmatched = cls._match_controls(observations)
        horizons = tuple(reason_report.horizons_weeks)
        partitions = cls._partitions(observations)
        legacy_directions = tuple(
            direction
            for direction in (EvidenceDirection.BULLISH, EvidenceDirection.BEARISH)
            if any(item.legacy_direction is direction for item in treatments)
        )

        regime_summaries: list[WeeklyOppositeRegimeSummary] = []
        regime_keys = sorted(
            {
                (
                    cls._enum_key(item.legacy_direction),
                    cls._enum_key(item.regime.trend_direction),
                    cls._enum_key(item.regime.trend_state),
                    cls._enum_key(item.regime.structural_pattern),
                )
                for item in treatments
            }
        )
        for legacy_key, trend_direction_key, trend_state_key, structural_pattern_key in regime_keys:
            sample = next(
                item
                for item in treatments
                if cls._enum_key(item.legacy_direction) == legacy_key
                and cls._enum_key(item.regime.trend_direction) == trend_direction_key
                and cls._enum_key(item.regime.trend_state) == trend_state_key
                and cls._enum_key(item.regime.structural_pattern) == structural_pattern_key
            )
            for horizon in horizons:
                for partition in partitions:
                    cohort = tuple(
                        item
                        for item in treatments
                        if cls._enum_key(item.legacy_direction) == legacy_key
                        and cls._enum_key(item.regime.trend_direction) == trend_direction_key
                        and cls._enum_key(item.regime.trend_state) == trend_state_key
                        and cls._enum_key(item.regime.structural_pattern) == structural_pattern_key
                        and cls._in_partition(item, partition)
                    )
                    regime_summaries.append(
                        WeeklyOppositeRegimeSummary(
                            horizon_weeks=horizon,
                            partition=partition,
                            legacy_direction=sample.legacy_direction,
                            trend_direction=sample.regime.trend_direction,
                            trend_state=sample.regime.trend_state,
                            structural_pattern=sample.regime.structural_pattern,
                            metrics=cls._metrics(cohort, horizon),
                        )
                    )

        symbol_balanced: list[WeeklyOppositeSymbolBalancedSummary] = []
        matched_summaries: list[WeeklyOppositeMatchedSummary] = []
        for horizon in horizons:
            for partition in partitions:
                for direction in legacy_directions:
                    symbol_balanced.append(
                        cls._symbol_balanced_summary(
                            treatments,
                            horizon=horizon,
                            partition=partition,
                            legacy_direction=direction,
                        )
                    )
                    matched_summaries.append(
                        cls._matched_summary(
                            pairs,
                            horizon=horizon,
                            partition=partition,
                            legacy_direction=direction,
                        )
                    )

        return WeeklyOppositeSupportedThesisAuditReport(
            symbols=tuple(sorted(reason_report.symbols)),
            horizons_weeks=horizons,
            observations=observations,
            regime_summaries=tuple(regime_summaries),
            symbol_balanced_summaries=tuple(symbol_balanced),
            matched_pairs=pairs,
            matched_summaries=tuple(matched_summaries),
            unmatched_treatments=unmatched,
        )


__all__ = [
    "WeeklyOppositeMatchedPair",
    "WeeklyOppositeMatchedSummary",
    "WeeklyOppositeMetrics",
    "WeeklyOppositeRegime",
    "WeeklyOppositeRegimeSummary",
    "WeeklyOppositeSupportedObservation",
    "WeeklyOppositeSupportedThesisAuditEngine",
    "WeeklyOppositeSupportedThesisAuditReport",
    "WeeklyOppositeSymbolBalancedSummary",
]
