from __future__ import annotations

from dataclasses import dataclass

from models import (
    Evidence,
    EvidenceCategory,
    EvidenceCode,
    EvidenceDirection,
    StructuralPattern,
    StructuralSwing,
    TrendDirection,
    TrendState,
)
from weekly_decision_audit import WeeklyDecisionGateAuditRecord
from weekly_setup import WeeklyPriceZone


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


@dataclass(frozen=True, slots=True)
class WeeklyBehaviorState:
    """Immutable, read-only description of point-in-time weekly behavior.

    WF2 does not decide whether a weekly campaign is actionable and does not
    create a WeeklySetup. It only organizes evidence that was already visible
    by the completed weekly bar into auditable behavioral dimensions.
    """

    symbol: str
    week: str | None
    bar_index: int | None

    trend_direction: TrendDirection
    trend_state: TrendState
    structural_pattern: StructuralPattern
    structural_swing_lineage: tuple[StructuralSwing, ...] = ()

    support_zone: WeeklyPriceZone | None = None
    resistance_zone: WeeklyPriceZone | None = None

    professional_strength: float = 0.0
    professional_weakness: float = 0.0
    professional_net_strength: float = 0.0
    professional_net_pressure: float = 0.0
    professional_confidence: float = 0.0

    current_evidence: tuple[Evidence, ...] = ()
    recent_evidence: tuple[Evidence, ...] = ()

    supply_evidence: tuple[Evidence, ...] = ()
    demand_evidence: tuple[Evidence, ...] = ()
    effort_result_evidence: tuple[Evidence, ...] = ()
    absorption_evidence: tuple[Evidence, ...] = ()
    progression_evidence: tuple[Evidence, ...] = ()

    bullish_evidence: tuple[Evidence, ...] = ()
    bearish_evidence: tuple[Evidence, ...] = ()
    neutral_evidence: tuple[Evidence, ...] = ()

    structural_reference_direction: EvidenceDirection = EvidenceDirection.NEUTRAL
    aligned_evidence: tuple[Evidence, ...] = ()
    opposing_evidence: tuple[Evidence, ...] = ()

    @property
    def is_actionable(self) -> bool:
        """WF2 behavior state has no production actionability authority."""

        return False

    @property
    def has_directional_structural_reference(self) -> bool:
        return self.structural_reference_direction is not EvidenceDirection.NEUTRAL


