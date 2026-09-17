from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum, auto
from statistics import mean, median

from models import (
    Evidence,
    EvidenceCategory,
    EvidenceCode,
    EvidenceDirection,
    StructuralPattern,
    TrendDirection,
    TrendState,
)
from scanner import ScannerEngine
from weekly_behavior import WeeklyBehaviorState, WeeklyBehaviorStateBuilder
from weekly_behavior_evolution import (
    WeeklyBehaviorEvolution,
    WeeklyBehaviorEvolutionEngine,
    WeeklyContradictionState,
)
from weekly_decision_audit import LegacyGateBlocker, WeeklyDecisionGateAuditRecord
from weekly_replay_comparison import (
    DirectionalForwardOutcome,
    WeeklyReplayBucket,
    WeeklyReplayBucketCount,
    WeeklyReplayComparisonEngine,
    WeeklyReplayComparisonRecord,
    WeeklyReplayPriceBar,
)
from weekly_thesis import ShadowWeeklyThesisState


class WeeklyEvidencePromotionCandidate(StrEnum):
    """WF6 evidence families audited independently for incremental value."""

    EFFORT_RESULT = auto()
    ABSORPTION = auto()
    LOCATION = auto()
    CAMPAIGN_CONTEXT = auto()
    PROFESSIONAL_SWING_PROGRESSION = auto()
    REJECTION_BEHAVIOR = auto()
    NAMED_VSA = auto()


class WeeklyEvidenceAuditPartition(StrEnum):
    """Optional caller-defined time split used only for robustness reporting."""

    ALL = auto()
    UNSPLIT = auto()
    IN_SAMPLE = auto()
    OUT_OF_SAMPLE = auto()


class WeeklyLocationRelation(StrEnum):
    UNAVAILABLE = auto()
    BELOW = auto()
    INSIDE = auto()
    ABOVE = auto()


class WeeklyStructuralOutcome(StrEnum):
    """First later structural event after a frozen weekly observation."""

    NEITHER = auto()
    CONFIRMED_FIRST = auto()
    INVALIDATED_FIRST = auto()
    SAME_BAR = auto()


@dataclass(frozen=True, slots=True)
class WeeklyEvidenceRegime:
    """Existing weekly regime dimensions used for descriptive stratification."""

    trend_direction: TrendDirection
    trend_state: TrendState
    structural_pattern: StructuralPattern


@dataclass(frozen=True, slots=True)
class WeeklyEvidencePromotionInput:
    """One symbol's causal weekly audit history plus completed weekly prices.

    ``out_of_sample_start_bar_index`` is intentionally caller supplied. WF6 does
    not invent a universal train/test split.
    """

    symbol: str
    audits: tuple[WeeklyDecisionGateAuditRecord, ...]
    prices: tuple[WeeklyReplayPriceBar, ...]
    out_of_sample_start_bar_index: int | None = None


@dataclass(frozen=True, slots=True)
class WeeklyEvidencePromotionObservation:
    """One frozen candidate-evidence observation on one completed weekly bar."""

    symbol: str
    week: str | None
    bar_index: int
    direction: EvidenceDirection
    candidate: WeeklyEvidencePromotionCandidate
    evidence_code: EvidenceCode | None
    eligible: bool
    present: bool
    evidence_codes: tuple[EvidenceCode, ...]

    partition: WeeklyEvidenceAuditPartition
    regime: WeeklyEvidenceRegime

    legacy_actionable: bool
    shadow_state: ShadowWeeklyThesisState
    bucket: WeeklyReplayBucket
    legacy_gate_blockers: tuple[LegacyGateBlocker, ...]
    contradiction_state: WeeklyContradictionState

    prior_aligned_evidence_count: int = 0
    location_relation: WeeklyLocationRelation = WeeklyLocationRelation.UNAVAILABLE
    location_distance_pct: float | None = None

    structural_outcome: WeeklyStructuralOutcome = WeeklyStructuralOutcome.NEITHER
    outcomes: tuple[DirectionalForwardOutcome, ...] = ()


@dataclass(frozen=True, slots=True)
class WeeklyEvidenceCohortMetrics:
    """Descriptive metrics only; no significance or promotion verdict."""

    observation_count: int
    complete_outcome_count: int

    mean_close_return_pct: float | None
    median_close_return_pct: float | None
    mean_mfe_pct: float | None
    mean_mae_pct: float | None

    structural_confirmation_first_count: int
    structural_invalidation_first_count: int
    structural_neither_count: int

    bucket_counts: tuple[WeeklyReplayBucketCount, ...]


@dataclass(frozen=True, slots=True)
class WeeklyEvidenceCandidateSummary:
    """Present-vs-absent descriptive comparison for one evidence candidate."""

    candidate: WeeklyEvidencePromotionCandidate
    evidence_code: EvidenceCode | None
    direction: EvidenceDirection
    horizon_weeks: int
    partition: WeeklyEvidenceAuditPartition
    regime: WeeklyEvidenceRegime | None

    present: WeeklyEvidenceCohortMetrics
    absent: WeeklyEvidenceCohortMetrics

    mean_close_return_delta_pct: float | None
    median_close_return_delta_pct: float | None
    mean_mfe_delta_pct: float | None
    mean_mae_delta_pct: float | None


