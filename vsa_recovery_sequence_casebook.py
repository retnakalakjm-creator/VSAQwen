from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from vsa_recovery_sequence_labels import (
    RecoverySequenceReviewLabel,
    RecoverySequenceReviewResult,
    label_stopping_volume_spring_shakeout_review,
)

CASE_RECOVERY_SEQUENCE_REVIEW = "recovery_sequence_review"
CASE_RECOVERY_SEQUENCE_BLOCKED = "recovery_sequence_blocked"
CASE_RECOVERY_SEQUENCE_NEEDS_FOLLOW_THROUGH = "recovery_sequence_needs_follow_through"
CASE_RECOVERY_SEQUENCE_NONE = "recovery_sequence_none"

RECOMMENDED_ACTION_REVIEW = "chart_review_recovery_sequence_candidate"
RECOMMENDED_ACTION_BLOCKED = "chart_review_recovery_sequence_blockers"
RECOMMENDED_ACTION_FOLLOW_THROUGH = "wait_for_recovery_sequence_follow_through"
RECOMMENDED_ACTION_NONE = "no_recovery_sequence_casebook_action"

CSV_COLUMNS = (
    "casebook_id",
    "symbol",
    "cluster_id",
    "case_type",
    "recovery_sequence_status",
    "review_marker",
    "recommended_casebook_action",
    "qualification",
    "start_week",
    "end_week",
    "start_bar_index",
    "end_bar_index",
    "prior_weakness_codes",
    "stopping_volume_codes",
    "spring_shakeout_codes",
    "follow_through_codes",
    "blocker_codes",
    "ignored_audit_only_codes",
    "follow_through_evidence_age",
    "used_fallback_evidence",
    "source_event_family",
    "source_priority",
    "manual_review_notes",
    "case_read",
)


@dataclass(frozen=True, slots=True)
class VSARecoverySequenceCasebookRow:
    """Audit-only casebook row for one 6C recovery-sequence review item."""

    casebook_id: str
    symbol: str
    cluster_id: str
    case_type: str
    recovery_sequence_status: str
    review_marker: str | None
    recommended_casebook_action: str
    qualification: str
    start_week: str
    end_week: str
    start_bar_index: int
    end_bar_index: int
    prior_weakness_codes: tuple[str, ...]
    stopping_volume_codes: tuple[str, ...]
    spring_shakeout_codes: tuple[str, ...]
    follow_through_codes: tuple[str, ...]
    blocker_codes: tuple[str, ...]
    ignored_audit_only_codes: tuple[str, ...]
    follow_through_evidence_age: int | None
    used_fallback_evidence: bool
    source_event_family: str
    source_priority: str
    manual_review_notes: str
    case_read: str
    audit_only: bool = True
    production_safe: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "audit_only": self.audit_only,
            "production_safe": self.production_safe,
            "casebook_id": self.casebook_id,
            "symbol": self.symbol,
            "cluster_id": self.cluster_id,
            "case_type": self.case_type,
            "recovery_sequence_status": self.recovery_sequence_status,
            "review_marker": self.review_marker,
            "recommended_casebook_action": self.recommended_casebook_action,
            "qualification": self.qualification,
            "start_week": self.start_week,
            "end_week": self.end_week,
            "start_bar_index": self.start_bar_index,
            "end_bar_index": self.end_bar_index,
            "prior_weakness_codes": list(self.prior_weakness_codes),
            "stopping_volume_codes": list(self.stopping_volume_codes),
            "spring_shakeout_codes": list(self.spring_shakeout_codes),
            "follow_through_codes": list(self.follow_through_codes),
            "blocker_codes": list(self.blocker_codes),
            "ignored_audit_only_codes": list(self.ignored_audit_only_codes),
            "follow_through_evidence_age": self.follow_through_evidence_age,
            "used_fallback_evidence": self.used_fallback_evidence,
            "source_event_family": self.source_event_family,
            "source_priority": self.source_priority,
            "manual_review_notes": self.manual_review_notes,
            "case_read": self.case_read,
        }


