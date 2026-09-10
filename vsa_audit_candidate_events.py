from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

DIAGNOSTIC_POTENTIAL_STOPPING_VOLUME = "review_potential_stopping_volume"
DIAGNOSTIC_POTENTIAL_EFFORT_GT_RESULT = "review_potential_effort_gt_result"
DIAGNOSTIC_POTENTIAL_ABSORPTION = "review_potential_absorption"
DIAGNOSTIC_POTENTIAL_SPRING_OR_SHAKEOUT = "review_potential_spring_or_shakeout"
DIAGNOSTIC_HIGH_VOLUME_REVERSAL_WITHOUT_BULLISH_EVENT = (
    "review_high_volume_reversal_without_bullish_event"
)

FLAG_BULLISH_VSA_AGAINST_BEARISH_QUALIFICATION = (
    "bullish_vsa_against_bearish_qualification"
)
FLAG_BEARISH_VSA_AGAINST_BULLISH_QUALIFICATION = (
    "bearish_vsa_against_bullish_qualification"
)
FLAG_STRUCTURAL_EVENT_WITHOUT_VSA_CONFIRMATION = (
    "structural_event_without_vsa_confirmation"
)
FLAG_STALE_SCORING_EVIDENCE = "stale_scoring_evidence"

CANDIDATE_EFFORT_GT_RESULT = "audit_effort_gt_result_candidate"
CANDIDATE_ABSORPTION = "audit_absorption_candidate"
CANDIDATE_STOPPING_VOLUME = "audit_stopping_volume_candidate"
CANDIDATE_SPRING_OR_SHAKEOUT = "audit_spring_shakeout_candidate"
CANDIDATE_HIGH_VOLUME_REVERSAL = "audit_high_volume_reversal_candidate"
CANDIDATE_CONTEXT_CONFLICT = "audit_qualification_conflict_candidate"
CANDIDATE_STALE_EVIDENCE = "audit_stale_evidence_candidate"

PRODUCTION_EVENTS_BY_CANDIDATE = {
    CANDIDATE_EFFORT_GT_RESULT: frozenset({"effort_gt_result"}),
    CANDIDATE_ABSORPTION: frozenset({"absorption"}),
    CANDIDATE_STOPPING_VOLUME: frozenset({"stopping_volume"}),
    CANDIDATE_SPRING_OR_SHAKEOUT: frozenset({"spring", "shakeout"}),
    CANDIDATE_HIGH_VOLUME_REVERSAL: frozenset(
        {
            "stopping_volume",
            "selling_climax",
            "shakeout",
            "spring",
            "absorption",
            "demand_coming_in",
            "increasing_demand",
        }
    ),
    CANDIDATE_CONTEXT_CONFLICT: frozenset(),
    CANDIDATE_STALE_EVIDENCE: frozenset(),
}

DIAGNOSTIC_TO_CANDIDATE = {
    DIAGNOSTIC_POTENTIAL_EFFORT_GT_RESULT: CANDIDATE_EFFORT_GT_RESULT,
    DIAGNOSTIC_POTENTIAL_ABSORPTION: CANDIDATE_ABSORPTION,
    DIAGNOSTIC_POTENTIAL_STOPPING_VOLUME: CANDIDATE_STOPPING_VOLUME,
    DIAGNOSTIC_POTENTIAL_SPRING_OR_SHAKEOUT: CANDIDATE_SPRING_OR_SHAKEOUT,
    DIAGNOSTIC_HIGH_VOLUME_REVERSAL_WITHOUT_BULLISH_EVENT: CANDIDATE_HIGH_VOLUME_REVERSAL,
}

CANDIDATE_FAMILIES = {
    CANDIDATE_EFFORT_GT_RESULT: "effort_vs_result",
    CANDIDATE_ABSORPTION: "absorption",
    CANDIDATE_STOPPING_VOLUME: "stopping_volume",
    CANDIDATE_SPRING_OR_SHAKEOUT: "spring_or_shakeout",
    CANDIDATE_HIGH_VOLUME_REVERSAL: "high_volume_reversal",
    CANDIDATE_CONTEXT_CONFLICT: "qualification_lifecycle",
    CANDIDATE_STALE_EVIDENCE: "evidence_lifecycle",
}

CANDIDATE_DIRECTIONS = {
    CANDIDATE_EFFORT_GT_RESULT: "bullish_reversal_review",
    CANDIDATE_ABSORPTION: "bullish_reversal_review",
    CANDIDATE_STOPPING_VOLUME: "bullish_reversal_review",
    CANDIDATE_SPRING_OR_SHAKEOUT: "bullish_reversal_review",
    CANDIDATE_HIGH_VOLUME_REVERSAL: "bullish_reversal_review",
    CANDIDATE_CONTEXT_CONFLICT: "context_review",
    CANDIDATE_STALE_EVIDENCE: "context_review",
}

HIGH_PRIORITY_CANDIDATES = frozenset(
    {
        CANDIDATE_EFFORT_GT_RESULT,
        CANDIDATE_ABSORPTION,
        CANDIDATE_HIGH_VOLUME_REVERSAL,
        CANDIDATE_CONTEXT_CONFLICT,
    }
)

