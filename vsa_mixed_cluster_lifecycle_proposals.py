from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

REVIEW_BEARISH_CONTEXT_DEMAND_REVERSAL_CLUSTER = "bearish_context_demand_reversal_cluster"
REVIEW_BULLISH_CONTEXT_SUPPLY_WARNING_CLUSTER = "bullish_context_supply_warning_cluster"
REVIEW_UNQUALIFIED_BIDIRECTIONAL_DETECTOR_CONFLICT = "unqualified_bidirectional_detector_conflict"

ACTION_REVIEW_LIFECYCLE_INVALIDATION = "review_lifecycle_invalidation_or_supersession"
ACTION_REVIEW_SUPPLY_WARNING = "review_supply_warning_against_active_bullish_context"
ACTION_REVIEW_DETECTOR_GATES = "review_detector_gates_before_activation"

PROPOSAL_MARK_BEARISH_CONFLICTED_PENDING_SUPERSESSION = "propose_mark_bearish_conflicted_pending_supersession"
PROPOSAL_INVALIDATE_BEARISH_QUALIFICATION = "propose_invalidate_bearish_qualification"
PROPOSAL_SUPERSEDE_BEARISH_WITH_DEMAND_REVIEW = "propose_supersede_bearish_context_with_demand_review"
PROPOSAL_DEFER_SUPPLY_WARNING = "defer_bullish_supply_warning_to_detector_gate_review"
PROPOSAL_DEFER_DETECTOR_GATE = "defer_unqualified_detector_conflict_to_gate_review"

DEMAND_CODES = frozenset(
    {
        "stopping_volume",
        "selling_climax",
        "shakeout",
        "spring",
        "test",
        "no_supply",
        "hidden_demand",
        "increasing_demand",
        "demand_coming_in",
        "absorption",
        "result_gt_effort",
    }
)

SUPPLY_CODES = frozenset(
    {
        "buying_climax",
        "upthrust",
        "no_demand",
        "hidden_supply",
        "increasing_supply",
        "supply_coming_in",
        "effort_gt_result",
    }
)

STRUCTURE_CODES = frozenset(
    {
        "structural_progression_weakening",
        "structural_progression_improving",
    }
)

CSV_COLUMNS = (
    "symbol",
    "cluster_id",
    "start_week",
    "end_week",
    "start_bar_index",
    "end_bar_index",
    "grade",
    "source_review_type",
    "source_priority_score",
    "proposed_transition",
    "proposal_confidence",
    "next_audit_step",
    "qualifications",
    "event_families",
    "demand_evidence_codes",
    "opposing_evidence_codes",
    "caution_evidence_codes",
    "proposal_reasons",
    "proposal_read",
)


@dataclass(frozen=True, slots=True)
class VSAMixedClusterLifecycleProposalRow:
    """Audit-only lifecycle proposal derived from one graded mixed-event cluster."""

    symbol: str
    cluster_id: str
    start_week: str
    end_week: str
    start_bar_index: int
    end_bar_index: int
    grade: str
    source_review_type: str
    source_priority_score: int
    proposed_transition: str
    proposal_confidence: int
    next_audit_step: str
    qualifications: tuple[str, ...]
    event_families: tuple[str, ...]
    demand_evidence_codes: tuple[str, ...]
    opposing_evidence_codes: tuple[str, ...]
    caution_evidence_codes: tuple[str, ...]
    proposal_reasons: tuple[str, ...]
    proposal_read: str
    audit_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "audit_only": self.audit_only,
            "symbol": self.symbol,
            "cluster_id": self.cluster_id,
            "start_week": self.start_week,
            "end_week": self.end_week,
            "start_bar_index": self.start_bar_index,
            "end_bar_index": self.end_bar_index,
            "grade": self.grade,
            "source_review_type": self.source_review_type,
            "source_priority_score": self.source_priority_score,
            "proposed_transition": self.proposed_transition,
            "proposal_confidence": self.proposal_confidence,
            "next_audit_step": self.next_audit_step,
            "qualifications": list(self.qualifications),
            "event_families": list(self.event_families),
            "demand_evidence_codes": list(self.demand_evidence_codes),
            "opposing_evidence_codes": list(self.opposing_evidence_codes),
            "caution_evidence_codes": list(self.caution_evidence_codes),
            "proposal_reasons": list(self.proposal_reasons),
            "proposal_read": self.proposal_read,
        }


