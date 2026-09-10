from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from vsa_qualification_lifecycle_audit import (
    LIFECYCLE_ACTIVE,
    LIFECYCLE_CONFLICTED,
    LIFECYCLE_EXPIRED_REVIEW,
    LIFECYCLE_INVALIDATED_REVIEW,
    LIFECYCLE_NEEDS_FOLLOW_THROUGH,
    build_qualification_lifecycle_audit,
)

TRANSITION_KEEP_ACTIVE = "keep_active"
TRANSITION_MARK_CONFLICTED = "mark_conflicted"
TRANSITION_INVALIDATE_QUALIFICATION = "invalidate_qualification"
TRANSITION_EXPIRE_QUALIFICATION = "expire_qualification"
TRANSITION_WAIT_FOR_FOLLOW_THROUGH = "wait_for_follow_through"

CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_LOW = "low"

CSV_COLUMNS = (
    "symbol",
    "replay_week",
    "replay_bar_index",
    "qualification",
    "qualification_side",
    "current_vsa_bias",
    "lifecycle_status",
    "proposed_action",
    "proposal_grade",
    "proposal_score",
    "proposal_confidence",
    "supporting_event_codes",
    "opposing_event_codes",
    "target_event_codes",
    "scoring_event_codes",
    "candidate_families",
    "candidate_codes",
    "source_audit_flags",
    "source_lifecycle_reason",
    "proposal_reason",
    "guardrails",
    "recommended_action",
)


@dataclass(frozen=True, slots=True)
class QualificationTransitionProposalRow:
    """Audit-only proposed transition for one qualification lifecycle row.

    This object is a review artifact. It does not mutate scanner state, activate
    detectors, change ranking/scoring, persist anything, or affect frontend/API
    production behavior.
    """

    symbol: str
    replay_week: str
    replay_bar_index: int
    qualification: str
    qualification_side: str
    current_vsa_bias: str
    lifecycle_status: str
    proposed_action: str
    proposal_grade: str
    proposal_score: int
    proposal_confidence: str
    supporting_event_codes: tuple[str, ...]
    opposing_event_codes: tuple[str, ...]
    target_event_codes: tuple[str, ...]
    scoring_event_codes: tuple[str, ...]
    candidate_families: tuple[str, ...]
    candidate_codes: tuple[str, ...]
    source_audit_flags: tuple[str, ...]
    source_lifecycle_reason: str
    proposal_reason: str
    guardrails: tuple[str, ...]
    recommended_action: str
    audit_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "replay_week": self.replay_week,
            "replay_bar_index": self.replay_bar_index,
            "qualification": self.qualification,
            "qualification_side": self.qualification_side,
            "current_vsa_bias": self.current_vsa_bias,
            "lifecycle_status": self.lifecycle_status,
            "proposed_action": self.proposed_action,
            "proposal_grade": self.proposal_grade,
            "proposal_score": self.proposal_score,
            "proposal_confidence": self.proposal_confidence,
            "supporting_event_codes": list(self.supporting_event_codes),
            "opposing_event_codes": list(self.opposing_event_codes),
            "target_event_codes": list(self.target_event_codes),
            "scoring_event_codes": list(self.scoring_event_codes),
            "candidate_families": list(self.candidate_families),
            "candidate_codes": list(self.candidate_codes),
            "source_audit_flags": list(self.source_audit_flags),
            "source_lifecycle_reason": self.source_lifecycle_reason,
            "proposal_reason": self.proposal_reason,
            "guardrails": list(self.guardrails),
            "recommended_action": self.recommended_action,
            "audit_only": self.audit_only,
        }


