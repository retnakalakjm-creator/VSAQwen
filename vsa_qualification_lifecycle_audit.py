from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from vsa_audit_candidate_triage import (
    BEARISH_VSA_CODES,
    BULLISH_VSA_CODES,
    TRIAGE_QUALIFICATION_LIFECYCLE,
    build_vsa_audit_candidate_triage,
)

LIFECYCLE_ACTIVE = "active"
LIFECYCLE_CONFLICTED = "conflicted"
LIFECYCLE_INVALIDATED_REVIEW = "invalidated_review"
LIFECYCLE_EXPIRED_REVIEW = "expired_review"
LIFECYCLE_NEEDS_FOLLOW_THROUGH = "needs_follow_through"

QUALIFICATION_BULLISH = "bullish"
QUALIFICATION_BEARISH = "bearish"
QUALIFICATION_UNQUALIFIED = "unqualified"

BIAS_BULLISH = "bullish"
BIAS_BEARISH = "bearish"
BIAS_MIXED = "mixed"
BIAS_NONE = "none"

CONFLICT_FLAGS = frozenset(
    {
        "bullish_vsa_against_bearish_qualification",
        "bearish_vsa_against_bullish_qualification",
    }
)
EXPIRY_FLAGS = frozenset(
    {
        "qualification_without_current_evidence",
        "stale_scoring_evidence",
        "structural_event_without_vsa_confirmation",
    }
)

CSV_COLUMNS = (
    "symbol",
    "replay_week",
    "replay_bar_index",
    "qualification",
    "qualification_side",
    "current_vsa_bias",
    "lifecycle_status",
    "severity_grade",
    "severity_score",
    "source_row_count",
    "candidate_families",
    "candidate_codes",
    "triage_buckets",
    "triage_grades",
    "supporting_event_codes",
    "opposing_event_codes",
    "target_event_codes",
    "scoring_event_codes",
    "source_audit_flags",
    "recommended_action",
    "reason",
)


@dataclass(frozen=True, slots=True)
class QualificationLifecycleAuditRow:
    """Audit-only review row for persistent qualification lifecycle state."""

    symbol: str
    replay_week: str
    replay_bar_index: int
    qualification: str
    qualification_side: str
    current_vsa_bias: str
    lifecycle_status: str
    severity_grade: str
    severity_score: int
    source_row_count: int
    candidate_families: tuple[str, ...]
    candidate_codes: tuple[str, ...]
    triage_buckets: tuple[str, ...]
    triage_grades: tuple[str, ...]
    target_event_codes: tuple[str, ...]
    scoring_event_codes: tuple[str, ...]
    supporting_event_codes: tuple[str, ...]
    opposing_event_codes: tuple[str, ...]
    source_audit_flags: tuple[str, ...]
    recommended_action: str
    reason: str
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
            "severity_grade": self.severity_grade,
            "severity_score": self.severity_score,
            "source_row_count": self.source_row_count,
            "candidate_families": list(self.candidate_families),
            "candidate_codes": list(self.candidate_codes),
            "triage_buckets": list(self.triage_buckets),
            "triage_grades": list(self.triage_grades),
            "target_event_codes": list(self.target_event_codes),
            "scoring_event_codes": list(self.scoring_event_codes),
            "supporting_event_codes": list(self.supporting_event_codes),
            "opposing_event_codes": list(self.opposing_event_codes),
            "source_audit_flags": list(self.source_audit_flags),
            "recommended_action": self.recommended_action,
            "reason": self.reason,
            "audit_only": self.audit_only,
        }


