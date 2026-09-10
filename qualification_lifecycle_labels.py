from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Iterable, Sequence


class QualificationLifecycleLabel(StrEnum):
    """Production-safe labels for persistent qualification lifecycle state."""

    UNQUALIFIED = "unqualified"
    ACTIVE = "active"
    CONFLICTED = "conflicted"
    INVALIDATED = "invalidated"
    EXPIRED = "expired"
    NEEDS_FOLLOW_THROUGH = "needs_follow_through"


class QualificationSide(StrEnum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    UNQUALIFIED = "unqualified"


class CurrentVSABias(StrEnum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    MIXED = "mixed"
    NONE = "none"


BULLISH_PRODUCTION_VSA_CODES = frozenset(
    {
        "stopping_volume",
        "demand_coming_in",
        "increasing_demand",
        "hidden_demand",
        "demand_drying_up",
        "no_supply",
        "spring",
        "test",
        "selling_climax",
        "shakeout",
    }
)

BEARISH_PRODUCTION_VSA_CODES = frozenset(
    {
        "buying_climax",
        "supply_coming_in",
        "increasing_supply",
        "hidden_supply",
        "supply_high_volume",
        "supply_wide_spread",
        "supply_absorption",
        "upthrust",
        "no_demand",
    }
)

# Audit-only candidate families stay deliberately outside the production label
# direction sets until a later PR promotes them through detector-specific gates.
AUDIT_ONLY_CANDIDATE_CODES = frozenset(
    {
        "effort_gt_result",
        "result_gt_effort",
        "absorption",
        "audit_effort_gt_result_candidate",
        "audit_absorption_candidate",
        "audit_high_volume_reversal_candidate",
    }
)

DEFAULT_MAX_ACTIONABLE_VSA_AGE = 3


@dataclass(frozen=True, slots=True)
class QualificationLifecycleLabelResult:
    """Read-only lifecycle label for the existing scanner qualification state."""

    qualification: str
    qualification_side: QualificationSide
    status: QualificationLifecycleLabel
    current_vsa_bias: CurrentVSABias
    actionable: bool
    scoring_evidence_age: int | None
    used_fallback_evidence: bool
    supporting_event_codes: tuple[str, ...]
    opposing_event_codes: tuple[str, ...]
    ignored_audit_only_codes: tuple[str, ...]
    reason: str
    production_safe: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "qualification": self.qualification,
            "qualification_side": self.qualification_side.value,
            "status": self.status.value,
            "current_vsa_bias": self.current_vsa_bias.value,
            "actionable": self.actionable,
            "scoring_evidence_age": self.scoring_evidence_age,
            "used_fallback_evidence": self.used_fallback_evidence,
            "supporting_event_codes": list(self.supporting_event_codes),
            "opposing_event_codes": list(self.opposing_event_codes),
            "ignored_audit_only_codes": list(self.ignored_audit_only_codes),
            "reason": self.reason,
            "production_safe": self.production_safe,
        }


def label_candidate_qualification_lifecycle(
    candidate: Any,
    *,
    max_actionable_vsa_age: int = DEFAULT_MAX_ACTIONABLE_VSA_AGE,
) -> QualificationLifecycleLabelResult:
    """Build a lifecycle label from a production ScannerCandidate-like object.

    This helper reads already-computed scanner fields only. It does not load
    market data, replay history, mutate scanner state, change ranking/scoring,
    or promote audit-only detector candidates into production evidence.
    """

    return label_qualification_lifecycle(
        qualification=getattr(candidate, "qualification", ""),
        actionable=bool(getattr(candidate, "actionable", False)),
        scoring_evidence=getattr(candidate, "scoring_evidence", ()),
        scoring_evidence_age=getattr(candidate, "scoring_evidence_age", None),
        used_fallback_evidence=bool(getattr(candidate, "used_fallback_evidence", False)),
        max_actionable_vsa_age=max_actionable_vsa_age,
    )


def label_qualification_lifecycle(
    *,
    qualification: Any,
    actionable: bool,
    scoring_evidence: Iterable[Any] | None = None,
    scoring_evidence_age: int | None = None,
    used_fallback_evidence: bool = False,
    max_actionable_vsa_age: int = DEFAULT_MAX_ACTIONABLE_VSA_AGE,
) -> QualificationLifecycleLabelResult:
    """Return a read-only lifecycle label for persistent qualification state."""

    qualification_text = _enum_text(qualification)
    side = _qualification_side(qualification_text)
    evidence_codes = _evidence_codes(scoring_evidence)
    ignored_audit_codes = tuple(code for code in evidence_codes if code in AUDIT_ONLY_CANDIDATE_CODES)
    directional_codes = tuple(code for code in evidence_codes if code not in AUDIT_ONLY_CANDIDATE_CODES)
    bullish = tuple(code for code in directional_codes if code in BULLISH_PRODUCTION_VSA_CODES)
    bearish = tuple(code for code in directional_codes if code in BEARISH_PRODUCTION_VSA_CODES)
    current_bias = _current_bias(bullish=bullish, bearish=bearish)

    if side is QualificationSide.UNQUALIFIED:
        return QualificationLifecycleLabelResult(
            qualification=qualification_text or QualificationSide.UNQUALIFIED.value,
            qualification_side=side,
            status=QualificationLifecycleLabel.UNQUALIFIED,
            current_vsa_bias=current_bias,
            actionable=False,
            scoring_evidence_age=scoring_evidence_age,
            used_fallback_evidence=used_fallback_evidence,
            supporting_event_codes=(),
            opposing_event_codes=(),
            ignored_audit_only_codes=ignored_audit_codes,
            reason="No persistent bullish or bearish qualification is active.",
        )

    supporting, opposing = _split_supporting_opposing(side, bullish=bullish, bearish=bearish)
    has_stale_evidence = _is_stale(scoring_evidence_age, max_actionable_vsa_age)
    has_current_fresh_evidence = bool(directional_codes) and not has_stale_evidence

    status = _status_for_persistent_qualification(
        actionable=actionable,
        has_current_fresh_evidence=has_current_fresh_evidence,
        has_stale_evidence=has_stale_evidence,
        used_fallback_evidence=used_fallback_evidence,
        supporting=supporting,
        opposing=opposing,
    )

    return QualificationLifecycleLabelResult(
        qualification=qualification_text,
        qualification_side=side,
        status=status,
        current_vsa_bias=current_bias,
        actionable=actionable,
        scoring_evidence_age=scoring_evidence_age,
        used_fallback_evidence=used_fallback_evidence,
        supporting_event_codes=supporting,
        opposing_event_codes=opposing,
        ignored_audit_only_codes=ignored_audit_codes,
        reason=_reason(status, side, current_bias),
    )


def _status_for_persistent_qualification(
    *,
    actionable: bool,
    has_current_fresh_evidence: bool,
    has_stale_evidence: bool,
    used_fallback_evidence: bool,
    supporting: tuple[str, ...],
    opposing: tuple[str, ...],
) -> QualificationLifecycleLabel:
    if supporting and opposing and has_current_fresh_evidence:
        return QualificationLifecycleLabel.CONFLICTED
    if opposing and not supporting:
        if has_stale_evidence or used_fallback_evidence:
            return QualificationLifecycleLabel.NEEDS_FOLLOW_THROUGH
        return QualificationLifecycleLabel.INVALIDATED
    if supporting and has_current_fresh_evidence:
        return QualificationLifecycleLabel.ACTIVE if actionable else QualificationLifecycleLabel.EXPIRED
    if has_stale_evidence or not has_current_fresh_evidence:
        return QualificationLifecycleLabel.EXPIRED
    return QualificationLifecycleLabel.ACTIVE if actionable else QualificationLifecycleLabel.EXPIRED


def _split_supporting_opposing(
    side: QualificationSide,
    *,
    bullish: tuple[str, ...],
    bearish: tuple[str, ...],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if side is QualificationSide.BULLISH:
        return bullish, bearish
    if side is QualificationSide.BEARISH:
        return bearish, bullish
    return (), ()


def _current_bias(*, bullish: tuple[str, ...], bearish: tuple[str, ...]) -> CurrentVSABias:
    if bullish and bearish:
        return CurrentVSABias.MIXED
    if bullish:
        return CurrentVSABias.BULLISH
    if bearish:
        return CurrentVSABias.BEARISH
    return CurrentVSABias.NONE


def _qualification_side(qualification: str) -> QualificationSide:
    lowered = qualification.lower()
    if "persistent_bullish" in lowered or lowered.endswith("bullish") or "bullish" in lowered:
        return QualificationSide.BULLISH
    if "persistent_bearish" in lowered or lowered.endswith("bearish") or "bearish" in lowered:
        return QualificationSide.BEARISH
    return QualificationSide.UNQUALIFIED


def _is_stale(age: int | None, max_actionable_vsa_age: int) -> bool:
    return age is not None and age > max_actionable_vsa_age


def _evidence_codes(scoring_evidence: Iterable[Any] | None) -> tuple[str, ...]:
    if scoring_evidence is None:
        return ()
    codes: list[str] = []
    for item in scoring_evidence:
        code = _enum_text(getattr(item, "code", item)).strip()
        if code:
            codes.append(code)
    return _dedupe(codes)


def _enum_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    enum_value = getattr(value, "value", None)
    if isinstance(enum_value, str):
        return enum_value
    enum_name = getattr(value, "name", None)
    if isinstance(enum_name, str):
        return enum_name.lower()
    return str(value)


def _dedupe(items: Iterable[str]) -> tuple[str, ...]:
    selected: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item not in seen:
            selected.append(item)
            seen.add(item)
    return tuple(selected)


def _reason(
    status: QualificationLifecycleLabel,
    side: QualificationSide,
    bias: CurrentVSABias,
) -> str:
    if status is QualificationLifecycleLabel.ACTIVE:
        return f"Persistent {side.value} qualification is supported by fresh same-side VSA evidence."
    if status is QualificationLifecycleLabel.CONFLICTED:
        return f"Persistent {side.value} qualification has both supporting and opposing fresh VSA evidence."
    if status is QualificationLifecycleLabel.INVALIDATED:
        return f"Persistent {side.value} qualification has fresh opposing {bias.value} VSA evidence without same-side support."
    if status is QualificationLifecycleLabel.EXPIRED:
        return f"Persistent {side.value} qualification lacks fresh same-side VSA confirmation."
    if status is QualificationLifecycleLabel.NEEDS_FOLLOW_THROUGH:
        return f"Persistent {side.value} qualification has an opposing challenge, but the evidence is fallback/stale and needs follow-through."
    return "No persistent qualification lifecycle applies."


__all__ = [
    "AUDIT_ONLY_CANDIDATE_CODES",
    "BEARISH_PRODUCTION_VSA_CODES",
    "BULLISH_PRODUCTION_VSA_CODES",
    "CurrentVSABias",
    "DEFAULT_MAX_ACTIONABLE_VSA_AGE",
    "QualificationLifecycleLabel",
    "QualificationLifecycleLabelResult",
    "QualificationSide",
    "label_candidate_qualification_lifecycle",
    "label_qualification_lifecycle",
]
