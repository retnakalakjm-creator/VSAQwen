from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

CASE_CONFLICT_PENDING_SUPERSESSION = "conflict_pending_supersession"
CASE_SUPERSESSION_RULE_CANDIDATE = "supersession_rule_candidate"
CASE_MANUAL_LIFECYCLE_REVIEW = "manual_lifecycle_review"

TRANSITION_MARK_BEARISH_CONFLICTED = "propose_mark_bearish_conflicted_pending_supersession"
TRANSITION_SUPERSEDE_BEARISH_WITH_DEMAND = "propose_supersede_bearish_context_with_demand_review"

MANUAL_REVIEW_STATUS_UNREVIEWED = "unreviewed"
CHART_REVIEW_STATUS_PENDING = "pending_chart_review"
PRODUCTION_DECISION_STATUS_PENDING = "not_proposed_for_production"

ACTION_REVIEW_CONFLICT = "chart_review_conflict_before_invalidation_or_supersession"
ACTION_CONFIRM_SUPERSESSION = "chart_confirm_supersession_rule_candidate"
ACTION_MANUAL_REVIEW = "manual_lifecycle_chart_review"

CSV_COLUMNS = (
    "casebook_id",
    "symbol",
    "cluster_id",
    "case_type",
    "grade",
    "proposal_confidence",
    "proposed_transition",
    "recommended_casebook_action",
    "manual_review_status",
    "chart_review_status",
    "production_decision_status",
    "start_week",
    "end_week",
    "start_bar_index",
    "end_bar_index",
    "source_review_type",
    "source_priority_score",
    "demand_evidence_codes",
    "caution_evidence_codes",
    "opposing_evidence_codes",
    "event_families",
    "proposal_reasons",
    "manual_review_notes",
    "case_read",
)


@dataclass(frozen=True, slots=True)
class VSALifecycleProposalCasebookRow:
    """Audit-only casebook row for one lifecycle transition proposal."""

    casebook_id: str
    symbol: str
    cluster_id: str
    case_type: str
    grade: str
    proposal_confidence: int
    proposed_transition: str
    recommended_casebook_action: str
    manual_review_status: str
    chart_review_status: str
    production_decision_status: str
    start_week: str
    end_week: str
    start_bar_index: int
    end_bar_index: int
    source_review_type: str
    source_priority_score: int
    demand_evidence_codes: tuple[str, ...]
    caution_evidence_codes: tuple[str, ...]
    opposing_evidence_codes: tuple[str, ...]
    event_families: tuple[str, ...]
    proposal_reasons: tuple[str, ...]
    manual_review_notes: str
    case_read: str
    audit_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "audit_only": self.audit_only,
            "casebook_id": self.casebook_id,
            "symbol": self.symbol,
            "cluster_id": self.cluster_id,
            "case_type": self.case_type,
            "grade": self.grade,
            "proposal_confidence": self.proposal_confidence,
            "proposed_transition": self.proposed_transition,
            "recommended_casebook_action": self.recommended_casebook_action,
            "manual_review_status": self.manual_review_status,
            "chart_review_status": self.chart_review_status,
            "production_decision_status": self.production_decision_status,
            "start_week": self.start_week,
            "end_week": self.end_week,
            "start_bar_index": self.start_bar_index,
            "end_bar_index": self.end_bar_index,
            "source_review_type": self.source_review_type,
            "source_priority_score": self.source_priority_score,
            "demand_evidence_codes": list(self.demand_evidence_codes),
            "caution_evidence_codes": list(self.caution_evidence_codes),
            "opposing_evidence_codes": list(self.opposing_evidence_codes),
            "event_families": list(self.event_families),
            "proposal_reasons": list(self.proposal_reasons),
            "manual_review_notes": self.manual_review_notes,
            "case_read": self.case_read,
        }


@dataclass(frozen=True, slots=True)
class VSALifecycleProposalCasebookSummary:
    """Compact audit-only casebook export summary."""

    rows: tuple[VSALifecycleProposalCasebookRow, ...]
    total_input_proposals: int
    total_casebook_rows: int
    case_type_counts: dict[str, int] = field(default_factory=dict)
    proposed_transition_counts: dict[str, int] = field(default_factory=dict)
    recommended_action_counts: dict[str, int] = field(default_factory=dict)
    review_status_counts: dict[str, int] = field(default_factory=dict)
    top_casebook_items: tuple[dict[str, Any], ...] = ()
    audit_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "audit_only": self.audit_only,
            "total_input_proposals": self.total_input_proposals,
            "total_casebook_rows": self.total_casebook_rows,
            "case_type_counts": dict(self.case_type_counts),
            "proposed_transition_counts": dict(self.proposed_transition_counts),
            "recommended_action_counts": dict(self.recommended_action_counts),
            "review_status_counts": dict(self.review_status_counts),
            "top_casebook_items": [dict(item) for item in self.top_casebook_items],
            "rows": [row.to_dict() for row in self.rows],
        }


