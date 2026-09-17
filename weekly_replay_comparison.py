from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum, auto
from math import isfinite

from background.qualification import PatternQualification
from models import EvidenceCode, EvidenceDirection
from weekly_behavior import WeeklyBehaviorState, WeeklyBehaviorStateBuilder
from weekly_behavior_evolution import (
    WeeklyBehaviorEvolution,
    WeeklyBehaviorEvolutionEngine,
    WeeklyContradictionState,
)
from weekly_decision_audit import LegacyGateBlocker, WeeklyDecisionGateAuditRecord
from weekly_thesis import (
    ShadowWeeklyThesis,
    ShadowWeeklyThesisBasis,
    ShadowWeeklyThesisBuilder,
    ShadowWeeklyThesisState,
)


class WeeklyReplayBucket(StrEnum):
    """WF5 legacy-vs-shadow comparison buckets."""

    LEGACY_YES_SHADOW_YES = auto()
    LEGACY_YES_SHADOW_NO = auto()
    LEGACY_NO_SHADOW_YES = auto()
    LEGACY_NO_SHADOW_NO = auto()


class WeeklyDirectionAgreement(StrEnum):
    """Directional relationship between comparable legacy/shadow decisions."""

    SAME = auto()
    OPPOSITE = auto()
    LEGACY_ONLY = auto()
    SHADOW_ONLY = auto()
    NEITHER = auto()


@dataclass(frozen=True, slots=True)
class WeeklyReplayPriceBar:
    """Minimal completed weekly price bar used only for outcome audit."""

    week: str | None
    bar_index: int
    high: float
    low: float
    close: float

    def __post_init__(self) -> None:
        if self.bar_index < 0:
            raise ValueError("bar_index cannot be negative")
        for name, value in {
            "high": self.high,
            "low": self.low,
            "close": self.close,
        }.items():
            if not isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be finite and positive")
        if self.high < self.low:
            raise ValueError("high must be >= low")
        if not self.low <= self.close <= self.high:
            raise ValueError("close must be within the weekly high/low range")


@dataclass(frozen=True, slots=True)
class DirectionalForwardOutcome:
    """Direction-adjusted forward result measured after a frozen decision."""

    horizon_weeks: int
    available_weeks: int
    complete: bool
    direction: EvidenceDirection
    close_return_pct: float | None
    maximum_favorable_excursion_pct: float | None
    maximum_adverse_excursion_pct: float | None


@dataclass(frozen=True, slots=True)
class DirectionalTimingSummary:
    """First observable milestones for one direction inside a replay window."""

    direction: EvidenceDirection

    first_opposing_pressure_reduction_week: str | None = None
    first_opposing_pressure_reduction_bar_index: int | None = None

    first_aligned_pressure_emergence_week: str | None = None
    first_aligned_pressure_emergence_bar_index: int | None = None

    first_supportive_effort_result_week: str | None = None
    first_supportive_effort_result_bar_index: int | None = None

    first_absorption_or_rejection_week: str | None = None
    first_absorption_or_rejection_bar_index: int | None = None

    first_structural_progression_week: str | None = None
    first_structural_progression_bar_index: int | None = None
    second_structural_progression_week: str | None = None
    second_structural_progression_bar_index: int | None = None
    third_structural_progression_week: str | None = None
    third_structural_progression_bar_index: int | None = None

    first_legacy_qualification_week: str | None = None
    first_legacy_qualification_bar_index: int | None = None
    first_legacy_actionable_week: str | None = None
    first_legacy_actionable_bar_index: int | None = None

    first_shadow_supported_week: str | None = None
    first_shadow_supported_bar_index: int | None = None

    shadow_supported_minus_legacy_actionable_weeks: int | None = None


@dataclass(frozen=True, slots=True)
class WeeklyReplayBucketCount:
    bucket: WeeklyReplayBucket
    count: int


