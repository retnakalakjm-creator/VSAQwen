from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


STATUS_REVIEW = "stopping_volume_spring_shakeout_review"
STATUS_BLOCKED = "stopping_volume_spring_shakeout_blocked"
STATUS_NEEDS_FOLLOW_THROUGH = "stopping_volume_spring_shakeout_needs_follow_through"
STATUS_NONE = "none"

OUTCOME_FIRED = "fired"
OUTCOME_BLOCKED = "blocked"
OUTCOME_NEEDS_FOLLOW_THROUGH = "needs_follow_through"
OUTCOME_NOT_FIRED = "not_fired"

EXPECTATION_MATCHED = "matched"
EXPECTATION_MISMATCHED = "mismatched"
EXPECTATION_UNSPECIFIED = "unspecified"

CSV_COLUMNS = (
    "symbol",
    "cluster_id",
    "casebook_id",
    "recovery_sequence_status",
    "label_firing_outcome",
    "expected_status",
    "expectation_result",
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
    "audit_note",
)


@dataclass(frozen=True, slots=True)
class VSARecoverySequenceLabelFiringAuditRow:
    """One saved-row validation result for the 6C recovery-sequence label."""

    symbol: str
    cluster_id: str
    casebook_id: str
    recovery_sequence_status: str
    label_firing_outcome: str
    expected_status: str
    expectation_result: str
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
    audit_note: str
    audit_only: bool = True
    production_safe: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "audit_only": self.audit_only,
            "production_safe": self.production_safe,
            "symbol": self.symbol,
            "cluster_id": self.cluster_id,
            "casebook_id": self.casebook_id,
            "recovery_sequence_status": self.recovery_sequence_status,
            "label_firing_outcome": self.label_firing_outcome,
            "expected_status": self.expected_status,
            "expectation_result": self.expectation_result,
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
            "audit_note": self.audit_note,
        }


@dataclass(frozen=True, slots=True)
class VSARecoverySequenceLabelFiringAuditSummary:
    """Repeatable audit-only summary for 6C label-firing validation."""

    rows: tuple[VSARecoverySequenceLabelFiringAuditRow, ...]
    total_input_rows: int
    fired_count: int
    blocked_count: int
    needs_follow_through_count: int
    not_fired_count: int
    matched_expectation_count: int
    mismatched_expectation_count: int
    unspecified_expectation_count: int
    outcome_counts: dict[str, int] = field(default_factory=dict)
    status_counts: dict[str, int] = field(default_factory=dict)
    expectation_counts: dict[str, int] = field(default_factory=dict)
    top_mismatches: tuple[dict[str, Any], ...] = ()
    top_fired_items: tuple[dict[str, Any], ...] = ()
    audit_only: bool = True
    production_safe: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "audit_only": self.audit_only,
            "production_safe": self.production_safe,
            "total_input_rows": self.total_input_rows,
            "fired_count": self.fired_count,
            "blocked_count": self.blocked_count,
            "needs_follow_through_count": self.needs_follow_through_count,
            "not_fired_count": self.not_fired_count,
            "matched_expectation_count": self.matched_expectation_count,
            "mismatched_expectation_count": self.mismatched_expectation_count,
            "unspecified_expectation_count": self.unspecified_expectation_count,
            "outcome_counts": dict(self.outcome_counts),
            "status_counts": dict(self.status_counts),
            "expectation_counts": dict(self.expectation_counts),
            "top_mismatches": [dict(item) for item in self.top_mismatches],
            "top_fired_items": [dict(item) for item in self.top_fired_items],
            "rows": [row.to_dict() for row in self.rows],
        }


def build_vsa_recovery_sequence_label_firing_audit(
    payload: Mapping[str, Any] | Sequence[Mapping[str, Any]],
) -> VSARecoverySequenceLabelFiringAuditSummary:
    """Summarize whether saved 6C recovery-sequence labels fired as expected.

    This helper consumes already-created casebook/audit JSON. It does not load
    market data, call providers, replay scanners, mutate scanner state, activate
    detectors, change scoring/ranking, or affect API/frontend/persistence.
    """

    input_rows = tuple(_extract_rows(payload))
    audit_rows = tuple(sorted((_audit_row(row) for row in input_rows), key=_audit_sort_key))
    return VSARecoverySequenceLabelFiringAuditSummary(
        rows=audit_rows,
        total_input_rows=len(input_rows),
        fired_count=sum(1 for row in audit_rows if row.label_firing_outcome == OUTCOME_FIRED),
        blocked_count=sum(1 for row in audit_rows if row.label_firing_outcome == OUTCOME_BLOCKED),
        needs_follow_through_count=sum(
            1 for row in audit_rows if row.label_firing_outcome == OUTCOME_NEEDS_FOLLOW_THROUGH
        ),
        not_fired_count=sum(1 for row in audit_rows if row.label_firing_outcome == OUTCOME_NOT_FIRED),
        matched_expectation_count=sum(
            1 for row in audit_rows if row.expectation_result == EXPECTATION_MATCHED
        ),
        mismatched_expectation_count=sum(
            1 for row in audit_rows if row.expectation_result == EXPECTATION_MISMATCHED
        ),
        unspecified_expectation_count=sum(
            1 for row in audit_rows if row.expectation_result == EXPECTATION_UNSPECIFIED
        ),
        outcome_counts=_count(row.label_firing_outcome for row in audit_rows),
        status_counts=_count(row.recovery_sequence_status for row in audit_rows),
        expectation_counts=_count(row.expectation_result for row in audit_rows),
        top_mismatches=_top_rows(
            (row for row in audit_rows if row.expectation_result == EXPECTATION_MISMATCHED),
        ),
        top_fired_items=_top_rows((row for row in audit_rows if row.label_firing_outcome == OUTCOME_FIRED)),
    )