@dataclass(frozen=True, slots=True)
class QualificationTransitionProposalSummary:
    """Compact audit-only summary of proposed qualification transitions."""

    rows: tuple[QualificationTransitionProposalRow, ...]
    total_input_rows: int
    total_proposal_rows: int
    min_priority: str
    include_active: bool
    action_counts: dict[str, int] = field(default_factory=dict)
    status_counts: dict[str, int] = field(default_factory=dict)
    grade_counts: dict[str, int] = field(default_factory=dict)
    confidence_counts: dict[str, int] = field(default_factory=dict)
    qualification_counts: dict[str, int] = field(default_factory=dict)
    symbol_counts: dict[str, int] = field(default_factory=dict)
    week_counts: dict[str, int] = field(default_factory=dict)
    transition_focus: tuple[dict[str, Any], ...] = ()
    top_transition_symbols: tuple[dict[str, Any], ...] = ()
    audit_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "audit_only": self.audit_only,
            "min_priority": self.min_priority,
            "include_active": self.include_active,
            "total_input_rows": self.total_input_rows,
            "total_proposal_rows": self.total_proposal_rows,
            "action_counts": dict(self.action_counts),
            "status_counts": dict(self.status_counts),
            "grade_counts": dict(self.grade_counts),
            "confidence_counts": dict(self.confidence_counts),
            "qualification_counts": dict(self.qualification_counts),
            "symbol_counts": dict(self.symbol_counts),
            "week_counts": dict(self.week_counts),
            "transition_focus": [dict(row) for row in self.transition_focus],
            "top_transition_symbols": [dict(row) for row in self.top_transition_symbols],
            "rows": [row.to_dict() for row in self.rows],
        }


def build_qualification_transition_proposals(
    payload: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    *,
    min_priority: str = "high",
    include_active: bool = False,
) -> QualificationTransitionProposalSummary:
    """Build audit-only proposed actions from qualification lifecycle rows.

    Input may be raw audit JSON, candidate-event JSON, batch-review JSON, triage
    JSON, or lifecycle-audit JSON. The helper reuses the PR #79 lifecycle audit
    path when needed and emits review proposals only.
    """

    lifecycle_rows = _coerce_lifecycle_rows(
        payload,
        min_priority=min_priority,
        include_active=include_active,
    )
    proposal_rows = tuple(
        sorted(
            (_build_proposal_row(row) for row in lifecycle_rows),
            key=_proposal_sort_key,
        )
    )
    return QualificationTransitionProposalSummary(
        rows=proposal_rows,
        total_input_rows=_total_input_rows(payload, lifecycle_rows),
        total_proposal_rows=len(proposal_rows),
        min_priority=min_priority,
        include_active=include_active,
        action_counts=_count(row.proposed_action for row in proposal_rows),
        status_counts=_count(row.lifecycle_status for row in proposal_rows),
        grade_counts=_count(row.proposal_grade for row in proposal_rows),
        confidence_counts=_count(row.proposal_confidence for row in proposal_rows),
        qualification_counts=_count(row.qualification_side for row in proposal_rows),
        symbol_counts=_count(row.symbol for row in proposal_rows),
        week_counts=_count(row.replay_week for row in proposal_rows),
        transition_focus=_transition_focus(proposal_rows),
        top_transition_symbols=_top_transition_symbols(proposal_rows),
    )


def render_qualification_transition_proposals_csv(
    summary: QualificationTransitionProposalSummary | Mapping[str, Any],
) -> str:
    """Render proposal rows to CSV for review."""

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(CSV_COLUMNS), lineterminator="\n")
    writer.writeheader()
    for row in _summary_rows(summary):
        writer.writerow(_csv_row(row))
    return output.getvalue()


def _coerce_lifecycle_rows(
    payload: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    *,
    min_priority: str,
    include_active: bool,
) -> tuple[dict[str, Any], ...]:
    if isinstance(payload, Mapping) and _looks_like_lifecycle_summary(payload):
        rows = tuple(_mapping_rows(payload.get("rows", ())))
    elif (
        isinstance(payload, Sequence)
        and not isinstance(payload, (str, bytes))
        and payload
        and all(isinstance(item, Mapping) and "lifecycle_status" in item for item in payload)
    ):
        rows = tuple(dict(item) for item in payload)
    else:
        lifecycle = build_qualification_lifecycle_audit(
            payload,
            min_priority=min_priority,
            include_active=include_active,
        )
        rows = tuple(row.to_dict() for row in lifecycle.rows)

    if not include_active:
        rows = tuple(row for row in rows if row.get("lifecycle_status") != LIFECYCLE_ACTIVE)
    return rows