def build_vsa_lifecycle_proposal_casebook(
    payload: Mapping[str, Any] | Sequence[Mapping[str, Any]],
) -> VSALifecycleProposalCasebookSummary:
    """Create compact casebook rows from saved lifecycle proposal JSON.

    This helper consumes output from ``vsa_mixed_cluster_lifecycle_proposals.py``
    or a compatible list of proposal dictionaries. It does not load market data,
    call providers, replay scanners, mutate scanner state, persist output,
    activate detectors, alter scoring/ranking, or affect API/frontend behavior.
    """

    proposals = tuple(sorted(_extract_proposals(payload), key=_proposal_sort_key))
    rows = tuple(sorted((_casebook_row(row) for row in proposals), key=_casebook_sort_key))
    return VSALifecycleProposalCasebookSummary(
        rows=rows,
        total_input_proposals=len(proposals),
        total_casebook_rows=len(rows),
        case_type_counts=_count(row.case_type for row in rows),
        proposed_transition_counts=_count(row.proposed_transition for row in rows),
        recommended_action_counts=_count(row.recommended_casebook_action for row in rows),
        review_status_counts=_count(row.manual_review_status for row in rows),
        top_casebook_items=_top_casebook_items(rows),
    )


def render_vsa_lifecycle_proposal_casebook_csv(
    summary: VSALifecycleProposalCasebookSummary | Mapping[str, Any],
) -> str:
    """Render lifecycle proposal casebook rows to CSV."""

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(CSV_COLUMNS), lineterminator="\n")
    writer.writeheader()
    for row in _summary_rows(summary):
        writer.writerow(_csv_row(row))
    return output.getvalue()


def _casebook_row(proposal: Mapping[str, Any]) -> VSALifecycleProposalCasebookRow:
    symbol = str(proposal.get("symbol", ""))
    cluster_id = str(proposal.get("cluster_id", ""))
    proposed_transition = str(proposal.get("proposed_transition", ""))
    case_type = _case_type_for_transition(proposed_transition)
    recommended_action = _recommended_casebook_action(
        case_type=case_type,
        next_audit_step=str(proposal.get("next_audit_step", "")),
    )
    demand_codes = _string_tuple(proposal.get("demand_evidence_codes"))
    caution_codes = _string_tuple(proposal.get("caution_evidence_codes"))
    opposing_codes = _string_tuple(proposal.get("opposing_evidence_codes"))
    event_families = _string_tuple(proposal.get("event_families"))
    proposal_reasons = _string_tuple(proposal.get("proposal_reasons"))
    proposal_confidence = _int_or_default(proposal.get("proposal_confidence"), 0)
    source_priority_score = _int_or_default(proposal.get("source_priority_score"), 0)
    start_bar_index = _int_or_default(proposal.get("start_bar_index"), -1)
    end_bar_index = _int_or_default(proposal.get("end_bar_index"), start_bar_index)
    grade = str(proposal.get("grade", ""))
    source_review_type = str(proposal.get("source_review_type", ""))
    start_week = str(proposal.get("start_week", ""))
    end_week = str(proposal.get("end_week", start_week))
    casebook_id = _casebook_id(symbol=symbol, cluster_id=cluster_id, case_type=case_type)

    return VSALifecycleProposalCasebookRow(
        casebook_id=casebook_id,
        symbol=symbol,
        cluster_id=cluster_id,
        case_type=case_type,
        grade=grade,
        proposal_confidence=proposal_confidence,
        proposed_transition=proposed_transition,
        recommended_casebook_action=recommended_action,
        manual_review_status=MANUAL_REVIEW_STATUS_UNREVIEWED,
        chart_review_status=CHART_REVIEW_STATUS_PENDING,
        production_decision_status=PRODUCTION_DECISION_STATUS_PENDING,
        start_week=start_week,
        end_week=end_week,
        start_bar_index=start_bar_index,
        end_bar_index=end_bar_index,
        source_review_type=source_review_type,
        source_priority_score=source_priority_score,
        demand_evidence_codes=demand_codes,
        caution_evidence_codes=caution_codes,
        opposing_evidence_codes=opposing_codes,
        event_families=event_families,
        proposal_reasons=proposal_reasons,
        manual_review_notes="",
        case_read=_case_read(
            symbol=symbol,
            case_type=case_type,
            proposed_transition=proposed_transition,
            recommended_action=recommended_action,
            demand_codes=demand_codes,
            caution_codes=caution_codes,
            event_families=event_families,
            start_week=start_week,
            end_week=end_week,
        ),
    )