@dataclass(frozen=True, slots=True)
class WeeklyReplayComparisonRecord:
    """One point-in-time legacy-vs-shadow comparison row."""

    symbol: str
    week: str | None
    bar_index: int

    legacy_qualification: PatternQualification
    legacy_actionable: bool
    legacy_direction: EvidenceDirection
    legacy_gate_blockers: tuple[LegacyGateBlocker, ...]

    shadow_state: ShadowWeeklyThesisState
    shadow_basis: ShadowWeeklyThesisBasis
    shadow_direction: EvidenceDirection
    shadow_supported: bool
    contradiction_state: WeeklyContradictionState

    bucket: WeeklyReplayBucket
    direction_agreement: WeeklyDirectionAgreement

    legacy_forward_outcomes: tuple[DirectionalForwardOutcome, ...] = ()
    shadow_forward_outcomes: tuple[DirectionalForwardOutcome, ...] = ()

    legacy_first_structural_confirmation_week: str | None = None
    legacy_first_structural_confirmation_bar_index: int | None = None
    legacy_first_structural_invalidation_week: str | None = None
    legacy_first_structural_invalidation_bar_index: int | None = None

    shadow_first_structural_confirmation_week: str | None = None
    shadow_first_structural_confirmation_bar_index: int | None = None
    shadow_first_structural_invalidation_week: str | None = None
    shadow_first_structural_invalidation_bar_index: int | None = None


@dataclass(frozen=True, slots=True)
class WeeklyReplayComparisonReport:
    """Immutable WF5 replay report. It has no production authority."""

    symbol: str
    horizons_weeks: tuple[int, ...]
    records: tuple[WeeklyReplayComparisonRecord, ...]
    bucket_counts: tuple[WeeklyReplayBucketCount, ...]
    timing: tuple[DirectionalTimingSummary, ...]

    @property
    def is_actionable(self) -> bool:
        return False