def _looks_like_lifecycle_summary(payload: Mapping[str, Any]) -> bool:
    rows = payload.get("rows")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        return False
    return any(isinstance(row, Mapping) and "lifecycle_status" in row for row in rows)


def _build_proposal_row(row: Mapping[str, Any]) -> QualificationTransitionProposalRow:
    lifecycle_status = str(row.get("lifecycle_status", ""))
    proposed_action = _proposal_action(lifecycle_status)
    grade = _proposal_grade(proposed_action)
    confidence = _proposal_confidence(proposed_action)
    return QualificationTransitionProposalRow(
        symbol=str(row.get("symbol", "")),
        replay_week=str(row.get("replay_week", "")),
        replay_bar_index=_int_or_default(row.get("replay_bar_index"), -1),
        qualification=str(row.get("qualification", "")),
        qualification_side=str(row.get("qualification_side", "")),
        current_vsa_bias=str(row.get("current_vsa_bias", "")),
        lifecycle_status=lifecycle_status,
        proposed_action=proposed_action,
        proposal_grade=grade,
        proposal_score=_proposal_score(proposed_action, grade),
        proposal_confidence=confidence,
        supporting_event_codes=_string_tuple(row.get("supporting_event_codes")),
        opposing_event_codes=_string_tuple(row.get("opposing_event_codes")),
        target_event_codes=_string_tuple(row.get("target_event_codes")),
        scoring_event_codes=_string_tuple(row.get("scoring_event_codes")),
        candidate_families=_string_tuple(row.get("candidate_families")),
        candidate_codes=_string_tuple(row.get("candidate_codes")),
        source_audit_flags=_string_tuple(row.get("source_audit_flags")),
        source_lifecycle_reason=str(row.get("reason", "")),
        proposal_reason=_proposal_reason(proposed_action, row),
        guardrails=_guardrails(proposed_action),
        recommended_action=_recommended_action(proposed_action),
    )


def _proposal_action(lifecycle_status: str) -> str:
    if lifecycle_status == LIFECYCLE_INVALIDATED_REVIEW:
        return TRANSITION_INVALIDATE_QUALIFICATION
    if lifecycle_status == LIFECYCLE_CONFLICTED:
        return TRANSITION_MARK_CONFLICTED
    if lifecycle_status == LIFECYCLE_EXPIRED_REVIEW:
        return TRANSITION_EXPIRE_QUALIFICATION
    if lifecycle_status == LIFECYCLE_NEEDS_FOLLOW_THROUGH:
        return TRANSITION_WAIT_FOR_FOLLOW_THROUGH
    if lifecycle_status == LIFECYCLE_ACTIVE:
        return TRANSITION_KEEP_ACTIVE
    return TRANSITION_MARK_CONFLICTED


def _proposal_grade(action: str) -> str:
    if action in {TRANSITION_INVALIDATE_QUALIFICATION, TRANSITION_MARK_CONFLICTED}:
        return "A"
    if action in {TRANSITION_EXPIRE_QUALIFICATION, TRANSITION_WAIT_FOR_FOLLOW_THROUGH}:
        return "B"
    return "C"


def _proposal_score(action: str, grade: str) -> int:
    if action == TRANSITION_INVALIDATE_QUALIFICATION:
        return 96
    if action == TRANSITION_MARK_CONFLICTED:
        return 92
    if action == TRANSITION_EXPIRE_QUALIFICATION:
        return 82
    if action == TRANSITION_WAIT_FOR_FOLLOW_THROUGH:
        return 74
    return 50 if grade == "C" else 60