def render_vsa_recovery_sequence_label_firing_audit_csv(
    summary: VSARecoverySequenceLabelFiringAuditSummary | Mapping[str, Any],
) -> str:
    """Render 6C label-firing audit rows to CSV."""

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(CSV_COLUMNS), lineterminator="\n")
    writer.writeheader()
    for row in _summary_rows(summary):
        writer.writerow(_csv_row(row))
    return output.getvalue()


def _audit_row(row: Mapping[str, Any]) -> VSARecoverySequenceLabelFiringAuditRow:
    status = str(row.get("recovery_sequence_status", row.get("status", STATUS_NONE)) or STATUS_NONE)
    outcome = _label_firing_outcome(status)
    expected_status = str(row.get("expected_status", row.get("expected_recovery_sequence_status", "")) or "")
    expectation_result = _expectation_result(actual=status, expected=expected_status)

    symbol = str(row.get("symbol", ""))
    cluster_id = str(row.get("cluster_id", ""))
    casebook_id = str(row.get("casebook_id", ""))

    prior_weakness_codes = _string_tuple(row.get("prior_weakness_codes"))
    stopping_volume_codes = _string_tuple(row.get("stopping_volume_codes"))
    spring_shakeout_codes = _string_tuple(row.get("spring_shakeout_codes"))
    follow_through_codes = _string_tuple(row.get("follow_through_codes"))
    blocker_codes = _string_tuple(row.get("blocker_codes"))
    ignored_audit_only_codes = _string_tuple(row.get("ignored_audit_only_codes"))

    return VSARecoverySequenceLabelFiringAuditRow(
        symbol=symbol,
        cluster_id=cluster_id,
        casebook_id=casebook_id,
        recovery_sequence_status=status,
        label_firing_outcome=outcome,
        expected_status=expected_status,
        expectation_result=expectation_result,
        review_marker=_optional_string(row.get("review_marker")),
        recommended_casebook_action=str(row.get("recommended_casebook_action", "")),
        qualification=str(row.get("qualification", "")),
        start_week=str(row.get("start_week", "")),
        end_week=str(row.get("end_week", row.get("start_week", ""))),
        start_bar_index=_int_or_default(row.get("start_bar_index"), -1),
        end_bar_index=_int_or_default(row.get("end_bar_index", row.get("start_bar_index")), -1),
        prior_weakness_codes=prior_weakness_codes,
        stopping_volume_codes=stopping_volume_codes,
        spring_shakeout_codes=spring_shakeout_codes,
        follow_through_codes=follow_through_codes,
        blocker_codes=blocker_codes,
        ignored_audit_only_codes=ignored_audit_only_codes,
        follow_through_evidence_age=_optional_int(row.get("follow_through_evidence_age")),
        used_fallback_evidence=_bool(row.get("used_fallback_evidence", False)),
        audit_note=_audit_note(
            outcome=outcome,
            expectation_result=expectation_result,
            prior_weakness_codes=prior_weakness_codes,
            stopping_volume_codes=stopping_volume_codes,
            spring_shakeout_codes=spring_shakeout_codes,
            follow_through_codes=follow_through_codes,
            blocker_codes=blocker_codes,
            ignored_audit_only_codes=ignored_audit_only_codes,
        ),
    )


def _label_firing_outcome(status: str) -> str:
    if status == STATUS_REVIEW:
        return OUTCOME_FIRED
    if status == STATUS_BLOCKED:
        return OUTCOME_BLOCKED
    if status == STATUS_NEEDS_FOLLOW_THROUGH:
        return OUTCOME_NEEDS_FOLLOW_THROUGH
    return OUTCOME_NOT_FIRED


