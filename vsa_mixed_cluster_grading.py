from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

GRADE_A = "A"
GRADE_B = "B"
GRADE_C = "C"

REVIEW_BEARISH_CONTEXT_DEMAND_REVERSAL_CLUSTER = "bearish_context_demand_reversal_cluster"
REVIEW_BULLISH_CONTEXT_SUPPLY_WARNING_CLUSTER = "bullish_context_supply_warning_cluster"
REVIEW_UNQUALIFIED_BIDIRECTIONAL_DETECTOR_CONFLICT = "unqualified_bidirectional_detector_conflict"
REVIEW_SAME_WEEK_MULTI_FAMILY_CONFLICT = "same_week_multi_family_conflict"
REVIEW_MULTI_WEEK_MULTI_FAMILY_CONFLICT = "multi_week_multi_family_conflict"
REVIEW_MANUAL_MIXED_CLUSTER_REVIEW = "manual_mixed_cluster_review"

ACTION_REVIEW_LIFECYCLE_INVALIDATION = "review_lifecycle_invalidation_or_supersession"
ACTION_REVIEW_SUPPLY_WARNING = "review_supply_warning_against_active_bullish_context"
ACTION_REVIEW_DETECTOR_GATES = "review_detector_gates_before_activation"
ACTION_REVIEW_CLUSTER_SEQUENCE = "review_cluster_sequence_before_weighting"
ACTION_MANUAL_CHART_CASEBOOK = "add_to_manual_chart_casebook"

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

BEARISH_STRUCTURE_CODES = frozenset({"structural_progression_weakening"})
BULLISH_STRUCTURE_CODES = frozenset({"structural_progression_improving"})
REVERSAL_FAMILIES = frozenset({"absorption", "effort_vs_result", "high_volume_reversal"})

CSV_COLUMNS = (
    "symbol",
    "cluster_id",
    "start_week",
    "end_week",
    "start_bar_index",
    "end_bar_index",
    "row_count",
    "grade",
    "review_type",
    "priority_score",
    "recommended_action",
    "event_families",
    "event_codes",
    "qualifications",
    "supporting_event_codes",
    "opposing_event_codes",
    "source_buckets",
    "grading_reasons",
    "cluster_read",
)


@dataclass(frozen=True, slots=True)
class VSAMixedClusterGradeRow:
    """Audit-only grade for one grouped mixed-event cluster."""

    symbol: str
    cluster_id: str
    start_week: str
    end_week: str
    start_bar_index: int
    end_bar_index: int
    row_count: int
    event_families: tuple[str, ...]
    event_codes: tuple[str, ...]
    qualifications: tuple[str, ...]
    supporting_event_codes: tuple[str, ...]
    opposing_event_codes: tuple[str, ...]
    source_buckets: tuple[str, ...]
    grade: str
    review_type: str
    priority_score: int
    recommended_action: str
    grading_reasons: tuple[str, ...]
    cluster_read: str
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
            "row_count": self.row_count,
            "event_families": list(self.event_families),
            "event_codes": list(self.event_codes),
            "qualifications": list(self.qualifications),
            "supporting_event_codes": list(self.supporting_event_codes),
            "opposing_event_codes": list(self.opposing_event_codes),
            "source_buckets": list(self.source_buckets),
            "grade": self.grade,
            "review_type": self.review_type,
            "priority_score": self.priority_score,
            "recommended_action": self.recommended_action,
            "grading_reasons": list(self.grading_reasons),
            "cluster_read": self.cluster_read,
        }


@dataclass(frozen=True, slots=True)
class VSAMixedClusterGradeSummary:
    """Compact audit-only summary for graded mixed clusters."""

    rows: tuple[VSAMixedClusterGradeRow, ...]
    total_input_clusters: int
    total_graded_clusters: int
    grade_counts: dict[str, int] = field(default_factory=dict)
    review_type_counts: dict[str, int] = field(default_factory=dict)
    recommended_action_counts: dict[str, int] = field(default_factory=dict)
    top_priority_clusters: tuple[dict[str, Any], ...] = ()
    audit_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "audit_only": self.audit_only,
            "total_input_clusters": self.total_input_clusters,
            "total_graded_clusters": self.total_graded_clusters,
            "grade_counts": dict(self.grade_counts),
            "review_type_counts": dict(self.review_type_counts),
            "recommended_action_counts": dict(self.recommended_action_counts),
            "top_priority_clusters": [dict(row) for row in self.top_priority_clusters],
            "rows": [row.to_dict() for row in self.rows],
        }