def _proposal_confidence(action: str) -> str:
    if action in {TRANSITION_INVALIDATE_QUALIFICATION, TRANSITION_MARK_CONFLICTED}:
        return CONFIDENCE_HIGH
    if action in {TRANSITION_EXPIRE_QUALIFICATION, TRANSITION_WAIT_FOR_FOLLOW_THROUGH}:
        return CONFIDENCE_MEDIUM
    return CONFIDENCE_LOW


def _recommended_action(action: str) -> str:
    if action == TRANSITION_INVALIDATE_QUALIFICATION:
        return "design production invalidation rule with point-in-time guards"
    if action == TRANSITION_MARK_CONFLICTED:
        return "design conflicted-state story label before changing qualification"
    if action == TRANSITION_EXPIRE_QUALIFICATION:
        return "design qualification expiry when current support disappears"
    if action == TRANSITION_WAIT_FOR_FOLLOW_THROUGH:
        return "keep qualification pending until follow-through confirms the challenge"
    return "keep qualification active while current same-side evidence supports it"


def _proposal_reason(action: str, row: Mapping[str, Any]) -> str:
    side = str(row.get("qualification_side", "qualification"))
    bias = str(row.get("current_vsa_bias", "current evidence"))
    if action == TRANSITION_INVALIDATE_QUALIFICATION:
        return f"propose invalidating {side} qualification because current VSA bias is {bias} with no same-side support"
    if action == TRANSITION_MARK_CONFLICTED:
        return f"propose marking {side} qualification conflicted because current VSA evidence is mixed or contradictory"
    if action == TRANSITION_EXPIRE_QUALIFICATION:
        return f"propose expiring {side} qualification because fresh supporting evidence is absent"
    if action == TRANSITION_WAIT_FOR_FOLLOW_THROUGH:
        return f"propose waiting because {side} qualification has an opposing challenge that still needs follow-through"
    return f"propose keeping {side} qualification active because it is still supported"


def _guardrails(action: str) -> tuple[str, ...]:
    common = (
        "audit-only proposal; do not mutate scanner state from this helper",
        "do not activate Effort-vs-Result, absorption, or high-volume reversal as production evidence in this PR",
    )
    if action == TRANSITION_INVALIDATE_QUALIFICATION:
        return common + (
            "require completed weekly bars only before production implementation",
            "verify opposing evidence is fresh and not stale fallback scoring evidence",
        )
    if action == TRANSITION_MARK_CONFLICTED:
        return common + (
            "preserve the original qualification until a separate production rule is implemented",
            "show mixed evidence as context rather than flipping bias immediately",
        )
    if action == TRANSITION_EXPIRE_QUALIFICATION:
        return common + (
            "expire only when fresh same-side evidence has disappeared for the chosen window",
            "avoid replacing expiry with an opposite qualification without separate confirmation",
        )
    if action == TRANSITION_WAIT_FOR_FOLLOW_THROUGH:
        return common + (
            "wait for later completed bars to confirm or reject the challenge",
            "do not downgrade qualification from one candidate bar alone",
        )
    return common + (
        "keep active labels separate from proposed invalidation rows",
        "continue monitoring for later opposing completed-bar evidence",
    )