@dataclass(frozen=True, slots=True)
class QualificationLifecycleAuditSummary:
    """Compact audit-only summary of qualification lifecycle review rows."""

    rows: tuple[QualificationLifecycleAuditRow, ...]
    total_input_rows: int
    total_lifecycle_rows: int
    min_priority: str
    include_active: bool
    status_counts: dict[str, int] = field(default_factory=dict)
    grade_counts: dict[str, int] = field(default_factory=dict)
    qualification_counts: dict[str, int] = field(default_factory=dict)
    symbol_counts: dict[str, int] = field(default_factory=dict)
    week_counts: dict[str, int] = field(default_factory=dict)
    top_lifecycle_symbols: tuple[dict[str, Any], ...] = ()
    lifecycle_focus: tuple[dict[str, Any], ...] = ()
    audit_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "audit_only": self.audit_only,
            "min_priority": self.min_priority,
            "include_active": self.include_active,
            "total_input_rows": self.total_input_rows,
            "total_lifecycle_rows": self.total_lifecycle_rows,
            "status_counts": dict(self.status_counts),
            "grade_counts": dict(self.grade_counts),
            "qualification_counts": dict(self.qualification_counts),
            "symbol_counts": dict(self.symbol_counts),
            "week_counts": dict(self.week_counts),
            "top_lifecycle_symbols": [dict(row) for row in self.top_lifecycle_symbols],
            "lifecycle_focus": [dict(row) for row in self.lifecycle_focus],
            "rows": [row.to_dict() for row in self.rows],
        }


def build_qualification_lifecycle_audit(
    payload: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    *,
    min_priority: str = "high",
    include_active: bool = False,
) -> QualificationLifecycleAuditSummary:
    """Build audit-only qualification lifecycle rows from saved audit outputs.

    Input may be candidate-event JSON, batch-review JSON, triage JSON, or raw VSA
    audit JSON. The helper reuses the triage normalization path and groups rows by
    symbol/week so one bar is reviewed once.
    """

    triage_rows = _coerce_triage_rows(payload, min_priority=min_priority)
    lifecycle_rows = tuple(
        sorted(
            (
                row
                for group_rows in _group_by_symbol_week(triage_rows).values()
                for row in _build_lifecycle_row(group_rows, include_active=include_active)
            ),
            key=_lifecycle_sort_key,
        )
    )
    return QualificationLifecycleAuditSummary(
        rows=lifecycle_rows,
        total_input_rows=len(triage_rows),
        total_lifecycle_rows=len(lifecycle_rows),
        min_priority=min_priority,
        include_active=include_active,
        status_counts=_count(row.lifecycle_status for row in lifecycle_rows),
        grade_counts=_count(row.severity_grade for row in lifecycle_rows),
        qualification_counts=_count(row.qualification_side for row in lifecycle_rows),
        symbol_counts=_count(row.symbol for row in lifecycle_rows),
        week_counts=_count(row.replay_week for row in lifecycle_rows),
        top_lifecycle_symbols=_top_lifecycle_symbols(lifecycle_rows),
        lifecycle_focus=_lifecycle_focus(lifecycle_rows),
    )


def render_qualification_lifecycle_audit_csv(
    summary: QualificationLifecycleAuditSummary | Mapping[str, Any],
) -> str:
    """Render qualification lifecycle audit rows as CSV."""

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(CSV_COLUMNS), lineterminator="\n")
    writer.writeheader()
    for row in _summary_rows(summary):
        writer.writerow(_csv_row(row))
    return output.getvalue()


def _coerce_triage_rows(
    payload: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    *,
    min_priority: str,
) -> tuple[dict[str, Any], ...]:
    if isinstance(payload, Mapping) and _looks_like_triage_summary(payload):
        return tuple(_mapping_rows(payload.get("rows", ())))
    if (
        isinstance(payload, Sequence)
        and not isinstance(payload, (str, bytes))
        and payload
        and all(isinstance(item, Mapping) and "triage_bucket" in item for item in payload)
    ):
        return tuple(dict(item) for item in payload)
    triage = build_vsa_audit_candidate_triage(payload, min_priority=min_priority)
    return tuple(row.to_dict() for row in triage.rows)


def _looks_like_triage_summary(payload: Mapping[str, Any]) -> bool:
    rows = payload.get("rows")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        return False
    return any(isinstance(row, Mapping) and "triage_bucket" in row for row in rows)