def build_vsa_mixed_cluster_grading(
    payload: Mapping[str, Any] | Sequence[Mapping[str, Any]],
) -> VSAMixedClusterGradeSummary:
    """Grade grouped mixed-event clusters from saved audit JSON.

    This helper consumes output from ``vsa_mixed_event_cluster_review.py`` or a
    compatible list of cluster dictionaries. It does not load market data, call
    providers, replay scanners, mutate scanner state, persist output, activate
    detectors, alter scoring/ranking, or affect API/frontend behavior.
    """

    clusters = tuple(sorted(_extract_clusters(payload), key=_cluster_sort_key))
    rows = tuple(sorted((_grade_cluster(cluster) for cluster in clusters), key=_grade_sort_key))
    return VSAMixedClusterGradeSummary(
        rows=rows,
        total_input_clusters=len(clusters),
        total_graded_clusters=len(rows),
        grade_counts=_count(row.grade for row in rows),
        review_type_counts=_count(row.review_type for row in rows),
        recommended_action_counts=_count(row.recommended_action for row in rows),
        top_priority_clusters=_top_priority_clusters(rows),
    )


def render_vsa_mixed_cluster_grading_csv(
    summary: VSAMixedClusterGradeSummary | Mapping[str, Any],
) -> str:
    """Render graded mixed clusters to CSV for casebook review."""

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(CSV_COLUMNS), lineterminator="\n")
    writer.writeheader()
    for row in _summary_rows(summary):
        writer.writerow(_csv_row(row))
    return output.getvalue()


def _grade_cluster(cluster: Mapping[str, Any]) -> VSAMixedClusterGradeRow:
    event_families = _string_tuple(cluster.get("event_families"))
    event_codes = _string_tuple(cluster.get("event_codes"))
    qualifications = _string_tuple(cluster.get("qualifications"))
    supporting = _string_tuple(cluster.get("supporting_event_codes"))
    opposing = _string_tuple(cluster.get("opposing_event_codes"))
    source_buckets = _string_tuple(cluster.get("source_buckets"))
    row_count = _int_or_default(cluster.get("row_count"), 0)
    start_bar_index = _int_or_default(cluster.get("start_bar_index"), -1)
    end_bar_index = _int_or_default(cluster.get("end_bar_index"), start_bar_index)

    review_type, recommended_action, reasons = _classify_cluster(
        event_families=event_families,
        qualifications=qualifications,
        supporting=supporting,
        opposing=opposing,
        source_buckets=source_buckets,
        row_count=row_count,
        start_bar_index=start_bar_index,
        end_bar_index=end_bar_index,
    )
    priority_score = _priority_score(
        review_type=review_type,
        event_families=event_families,
        qualifications=qualifications,
        supporting=supporting,
        opposing=opposing,
        source_buckets=source_buckets,
        row_count=row_count,
        start_bar_index=start_bar_index,
        end_bar_index=end_bar_index,
    )
    grade = _grade_from_score(priority_score)
    return VSAMixedClusterGradeRow(
        symbol=str(cluster.get("symbol", "")),
        cluster_id=str(cluster.get("cluster_id", "")),
        start_week=str(cluster.get("start_week", "")),
        end_week=str(cluster.get("end_week", cluster.get("start_week", ""))),
        start_bar_index=start_bar_index,
        end_bar_index=end_bar_index,
        row_count=row_count,
        event_families=event_families,
        event_codes=event_codes,
        qualifications=qualifications,
        supporting_event_codes=supporting,
        opposing_event_codes=opposing,
        source_buckets=source_buckets,
        grade=grade,
        review_type=review_type,
        priority_score=priority_score,
        recommended_action=recommended_action,
        grading_reasons=reasons,
        cluster_read=_cluster_read(
            symbol=str(cluster.get("symbol", "")),
            review_type=review_type,
            grade=grade,
            recommended_action=recommended_action,
            supporting=supporting,
            opposing=opposing,
            qualifications=qualifications,
            event_families=event_families,
        ),
    )


