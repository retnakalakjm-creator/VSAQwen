from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum, auto

from background.qualification import PatternQualification
from models import (
    Evidence,
    EvidenceCode,
    StructuralPattern,
    StructuralSwing,
    TrendDirection,
    TrendState,
)
from scanner import ScannerCandidate, ScannerEngine
from weekly_setup import WeeklyPriceZone


class LegacyGateBlocker(StrEnum):
    """Observable reasons the current legacy weekly gate is not actionable.

    These values describe the existing production decision boundary. They are
    audit facts only; WF1 does not change qualification or actionability.
    """

    QUALIFICATION_MISSING = auto()
    STRUCTURAL_QUALIFICATION_STALE_NO_VSA = auto()
    NAMED_VSA_CONFIRMATION_MISSING = auto()
    NAMED_VSA_CONFIRMATION_STALE = auto()
    OPPOSING_NAMED_VSA_PRESENT = auto()
    PROFESSIONAL_PRESSURE_CONFLICT = auto()
    PROFESSIONAL_CONFIDENCE_ZERO = auto()
    SIGNAL_BAR_ANOMALY = auto()


@dataclass(frozen=True, slots=True)
class WeeklyDecisionGateAuditRecord:
    """Point-in-time snapshot of what the legacy weekly gate actually saw."""

    symbol: str
    week: str | None
    bar_index: int | None

    trend_direction: TrendDirection
    trend_state: TrendState
    structural_pattern: StructuralPattern
    structural_swing_lineage: tuple[StructuralSwing, ...]
    structural_progression_events: tuple[Evidence, ...]

    legacy_qualification: PatternQualification
    legacy_qualification_reason: str
    legacy_candidate_reason: str
    legacy_qualification_actionable_evidence: bool
    legacy_actionable: bool
    structural_qualification_current: bool

    qualifying_evidence: tuple[Evidence, ...]
    scoring_evidence: tuple[Evidence, ...]
    scoring_evidence_age: int | None
    current_evidence: tuple[Evidence, ...]
    recent_evidence: tuple[Evidence, ...]
    campaign_evidence: tuple[Evidence, ...]

    effort_result_evidence: tuple[Evidence, ...]
    absorption_evidence: tuple[Evidence, ...]

    bullish_named_vsa_evidence: tuple[Evidence, ...]
    bearish_named_vsa_evidence: tuple[Evidence, ...]
    aligned_named_vsa_present: bool
    opposing_named_vsa_present: bool
    professional_pressure_conflict: bool

    professional_strength: float
    professional_weakness: float
    professional_net_strength: float
    professional_net_pressure: float
    professional_confidence: float

    support_zone: WeeklyPriceZone | None = None
    resistance_zone: WeeklyPriceZone | None = None
    gate_blockers: tuple[LegacyGateBlocker, ...] = ()