CONTEXT_CONFLICT_FLAGS = frozenset(
    {
        FLAG_BULLISH_VSA_AGAINST_BEARISH_QUALIFICATION,
        FLAG_BEARISH_VSA_AGAINST_BULLISH_QUALIFICATION,
    }
)

LIFECYCLE_FLAGS = frozenset(
    {
        FLAG_STRUCTURAL_EVENT_WITHOUT_VSA_CONFIRMATION,
        FLAG_STALE_SCORING_EVIDENCE,
    }
)


@dataclass(frozen=True, slots=True)
class VSAAuditCandidateEvent:
    """Structured audit-only candidate event for detector calibration.

    Candidate events are not production evidence. They are generated from audit
    diagnostics and flags after the scanner has already produced its normal
    target/scoring evidence. They must not affect scanner scoring, ranking,
    persistence, frontend behavior, broker integration, or order/account logic.
    """

    symbol: str
    replay_week: str
    replay_bar_index: int
    candidate_code: str
    candidate_family: str
    direction: str
    priority: str
    production_status: str
    source_diagnostics: tuple[str, ...]
    source_audit_flags: tuple[str, ...]
    target_event_codes: tuple[str, ...]
    scoring_event_codes: tuple[str, ...]
    qualification: str
    reason: str
    audit_only: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "replay_week": self.replay_week,
            "replay_bar_index": self.replay_bar_index,
            "candidate_code": self.candidate_code,
            "candidate_family": self.candidate_family,
            "direction": self.direction,
            "priority": self.priority,
            "production_status": self.production_status,
            "source_diagnostics": list(self.source_diagnostics),
            "source_audit_flags": list(self.source_audit_flags),
            "target_event_codes": list(self.target_event_codes),
            "scoring_event_codes": list(self.scoring_event_codes),
            "qualification": self.qualification,
            "reason": self.reason,
            "audit_only": self.audit_only,
        }


@dataclass(frozen=True, slots=True)
class VSAAuditCandidateEventSummary:
    """Compact candidate-event summary across supplied audit rows."""

    rows: tuple[VSAAuditCandidateEvent, ...]
    candidate_counts: dict[str, int] = field(default_factory=dict)
    family_counts: dict[str, int] = field(default_factory=dict)
    priority_counts: dict[str, int] = field(default_factory=dict)
    symbol_counts: dict[str, int] = field(default_factory=dict)
    audit_only: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "rows": [row.to_dict() for row in self.rows],
            "candidate_counts": dict(self.candidate_counts),
            "family_counts": dict(self.family_counts),
            "priority_counts": dict(self.priority_counts),
            "symbol_counts": dict(self.symbol_counts),
            "audit_only": self.audit_only,
        }


def build_audit_candidate_event_summary(
    audit_payload: Mapping[str, Any] | Sequence[Mapping[str, Any]],
) -> VSAAuditCandidateEventSummary:
    """Build structured audit-only candidate events from VSA audit output.

    Input can be the full `/api/vsa-audit/events` JSON, a list of symbol result
    dictionaries, or a flat list of audit row dictionaries. The function loops
    over the supplied rows once, does no data loading, performs no scanner replay,
    and returns review candidates only.
    """

    rows = tuple(
        event
        for audit_row in _iter_audit_rows(audit_payload)
        for event in build_audit_candidate_events_for_row(audit_row)
    )
    return VSAAuditCandidateEventSummary(
        rows=rows,
        candidate_counts=_count_values(row.candidate_code for row in rows),
        family_counts=_count_values(row.candidate_family for row in rows),
        priority_counts=_count_values(row.priority for row in rows),
        symbol_counts=_count_values(row.symbol for row in rows),
    )


def build_audit_candidate_events_for_row(
    row: Mapping[str, Any],
) -> tuple[VSAAuditCandidateEvent, ...]:
    """Convert one audit row into zero or more structured candidates."""

    diagnostics = _string_tuple(row.get("detector_diagnostics", ()))
    flags = _string_tuple(row.get("audit_flags", ()))
    target_codes = _string_tuple(row.get("target_event_codes", ()))
    scoring_codes = _string_tuple(row.get("scoring_event_codes", ()))
    selected: list[VSAAuditCandidateEvent] = []

    for diagnostic in diagnostics:
        candidate_code = DIAGNOSTIC_TO_CANDIDATE.get(diagnostic)
        if candidate_code is None:
            continue
        if _candidate_already_confirmed(candidate_code, target_codes):
            continue
        selected.append(
            _candidate_event(
                row,
                candidate_code=candidate_code,
                target_codes=target_codes,
                scoring_codes=scoring_codes,
                diagnostics=(diagnostic,),
                flags=(),
            )
        )

    context_flags = tuple(flag for flag in flags if flag in CONTEXT_CONFLICT_FLAGS)
    if context_flags:
        selected.append(
            _candidate_event(
                row,
                candidate_code=CANDIDATE_CONTEXT_CONFLICT,
                target_codes=target_codes,
                scoring_codes=scoring_codes,
                diagnostics=(),
                flags=context_flags,
            )
        )

    lifecycle_flags = tuple(flag for flag in flags if flag in LIFECYCLE_FLAGS)
    if lifecycle_flags:
        selected.append(
            _candidate_event(
                row,
                candidate_code=CANDIDATE_STALE_EVIDENCE,
                target_codes=target_codes,
                scoring_codes=scoring_codes,
                diagnostics=(),
                flags=lifecycle_flags,
            )
        )

    return tuple(selected)