def _build_lifecycle_row(
    rows: Sequence[Mapping[str, Any]],
    *,
    include_active: bool,
) -> tuple[QualificationLifecycleAuditRow, ...]:
    if not rows:
        return ()

    qualification = _first_text(row.get("qualification") for row in rows)
    qualification_side = _qualification_side(qualification)
    if qualification_side == QUALIFICATION_UNQUALIFIED:
        return ()

    target_codes = _merge_string_values(row.get("target_event_codes") for row in rows)
    scoring_codes = _merge_string_values(row.get("scoring_event_codes") for row in rows)
    all_codes = _dedupe((*target_codes, *scoring_codes))
    source_flags = _merge_string_values(row.get("source_audit_flags") for row in rows)
    candidate_families = _merge_string_values(row.get("candidate_families") for row in rows)
    if not candidate_families:
        candidate_families = _merge_string_values(row.get("candidate_family") for row in rows)
    candidate_codes = _merge_string_values(row.get("candidate_codes") for row in rows)
    if not candidate_codes:
        candidate_codes = _merge_string_values(row.get("candidate_code") for row in rows)
    triage_buckets = _merge_string_values(row.get("triage_buckets") for row in rows)
    if not triage_buckets:
        triage_buckets = _merge_string_values(row.get("triage_bucket") for row in rows)
    triage_grades = _merge_string_values(row.get("triage_grades") for row in rows)
    if not triage_grades:
        triage_grades = _merge_string_values(row.get("triage_grade") for row in rows)

    supporting_codes, opposing_codes = _split_supporting_opposing(qualification_side, all_codes)
    current_bias = _current_vsa_bias(all_codes)
    lifecycle_status = _lifecycle_status(
        qualification_side=qualification_side,
        current_bias=current_bias,
        source_flags=source_flags,
        triage_buckets=triage_buckets,
        supporting_codes=supporting_codes,
        opposing_codes=opposing_codes,
    )
    if lifecycle_status == LIFECYCLE_ACTIVE and not include_active:
        return ()

    grade = _severity_grade(lifecycle_status)
    replay_index = min(_int_or_default(row.get("replay_bar_index"), 0) for row in rows)
    return (
        QualificationLifecycleAuditRow(
            symbol=str(rows[0].get("symbol", "")),
            replay_week=str(rows[0].get("replay_week", "")),
            replay_bar_index=replay_index,
            qualification=qualification,
            qualification_side=qualification_side,
            current_vsa_bias=current_bias,
            lifecycle_status=lifecycle_status,
            severity_grade=grade,
            severity_score=_severity_score(lifecycle_status, grade),
            source_row_count=len(rows),
            candidate_families=candidate_families,
            candidate_codes=candidate_codes,
            triage_buckets=triage_buckets,
            triage_grades=triage_grades,
            target_event_codes=target_codes,
            scoring_event_codes=scoring_codes,
            supporting_event_codes=supporting_codes,
            opposing_event_codes=opposing_codes,
            source_audit_flags=source_flags,
            recommended_action=_recommended_action(lifecycle_status),
            reason=_reason(lifecycle_status, qualification_side, current_bias),
        ),
    )


def _lifecycle_status(
    *,
    qualification_side: str,
    current_bias: str,
    source_flags: tuple[str, ...],
    triage_buckets: tuple[str, ...],
    supporting_codes: tuple[str, ...],
    opposing_codes: tuple[str, ...],
) -> str:
    has_conflict_flag = bool(set(source_flags).intersection(CONFLICT_FLAGS))
    has_expiry_flag = bool(set(source_flags).intersection(EXPIRY_FLAGS))
    has_lifecycle_bucket = TRIAGE_QUALIFICATION_LIFECYCLE in triage_buckets

    if has_expiry_flag and current_bias == BIAS_NONE:
        return LIFECYCLE_EXPIRED_REVIEW
    if has_conflict_flag or has_lifecycle_bucket:
        if opposing_codes and not supporting_codes:
            return LIFECYCLE_INVALIDATED_REVIEW
        return LIFECYCLE_CONFLICTED
    if opposing_codes and not supporting_codes:
        return LIFECYCLE_NEEDS_FOLLOW_THROUGH
    if has_expiry_flag:
        return LIFECYCLE_EXPIRED_REVIEW
    if supporting_codes and not opposing_codes:
        return LIFECYCLE_ACTIVE
    if current_bias == BIAS_NONE:
        return LIFECYCLE_EXPIRED_REVIEW
    return LIFECYCLE_CONFLICTED