@dataclass(frozen=True, slots=True)
class VSARecoverySequenceCasebookSummary:
    """Audit-only summary for 6C recovery-sequence casebook rows."""

    rows: tuple[VSARecoverySequenceCasebookRow, ...]
    total_input_rows: int
    total_casebook_rows: int
    status_counts: dict[str, int] = field(default_factory=dict)
    case_type_counts: dict[str, int] = field(default_factory=dict)
    recommended_action_counts: dict[str, int] = field(default_factory=dict)
    top_casebook_items: tuple[dict[str, Any], ...] = ()
    audit_only: bool = True
    production_safe: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "audit_only": self.audit_only,
            "production_safe": self.production_safe,
            "total_input_rows": self.total_input_rows,
            "total_casebook_rows": self.total_casebook_rows,
            "status_counts": dict(self.status_counts),
            "case_type_counts": dict(self.case_type_counts),
            "recommended_action_counts": dict(self.recommended_action_counts),
            "top_casebook_items": [dict(item) for item in self.top_casebook_items],
            "rows": [row.to_dict() for row in self.rows],
        }


def build_vsa_recovery_sequence_casebook(
    payload: Mapping[str, Any] | Sequence[Mapping[str, Any]],
) -> VSARecoverySequenceCasebookSummary:
    """Create audit-only 6C casebook rows from saved audit/review JSON.

    The builder enriches already-saved rows with the review-only 6C recovery
    sequence marker. It does not load market data, replay scanners, mutate
    scanner state, activate detectors, alter scoring/ranking, or affect API,
    frontend, provider, persistence, or production scanner behavior.
    """

    input_rows = tuple(_extract_rows(payload))
    casebook_rows = tuple(
        sorted(
            (_casebook_row(row) for row in input_rows),
            key=_casebook_sort_key,
        )
    )
    return VSARecoverySequenceCasebookSummary(
        rows=casebook_rows,
        total_input_rows=len(input_rows),
        total_casebook_rows=len(casebook_rows),
        status_counts=_count(row.recovery_sequence_status for row in casebook_rows),
        case_type_counts=_count(row.case_type for row in casebook_rows),
        recommended_action_counts=_count(row.recommended_casebook_action for row in casebook_rows),
        top_casebook_items=_top_casebook_items(casebook_rows),
    )


def render_vsa_recovery_sequence_casebook_csv(
    summary: VSARecoverySequenceCasebookSummary | Mapping[str, Any],
) -> str:
    """Render 6C recovery-sequence casebook rows to CSV."""

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(CSV_COLUMNS), lineterminator="\n")
    writer.writeheader()
    for row in _summary_rows(summary):
        writer.writerow(_csv_row(row))
    return output.getvalue()


def _casebook_row(row: Mapping[str, Any]) -> VSARecoverySequenceCasebookRow:
    symbol = str(row.get("symbol", ""))
    cluster_id = str(row.get("cluster_id", row.get("event_id", "")))
    start_week = str(row.get("start_week", row.get("week_beginning", "")))
    end_week = str(row.get("end_week", start_week))
    start_bar_index = _int_or_default(row.get("start_bar_index", row.get("bar_index", -1)), -1)
    end_bar_index = _int_or_default(row.get("end_bar_index", start_bar_index), start_bar_index)
    source_event_family = str(row.get("event_family", row.get("source_event_family", "")))
    source_priority = str(row.get("priority", row.get("source_priority", "")))
    result = _review_result(row)
    case_type = _case_type(result.status)
    recommended_action = _recommended_action(result.status)
    casebook_id = _casebook_id(
        symbol=symbol,
        cluster_id=cluster_id,
        case_type=case_type,
        start_week=start_week,
        start_bar_index=start_bar_index,
    )

    return VSARecoverySequenceCasebookRow(
        casebook_id=casebook_id,
        symbol=symbol,
        cluster_id=cluster_id,
        case_type=case_type,
        recovery_sequence_status=result.status.value,
        review_marker=result.review_marker,
        recommended_casebook_action=recommended_action,
        qualification=result.qualification,
        start_week=start_week,
        end_week=end_week,
        start_bar_index=start_bar_index,
        end_bar_index=end_bar_index,
        prior_weakness_codes=result.prior_weakness_codes,
        stopping_volume_codes=result.stopping_volume_codes,
        spring_shakeout_codes=result.spring_shakeout_codes,
        follow_through_codes=result.follow_through_codes,
        blocker_codes=result.blocker_codes,
        ignored_audit_only_codes=result.ignored_audit_only_codes,
        follow_through_evidence_age=result.follow_through_evidence_age,
        used_fallback_evidence=result.used_fallback_evidence,
        source_event_family=source_event_family,
        source_priority=source_priority,
        manual_review_notes="",
        case_read=_case_read(
            symbol=symbol,
            case_type=case_type,
            recommended_action=recommended_action,
            result=result,
            start_week=start_week,
            end_week=end_week,
        ),
    )