@dataclass(frozen=True, slots=True)
class VSAMixedClusterLifecycleProposalSummary:
    """Compact audit-only summary for mixed-cluster lifecycle proposals."""

    rows: tuple[VSAMixedClusterLifecycleProposalRow, ...]
    total_input_clusters: int
    total_lifecycle_proposals: int
    transition_counts: dict[str, int] = field(default_factory=dict)
    next_audit_step_counts: dict[str, int] = field(default_factory=dict)
    skipped_cluster_counts: dict[str, int] = field(default_factory=dict)
    top_lifecycle_proposals: tuple[dict[str, Any], ...] = ()
    audit_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "audit_only": self.audit_only,
            "total_input_clusters": self.total_input_clusters,
            "total_lifecycle_proposals": self.total_lifecycle_proposals,
            "transition_counts": dict(self.transition_counts),
            "next_audit_step_counts": dict(self.next_audit_step_counts),
            "skipped_cluster_counts": dict(self.skipped_cluster_counts),
            "top_lifecycle_proposals": [dict(row) for row in self.top_lifecycle_proposals],
            "rows": [row.to_dict() for row in self.rows],
        }


def build_vsa_mixed_cluster_lifecycle_proposals(
    payload: Mapping[str, Any] | Sequence[Mapping[str, Any]],
) -> VSAMixedClusterLifecycleProposalSummary:
    """Extract audit-only lifecycle proposals from graded mixed-cluster output.

    This helper consumes saved output from ``vsa_mixed_cluster_grading.py`` or a
    compatible list of graded cluster dictionaries. It does not load market data,
    call providers, replay scanners, mutate scanner state, persist output,
    activate detectors, alter scoring/ranking, or affect API/frontend behavior.
    """

    clusters = tuple(sorted(_extract_rows(payload), key=_row_sort_key))
    rows = tuple(
        sorted(
            (_build_proposal(row) for row in clusters if _is_lifecycle_candidate(row)),
            key=_proposal_sort_key,
        )
    )
    skipped_counts = _skipped_counts(clusters)
    return VSAMixedClusterLifecycleProposalSummary(
        rows=rows,
        total_input_clusters=len(clusters),
        total_lifecycle_proposals=len(rows),
        transition_counts=_count(row.proposed_transition for row in rows),
        next_audit_step_counts=_count(row.next_audit_step for row in rows),
        skipped_cluster_counts=skipped_counts,
        top_lifecycle_proposals=_top_lifecycle_proposals(rows),
    )


def render_vsa_mixed_cluster_lifecycle_proposals_csv(
    summary: VSAMixedClusterLifecycleProposalSummary | Mapping[str, Any],
) -> str:
    """Render lifecycle proposals to CSV for manual casebook review."""

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(CSV_COLUMNS), lineterminator="\n")
    writer.writeheader()
    for row in _summary_rows(summary):
        writer.writerow(_csv_row(row))
    return output.getvalue()


def _is_lifecycle_candidate(row: Mapping[str, Any]) -> bool:
    return (
        str(row.get("review_type", "")) == REVIEW_BEARISH_CONTEXT_DEMAND_REVERSAL_CLUSTER
        or str(row.get("recommended_action", "")) == ACTION_REVIEW_LIFECYCLE_INVALIDATION
    )


def _build_proposal(row: Mapping[str, Any]) -> VSAMixedClusterLifecycleProposalRow:
    qualifications = _string_tuple(row.get("qualifications"))
    event_families = _string_tuple(row.get("event_families"))
    supporting = _string_tuple(row.get("supporting_event_codes"))
    opposing = _string_tuple(row.get("opposing_event_codes"))
    demand_codes = _matching_codes(supporting, DEMAND_CODES)
    caution_codes = _matching_codes(opposing, SUPPLY_CODES | STRUCTURE_CODES)
    source_priority = _int_or_default(row.get("priority_score"), 0)
    proposed_transition, next_step, reasons = _classify_transition(
        qualifications=qualifications,
        event_families=event_families,
        demand_codes=demand_codes,
        opposing_codes=opposing,
        caution_codes=caution_codes,
        source_priority=source_priority,
    )
    confidence = _proposal_confidence(
        proposed_transition=proposed_transition,
        source_priority=source_priority,
        event_families=event_families,
        demand_codes=demand_codes,
        caution_codes=caution_codes,
    )
    return VSAMixedClusterLifecycleProposalRow(
        symbol=str(row.get("symbol", "")),
        cluster_id=str(row.get("cluster_id", "")),
        start_week=str(row.get("start_week", "")),
        end_week=str(row.get("end_week", row.get("start_week", ""))),
        start_bar_index=_int_or_default(row.get("start_bar_index"), -1),
        end_bar_index=_int_or_default(row.get("end_bar_index"), -1),
        grade=str(row.get("grade", "")),
        source_review_type=str(row.get("review_type", "")),
        source_priority_score=source_priority,
        proposed_transition=proposed_transition,
        proposal_confidence=confidence,
        next_audit_step=next_step,
        qualifications=qualifications,
        event_families=event_families,
        demand_evidence_codes=demand_codes,
        opposing_evidence_codes=opposing,
        caution_evidence_codes=caution_codes,
        proposal_reasons=reasons,
        proposal_read=_proposal_read(
            symbol=str(row.get("symbol", "")),
            proposed_transition=proposed_transition,
            confidence=confidence,
            qualifications=qualifications,
            demand_codes=demand_codes,
            caution_codes=caution_codes,
            next_step=next_step,
        ),
    )