@dataclass(frozen=True, slots=True)
class WeeklyLocationSensitivitySummary:
    """Caller-selected support/resistance proximity sensitivity result."""

    direction: EvidenceDirection
    horizon_weeks: int
    threshold_pct: float
    supportive_near_zone: WeeklyEvidenceCohortMetrics
    other_eligible_location: WeeklyEvidenceCohortMetrics

    mean_close_return_delta_pct: float | None
    mean_mfe_delta_pct: float | None
    mean_mae_delta_pct: float | None


@dataclass(frozen=True, slots=True)
class WeeklyLeaveOneSymbolOutSummary:
    """Descriptive held-out-vs-other-symbol effect comparison.

    No automatic pass/fail decision is attached. The caller can inspect whether
    a candidate's observed delta remains similar on the held-out symbol instead
    of accepting an in-sample aggregate blindly.
    """

    candidate: WeeklyEvidencePromotionCandidate
    evidence_code: EvidenceCode | None
    direction: EvidenceDirection
    horizon_weeks: int
    held_out_symbol: str

    held_out_present: WeeklyEvidenceCohortMetrics
    held_out_absent: WeeklyEvidenceCohortMetrics
    held_out_mean_close_delta_pct: float | None

    other_symbols_present: WeeklyEvidenceCohortMetrics
    other_symbols_absent: WeeklyEvidenceCohortMetrics
    other_symbols_mean_close_delta_pct: float | None


@dataclass(frozen=True, slots=True)
class WeeklyEvidencePromotionAuditReport:
    """WF6 read-only evidence-promotion audit report."""

    symbols: tuple[str, ...]
    horizons_weeks: tuple[int, ...]
    observations: tuple[WeeklyEvidencePromotionObservation, ...]
    summaries: tuple[WeeklyEvidenceCandidateSummary, ...]
    location_sensitivity: tuple[WeeklyLocationSensitivitySummary, ...]
    leave_one_symbol_out: tuple[WeeklyLeaveOneSymbolOutSummary, ...]

    @property
    def is_actionable(self) -> bool:
        return False