def _case_type_for_transition(proposed_transition: str) -> str:
    if proposed_transition == TRANSITION_MARK_BEARISH_CONFLICTED:
        return CASE_CONFLICT_PENDING_SUPERSESSION
    if proposed_transition == TRANSITION_SUPERSEDE_BEARISH_WITH_DEMAND:
        return CASE_SUPERSESSION_RULE_CANDIDATE
    return CASE_MANUAL_LIFECYCLE_REVIEW


def _recommended_casebook_action(*, case_type: str, next_audit_step: str) -> str:
    if next_audit_step:
        return next_audit_step
    if case_type == CASE_SUPERSESSION_RULE_CANDIDATE:
        return ACTION_CONFIRM_SUPERSESSION
    if case_type == CASE_CONFLICT_PENDING_SUPERSESSION:
        return ACTION_REVIEW_CONFLICT
    return ACTION_MANUAL_REVIEW


def _casebook_id(*, symbol: str, cluster_id: str, case_type: str) -> str:
    return f"{symbol}:{case_type}:{cluster_id}"


def _case_read(
    *,
    symbol: str,
    case_type: str,
    proposed_transition: str,
    recommended_action: str,
    demand_codes: tuple[str, ...],
    caution_codes: tuple[str, ...],
    event_families: tuple[str, ...],
    start_week: str,
    end_week: str,
) -> str:
    period = start_week if start_week == end_week else f"{start_week} to {end_week}"
    return (
        f"{symbol} casebook item is {case_type} for {period}. "
        f"Proposed transition: {proposed_transition}. "
        f"Families: {_join_or_none(event_families)}. "
        f"Demand evidence: {_join_or_none(demand_codes)}. "
        f"Caution evidence: {_join_or_none(caution_codes)}. "
        f"Manual status: {MANUAL_REVIEW_STATUS_UNREVIEWED}; "
        f"next action: {recommended_action}."
    )


def _extract_proposals(payload: Mapping[str, Any] | Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    if isinstance(payload, Mapping):
        if "rows" in payload:
            return tuple(dict(item) for item in _mapping_sequence(payload.get("rows")))
        return (dict(payload),)
    return tuple(dict(item) for item in payload if isinstance(item, Mapping))


def _summary_rows(summary: VSALifecycleProposalCasebookSummary | Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    if isinstance(summary, VSALifecycleProposalCasebookSummary):
        return tuple(row.to_dict() for row in summary.rows)
    return tuple(dict(item) for item in _mapping_sequence(summary.get("rows")))


def _csv_row(row: Mapping[str, Any]) -> dict[str, str]:
    output: dict[str, str] = {}
    for column in CSV_COLUMNS:
        value = row.get(column, "")
        if isinstance(value, (list, tuple)):
            output[column] = ";".join(str(item) for item in value)
        else:
            output[column] = str(value)
    return output


def _top_casebook_items(rows: Sequence[VSALifecycleProposalCasebookRow], *, limit: int = 10) -> tuple[dict[str, Any], ...]:
    ordered = sorted(rows, key=_casebook_sort_key)[:limit]
    return tuple(
        {
            "casebook_id": row.casebook_id,
            "symbol": row.symbol,
            "cluster_id": row.cluster_id,
            "case_type": row.case_type,
            "proposal_confidence": row.proposal_confidence,
            "source_priority_score": row.source_priority_score,
            "proposed_transition": row.proposed_transition,
            "recommended_casebook_action": row.recommended_casebook_action,
        }
        for row in ordered
    )


def _casebook_sort_key(row: VSALifecycleProposalCasebookRow) -> tuple[int, int, str, str]:
    return (-row.proposal_confidence, -row.source_priority_score, row.symbol, row.cluster_id)


def _proposal_sort_key(row: Mapping[str, Any]) -> tuple[int, int, str, str]:
    return (
        -_int_or_default(row.get("proposal_confidence"), 0),
        -_int_or_default(row.get("source_priority_score"), 0),
        str(row.get("symbol", "")),
        str(row.get("cluster_id", "")),
    )


def _mapping_sequence(value: Any) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def _string_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,) if value else ()
    if isinstance(value, Iterable):
        return tuple(str(item) for item in value if str(item))
    return (str(value),) if str(value) else ()


def _int_or_default(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _count(values: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def _join_or_none(values: Sequence[str]) -> str:
    return ", ".join(values) if values else "none"