def _classify_transition(
    *,
    qualifications: tuple[str, ...],
    event_families: tuple[str, ...],
    demand_codes: tuple[str, ...],
    opposing_codes: tuple[str, ...],
    caution_codes: tuple[str, ...],
    source_priority: int,
) -> tuple[str, str, tuple[str, ...]]:
    reasons: list[str] = []
    has_persistent_bearish = "persistent_bearish" in qualifications
    has_multiple_reversal_families = len(set(event_families)) >= 2
    has_structure_caution = any(code in STRUCTURE_CODES for code in caution_codes)
    has_supply_caution = any(code in SUPPLY_CODES for code in caution_codes)
    has_demand_pair = {"increasing_demand", "demand_coming_in"}.issubset(set(demand_codes))

    if not has_persistent_bearish:
        reasons.append("cluster is not a persistent-bearish lifecycle candidate")
        return (
            PROPOSAL_DEFER_DETECTOR_GATE,
            "defer_to_non_lifecycle_cluster_review",
            tuple(reasons),
        )

    reasons.append("persistent bearish qualification is challenged by demand/reversal evidence")
    if has_demand_pair:
        reasons.append("both increasing demand and demand coming in appear in the cluster evidence")
    if has_multiple_reversal_families:
        reasons.append("multiple reversal/absorption families support a lifecycle review")
    if has_structure_caution:
        reasons.append("bearish structure evidence remains, so do not treat the case as a clean bullish activation")
    if has_supply_caution:
        reasons.append("supply evidence remains, so review conflict/supersession before changing production behavior")

    if not caution_codes:
        return (
            PROPOSAL_INVALIDATE_BEARISH_QUALIFICATION,
            "chart_confirm_bearish_invalidation_rule_candidate",
            tuple(reasons),
        )
    if source_priority >= 95 and has_demand_pair and has_multiple_reversal_families and not has_structure_caution:
        return (
            PROPOSAL_SUPERSEDE_BEARISH_WITH_DEMAND_REVIEW,
            "chart_confirm_supersession_rule_candidate",
            tuple(reasons),
        )
    return (
        PROPOSAL_MARK_BEARISH_CONFLICTED_PENDING_SUPERSESSION,
        "chart_review_conflict_before_invalidation_or_supersession",
        tuple(reasons),
    )


def _proposal_confidence(
    *,
    proposed_transition: str,
    source_priority: int,
    event_families: tuple[str, ...],
    demand_codes: tuple[str, ...],
    caution_codes: tuple[str, ...],
) -> int:
    confidence = min(source_priority, 90)
    if proposed_transition == PROPOSAL_MARK_BEARISH_CONFLICTED_PENDING_SUPERSESSION:
        confidence += 8
    elif proposed_transition == PROPOSAL_INVALIDATE_BEARISH_QUALIFICATION:
        confidence += 5
    elif proposed_transition == PROPOSAL_SUPERSEDE_BEARISH_WITH_DEMAND_REVIEW:
        confidence += 10
    if len(set(event_families)) >= 3:
        confidence += 4
    if {"increasing_demand", "demand_coming_in"}.issubset(set(demand_codes)):
        confidence += 4
    if any(code in STRUCTURE_CODES for code in caution_codes):
        confidence += 2
    return min(confidence, 100)


def _skipped_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    skipped: list[str] = []
    for row in rows:
        if _is_lifecycle_candidate(row):
            continue
        action = str(row.get("recommended_action", ""))
        review_type = str(row.get("review_type", ""))
        if action == ACTION_REVIEW_DETECTOR_GATES or review_type == REVIEW_UNQUALIFIED_BIDIRECTIONAL_DETECTOR_CONFLICT:
            skipped.append("detector_gate_review")
        elif action == ACTION_REVIEW_SUPPLY_WARNING or review_type == REVIEW_BULLISH_CONTEXT_SUPPLY_WARNING_CLUSTER:
            skipped.append("active_bullish_supply_warning_review")
        else:
            skipped.append("other_mixed_cluster_review")
    return _count(skipped)