def _review_result(row: Mapping[str, Any]) -> RecoverySequenceReviewResult:
    return label_stopping_volume_spring_shakeout_review(
        qualification=row.get("qualification", row.get("source_qualification", "")),
        prior_evidence=_row_codes(
            row,
            "prior_weakness_codes",
            "prior_evidence_codes",
            "caution_evidence_codes",
        ),
        stopping_volume_evidence=_row_codes(
            row,
            "stopping_volume_codes",
            "stopping_volume_evidence_codes",
            "anchor_evidence_codes",
        ),
        spring_shakeout_evidence=_row_codes(
            row,
            "spring_shakeout_codes",
            "spring_shakeout_evidence_codes",
            "test_evidence_codes",
        ),
        follow_through_evidence=_row_codes(
            row,
            "follow_through_codes",
            "follow_through_evidence_codes",
            "demand_evidence_codes",
        ),
        same_window_evidence=_row_codes(
            row,
            "same_window_evidence_codes",
            "caution_evidence_codes",
            "opposing_evidence_codes",
        ),
        follow_through_evidence_age=_optional_int(
            row.get("follow_through_evidence_age", row.get("scoring_evidence_age"))
        ),
        used_fallback_evidence=_bool(row.get("used_fallback_evidence", False)),
    )


def _case_type(status: RecoverySequenceReviewLabel) -> str:
    if status is RecoverySequenceReviewLabel.REVIEW:
        return CASE_RECOVERY_SEQUENCE_REVIEW
    if status is RecoverySequenceReviewLabel.BLOCKED:
        return CASE_RECOVERY_SEQUENCE_BLOCKED
    if status is RecoverySequenceReviewLabel.NEEDS_FOLLOW_THROUGH:
        return CASE_RECOVERY_SEQUENCE_NEEDS_FOLLOW_THROUGH
    return CASE_RECOVERY_SEQUENCE_NONE


def _recommended_action(status: RecoverySequenceReviewLabel) -> str:
    if status is RecoverySequenceReviewLabel.REVIEW:
        return RECOMMENDED_ACTION_REVIEW
    if status is RecoverySequenceReviewLabel.BLOCKED:
        return RECOMMENDED_ACTION_BLOCKED
    if status is RecoverySequenceReviewLabel.NEEDS_FOLLOW_THROUGH:
        return RECOMMENDED_ACTION_FOLLOW_THROUGH
    return RECOMMENDED_ACTION_NONE


def _casebook_id(*, symbol: str, cluster_id: str, case_type: str, start_week: str, start_bar_index: int) -> str:
    source_id = cluster_id or f"{start_week}:{start_bar_index}"
    return f"{symbol}:{case_type}:{source_id}"