def _classify_cluster(
    *,
    event_families: tuple[str, ...],
    qualifications: tuple[str, ...],
    supporting: tuple[str, ...],
    opposing: tuple[str, ...],
    source_buckets: tuple[str, ...],
    row_count: int,
    start_bar_index: int,
    end_bar_index: int,
) -> tuple[str, str, tuple[str, ...]]:
    reasons: list[str] = []
    has_persistent_bearish = "persistent_bearish" in qualifications
    has_persistent_bullish = "persistent_bullish" in qualifications
    has_demand_support = any(code in DEMAND_CODES or "demand" in code or code in {"spring", "shakeout"} for code in supporting)
    has_supply_opposition = any(code in SUPPLY_CODES or code in BEARISH_STRUCTURE_CODES or "supply" in code for code in opposing)
    has_structure_opposition = any(code in BEARISH_STRUCTURE_CODES | BULLISH_STRUCTURE_CODES for code in opposing)
    has_multi_family = len(set(event_families)) > 1
    same_week = start_bar_index == end_bar_index

    if has_persistent_bearish and has_demand_support:
        reasons.append("persistent bearish qualification is being challenged by same-side demand evidence")
        if has_supply_opposition or has_structure_opposition:
            reasons.append("opposing supply/structure evidence remains inside the same cluster window")
        if has_multi_family:
            reasons.append("multiple reversal/absorption families fire in the same context")
        return (
            REVIEW_BEARISH_CONTEXT_DEMAND_REVERSAL_CLUSTER,
            ACTION_REVIEW_LIFECYCLE_INVALIDATION,
            tuple(reasons),
        )

    if has_persistent_bullish and has_supply_opposition:
        reasons.append("persistent bullish qualification has supply/structure warning evidence inside the mixed cluster")
        if has_demand_support:
            reasons.append("same-side demand evidence prevents treating the warning as clean bearish invalidation")
        return (
            REVIEW_BULLISH_CONTEXT_SUPPLY_WARNING_CLUSTER,
            ACTION_REVIEW_SUPPLY_WARNING,
            tuple(reasons),
        )

    if "unqualified" in qualifications and has_demand_support and has_supply_opposition:
        reasons.append("unqualified cluster contains both demand/reversal and supply/structure evidence")
        if has_multi_family:
            reasons.append("multiple candidate families overlap before a clear qualification exists")
        return (
            REVIEW_UNQUALIFIED_BIDIRECTIONAL_DETECTOR_CONFLICT,
            ACTION_REVIEW_DETECTOR_GATES,
            tuple(reasons),
        )

    if has_multi_family and same_week:
        reasons.append("multiple candidate families fire on the same completed bar")
        reasons.append("same-week grouping should be reviewed before detector weighting")
        return (
            REVIEW_SAME_WEEK_MULTI_FAMILY_CONFLICT,
            ACTION_REVIEW_CLUSTER_SEQUENCE,
            tuple(reasons),
        )

    if has_multi_family or row_count >= 3:
        reasons.append("cluster spans multiple candidate rows or families")
        reasons.append("review sequence before activating or weighting a single detector family")
        return (
            REVIEW_MULTI_WEEK_MULTI_FAMILY_CONFLICT,
            ACTION_REVIEW_CLUSTER_SEQUENCE,
            tuple(reasons),
        )

    reasons.append("mixed cluster does not fit a high-confidence lifecycle or detector-gate pattern")
    return (
        REVIEW_MANUAL_MIXED_CLUSTER_REVIEW,
        ACTION_MANUAL_CHART_CASEBOOK,
        tuple(reasons),
    )


def _priority_score(
    *,
    review_type: str,
    event_families: tuple[str, ...],
    qualifications: tuple[str, ...],
    supporting: tuple[str, ...],
    opposing: tuple[str, ...],
    source_buckets: tuple[str, ...],
    row_count: int,
    start_bar_index: int,
    end_bar_index: int,
) -> int:
    score = 0
    if review_type == REVIEW_BEARISH_CONTEXT_DEMAND_REVERSAL_CLUSTER:
        score += 45
    elif review_type == REVIEW_BULLISH_CONTEXT_SUPPLY_WARNING_CLUSTER:
        score += 38
    elif review_type == REVIEW_UNQUALIFIED_BIDIRECTIONAL_DETECTOR_CONFLICT:
        score += 32
    elif review_type in {REVIEW_SAME_WEEK_MULTI_FAMILY_CONFLICT, REVIEW_MULTI_WEEK_MULTI_FAMILY_CONFLICT}:
        score += 25
    else:
        score += 15

    if any(item.startswith("persistent_") for item in qualifications):
        score += 18
    if len(set(event_families)) >= 3:
        score += 15
    elif len(set(event_families)) == 2:
        score += 10
    if row_count >= 5:
        score += 12
    elif row_count >= 3:
        score += 8
    elif row_count >= 2:
        score += 4
    if any(code in BEARISH_STRUCTURE_CODES | BULLISH_STRUCTURE_CODES for code in opposing):
        score += 8
    if "contradictory_production_evidence" in source_buckets:
        score += 8
    if end_bar_index > start_bar_index:
        score += 5
    if supporting and opposing:
        score += 5
    return min(score, 100)