def _split_supporting_opposing(
    qualification_side: str,
    event_codes: tuple[str, ...],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    bullish = tuple(code for code in event_codes if code in BULLISH_VSA_CODES)
    bearish = tuple(code for code in event_codes if code in BEARISH_VSA_CODES)
    if qualification_side == QUALIFICATION_BEARISH:
        return bearish, bullish
    if qualification_side == QUALIFICATION_BULLISH:
        return bullish, bearish
    return (), ()


def _current_vsa_bias(event_codes: tuple[str, ...]) -> str:
    has_bullish = any(code in BULLISH_VSA_CODES for code in event_codes)
    has_bearish = any(code in BEARISH_VSA_CODES for code in event_codes)
    if has_bullish and has_bearish:
        return BIAS_MIXED
    if has_bullish:
        return BIAS_BULLISH
    if has_bearish:
        return BIAS_BEARISH
    return BIAS_NONE


def _qualification_side(qualification: str) -> str:
    lowered = qualification.lower()
    if "bearish" in lowered:
        return QUALIFICATION_BEARISH
    if "bullish" in lowered:
        return QUALIFICATION_BULLISH
    return QUALIFICATION_UNQUALIFIED


def _severity_grade(status: str) -> str:
    if status in {LIFECYCLE_CONFLICTED, LIFECYCLE_INVALIDATED_REVIEW}:
        return "A"
    if status in {LIFECYCLE_EXPIRED_REVIEW, LIFECYCLE_NEEDS_FOLLOW_THROUGH}:
        return "B"
    return "C"


def _severity_score(status: str, grade: str) -> int:
    if status == LIFECYCLE_INVALIDATED_REVIEW:
        return 96
    if status == LIFECYCLE_CONFLICTED:
        return 92
    if status == LIFECYCLE_EXPIRED_REVIEW:
        return 80
    if status == LIFECYCLE_NEEDS_FOLLOW_THROUGH:
        return 74
    return 50 if grade == "C" else 60


def _recommended_action(status: str) -> str:
    if status == LIFECYCLE_INVALIDATED_REVIEW:
        return "review qualification invalidation or expiry rule"
    if status == LIFECYCLE_CONFLICTED:
        return "separate mixed evidence from persistent qualification state"
    if status == LIFECYCLE_EXPIRED_REVIEW:
        return "expire stale qualification when fresh evidence disappears"
    if status == LIFECYCLE_NEEDS_FOLLOW_THROUGH:
        return "wait for follow-through before changing qualification state"
    return "keep qualification active unless later opposing evidence appears"


def _reason(status: str, qualification_side: str, current_bias: str) -> str:
    if status == LIFECYCLE_INVALIDATED_REVIEW:
        return (
            f"{qualification_side} qualification has opposing {current_bias} VSA evidence "
            "without same-side support in the reviewed bar."
        )
    if status == LIFECYCLE_CONFLICTED:
        return (
            f"{qualification_side} qualification conflicts with mixed or opposing "
            f"{current_bias} VSA evidence."
        )
    if status == LIFECYCLE_EXPIRED_REVIEW:
        return (
            f"{qualification_side} qualification appears stale or unsupported by fresh "
            "current evidence."
        )
    if status == LIFECYCLE_NEEDS_FOLLOW_THROUGH:
        return (
            f"{qualification_side} qualification has a candidate challenge but needs "
            "follow-through before invalidation."
        )
    return f"{qualification_side} qualification is supported by current {current_bias} VSA evidence."


def _group_by_symbol_week(
    rows: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, str], tuple[Mapping[str, Any], ...]]:
    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(
            (str(row.get("symbol", "")), str(row.get("replay_week", ""))),
            [],
        ).append(row)
    return {key: tuple(value) for key, value in grouped.items()}