class WeeklyEvidencePromotionAuditEngine:
    """Audit candidate weekly evidence without changing production semantics.

    Candidate presence is frozen from the point-in-time WF1 audit record. Future
    weekly prices and later structural events are attached only after that
    observation is frozen. The engine intentionally produces descriptive cohort
    deltas rather than a promotion recommendation or score.
    """

    DEFAULT_HORIZONS = WeeklyReplayComparisonEngine.DEFAULT_HORIZONS

    _EFFORT_RESULT_CODES = frozenset(
        {
            EvidenceCode.EFFORT_GT_RESULT,
            EvidenceCode.RESULT_GT_EFFORT,
            EvidenceCode.EFFORT_RESULT,
        }
    )
    _ABSORPTION_CODES = frozenset({EvidenceCode.ABSORPTION})
    _PROGRESSION_CODES = frozenset(
        {
            EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING,
            EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING,
        }
    )
    _BULLISH_REJECTION_CODES = frozenset(
        {
            EvidenceCode.STOPPING_VOLUME,
            EvidenceCode.SELLING_CLIMAX,
            EvidenceCode.SHAKEOUT,
            EvidenceCode.SPRING,
            EvidenceCode.TEST,
        }
    )
    _BEARISH_REJECTION_CODES = frozenset(
        {
            EvidenceCode.BUYING_CLIMAX,
            EvidenceCode.UPTHRUST,
        }
    )
    _BULLISH_NAMED_VSA_CODES = frozenset(ScannerEngine._BULLISH_VSA_CODES)
    _BEARISH_NAMED_VSA_CODES = frozenset(ScannerEngine._BEARISH_VSA_CODES)

    @staticmethod
    def _normalize_inputs(
        datasets: Sequence[WeeklyEvidencePromotionInput],
        horizons_weeks: Sequence[int],
        location_distance_thresholds_pct: Sequence[float],
    ) -> tuple[
        tuple[WeeklyEvidencePromotionInput, ...],
        tuple[int, ...],
        tuple[float, ...],
    ]:
        items = tuple(datasets)
        if not items:
            raise ValueError("at least one weekly evidence-promotion dataset is required")

        horizons = tuple(sorted(set(horizons_weeks)))
        if not horizons or any(item <= 0 for item in horizons):
            raise ValueError("forward horizons must contain positive week counts")

        thresholds = tuple(sorted(set(float(item) for item in location_distance_thresholds_pct)))
        if any(item < 0.0 for item in thresholds):
            raise ValueError("location distance thresholds must be non-negative")

        seen_symbols: set[str] = set()
        for dataset in items:
            symbol = dataset.symbol.strip().upper()
            if not symbol:
                raise ValueError("dataset symbol cannot be empty")
            if symbol in seen_symbols:
                raise ValueError("weekly evidence-promotion datasets require unique symbols")
            seen_symbols.add(symbol)

            if not dataset.audits:
                raise ValueError(f"{symbol}: audit history cannot be empty")
            if len(dataset.audits) != len(dataset.prices):
                raise ValueError(f"{symbol}: audit and price histories must have equal length")
            if dataset.out_of_sample_start_bar_index is not None and dataset.out_of_sample_start_bar_index < 0:
                raise ValueError("out_of_sample_start_bar_index cannot be negative")

            previous_index: int | None = None
            for audit, price in zip(dataset.audits, dataset.prices):
                if audit.symbol != symbol:
                    raise ValueError(f"{symbol}: audit symbol does not match dataset symbol")
                if audit.bar_index is None:
                    raise ValueError(f"{symbol}: audit bar_index is required")
                if previous_index is not None and audit.bar_index <= previous_index:
                    raise ValueError(f"{symbol}: audit history must be strictly increasing")
                if price.bar_index != audit.bar_index or price.week != audit.week:
                    raise ValueError(f"{symbol}: price identity must match audit identity")
                previous_index = audit.bar_index

        return items, horizons, thresholds

    @staticmethod
    def _partition(
        bar_index: int,
        out_of_sample_start_bar_index: int | None,
    ) -> WeeklyEvidenceAuditPartition:
        if out_of_sample_start_bar_index is None:
            return WeeklyEvidenceAuditPartition.UNSPLIT
        if bar_index >= out_of_sample_start_bar_index:
            return WeeklyEvidenceAuditPartition.OUT_OF_SAMPLE
        return WeeklyEvidenceAuditPartition.IN_SAMPLE

    @staticmethod
    def _current_aligned(
        audit: WeeklyDecisionGateAuditRecord,
        direction: EvidenceDirection,
        *,
        codes: frozenset[EvidenceCode] | None = None,
        categories: frozenset[EvidenceCategory] | None = None,
    ) -> tuple[Evidence, ...]:
        assert audit.bar_index is not None
        result: list[Evidence] = []
        for item in audit.current_evidence:
            if item.bar_index != audit.bar_index or item.direction is not direction:
                continue
            if codes is not None and item.code not in codes:
                continue
            if categories is not None and item.category not in categories:
                continue
            result.append(item)
        return tuple(result)

    @classmethod
    def _effort_result_evidence(
        cls,
        audit: WeeklyDecisionGateAuditRecord,
        direction: EvidenceDirection,
    ) -> tuple[Evidence, ...]:
        assert audit.bar_index is not None
        return tuple(
            item
            for item in audit.current_evidence
            if item.bar_index == audit.bar_index
            and item.direction is direction
            and (
                item.code in cls._EFFORT_RESULT_CODES
                or item.category in {EvidenceCategory.EFFORT, EvidenceCategory.RESULT}
            )
        )

    @classmethod
    def _named_codes_for_direction(
        cls,
        direction: EvidenceDirection,
    ) -> tuple[EvidenceCode, ...]:
        if direction is EvidenceDirection.BULLISH:
            return tuple(sorted(cls._BULLISH_NAMED_VSA_CODES, key=str))
        if direction is EvidenceDirection.BEARISH:
            return tuple(sorted(cls._BEARISH_NAMED_VSA_CODES, key=str))
        return ()

    @classmethod
    def _rejection_codes_for_direction(
        cls,
        direction: EvidenceDirection,
    ) -> frozenset[EvidenceCode]:
        if direction is EvidenceDirection.BULLISH:
            return cls._BULLISH_REJECTION_CODES
        if direction is EvidenceDirection.BEARISH:
            return cls._BEARISH_REJECTION_CODES
        return frozenset()

    @staticmethod
    def _aligned_progression_code(direction: EvidenceDirection) -> EvidenceCode | None:
        if direction is EvidenceDirection.BULLISH:
            return EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING
        if direction is EvidenceDirection.BEARISH:
            return EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING
        return None

    @staticmethod
    def _location(
        audit: WeeklyDecisionGateAuditRecord,
        price: WeeklyReplayPriceBar,
        direction: EvidenceDirection,
    ) -> tuple[bool, bool, WeeklyLocationRelation, float | None]:
        zone = (
            audit.support_zone
            if direction is EvidenceDirection.BULLISH
            else audit.resistance_zone
            if direction is EvidenceDirection.BEARISH
            else None
        )
        if zone is None:
            return False, False, WeeklyLocationRelation.UNAVAILABLE, None

        close = price.close
        if close < zone.lower:
            distance = ((zone.lower - close) / close) * 100.0
            return True, False, WeeklyLocationRelation.BELOW, distance
        if close > zone.upper:
            distance = ((close - zone.upper) / close) * 100.0
            return True, False, WeeklyLocationRelation.ABOVE, distance
        return True, True, WeeklyLocationRelation.INSIDE, 0.0

    @staticmethod
    def _outcomes_for(
        prices: tuple[WeeklyReplayPriceBar, ...],
        position: int,
        direction: EvidenceDirection,
        horizons: tuple[int, ...],
    ) -> tuple[DirectionalForwardOutcome, ...]:
        """Use the same direction-adjusted outcome semantics as WF5.

        This is kept local so candidate observations can receive outcomes even
        when WF5 classifies the current shadow thesis as DEVELOPING/CHALLENGED
        and therefore does not attach a shadow-YES outcome to that row.
        """

        outcomes: list[DirectionalForwardOutcome] = []
        for horizon in horizons:
            available = min(horizon, len(prices) - position - 1)
            if available <= 0:
                outcomes.append(
                    DirectionalForwardOutcome(
                        horizon_weeks=horizon,
                        available_weeks=0,
                        complete=False,
                        direction=direction,
                        close_return_pct=None,
                        maximum_favorable_excursion_pct=None,
                        maximum_adverse_excursion_pct=None,
                    )
                )
                continue

            entry = prices[position].close
            future = prices[position + 1 : position + 1 + available]
            end_close = future[-1].close
            future_high = max(item.high for item in future)
            future_low = min(item.low for item in future)

            if direction is EvidenceDirection.BULLISH:
                close_return = ((end_close - entry) / entry) * 100.0
                favorable = max(0.0, ((future_high - entry) / entry) * 100.0)
                adverse = min(0.0, ((future_low - entry) / entry) * 100.0)
            else:
                close_return = ((entry - end_close) / entry) * 100.0
                favorable = max(0.0, ((entry - future_low) / entry) * 100.0)
                adverse = min(0.0, ((entry - future_high) / entry) * 100.0)

            outcomes.append(
                DirectionalForwardOutcome(
                    horizon_weeks=horizon,
                    available_weeks=available,
                    complete=available == horizon,
                    direction=direction,
                    close_return_pct=close_return,
                    maximum_favorable_excursion_pct=favorable,
                    maximum_adverse_excursion_pct=adverse,
                )
            )
        return tuple(outcomes)

    @classmethod
    def _first_structural_outcome(
        cls,
        audits: tuple[WeeklyDecisionGateAuditRecord, ...],
        evolutions: tuple[WeeklyBehaviorEvolution, ...],
        position: int,
        direction: EvidenceDirection,
    ) -> WeeklyStructuralOutcome:
        wanted = cls._aligned_progression_code(direction)
        confirmation_position: int | None = None
        invalidation_position: int | None = None

        if wanted is not None:
            for future_position, audit in enumerate(audits[position + 1 :], start=position + 1):
                assert audit.bar_index is not None
                if any(
                    item.code is wanted
                    and item.direction is direction
                    and item.bar_index == audit.bar_index
                    for item in audit.structural_progression_events
                ):
                    confirmation_position = future_position
                    break

        for future_position, evolution in enumerate(evolutions[position + 1 :], start=position + 1):
            if (
                evolution.reference_direction is direction
                and evolution.contradiction_state
                is WeeklyContradictionState.STRUCTURAL_INVALIDATION_EVIDENCE
            ):
                invalidation_position = future_position
                break

        if confirmation_position is None and invalidation_position is None:
            return WeeklyStructuralOutcome.NEITHER
        if invalidation_position is None:
            return WeeklyStructuralOutcome.CONFIRMED_FIRST
        if confirmation_position is None:
            return WeeklyStructuralOutcome.INVALIDATED_FIRST
        if confirmation_position < invalidation_position:
            return WeeklyStructuralOutcome.CONFIRMED_FIRST
        if invalidation_position < confirmation_position:
            return WeeklyStructuralOutcome.INVALIDATED_FIRST
        return WeeklyStructuralOutcome.SAME_BAR

    @classmethod
    def _base_observation(
        cls,
        *,
        audit: WeeklyDecisionGateAuditRecord,
        price: WeeklyReplayPriceBar,
        replay_record: WeeklyReplayComparisonRecord,
        evolution: WeeklyBehaviorEvolution,
        direction: EvidenceDirection,
        candidate: WeeklyEvidencePromotionCandidate,
        evidence_code: EvidenceCode | None,
        evidence: tuple[Evidence, ...],
        eligible: bool,
        present: bool,
        partition: WeeklyEvidenceAuditPartition,
        prior_aligned_evidence_count: int,
        structural_outcome: WeeklyStructuralOutcome,
        outcomes: tuple[DirectionalForwardOutcome, ...],
        location_relation: WeeklyLocationRelation = WeeklyLocationRelation.UNAVAILABLE,
        location_distance_pct: float | None = None,
    ) -> WeeklyEvidencePromotionObservation:
        assert audit.bar_index is not None
        return WeeklyEvidencePromotionObservation(
            symbol=audit.symbol,
            week=audit.week,
            bar_index=audit.bar_index,
            direction=direction,
            candidate=candidate,
            evidence_code=evidence_code,
            eligible=eligible,
            present=present,
            evidence_codes=tuple(item.code for item in evidence),
            partition=partition,
            regime=WeeklyEvidenceRegime(
                trend_direction=audit.trend_direction,
                trend_state=audit.trend_state,
                structural_pattern=audit.structural_pattern,
            ),
            legacy_actionable=replay_record.legacy_actionable,
            shadow_state=replay_record.shadow_state,
            bucket=replay_record.bucket,
            legacy_gate_blockers=replay_record.legacy_gate_blockers,
            contradiction_state=evolution.contradiction_state,
            prior_aligned_evidence_count=prior_aligned_evidence_count,
            location_relation=location_relation,
            location_distance_pct=location_distance_pct,
            structural_outcome=structural_outcome,
            outcomes=outcomes,
        )

    @classmethod
    def _observations_for_dataset(
        cls,
        dataset: WeeklyEvidencePromotionInput,
        horizons: tuple[int, ...],
    ) -> tuple[WeeklyEvidencePromotionObservation, ...]:
        audits = tuple(dataset.audits)
        prices = tuple(dataset.prices)
        replay = WeeklyReplayComparisonEngine.compare(
            audits=audits,
            prices=prices,
            horizons_weeks=horizons,
        )

        behaviors: list[WeeklyBehaviorState] = []
        evolutions: list[WeeklyBehaviorEvolution] = []
        for audit in audits:
            behavior = WeeklyBehaviorStateBuilder.from_audit(audit)
            behaviors.append(behavior)
            evolutions.append(WeeklyBehaviorEvolutionEngine.evaluate(behaviors))

        evolution_history = tuple(evolutions)
        replay_by_index = {item.bar_index: item for item in replay.records}
        observations: list[WeeklyEvidencePromotionObservation] = []

        for position, (audit, price, behavior, evolution) in enumerate(
            zip(audits, prices, behaviors, evolution_history)
        ):
            assert audit.bar_index is not None
            direction = evolution.reference_direction
            if direction is EvidenceDirection.NEUTRAL:
                continue

            replay_record = replay_by_index[audit.bar_index]
            partition = cls._partition(
                audit.bar_index,
                dataset.out_of_sample_start_bar_index,
            )
            outcomes = cls._outcomes_for(prices, position, direction, horizons)
            structural_outcome = cls._first_structural_outcome(
                audits,
                evolution_history,
                position,
                direction,
            )
            prior_aligned = tuple(
                item
                for item in behavior.recent_evidence
                if item.bar_index < audit.bar_index and item.direction is direction
            )

            effort = cls._effort_result_evidence(audit, direction)
            observations.append(
                cls._base_observation(
                    audit=audit,
                    price=price,
                    replay_record=replay_record,
                    evolution=evolution,
                    direction=direction,
                    candidate=WeeklyEvidencePromotionCandidate.EFFORT_RESULT,
                    evidence_code=None,
                    evidence=effort,
                    eligible=True,
                    present=bool(effort),
                    partition=partition,
                    prior_aligned_evidence_count=len(prior_aligned),
                    structural_outcome=structural_outcome,
                    outcomes=outcomes,
                )
            )

            absorption = cls._current_aligned(
                audit,
                direction,
                codes=cls._ABSORPTION_CODES,
            )
            observations.append(
                cls._base_observation(
                    audit=audit,
                    price=price,
                    replay_record=replay_record,
                    evolution=evolution,
                    direction=direction,
                    candidate=WeeklyEvidencePromotionCandidate.ABSORPTION,
                    evidence_code=None,
                    evidence=absorption,
                    eligible=True,
                    present=bool(absorption),
                    partition=partition,
                    prior_aligned_evidence_count=len(prior_aligned),
                    structural_outcome=structural_outcome,
                    outcomes=outcomes,
                )
            )

            location_eligible, inside_zone, relation, distance = cls._location(
                audit,
                price,
                direction,
            )
            observations.append(
                cls._base_observation(
                    audit=audit,
                    price=price,
                    replay_record=replay_record,
                    evolution=evolution,
                    direction=direction,
                    candidate=WeeklyEvidencePromotionCandidate.LOCATION,
                    evidence_code=None,
                    evidence=(),
                    eligible=location_eligible,
                    present=inside_zone,
                    partition=partition,
                    prior_aligned_evidence_count=len(prior_aligned),
                    structural_outcome=structural_outcome,
                    outcomes=outcomes,
                    location_relation=relation,
                    location_distance_pct=distance,
                )
            )

            observations.append(
                cls._base_observation(
                    audit=audit,
                    price=price,
                    replay_record=replay_record,
                    evolution=evolution,
                    direction=direction,
                    candidate=WeeklyEvidencePromotionCandidate.CAMPAIGN_CONTEXT,
                    evidence_code=None,
                    evidence=prior_aligned,
                    eligible=True,
                    present=bool(prior_aligned),
                    partition=partition,
                    prior_aligned_evidence_count=len(prior_aligned),
                    structural_outcome=structural_outcome,
                    outcomes=outcomes,
                )
            )

            wanted_progression = cls._aligned_progression_code(direction)
            progression = (
                cls._current_aligned(
                    audit,
                    direction,
                    codes=frozenset({wanted_progression}),
                )
                if wanted_progression is not None
                else ()
            )
            observations.append(
                cls._base_observation(
                    audit=audit,
                    price=price,
                    replay_record=replay_record,
                    evolution=evolution,
                    direction=direction,
                    candidate=WeeklyEvidencePromotionCandidate.PROFESSIONAL_SWING_PROGRESSION,
                    evidence_code=wanted_progression,
                    evidence=progression,
                    eligible=True,
                    present=bool(progression),
                    partition=partition,
                    prior_aligned_evidence_count=len(prior_aligned),
                    structural_outcome=structural_outcome,
                    outcomes=outcomes,
                )
            )

            rejection_codes = cls._rejection_codes_for_direction(direction)
            rejection = cls._current_aligned(
                audit,
                direction,
                codes=rejection_codes,
            )
            observations.append(
                cls._base_observation(
                    audit=audit,
                    price=price,
                    replay_record=replay_record,
                    evolution=evolution,
                    direction=direction,
                    candidate=WeeklyEvidencePromotionCandidate.REJECTION_BEHAVIOR,
                    evidence_code=None,
                    evidence=rejection,
                    eligible=True,
                    present=bool(rejection),
                    partition=partition,
                    prior_aligned_evidence_count=len(prior_aligned),
                    structural_outcome=structural_outcome,
                    outcomes=outcomes,
                )
            )

            for named_code in cls._named_codes_for_direction(direction):
                named = cls._current_aligned(
                    audit,
                    direction,
                    codes=frozenset({named_code}),
                )
                observations.append(
                    cls._base_observation(
                        audit=audit,
                        price=price,
                        replay_record=replay_record,
                        evolution=evolution,
                        direction=direction,
                        candidate=WeeklyEvidencePromotionCandidate.NAMED_VSA,
                        evidence_code=named_code,
                        evidence=named,
                        eligible=True,
                        present=bool(named),
                        partition=partition,
                        prior_aligned_evidence_count=len(prior_aligned),
                        structural_outcome=structural_outcome,
                        outcomes=outcomes,
                    )
                )

        return tuple(observations)

    @staticmethod
    def _outcome_for_horizon(
        observation: WeeklyEvidencePromotionObservation,
        horizon: int,
    ) -> DirectionalForwardOutcome | None:
        return next(
            (item for item in observation.outcomes if item.horizon_weeks == horizon),
            None,
        )

    @classmethod
    def _cohort_metrics(
        cls,
        observations: Sequence[WeeklyEvidencePromotionObservation],
        horizon: int,
    ) -> WeeklyEvidenceCohortMetrics:
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

        bucket_counts = tuple(
            WeeklyReplayBucketCount(
                bucket=bucket,
                count=sum(item.bucket is bucket for item in items),
            )
            for bucket in WeeklyReplayBucket
        )

        return WeeklyEvidenceCohortMetrics(
            observation_count=len(items),
            complete_outcome_count=len(complete),
            mean_close_return_pct=mean(close_values) if close_values else None,
            median_close_return_pct=median(close_values) if close_values else None,
            mean_mfe_pct=mean(mfe_values) if mfe_values else None,
            mean_mae_pct=mean(mae_values) if mae_values else None,
            structural_confirmation_first_count=sum(
                item.structural_outcome is WeeklyStructuralOutcome.CONFIRMED_FIRST
                for item in items
            ),
            structural_invalidation_first_count=sum(
                item.structural_outcome is WeeklyStructuralOutcome.INVALIDATED_FIRST
                for item in items
            ),
            structural_neither_count=sum(
                item.structural_outcome is WeeklyStructuralOutcome.NEITHER
                for item in items
            ),
            bucket_counts=bucket_counts,
        )

    @staticmethod
    def _delta(left: float | None, right: float | None) -> float | None:
        if left is None or right is None:
            return None
        return left - right

    @classmethod
    def _candidate_summary(
        cls,
        *,
        observations: Sequence[WeeklyEvidencePromotionObservation],
        candidate: WeeklyEvidencePromotionCandidate,
        evidence_code: EvidenceCode | None,
        direction: EvidenceDirection,
        horizon: int,
        partition: WeeklyEvidenceAuditPartition,
        regime: WeeklyEvidenceRegime | None,
    ) -> WeeklyEvidenceCandidateSummary:
        eligible = tuple(
            item
            for item in observations
            if item.eligible
            and item.candidate is candidate
            and item.evidence_code is evidence_code
            and item.direction is direction
            and (
                partition is WeeklyEvidenceAuditPartition.ALL
                or item.partition is partition
            )
            and (regime is None or item.regime == regime)
        )
        present_items = tuple(item for item in eligible if item.present)
        absent_items = tuple(item for item in eligible if not item.present)
        present = cls._cohort_metrics(present_items, horizon)
        absent = cls._cohort_metrics(absent_items, horizon)
        return WeeklyEvidenceCandidateSummary(
            candidate=candidate,
            evidence_code=evidence_code,
            direction=direction,
            horizon_weeks=horizon,
            partition=partition,
            regime=regime,
            present=present,
            absent=absent,
            mean_close_return_delta_pct=cls._delta(
                present.mean_close_return_pct,
                absent.mean_close_return_pct,
            ),
            median_close_return_delta_pct=cls._delta(
                present.median_close_return_pct,
                absent.median_close_return_pct,
            ),
            mean_mfe_delta_pct=cls._delta(present.mean_mfe_pct, absent.mean_mfe_pct),
            mean_mae_delta_pct=cls._delta(present.mean_mae_pct, absent.mean_mae_pct),
        )

    @classmethod
    def _summaries(
        cls,
        observations: tuple[WeeklyEvidencePromotionObservation, ...],
        horizons: tuple[int, ...],
    ) -> tuple[WeeklyEvidenceCandidateSummary, ...]:
        keys = sorted(
            {
                (item.candidate, item.evidence_code, item.direction)
                for item in observations
                if item.eligible
            },
            key=lambda item: (str(item[0]), str(item[1]), int(item[2])),
        )
        partitions = [WeeklyEvidenceAuditPartition.ALL]
        for partition in (
            WeeklyEvidenceAuditPartition.UNSPLIT,
            WeeklyEvidenceAuditPartition.IN_SAMPLE,
            WeeklyEvidenceAuditPartition.OUT_OF_SAMPLE,
        ):
            if any(item.partition is partition for item in observations):
                partitions.append(partition)

        result: list[WeeklyEvidenceCandidateSummary] = []
        for candidate, evidence_code, direction in keys:
            regimes = sorted(
                {
                    item.regime
                    for item in observations
                    if item.eligible
                    and item.candidate is candidate
                    and item.evidence_code is evidence_code
                    and item.direction is direction
                },
                key=lambda regime: (
                    str(regime.trend_direction),
                    str(regime.trend_state),
                    int(regime.structural_pattern),
                ),
            )
            for horizon in horizons:
                for partition in partitions:
                    result.append(
                        cls._candidate_summary(
                            observations=observations,
                            candidate=candidate,
                            evidence_code=evidence_code,
                            direction=direction,
                            horizon=horizon,
                            partition=partition,
                            regime=None,
                        )
                    )
                    for regime in regimes:
                        result.append(
                            cls._candidate_summary(
                                observations=observations,
                                candidate=candidate,
                                evidence_code=evidence_code,
                                direction=direction,
                                horizon=horizon,
                                partition=partition,
                                regime=regime,
                            )
                        )
        return tuple(result)

    @staticmethod
    def _supportive_location_at_threshold(
        observation: WeeklyEvidencePromotionObservation,
        threshold_pct: float,
    ) -> bool:
        if (
            not observation.eligible
            or observation.candidate is not WeeklyEvidencePromotionCandidate.LOCATION
            or observation.location_distance_pct is None
        ):
            return False
        if observation.location_relation is WeeklyLocationRelation.INSIDE:
            return True
        if observation.location_distance_pct > threshold_pct:
            return False
        if observation.direction is EvidenceDirection.BULLISH:
            return observation.location_relation is WeeklyLocationRelation.ABOVE
        if observation.direction is EvidenceDirection.BEARISH:
            return observation.location_relation is WeeklyLocationRelation.BELOW
        return False

    @classmethod
    def _location_sensitivity(
        cls,
        observations: tuple[WeeklyEvidencePromotionObservation, ...],
        horizons: tuple[int, ...],
        thresholds: tuple[float, ...],
    ) -> tuple[WeeklyLocationSensitivitySummary, ...]:
        if not thresholds:
            return ()

        location = tuple(
            item
            for item in observations
            if item.candidate is WeeklyEvidencePromotionCandidate.LOCATION and item.eligible
        )
        result: list[WeeklyLocationSensitivitySummary] = []
        for direction in (EvidenceDirection.BULLISH, EvidenceDirection.BEARISH):
            directional = tuple(item for item in location if item.direction is direction)
            for horizon in horizons:
                for threshold in thresholds:
                    near = tuple(
                        item
                        for item in directional
                        if cls._supportive_location_at_threshold(item, threshold)
                    )
                    other = tuple(item for item in directional if item not in near)
                    near_metrics = cls._cohort_metrics(near, horizon)
                    other_metrics = cls._cohort_metrics(other, horizon)
                    result.append(
                        WeeklyLocationSensitivitySummary(
                            direction=direction,
                            horizon_weeks=horizon,
                            threshold_pct=threshold,
                            supportive_near_zone=near_metrics,
                            other_eligible_location=other_metrics,
                            mean_close_return_delta_pct=cls._delta(
                                near_metrics.mean_close_return_pct,
                                other_metrics.mean_close_return_pct,
                            ),
                            mean_mfe_delta_pct=cls._delta(
                                near_metrics.mean_mfe_pct,
                                other_metrics.mean_mfe_pct,
                            ),
                            mean_mae_delta_pct=cls._delta(
                                near_metrics.mean_mae_pct,
                                other_metrics.mean_mae_pct,
                            ),
                        )
                    )
        return tuple(result)

    @classmethod
    def _leave_one_symbol_out(
        cls,
        observations: tuple[WeeklyEvidencePromotionObservation, ...],
        horizons: tuple[int, ...],
    ) -> tuple[WeeklyLeaveOneSymbolOutSummary, ...]:
        symbols = tuple(sorted({item.symbol for item in observations}))
        if len(symbols) < 2:
            return ()

        keys = sorted(
            {
                (item.candidate, item.evidence_code, item.direction)
                for item in observations
                if item.eligible
            },
            key=lambda item: (str(item[0]), str(item[1]), int(item[2])),
        )
        result: list[WeeklyLeaveOneSymbolOutSummary] = []
        for candidate, evidence_code, direction in keys:
            candidate_items = tuple(
                item
                for item in observations
                if item.eligible
                and item.candidate is candidate
                and item.evidence_code is evidence_code
                and item.direction is direction
            )
            for horizon in horizons:
                for held_out_symbol in symbols:
                    held_out = tuple(
                        item for item in candidate_items if item.symbol == held_out_symbol
                    )
                    others = tuple(
                        item for item in candidate_items if item.symbol != held_out_symbol
                    )
                    if not held_out or not others:
                        continue

                    held_present = cls._cohort_metrics(
                        tuple(item for item in held_out if item.present),
                        horizon,
                    )
                    held_absent = cls._cohort_metrics(
                        tuple(item for item in held_out if not item.present),
                        horizon,
                    )
                    other_present = cls._cohort_metrics(
                        tuple(item for item in others if item.present),
                        horizon,
                    )
                    other_absent = cls._cohort_metrics(
                        tuple(item for item in others if not item.present),
                        horizon,
                    )
                    result.append(
                        WeeklyLeaveOneSymbolOutSummary(
                            candidate=candidate,
                            evidence_code=evidence_code,
                            direction=direction,
                            horizon_weeks=horizon,
                            held_out_symbol=held_out_symbol,
                            held_out_present=held_present,
                            held_out_absent=held_absent,
                            held_out_mean_close_delta_pct=cls._delta(
                                held_present.mean_close_return_pct,
                                held_absent.mean_close_return_pct,
                            ),
                            other_symbols_present=other_present,
                            other_symbols_absent=other_absent,
                            other_symbols_mean_close_delta_pct=cls._delta(
                                other_present.mean_close_return_pct,
                                other_absent.mean_close_return_pct,
                            ),
                        )
                    )
        return tuple(result)

    @classmethod
    def audit(
        cls,
        *,
        datasets: Sequence[WeeklyEvidencePromotionInput],
        horizons_weeks: Sequence[int] = DEFAULT_HORIZONS,
        location_distance_thresholds_pct: Sequence[float] = (),
    ) -> WeeklyEvidencePromotionAuditReport:
        items, horizons, thresholds = cls._normalize_inputs(
            datasets,
            horizons_weeks,
            location_distance_thresholds_pct,
        )

        observations = tuple(
            observation
            for dataset in items
            for observation in cls._observations_for_dataset(dataset, horizons)
        )

        return WeeklyEvidencePromotionAuditReport(
            symbols=tuple(sorted(dataset.symbol.strip().upper() for dataset in items)),
            horizons_weeks=horizons,
            observations=observations,
            summaries=cls._summaries(observations, horizons),
            location_sensitivity=cls._location_sensitivity(
                observations,
                horizons,
                thresholds,
            ),
            leave_one_symbol_out=cls._leave_one_symbol_out(observations, horizons),
        )


__all__ = [
    "WeeklyEvidenceAuditPartition",
    "WeeklyEvidenceCandidateSummary",
    "WeeklyEvidenceCohortMetrics",
    "WeeklyEvidencePromotionAuditEngine",
    "WeeklyEvidencePromotionAuditReport",
    "WeeklyEvidencePromotionCandidate",
    "WeeklyEvidencePromotionInput",
    "WeeklyEvidencePromotionObservation",
    "WeeklyEvidenceRegime",
    "WeeklyLeaveOneSymbolOutSummary",
    "WeeklyLocationRelation",
    "WeeklyLocationSensitivitySummary",
    "WeeklyStructuralOutcome",
]