def _grade_from_score(score: int) -> str:
    if score >= 70:
        return GRADE_A
    if score >= 45:
        return GRADE_B
    return GRADE_C


def _cluster_read(
    *,
    symbol: str,
    review_type: str,
    grade: str,
    recommended_action: str,
    supporting: tuple[str, ...],
    opposing: tuple[str, ...],
    qualifications: tuple[str, ...],
    event_families: tuple[str, ...],
) -> str:
    return (
        f"{symbol} is graded {grade} as {review_type}. "
        f"Families: {_join_or_none(event_families)}. "
        f"Qualifications: {_join_or_none(qualifications)}. "
        f"Demand/support side: {_join_or_none(supporting)}. "
        f"Opposing side: {_join_or_none(opposing)}. "
        f"Next audit action: {recommended_action}."
    )


def _extract_clusters(payload: Mapping[str, Any] | Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    if isinstance(payload, Mapping):
        if "clusters" in payload:
            return tuple(dict(item) for item in _mapping_sequence(payload.get("clusters")))
        if "rows" in payload:
            return tuple(dict(item) for item in _mapping_sequence(payload.get("rows")))
        return (dict(payload),)
    return tuple(dict(item) for item in payload)


def _summary_rows(summary: VSAMixedClusterGradeSummary | Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    if isinstance(summary, VSAMixedClusterGradeSummary):
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


def _top_priority_clusters(rows: Sequence[VSAMixedClusterGradeRow], *, limit: int = 10) -> tuple[dict[str, Any], ...]:
    ordered = sorted(rows, key=lambda row: (-row.priority_score, row.symbol, row.cluster_id))[:limit]
    return tuple(
        {
            "symbol": row.symbol,
            "cluster_id": row.cluster_id,
            "grade": row.grade,
            "priority_score": row.priority_score,
            "review_type": row.review_type,
            "recommended_action": row.recommended_action,
        }
        for row in ordered
    )


def _cluster_sort_key(cluster: Mapping[str, Any]) -> tuple[str, int, str]:
    return (
        str(cluster.get("symbol", "")),
        _int_or_default(cluster.get("start_bar_index"), -1),
        str(cluster.get("cluster_id", "")),
    )


def _grade_sort_key(row: VSAMixedClusterGradeRow) -> tuple[int, str, int, str]:
    return (-row.priority_score, row.symbol, row.start_bar_index, row.cluster_id)


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
        if not value:
            continue
        counts[value] = counts.get(value, 0) + 1
    return counts


def _int_or_default(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _join_or_none(values: Iterable[str]) -> str:
    materialized = tuple(values)
    return ", ".join(materialized) if materialized else "none"


__all__ = [
    "ACTION_ADD_TO_MANUAL_CHART_CASEBOOK",
    "ACTION_MANUAL_CHART_CASEBOOK",
    "ACTION_REVIEW_CLUSTER_SEQUENCE",
    "ACTION_REVIEW_DETECTOR_GATES",
    "ACTION_REVIEW_LIFECYCLE_INVALIDATION",
    "ACTION_REVIEW_SUPPLY_WARNING",
    "GRADE_A",
    "GRADE_B",
    "GRADE_C",
    "REVIEW_BEARISH_CONTEXT_DEMAND_REVERSAL_CLUSTER",
    "REVIEW_BULLISH_CONTEXT_SUPPLY_WARNING_CLUSTER",
    "REVIEW_MANUAL_MIXED_CLUSTER_REVIEW",
    "REVIEW_MULTI_WEEK_MULTI_FAMILY_CONFLICT",
    "REVIEW_SAME_WEEK_MULTI_FAMILY_CONFLICT",
    "REVIEW_UNQUALIFIED_BIDIRECTIONAL_DETECTOR_CONFLICT",
    "VSAMixedClusterGradeRow",
    "VSAMixedClusterGradeSummary",
    "build_vsa_mixed_cluster_grading",
    "render_vsa_mixed_cluster_grading_csv",
]