def _case_read(
    *,
    symbol: str,
    case_type: str,
    recommended_action: str,
    result: RecoverySequenceReviewResult,
    start_week: str,
    end_week: str,
) -> str:
    period = start_week if start_week == end_week else f"{start_week} to {end_week}"
    return (
        f"{symbol} 6C casebook item is {case_type} for {period}. "
        f"Recovery status: {result.status.value}. "
        f"Prior weakness: {_join_or_none(result.prior_weakness_codes)}. "
        f"Anchor: {_join_or_none(result.stopping_volume_codes)}. "
        f"Spring/Shakeout: {_join_or_none(result.spring_shakeout_codes)}. "
        f"Follow-through: {_join_or_none(result.follow_through_codes)}. "
        f"Blockers: {_join_or_none(result.blocker_codes)}. "
        f"Next action: {recommended_action}."
    )


def _extract_rows(payload: Mapping[str, Any] | Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    if isinstance(payload, Mapping):
        for key in ("rows", "casebook_rows", "review_rows", "results"):
            if key in payload:
                return tuple(dict(item) for item in _mapping_sequence(payload.get(key)))
        return (dict(payload),)
    return tuple(dict(item) for item in payload if isinstance(item, Mapping))


def _summary_rows(summary: VSARecoverySequenceCasebookSummary | Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    if isinstance(summary, VSARecoverySequenceCasebookSummary):
        return tuple(row.to_dict() for row in summary.rows)
    return tuple(dict(item) for item in _mapping_sequence(summary.get("rows")))


def _csv_row(row: Mapping[str, Any]) -> dict[str, str]:
    output: dict[str, str] = {}
    for column in CSV_COLUMNS:
        value = row.get(column, "")
        if isinstance(value, (list, tuple)):
            output[column] = ";".join(str(item) for item in value)
        else:
            output[column] = "" if value is None else str(value)
    return output


def _top_casebook_items(rows: Sequence[VSARecoverySequenceCasebookRow], *, limit: int = 10) -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "casebook_id": row.casebook_id,
            "symbol": row.symbol,
            "cluster_id": row.cluster_id,
            "case_type": row.case_type,
            "recovery_sequence_status": row.recovery_sequence_status,
            "review_marker": row.review_marker,
            "recommended_casebook_action": row.recommended_casebook_action,
        }
        for row in sorted(rows, key=_casebook_sort_key)[:limit]
    )


def _casebook_sort_key(row: VSARecoverySequenceCasebookRow) -> tuple[int, str, str, str]:
    rank = {
        CASE_RECOVERY_SEQUENCE_REVIEW: 0,
        CASE_RECOVERY_SEQUENCE_BLOCKED: 1,
        CASE_RECOVERY_SEQUENCE_NEEDS_FOLLOW_THROUGH: 2,
        CASE_RECOVERY_SEQUENCE_NONE: 3,
    }.get(row.case_type, 9)
    return (rank, row.symbol, row.start_week, row.cluster_id)


def _row_codes(row: Mapping[str, Any], *keys: str) -> tuple[str, ...]:
    selected: list[str] = []
    seen: set[str] = set()
    for key in keys:
        for code in _string_tuple(row.get(key)):
            if code not in seen:
                selected.append(code)
                seen.add(code)
    return tuple(selected)


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
        return tuple(str(getattr(item, "value", item)) for item in value if str(getattr(item, "value", item)))
    return (str(value),) if str(value) else ()


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return _int_or_default(value, 0)


def _int_or_default(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _count(values: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def _join_or_none(values: Sequence[str]) -> str:
    return ", ".join(values) if values else "none"


__all__ = [
    "CASE_RECOVERY_SEQUENCE_BLOCKED",
    "CASE_RECOVERY_SEQUENCE_NEEDS_FOLLOW_THROUGH",
    "CASE_RECOVERY_SEQUENCE_NONE",
    "CASE_RECOVERY_SEQUENCE_REVIEW",
    "RECOMMENDED_ACTION_BLOCKED",
    "RECOMMENDED_ACTION_FOLLOW_THROUGH",
    "RECOMMENDED_ACTION_NONE",
    "RECOMMENDED_ACTION_REVIEW",
    "VSARecoverySequenceCasebookRow",
    "VSARecoverySequenceCasebookSummary",
    "build_vsa_recovery_sequence_casebook",
    "render_vsa_recovery_sequence_casebook_csv",
]