def _expectation_result(*, actual: str, expected: str) -> str:
    if not expected:
        return EXPECTATION_UNSPECIFIED
    if actual == expected:
        return EXPECTATION_MATCHED
    return EXPECTATION_MISMATCHED


def _audit_note(
    *,
    outcome: str,
    expectation_result: str,
    prior_weakness_codes: tuple[str, ...],
    stopping_volume_codes: tuple[str, ...],
    spring_shakeout_codes: tuple[str, ...],
    follow_through_codes: tuple[str, ...],
    blocker_codes: tuple[str, ...],
    ignored_audit_only_codes: tuple[str, ...],
) -> str:
    expectation_note = {
        EXPECTATION_MATCHED: "expected status matched",
        EXPECTATION_MISMATCHED: "expected status mismatched",
        EXPECTATION_UNSPECIFIED: "no expected status supplied",
    }[expectation_result]

    if outcome == OUTCOME_FIRED:
        return (
            "6C label fired with prior weakness, stopping-volume anchor, "
            f"Spring/Shakeout test, and follow-through; {expectation_note}."
        )
    if outcome == OUTCOME_BLOCKED:
        return (
            "6C sequence was present but blocked by same-window supply/weakness "
            f"codes: {_join_or_none(blocker_codes)}; {expectation_note}."
        )
    if outcome == OUTCOME_NEEDS_FOLLOW_THROUGH:
        return (
            "6C sequence needs fresh follow-through before label firing; "
            f"follow-through codes: {_join_or_none(follow_through_codes)}; {expectation_note}."
        )

    missing = []
    if not prior_weakness_codes:
        missing.append("prior weakness")
    if not stopping_volume_codes:
        missing.append("stopping-volume anchor")
    if not spring_shakeout_codes:
        missing.append("Spring/Shakeout test")
    if not follow_through_codes:
        missing.append("demand follow-through")
    if ignored_audit_only_codes and not stopping_volume_codes:
        missing.append("production anchor after ignoring audit-only candidates")
    return f"6C label did not fire; missing {_join_or_none(tuple(missing))}; {expectation_note}."


def _extract_rows(payload: Mapping[str, Any] | Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    if isinstance(payload, Mapping):
        for key in ("rows", "casebook_rows", "audit_rows", "results"):
            if key in payload:
                return tuple(dict(item) for item in _mapping_sequence(payload.get(key)))
        return (dict(payload),)
    return tuple(dict(item) for item in payload if isinstance(item, Mapping))


def _summary_rows(
    summary: VSARecoverySequenceLabelFiringAuditSummary | Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    if isinstance(summary, VSARecoverySequenceLabelFiringAuditSummary):
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


def _top_rows(
    rows: Iterable[VSARecoverySequenceLabelFiringAuditRow],
    *,
    limit: int = 10,
) -> tuple[dict[str, Any], ...]:
    selected = sorted(rows, key=_audit_sort_key)[:limit]
    return tuple(
        {
            "symbol": row.symbol,
            "cluster_id": row.cluster_id,
            "casebook_id": row.casebook_id,
            "recovery_sequence_status": row.recovery_sequence_status,
            "label_firing_outcome": row.label_firing_outcome,
            "expected_status": row.expected_status,
            "expectation_result": row.expectation_result,
        }
        for row in selected
    )


def _audit_sort_key(row: VSARecoverySequenceLabelFiringAuditRow) -> tuple[int, int, str, str, str]:
    outcome_rank = {
        OUTCOME_FIRED: 0,
        OUTCOME_BLOCKED: 1,
        OUTCOME_NEEDS_FOLLOW_THROUGH: 2,
        OUTCOME_NOT_FIRED: 3,
    }.get(row.label_firing_outcome, 9)
    expectation_rank = {
        EXPECTATION_MISMATCHED: 0,
        EXPECTATION_MATCHED: 1,
        EXPECTATION_UNSPECIFIED: 2,
    }.get(row.expectation_result, 9)
    return (expectation_rank, outcome_rank, row.symbol, row.start_week, row.cluster_id)


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


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


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
    "EXPECTATION_MATCHED",
    "EXPECTATION_MISMATCHED",
    "EXPECTATION_UNSPECIFIED",
    "OUTCOME_BLOCKED",
    "OUTCOME_FIRED",
    "OUTCOME_NEEDS_FOLLOW_THROUGH",
    "OUTCOME_NOT_FIRED",
    "STATUS_BLOCKED",
    "STATUS_NEEDS_FOLLOW_THROUGH",
    "STATUS_NONE",
    "STATUS_REVIEW",
    "VSARecoverySequenceLabelFiringAuditRow",
    "VSARecoverySequenceLabelFiringAuditSummary",
    "build_vsa_recovery_sequence_label_firing_audit",
    "render_vsa_recovery_sequence_label_firing_audit_csv",
]