def _proposal_read(
    *,
    symbol: str,
    proposed_transition: str,
    confidence: int,
    qualifications: tuple[str, ...],
    demand_codes: tuple[str, ...],
    caution_codes: tuple[str, ...],
    next_step: str,
) -> str:
    return (
        f"{symbol} proposes {proposed_transition} with confidence {confidence}. "
        f"Qualification: {_join_or_none(qualifications)}. "
        f"Demand/reversal evidence: {_join_or_none(demand_codes)}. "
        f"Caution evidence: {_join_or_none(caution_codes)}. "
        f"Next audit step: {next_step}."
    )


def _extract_rows(payload: Mapping[str, Any] | Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    if isinstance(payload, Mapping):
        if "rows" in payload:
            return tuple(dict(item) for item in _mapping_sequence(payload.get("rows")))
        if "clusters" in payload:
            return tuple(dict(item) for item in _mapping_sequence(payload.get("clusters")))
        return (dict(payload),)
    return tuple(dict(item) for item in payload)


def _summary_rows(summary: VSAMixedClusterLifecycleProposalSummary | Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    if isinstance(summary, VSAMixedClusterLifecycleProposalSummary):
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


def _top_lifecycle_proposals(
    rows: Sequence[VSAMixedClusterLifecycleProposalRow],
    *,
    limit: int = 10,
) -> tuple[dict[str, Any], ...]:
    ordered = sorted(rows, key=lambda row: (-row.proposal_confidence, -row.source_priority_score, row.symbol, row.cluster_id))[:limit]
    return tuple(
        {
            "symbol": row.symbol,
            "cluster_id": row.cluster_id,
            "proposed_transition": row.proposed_transition,
            "proposal_confidence": row.proposal_confidence,
            "source_priority_score": row.source_priority_score,
            "next_audit_step": row.next_audit_step,
        }
        for row in ordered
    )


def _matching_codes(values: Iterable[str], accepted: frozenset[str]) -> tuple[str, ...]:
    return _dedupe(code for code in values if code in accepted or _matches_family(code, accepted))


def _matches_family(code: str, accepted: frozenset[str]) -> bool:
    if accepted is DEMAND_CODES:
        return "demand" in code or code in {"spring", "shakeout", "test", "no_supply"}
    if accepted is SUPPLY_CODES:
        return "supply" in code or code in {"buying_climax", "upthrust", "no_demand"}
    return code in accepted


def _row_sort_key(row: Mapping[str, Any]) -> tuple[str, int, str]:
    return (
        str(row.get("symbol", "")),
        _int_or_default(row.get("start_bar_index"), -1),
        str(row.get("cluster_id", "")),
    )


def _proposal_sort_key(row: VSAMixedClusterLifecycleProposalRow) -> tuple[int, int, str, str]:
    return (-row.proposal_confidence, -row.source_priority_score, row.symbol, row.cluster_id)


def _mapping_sequence(value: Any) -> tuple[Mapping[str, Any], ...]:
    if value is None:
        return ()
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return tuple(item for item in value if isinstance(item, Mapping))
    return ()


def _string_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,) if value else ()
    if isinstance(value, Iterable):
        return _dedupe(str(item) for item in value if str(item))
    return (str(value),) if str(value) else ()


def _dedupe(values: Iterable[str]) -> tuple[str, ...]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value)
        if not text or text in seen:
            continue
        output.append(text)
        seen.add(text)
    return tuple(output)


def _count(values: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = str(value)
        if not key:
            continue
        counts[key] = counts.get(key, 0) + 1
    return counts


def _int_or_default(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _join_or_none(values: tuple[str, ...]) -> str:
    return ", ".join(values) if values else "none"


__all__ = [
    "ACTION_REVIEW_DETECTOR_GATES",
    "ACTION_REVIEW_LIFECYCLE_INVALIDATION",
    "ACTION_REVIEW_SUPPLY_WARNING",
    "PROPOSAL_DEFER_DETECTOR_GATE",
    "PROPOSAL_DEFER_SUPPLY_WARNING",
    "PROPOSAL_INVALIDATE_BEARISH_QUALIFICATION",
    "PROPOSAL_MARK_BEARISH_CONFLICTED_PENDING_SUPERSESSION",
    "PROPOSAL_SUPERSEDE_BEARISH_WITH_DEMAND_REVIEW",
    "REVIEW_BEARISH_CONTEXT_DEMAND_REVERSAL_CLUSTER",
    "REVIEW_BULLISH_CONTEXT_SUPPLY_WARNING_CLUSTER",
    "REVIEW_UNQUALIFIED_BIDIRECTIONAL_DETECTOR_CONFLICT",
    "VSAMixedClusterLifecycleProposalRow",
    "VSAMixedClusterLifecycleProposalSummary",
    "build_vsa_mixed_cluster_lifecycle_proposals",
    "render_vsa_mixed_cluster_lifecycle_proposals_csv",
]