class WeeklyReplayComparisonEngine:
    """Build a causal legacy-vs-shadow weekly replay comparison.

    Decisions are built only from the audit prefix available at each completed
    weekly bar. Forward prices and later structural observations are attached
    only after those decision states have been frozen; they never feed back into
    WF2/WF3/WF4 state construction.
    """

    DEFAULT_HORIZONS = (5, 10, 15)

    _SHADOW_SUPPORTED_STATES = frozenset(
        {
            ShadowWeeklyThesisState.BULLISH_SUPPORTED,
            ShadowWeeklyThesisState.BEARISH_SUPPORTED,
        }
    )

    _BULLISH_PRESSURE_REDUCTION_CODES = frozenset(
        {
            EvidenceCode.SUPPLY_DRYING_UP,
            EvidenceCode.NO_SUPPLY,
        }
    )
    _BEARISH_PRESSURE_REDUCTION_CODES = frozenset(
        {
            EvidenceCode.DEMAND_DRYING_UP,
            EvidenceCode.NO_DEMAND,
        }
    )

    _BULLISH_ALIGNED_EMERGENCE_CODES = frozenset(
        {
            EvidenceCode.DEMAND_COMING_IN,
            EvidenceCode.INCREASING_DEMAND,
            EvidenceCode.HIDDEN_DEMAND,
        }
    )
    _BEARISH_ALIGNED_EMERGENCE_CODES = frozenset(
        {
            EvidenceCode.SUPPLY_COMING_IN,
            EvidenceCode.INCREASING_SUPPLY,
            EvidenceCode.HIDDEN_SUPPLY,
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

    @staticmethod
    def _opposite(direction: EvidenceDirection) -> EvidenceDirection:
        if direction is EvidenceDirection.BULLISH:
            return EvidenceDirection.BEARISH
        if direction is EvidenceDirection.BEARISH:
            return EvidenceDirection.BULLISH
        return EvidenceDirection.NEUTRAL

    @staticmethod
    def _legacy_direction(
        qualification: PatternQualification,
    ) -> EvidenceDirection:
        if qualification is PatternQualification.PERSISTENT_BULLISH:
            return EvidenceDirection.BULLISH
        if qualification is PatternQualification.PERSISTENT_BEARISH:
            return EvidenceDirection.BEARISH
        return EvidenceDirection.NEUTRAL

    @classmethod
    def _bucket(
        cls,
        *,
        legacy_yes: bool,
        shadow_yes: bool,
    ) -> WeeklyReplayBucket:
        if legacy_yes and shadow_yes:
            return WeeklyReplayBucket.LEGACY_YES_SHADOW_YES
        if legacy_yes:
            return WeeklyReplayBucket.LEGACY_YES_SHADOW_NO
        if shadow_yes:
            return WeeklyReplayBucket.LEGACY_NO_SHADOW_YES
        return WeeklyReplayBucket.LEGACY_NO_SHADOW_NO

    @staticmethod
    def _direction_agreement(
        *,
        legacy_yes: bool,
        legacy_direction: EvidenceDirection,
        shadow_yes: bool,
        shadow_direction: EvidenceDirection,
    ) -> WeeklyDirectionAgreement:
        if legacy_yes and shadow_yes:
            if legacy_direction is shadow_direction:
                return WeeklyDirectionAgreement.SAME
            return WeeklyDirectionAgreement.OPPOSITE
        if legacy_yes:
            return WeeklyDirectionAgreement.LEGACY_ONLY
        if shadow_yes:
            return WeeklyDirectionAgreement.SHADOW_ONLY
        return WeeklyDirectionAgreement.NEITHER

    @classmethod
    def _validate(
        cls,
        audits: Sequence[WeeklyDecisionGateAuditRecord],
        prices: Sequence[WeeklyReplayPriceBar],
        horizons_weeks: Sequence[int],
    ) -> tuple[
        tuple[WeeklyDecisionGateAuditRecord, ...],
        tuple[WeeklyReplayPriceBar, ...],
        tuple[int, ...],
    ]:
        audit_history = tuple(audits)
        price_history = tuple(prices)
        if not audit_history:
            raise ValueError("at least one weekly audit record is required")
        if len(audit_history) != len(price_history):
            raise ValueError("weekly audit and price histories must have equal length")

        normalized_horizons = tuple(sorted(set(horizons_weeks)))
        if not normalized_horizons or any(item <= 0 for item in normalized_horizons):
            raise ValueError("forward horizons must contain positive week counts")

        symbol = audit_history[0].symbol
        previous_index: int | None = None
        for audit, price in zip(audit_history, price_history):
            if audit.symbol != symbol:
                raise ValueError("all weekly audit records must have the same symbol")
            if audit.bar_index is None:
                raise ValueError("weekly replay comparison requires audit bar_index")
            if previous_index is not None and audit.bar_index <= previous_index:
                raise ValueError("weekly audit records must be strictly increasing")
            if price.bar_index != audit.bar_index or price.week != audit.week:
                raise ValueError("weekly price identity must match audit identity")
            previous_index = audit.bar_index

        return audit_history, price_history, normalized_horizons

    @staticmethod
    def _forward_outcome(
        prices: tuple[WeeklyReplayPriceBar, ...],
        position: int,
        direction: EvidenceDirection,
        horizon: int,
    ) -> DirectionalForwardOutcome:
        available = min(horizon, len(prices) - position - 1)
        if direction is EvidenceDirection.NEUTRAL or available <= 0:
            return DirectionalForwardOutcome(
                horizon_weeks=horizon,
                available_weeks=max(0, available),
                complete=False,
                direction=direction,
                close_return_pct=None,
                maximum_favorable_excursion_pct=None,
                maximum_adverse_excursion_pct=None,
            )

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

        return DirectionalForwardOutcome(
            horizon_weeks=horizon,
            available_weeks=available,
            complete=available == horizon,
            direction=direction,
            close_return_pct=close_return,
            maximum_favorable_excursion_pct=favorable,
            maximum_adverse_excursion_pct=adverse,
        )

    @classmethod
    def _outcomes_for(
        cls,
        prices: tuple[WeeklyReplayPriceBar, ...],
        position: int,
        direction: EvidenceDirection,
        horizons: tuple[int, ...],
    ) -> tuple[DirectionalForwardOutcome, ...]:
        if direction is EvidenceDirection.NEUTRAL:
            return ()
        return tuple(
            cls._forward_outcome(prices, position, direction, horizon)
            for horizon in horizons
        )

    @staticmethod
    def _aligned_progression_code(direction: EvidenceDirection) -> EvidenceCode | None:
        if direction is EvidenceDirection.BULLISH:
            return EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING
        if direction is EvidenceDirection.BEARISH:
            return EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING
        return None

    @classmethod
    def _first_future_structural_confirmation(
        cls,
        audits: tuple[WeeklyDecisionGateAuditRecord, ...],
        position: int,
        direction: EvidenceDirection,
    ) -> tuple[str | None, int | None]:
        wanted = cls._aligned_progression_code(direction)
        if wanted is None:
            return None, None
        for audit in audits[position + 1 :]:
            assert audit.bar_index is not None
            if any(
                item.code is wanted
                and item.direction is direction
                and item.bar_index == audit.bar_index
                for item in audit.structural_progression_events
            ):
                return audit.week, audit.bar_index
        return None, None

    @staticmethod
    def _first_future_structural_invalidation(
        evolutions: tuple[WeeklyBehaviorEvolution, ...],
        position: int,
        direction: EvidenceDirection,
    ) -> tuple[str | None, int | None]:
        if direction is EvidenceDirection.NEUTRAL:
            return None, None
        for evolution in evolutions[position + 1 :]:
            if (
                evolution.reference_direction is direction
                and evolution.contradiction_state
                is WeeklyContradictionState.STRUCTURAL_INVALIDATION_EVIDENCE
            ):
                return evolution.week, evolution.bar_index
        return None, None

    @classmethod
    def _timing_summary(
        cls,
        audits: tuple[WeeklyDecisionGateAuditRecord, ...],
        theses: tuple[ShadowWeeklyThesis, ...],
        direction: EvidenceDirection,
    ) -> DirectionalTimingSummary:
        if direction is EvidenceDirection.BULLISH:
            pressure_codes = cls._BULLISH_PRESSURE_REDUCTION_CODES
            emergence_codes = cls._BULLISH_ALIGNED_EMERGENCE_CODES
            rejection_codes = cls._BULLISH_REJECTION_CODES
            legacy_qualification = PatternQualification.PERSISTENT_BULLISH
            supported_state = ShadowWeeklyThesisState.BULLISH_SUPPORTED
        elif direction is EvidenceDirection.BEARISH:
            pressure_codes = cls._BEARISH_PRESSURE_REDUCTION_CODES
            emergence_codes = cls._BEARISH_ALIGNED_EMERGENCE_CODES
            rejection_codes = cls._BEARISH_REJECTION_CODES
            legacy_qualification = PatternQualification.PERSISTENT_BEARISH
            supported_state = ShadowWeeklyThesisState.BEARISH_SUPPORTED
        else:
            raise ValueError("timing summary requires bullish or bearish direction")

        def first_current_code(codes: frozenset[EvidenceCode]) -> tuple[str | None, int | None, int | None]:
            for position, audit in enumerate(audits):
                assert audit.bar_index is not None
                if any(
                    item.code in codes and item.bar_index == audit.bar_index
                    for item in audit.current_evidence
                ):
                    return audit.week, audit.bar_index, position
            return None, None, None

        pressure_week, pressure_index, _ = first_current_code(pressure_codes)
        emergence_week, emergence_index, _ = first_current_code(emergence_codes)

        effort_week: str | None = None
        effort_index: int | None = None
        for audit in audits:
            assert audit.bar_index is not None
            if any(
                item.direction is direction and item.bar_index == audit.bar_index
                for item in audit.effort_result_evidence
            ):
                effort_week = audit.week
                effort_index = audit.bar_index
                break

        rejection_week: str | None = None
        rejection_index: int | None = None
        for audit in audits:
            assert audit.bar_index is not None
            current_rejection = any(
                item.code in rejection_codes and item.bar_index == audit.bar_index
                for item in audit.current_evidence
            )
            current_absorption = any(
                item.direction is direction and item.bar_index == audit.bar_index
                for item in audit.absorption_evidence
            )
            if current_rejection or current_absorption:
                rejection_week = audit.week
                rejection_index = audit.bar_index
                break

        progression_events: list[tuple[str | None, int]] = []
        wanted_progression = cls._aligned_progression_code(direction)
        assert wanted_progression is not None
        for audit in audits:
            assert audit.bar_index is not None
            if any(
                item.code is wanted_progression
                and item.direction is direction
                and item.bar_index == audit.bar_index
                for item in audit.structural_progression_events
            ):
                progression_events.append((audit.week, audit.bar_index))

        first_legacy_qualification_week: str | None = None
        first_legacy_qualification_index: int | None = None
        first_legacy_actionable_week: str | None = None
        first_legacy_actionable_index: int | None = None
        legacy_actionable_position: int | None = None
        for position, audit in enumerate(audits):
            if (
                first_legacy_qualification_index is None
                and audit.legacy_qualification is legacy_qualification
            ):
                first_legacy_qualification_week = audit.week
                first_legacy_qualification_index = audit.bar_index
            if (
                first_legacy_actionable_index is None
                and audit.legacy_actionable
                and audit.legacy_qualification is legacy_qualification
            ):
                first_legacy_actionable_week = audit.week
                first_legacy_actionable_index = audit.bar_index
                legacy_actionable_position = position

        first_shadow_week: str | None = None
        first_shadow_index: int | None = None
        shadow_position: int | None = None
        for position, thesis in enumerate(theses):
            if thesis.state is supported_state:
                first_shadow_week = thesis.week
                first_shadow_index = thesis.bar_index
                shadow_position = position
                break

        lead_lag: int | None = None
        if shadow_position is not None and legacy_actionable_position is not None:
            lead_lag = shadow_position - legacy_actionable_position

        first_progression = progression_events[0] if len(progression_events) >= 1 else (None, None)
        second_progression = progression_events[1] if len(progression_events) >= 2 else (None, None)
        third_progression = progression_events[2] if len(progression_events) >= 3 else (None, None)

        return DirectionalTimingSummary(
            direction=direction,
            first_opposing_pressure_reduction_week=pressure_week,
            first_opposing_pressure_reduction_bar_index=pressure_index,
            first_aligned_pressure_emergence_week=emergence_week,
            first_aligned_pressure_emergence_bar_index=emergence_index,
            first_supportive_effort_result_week=effort_week,
            first_supportive_effort_result_bar_index=effort_index,
            first_absorption_or_rejection_week=rejection_week,
            first_absorption_or_rejection_bar_index=rejection_index,
            first_structural_progression_week=first_progression[0],
            first_structural_progression_bar_index=first_progression[1],
            second_structural_progression_week=second_progression[0],
            second_structural_progression_bar_index=second_progression[1],
            third_structural_progression_week=third_progression[0],
            third_structural_progression_bar_index=third_progression[1],
            first_legacy_qualification_week=first_legacy_qualification_week,
            first_legacy_qualification_bar_index=first_legacy_qualification_index,
            first_legacy_actionable_week=first_legacy_actionable_week,
            first_legacy_actionable_bar_index=first_legacy_actionable_index,
            first_shadow_supported_week=first_shadow_week,
            first_shadow_supported_bar_index=first_shadow_index,
            shadow_supported_minus_legacy_actionable_weeks=lead_lag,
        )

    @classmethod
    def compare(
        cls,
        *,
        audits: Sequence[WeeklyDecisionGateAuditRecord],
        prices: Sequence[WeeklyReplayPriceBar],
        horizons_weeks: Sequence[int] = DEFAULT_HORIZONS,
    ) -> WeeklyReplayComparisonReport:
        audit_history, price_history, horizons = cls._validate(
            audits,
            prices,
            horizons_weeks,
        )

        behaviors: list[WeeklyBehaviorState] = []
        evolutions: list[WeeklyBehaviorEvolution] = []
        theses: list[ShadowWeeklyThesis] = []

        for audit in audit_history:
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

        evolution_history = tuple(evolutions)
        thesis_history = tuple(theses)
        records: list[WeeklyReplayComparisonRecord] = []

        for position, (audit, thesis) in enumerate(zip(audit_history, thesis_history)):
            assert audit.bar_index is not None
            legacy_direction = cls._legacy_direction(audit.legacy_qualification)
            legacy_yes = audit.legacy_actionable
            shadow_yes = thesis.state in cls._SHADOW_SUPPORTED_STATES
            shadow_direction = thesis.direction if shadow_yes else EvidenceDirection.NEUTRAL

            bucket = cls._bucket(legacy_yes=legacy_yes, shadow_yes=shadow_yes)
            agreement = cls._direction_agreement(
                legacy_yes=legacy_yes,
                legacy_direction=legacy_direction,
                shadow_yes=shadow_yes,
                shadow_direction=shadow_direction,
            )

            legacy_confirmation = cls._first_future_structural_confirmation(
                audit_history,
                position,
                legacy_direction if legacy_yes else EvidenceDirection.NEUTRAL,
            )
            legacy_invalidation = cls._first_future_structural_invalidation(
                evolution_history,
                position,
                legacy_direction if legacy_yes else EvidenceDirection.NEUTRAL,
            )
            shadow_confirmation = cls._first_future_structural_confirmation(
                audit_history,
                position,
                shadow_direction if shadow_yes else EvidenceDirection.NEUTRAL,
            )
            shadow_invalidation = cls._first_future_structural_invalidation(
                evolution_history,
                position,
                shadow_direction if shadow_yes else EvidenceDirection.NEUTRAL,
            )

            records.append(
                WeeklyReplayComparisonRecord(
                    symbol=audit.symbol,
                    week=audit.week,
                    bar_index=audit.bar_index,
                    legacy_qualification=audit.legacy_qualification,
                    legacy_actionable=legacy_yes,
                    legacy_direction=legacy_direction,
                    legacy_gate_blockers=tuple(audit.gate_blockers),
                    shadow_state=thesis.state,
                    shadow_basis=thesis.basis,
                    shadow_direction=shadow_direction,
                    shadow_supported=shadow_yes,
                    contradiction_state=thesis.contradiction_state,
                    bucket=bucket,
                    direction_agreement=agreement,
                    legacy_forward_outcomes=(
                        cls._outcomes_for(
                            price_history,
                            position,
                            legacy_direction,
                            horizons,
                        )
                        if legacy_yes
                        else ()
                    ),
                    shadow_forward_outcomes=(
                        cls._outcomes_for(
                            price_history,
                            position,
                            shadow_direction,
                            horizons,
                        )
                        if shadow_yes
                        else ()
                    ),
                    legacy_first_structural_confirmation_week=legacy_confirmation[0],
                    legacy_first_structural_confirmation_bar_index=legacy_confirmation[1],
                    legacy_first_structural_invalidation_week=legacy_invalidation[0],
                    legacy_first_structural_invalidation_bar_index=legacy_invalidation[1],
                    shadow_first_structural_confirmation_week=shadow_confirmation[0],
                    shadow_first_structural_confirmation_bar_index=shadow_confirmation[1],
                    shadow_first_structural_invalidation_week=shadow_invalidation[0],
                    shadow_first_structural_invalidation_bar_index=shadow_invalidation[1],
                )
            )

        record_history = tuple(records)
        bucket_counts = tuple(
            WeeklyReplayBucketCount(
                bucket=bucket,
                count=sum(item.bucket is bucket for item in record_history),
            )
            for bucket in WeeklyReplayBucket
        )

        timing = (
            cls._timing_summary(
                audit_history,
                thesis_history,
                EvidenceDirection.BULLISH,
            ),
            cls._timing_summary(
                audit_history,
                thesis_history,
                EvidenceDirection.BEARISH,
            ),
        )

        return WeeklyReplayComparisonReport(
            symbol=audit_history[0].symbol,
            horizons_weeks=horizons,
            records=record_history,
            bucket_counts=bucket_counts,
            timing=timing,
        )


__all__ = [
    "DirectionalForwardOutcome",
    "DirectionalTimingSummary",
    "WeeklyDirectionAgreement",
    "WeeklyReplayBucket",
    "WeeklyReplayBucketCount",
    "WeeklyReplayComparisonEngine",
    "WeeklyReplayComparisonRecord",
    "WeeklyReplayComparisonReport",
    "WeeklyReplayPriceBar",
]