def _summary_rows(
    summary: QualificationTransitionProposalSummary | Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    if isinstance(summary, QualificationTransitionProposalSummary):
        return tuple(row.to_dict() for row in summary.rows)
    return tuple(_mapping_rows(summary.get("rows", ())))


def _csv_row(row: Mapping[str, Any]) -> dict[str, str]:
    return {column: _csv_value(row.get(column)) for column in CSV_COLUMNS}


def _transition_focus(
    rows: tuple[QualificationTransitionProposalRow, ...],
) -> tuple[dict[str, Any], ...]:
    grouped: dict[str, list[QualificationTransitionProposalRow]] = {}
    for row in rows:
        grouped.setdefault(row.proposed_action, []).append(row)

    selected: list[dict[str, Any]] = []
    for action, action_rows in grouped.items():
        selected.append(
            {
                "proposed_action": action,
                "total_rows": len(action_rows),
                "grade_counts": _count(row.proposal_grade for row in action_rows),
                "confidence_counts": _count(row.proposal_confidence for row in action_rows),
                "status_counts": _count(row.lifecycle_status for row in action_rows),
                "qualification_counts": _count(row.qualification_side for row in action_rows),
                "symbols": sorted(_unique(row.symbol for row in action_rows)),
                "recommended_action": _recommended_action(action),
            }
        )
    return tuple(
        sorted(
            selected,
            key=lambda item: (
                _action_rank(str(item["proposed_action"])),
                -int(item["total_rows"]),
            ),
        )
    )


def _top_transition_symbols(
    rows: tuple[QualificationTransitionProposalRow, ...],
) -> tuple[dict[str, Any], ...]:
    grouped: dict[str, list[QualificationTransitionProposalRow]] = {}
    for row in rows:
        grouped.setdefault(row.symbol, []).append(row)

    selected: list[dict[str, Any]] = []
    for symbol, symbol_rows in grouped.items():
        selected.append(
            {
                "symbol": symbol,
                "total_rows": len(symbol_rows),
                "action_counts": _count(row.proposed_action for row in symbol_rows),
                "status_counts": _count(row.lifecycle_status for row in symbol_rows),
                "grade_counts": _count(row.proposal_grade for row in symbol_rows),
                "highest_grade": min((row.proposal_grade for row in symbol_rows), key=_grade_rank),
            }
        )
    return tuple(
        sorted(
            selected,
            key=lambda item: (
                _grade_rank(str(item["highest_grade"])),
                -int(item["total_rows"]),
                str(item["symbol"]),
            ),
        )
    )


def _proposal_sort_key(row: QualificationTransitionProposalRow) -> tuple[int, int, str, str, int]:
    return (
        _action_rank(row.proposed_action),
        _grade_rank(row.proposal_grade),
        row.symbol,
        row.replay_week,
        row.replay_bar_index,
    )


def _action_rank(action: str) -> int:
    return {
        TRANSITION_INVALIDATE_QUALIFICATION: 0,
        TRANSITION_MARK_CONFLICTED: 1,
        TRANSITION_EXPIRE_QUALIFICATION: 2,
        TRANSITION_WAIT_FOR_FOLLOW_THROUGH: 3,
        TRANSITION_KEEP_ACTIVE: 4,
    }.get(action, 99)


def _grade_rank(grade: str) -> int:
    return {"A": 0, "B": 1, "C": 2, "D": 3}.get(grade, 99)


def _total_input_rows(
    payload: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    lifecycle_rows: tuple[dict[str, Any], ...],
) -> int:
    if isinstance(payload, Mapping):
        value = payload.get("total_input_rows")
        if value is None:
            value = payload.get("total_lifecycle_rows")
        if value is None:
            value = payload.get("total_proposal_rows")
        if value is not None:
            return _int_or_default(value, len(lifecycle_rows))
    return len(lifecycle_rows)


def _mapping_rows(rows: Iterable[Any]) -> Iterable[dict[str, Any]]:
    for row in rows:
        if isinstance(row, Mapping):
            yield dict(row)


def _string_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,) if value else ()
    try:
        return _dedupe(str(item) for item in value if str(item or ""))
    except TypeError:
        text = str(value)
        return (text,) if text else ()


def _dedupe(items: Iterable[str]) -> tuple[str, ...]:
    selected: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item not in seen:
            selected.append(item)
            seen.add(item)
    return tuple(selected)


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    return _dedupe(str(value) for value in values if str(value or ""))


def _count(values: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        text = str(value or "")
        if not text:
            continue
        counts[text] = counts.get(text, 0) + 1
    return counts


def _int_or_default(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return "|".join(str(item) for item in value)
    return str(value)