def _candidate_event(
    row: Mapping[str, Any],
    *,
    candidate_code: str,
    target_codes: tuple[str, ...],
    scoring_codes: tuple[str, ...],
    diagnostics: tuple[str, ...],
    flags: tuple[str, ...],
) -> VSAAuditCandidateEvent:
    return VSAAuditCandidateEvent(
        symbol=str(row.get("symbol", "")),
        replay_week=str(row.get("replay_week", "")),
        replay_bar_index=_int_or_default(row.get("replay_bar_index"), -1),
        candidate_code=candidate_code,
        candidate_family=CANDIDATE_FAMILIES[candidate_code],
        direction=CANDIDATE_DIRECTIONS[candidate_code],
        priority=_candidate_priority(candidate_code, flags),
        production_status=_production_status(candidate_code, target_codes),
        source_diagnostics=diagnostics,
        source_audit_flags=flags,
        target_event_codes=target_codes,
        scoring_event_codes=scoring_codes,
        qualification=str(row.get("qualification", "")),
        reason=_candidate_reason(candidate_code, diagnostics, flags),
    )


def _candidate_already_confirmed(
    candidate_code: str,
    target_codes: tuple[str, ...],
) -> bool:
    expected = PRODUCTION_EVENTS_BY_CANDIDATE.get(candidate_code, frozenset())
    return bool(expected and set(target_codes).intersection(expected))


def _candidate_priority(candidate_code: str, flags: tuple[str, ...]) -> str:
    if candidate_code in HIGH_PRIORITY_CANDIDATES:
        return "high"
    if set(flags).intersection(CONTEXT_CONFLICT_FLAGS):
        return "high"
    return "medium"


def _production_status(candidate_code: str, target_codes: tuple[str, ...]) -> str:
    expected = PRODUCTION_EVENTS_BY_CANDIDATE.get(candidate_code, frozenset())
    if expected and set(target_codes).intersection(expected):
        return "already_confirmed_by_current_detector"
    return "not_confirmed_by_current_detector"


def _candidate_reason(
    candidate_code: str,
    diagnostics: tuple[str, ...],
    flags: tuple[str, ...],
) -> str:
    if candidate_code == CANDIDATE_EFFORT_GT_RESULT:
        return (
            "Audit diagnostics suggest very-high-volume effort with muted result; "
            "review as an Effort-vs-Result candidate before changing production rules."
        )
    if candidate_code == CANDIDATE_ABSORPTION:
        return (
            "Audit diagnostics suggest high-volume support behavior in bearish context; "
            "review as an absorption candidate before changing production rules."
        )
    if candidate_code == CANDIDATE_STOPPING_VOLUME:
        return (
            "Audit diagnostics suggest a high-volume down bar closing off the low; "
            "review as a Stopping Volume candidate before changing production rules."
        )
    if candidate_code == CANDIDATE_SPRING_OR_SHAKEOUT:
        return (
            "Audit diagnostics suggest support interaction and recovery; review whether "
            "Spring or Shakeout confirmation gates are too strict."
        )
    if candidate_code == CANDIDATE_HIGH_VOLUME_REVERSAL:
        return (
            "Audit diagnostics found high-volume reversal behavior without same-week "
            "bullish VSA evidence; review missing reversal classification."
        )
    if candidate_code == CANDIDATE_CONTEXT_CONFLICT:
        return (
            "Audit flags show current VSA evidence conflicting with active qualification; "
            "review lifecycle or invalidation behavior."
        )
    if candidate_code == CANDIDATE_STALE_EVIDENCE:
        return (
            "Audit flags show stale or structurally unconfirmed evidence; review whether "
            "the event should expire, wait for follow-through, or be invalidated."
        )
    detail = ", ".join((*diagnostics, *flags))
    return f"Audit-only review candidate selected from: {detail}"


def _iter_audit_rows(
    audit_payload: Mapping[str, Any] | Sequence[Mapping[str, Any]],
) -> Iterable[Mapping[str, Any]]:
    if isinstance(audit_payload, Mapping):
        if "results" in audit_payload:
            for result in audit_payload.get("results", []):
                yield from _iter_result_rows(result)
            return
        if "rows" in audit_payload:
            yield from _iter_result_rows(audit_payload)
            return
        yield audit_payload
        return

    for item in audit_payload:
        if "rows" in item or "results" in item:
            yield from _iter_audit_rows(item)
        else:
            yield item


def _iter_result_rows(result: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    for row in result.get("rows", []):
        yield row


def _string_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return _dedupe(str(item) for item in value)


def _int_or_default(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _count_values(values: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def _dedupe(items: Iterable[str]) -> tuple[str, ...]:
    selected: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item not in seen:
            selected.append(item)
            seen.add(item)
    return tuple(selected)