def _summary_rows(
    summary: QualificationLifecycleAuditSummary | Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    if isinstance(summary, QualificationLifecycleAuditSummary):
        return tuple(row.to_dict() for row in summary.rows)
    return tuple(_mapping_rows(summary.get("rows", ())))


def _csv_row(row: Mapping[str, Any]) -> dict[str, str]:
    return {column: _csv_value(row.get(column)) for column in CSV_COLUMNS}


def _top_lifecycle_symbols(
    rows: tuple[QualificationLifecycleAuditRow, ...],
) -> tuple[dict[str, Any], ...]:
    grouped: dict[str, list[QualificationLifecycleAuditRow]] = {}
    for row in rows:
        grouped.setdefault(row.symbol, []).append(row)

    selected: list[dict[str, Any]] = []
    for symbol, symbol_rows in grouped.items():
        selected.append(
            {
                "symbol": symbol,
                "total_rows": len(symbol_rows),
                "status_counts": _count(row.lifecycle_status for row in symbol_rows),
                "grade_counts": _count(row.severity_grade for row in symbol_rows),
                "qualification_counts": _count(row.qualification_side for row in symbol_rows),
                "highest_grade": min((row.severity_grade for row in symbol_rows), key=_grade_rank),
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


def _lifecycle_focus(
    rows: tuple[QualificationLifecycleAuditRow, ...],
) -> tuple[dict[str, Any], ...]:
    grouped: dict[str, list[QualificationLifecycleAuditRow]] = {}
    for row in rows:
        grouped.setdefault(row.lifecycle_status, []).append(row)

    selected: list[dict[str, Any]] = []
    for status, status_rows in grouped.items():
        selected.append(
            {
                "lifecycle_status": status,
                "total_rows": len(status_rows),
                "grade_counts": _count(row.severity_grade for row in status_rows),
                "qualification_counts": _count(row.qualification_side for row in status_rows),
                "symbols": sorted(_unique(row.symbol for row in status_rows)),
                "recommended_action": _recommended_action(status),
            }
        )
    return tuple(
        sorted(
            selected,
            key=lambda item: (
                _status_rank(str(item["lifecycle_status"])),
                -int(item["total_rows"]),
            ),
        )
    )


def _lifecycle_sort_key(row: QualificationLifecycleAuditRow) -> tuple[int, int, str, str, int]:
    return (
        _status_rank(row.lifecycle_status),
        _grade_rank(row.severity_grade),
        row.symbol,
        row.replay_week,
        row.replay_bar_index,
    )


def _status_rank(status: str) -> int:
    return {
        LIFECYCLE_INVALIDATED_REVIEW: 0,
        LIFECYCLE_CONFLICTED: 1,
        LIFECYCLE_EXPIRED_REVIEW: 2,
        LIFECYCLE_NEEDS_FOLLOW_THROUGH: 3,
        LIFECYCLE_ACTIVE: 4,
    }.get(status, 99)


def _grade_rank(grade: str) -> int:
    return {"A": 0, "B": 1, "C": 2, "D": 3}.get(grade, 99)


def _mapping_rows(rows: Iterable[Any]) -> Iterable[dict[str, Any]]:
    for row in rows:
        if isinstance(row, Mapping):
            yield dict(row)


def _merge_string_values(values: Iterable[Any]) -> tuple[str, ...]:
    merged: list[str] = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, str):
            items = (value,)
        else:
            try:
                items = tuple(str(item) for item in value)
            except TypeError:
                items = (str(value),)
        merged.extend(item for item in items if item)
    return _dedupe(merged)


def _first_text(values: Iterable[Any]) -> str:
    for value in values:
        text = str(value or "")
        if text:
            return text
    return ""


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