class WeeklyDecisionGateAuditor:
    """Read-only instrumentation for the current weekly decision boundary.

    WF1 intentionally mirrors the legacy scanner constants and named-VSA sets.
    Coupling to those legacy definitions is deliberate: an audit that silently
    redefines the gate would drift away from the production baseline it is meant
    to measure.
    """

    _STRUCTURAL_CODES = frozenset(
        {
            EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING,
            EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING,
        }
    )

    @staticmethod
    def _bounded_recent_evidence(candidate: ScannerCandidate) -> tuple[Evidence, ...]:
        bar_index = candidate.bar_index
        if bar_index is None:
            return tuple(candidate.campaign_evidence)

        earliest = max(0, bar_index - ScannerEngine.SCORING_LOOKBACK_BARS)
        return tuple(
            item
            for item in candidate.campaign_evidence
            if earliest <= item.bar_index <= bar_index
        )

    @staticmethod
    def _structural_qualification_current(candidate: ScannerCandidate) -> bool:
        if candidate.qualification is PatternQualification.UNQUALIFIED:
            return False
        if candidate.bar_index is None:
            return bool(candidate.qualifying_evidence)
        return bool(candidate.qualifying_evidence) and max(
            item.bar_index for item in candidate.qualifying_evidence
        ) == candidate.bar_index

    @staticmethod
    def _directional_named_evidence(
        candidate: ScannerCandidate,
    ) -> tuple[tuple[Evidence, ...], tuple[Evidence, ...]]:
        bullish = tuple(
            item
            for item in candidate.scoring_evidence
            if item.code in ScannerEngine._BULLISH_VSA_CODES
        )
        bearish = tuple(
            item
            for item in candidate.scoring_evidence
            if item.code in ScannerEngine._BEARISH_VSA_CODES
        )
        return bullish, bearish

    @classmethod
    def audit(
        cls,
        *,
        symbol: str,
        candidate: ScannerCandidate,
        support_zone: WeeklyPriceZone | None = None,
        resistance_zone: WeeklyPriceZone | None = None,
    ) -> WeeklyDecisionGateAuditRecord:
        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol:
            raise ValueError("symbol cannot be empty")

        context = candidate.evidence.context
        trend = context.trend
        bullish_named, bearish_named = cls._directional_named_evidence(candidate)

        qualification = candidate.qualification
        structural_current = cls._structural_qualification_current(candidate)

        if qualification is PatternQualification.PERSISTENT_BULLISH:
            aligned_named = bullish_named
            opposing_named = bearish_named
            pressure_conflict = not bullish_named and candidate.net_pressure < 0.0
        elif qualification is PatternQualification.PERSISTENT_BEARISH:
            aligned_named = bearish_named
            opposing_named = bullish_named
            pressure_conflict = not bearish_named and candidate.net_pressure > 0.0
        else:
            aligned_named = ()
            opposing_named = ()
            pressure_conflict = False

        blockers: list[LegacyGateBlocker] = []

        if qualification is PatternQualification.UNQUALIFIED:
            blockers.append(LegacyGateBlocker.QUALIFICATION_MISSING)
        else:
            if not candidate.scoring_evidence:
                if not structural_current:
                    blockers.append(
                        LegacyGateBlocker.STRUCTURAL_QUALIFICATION_STALE_NO_VSA
                    )
                else:
                    blockers.append(LegacyGateBlocker.NAMED_VSA_CONFIRMATION_MISSING)
            elif (
                candidate.scoring_evidence_age is None
                or candidate.scoring_evidence_age < 0
                or candidate.scoring_evidence_age > ScannerEngine.MAX_ACTIONABLE_VSA_AGE
            ):
                blockers.append(LegacyGateBlocker.NAMED_VSA_CONFIRMATION_STALE)
            else:
                if opposing_named:
                    blockers.append(LegacyGateBlocker.OPPOSING_NAMED_VSA_PRESENT)
                elif pressure_conflict:
                    blockers.append(LegacyGateBlocker.PROFESSIONAL_PRESSURE_CONFLICT)
                elif not aligned_named:
                    blockers.append(LegacyGateBlocker.NAMED_VSA_CONFIRMATION_MISSING)

        if (
            candidate.qualification_result.is_actionable_evidence
            and candidate.professional.confidence <= 0.0
        ):
            blockers.append(LegacyGateBlocker.PROFESSIONAL_CONFIDENCE_ZERO)

        if candidate.signal_bar_anomaly:
            blockers.append(LegacyGateBlocker.SIGNAL_BAR_ANOMALY)

        structural_events = tuple(
            item
            for item in candidate.campaign_evidence
            if item.code in cls._STRUCTURAL_CODES
            and (candidate.bar_index is None or item.bar_index <= candidate.bar_index)
        )

        return WeeklyDecisionGateAuditRecord(
            symbol=normalized_symbol,
            week=candidate.week,
            bar_index=candidate.bar_index,
            trend_direction=trend.direction,
            trend_state=trend.state,
            structural_pattern=context.structural_pattern,
            structural_swing_lineage=tuple(context.structural_swings),
            structural_progression_events=structural_events,
            legacy_qualification=qualification,
            legacy_qualification_reason=candidate.qualification_result.reason,
            legacy_candidate_reason=candidate.reason,
            legacy_qualification_actionable_evidence=(
                candidate.qualification_result.is_actionable_evidence
            ),
            legacy_actionable=candidate.actionable,
            structural_qualification_current=structural_current,
            qualifying_evidence=tuple(candidate.qualifying_evidence),
            scoring_evidence=tuple(candidate.scoring_evidence),
            scoring_evidence_age=candidate.scoring_evidence_age,
            current_evidence=tuple(candidate.target_bar_evidence),
            recent_evidence=cls._bounded_recent_evidence(candidate),
            campaign_evidence=tuple(candidate.campaign_evidence),
            effort_result_evidence=tuple(candidate.effort_result_evidence),
            absorption_evidence=tuple(candidate.absorption_evidence),
            bullish_named_vsa_evidence=bullish_named,
            bearish_named_vsa_evidence=bearish_named,
            aligned_named_vsa_present=bool(aligned_named),
            opposing_named_vsa_present=bool(opposing_named),
            professional_pressure_conflict=pressure_conflict,
            professional_strength=candidate.professional.strength,
            professional_weakness=candidate.professional.weakness,
            professional_net_strength=candidate.net_strength,
            professional_net_pressure=candidate.net_pressure,
            professional_confidence=candidate.confidence,
            support_zone=support_zone,
            resistance_zone=resistance_zone,
            gate_blockers=tuple(blockers),
        )


__all__ = [
    "LegacyGateBlocker",
    "WeeklyDecisionGateAuditRecord",
    "WeeklyDecisionGateAuditor",
]