class WeeklyBehaviorStateBuilder:
    """Build WF2 behavior state without re-detecting market events.

    The builder is intentionally a projection over existing evidence. It does
    not calculate indicators, rerun detectors, score observations, or infer a
    weekly thesis. This keeps WF2 auditable and prevents a second parallel VSA
    engine from emerging.
    """

    @staticmethod
    def _sort_evidence(evidence: tuple[Evidence, ...]) -> tuple[Evidence, ...]:
        """Order chronologically while preserving source order within a bar.

        Evidence emitted on the same weekly bar already has deterministic
        detector/provenance order. Re-sorting same-bar observations by code
        would manufacture a new ordering that carries no market meaning and
        obscures the source lineage WF2 is intended to preserve.
        """

        return tuple(sorted(evidence, key=lambda item: item.bar_index))

    @staticmethod
    def _structural_reference(trend_direction: TrendDirection) -> EvidenceDirection:
        if trend_direction is TrendDirection.UP:
            return EvidenceDirection.BULLISH
        if trend_direction is TrendDirection.DOWN:
            return EvidenceDirection.BEARISH
        return EvidenceDirection.NEUTRAL

    @classmethod
    def build(
        cls,
        *,
        symbol: str,
        week: str | None,
        bar_index: int | None,
        trend_direction: TrendDirection,
        trend_state: TrendState,
        structural_pattern: StructuralPattern,
        structural_swing_lineage: tuple[StructuralSwing, ...] = (),
        current_evidence: tuple[Evidence, ...] = (),
        recent_evidence: tuple[Evidence, ...] = (),
        support_zone: WeeklyPriceZone | None = None,
        resistance_zone: WeeklyPriceZone | None = None,
        professional_strength: float = 0.0,
        professional_weakness: float = 0.0,
        professional_net_strength: float = 0.0,
        professional_net_pressure: float = 0.0,
        professional_confidence: float = 0.0,
    ) -> WeeklyBehaviorState:
        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol:
            raise ValueError("symbol cannot be empty")
        if bar_index is not None and bar_index < 0:
            raise ValueError("bar_index cannot be negative")

        if bar_index is None:
            current = cls._sort_evidence(tuple(current_evidence))
            recent = cls._sort_evidence(tuple(recent_evidence))
        else:
            # Defensive point-in-time filtering. WF1 already supplies bounded
            # recent evidence, but WF2 refuses future evidence if called
            # directly by replay/audit tooling.
            current = cls._sort_evidence(
                tuple(item for item in current_evidence if item.bar_index == bar_index)
            )
            recent = cls._sort_evidence(
                tuple(item for item in recent_evidence if item.bar_index <= bar_index)
            )

        supply = tuple(
            item for item in recent if item.category is EvidenceCategory.SUPPLY
        )
        demand = tuple(
            item for item in recent if item.category is EvidenceCategory.DEMAND
        )
        effort_result = tuple(
            item
            for item in recent
            if item.code in _EFFORT_RESULT_CODES
            or item.category in (EvidenceCategory.EFFORT, EvidenceCategory.RESULT)
        )
        absorption = tuple(item for item in recent if item.code in _ABSORPTION_CODES)
        progression = tuple(item for item in recent if item.code in _PROGRESSION_CODES)

        bullish = tuple(
            item for item in recent if item.direction is EvidenceDirection.BULLISH
        )
        bearish = tuple(
            item for item in recent if item.direction is EvidenceDirection.BEARISH
        )
        neutral = tuple(
            item for item in recent if item.direction is EvidenceDirection.NEUTRAL
        )

        structural_reference = cls._structural_reference(trend_direction)
        if structural_reference is EvidenceDirection.BULLISH:
            aligned = bullish
            opposing = bearish
        elif structural_reference is EvidenceDirection.BEARISH:
            aligned = bearish
            opposing = bullish
        else:
            # RANGE/UNKNOWN is deliberately not converted into a synthetic
            # bullish or bearish campaign. Directional observations remain
            # visible through bullish_evidence/bearish_evidence only.
            aligned = ()
            opposing = ()

        return WeeklyBehaviorState(
            symbol=normalized_symbol,
            week=week,
            bar_index=bar_index,
            trend_direction=trend_direction,
            trend_state=trend_state,
            structural_pattern=structural_pattern,
            structural_swing_lineage=tuple(structural_swing_lineage),
            support_zone=support_zone,
            resistance_zone=resistance_zone,
            professional_strength=professional_strength,
            professional_weakness=professional_weakness,
            professional_net_strength=professional_net_strength,
            professional_net_pressure=professional_net_pressure,
            professional_confidence=professional_confidence,
            current_evidence=current,
            recent_evidence=recent,
            supply_evidence=supply,
            demand_evidence=demand,
            effort_result_evidence=effort_result,
            absorption_evidence=absorption,
            progression_evidence=progression,
            bullish_evidence=bullish,
            bearish_evidence=bearish,
            neutral_evidence=neutral,
            structural_reference_direction=structural_reference,
            aligned_evidence=aligned,
            opposing_evidence=opposing,
        )

    @classmethod
    def from_audit(cls, audit: WeeklyDecisionGateAuditRecord) -> WeeklyBehaviorState:
        """Project the bounded WF1 audit snapshot into the WF2 behavior model."""

        return cls.build(
            symbol=audit.symbol,
            week=audit.week,
            bar_index=audit.bar_index,
            trend_direction=audit.trend_direction,
            trend_state=audit.trend_state,
            structural_pattern=audit.structural_pattern,
            structural_swing_lineage=audit.structural_swing_lineage,
            current_evidence=audit.current_evidence,
            recent_evidence=audit.recent_evidence,
            support_zone=audit.support_zone,
            resistance_zone=audit.resistance_zone,
            professional_strength=audit.professional_strength,
            professional_weakness=audit.professional_weakness,
            professional_net_strength=audit.professional_net_strength,
            professional_net_pressure=audit.professional_net_pressure,
            professional_confidence=audit.professional_confidence,
        )


__all__ = [
    "WeeklyBehaviorState",
    "WeeklyBehaviorStateBuilder",
]
