from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from vsa_audit_batch_review import build_vsa_audit_batch_review

TRIAGE_CLEAN_CANDIDATE = "clean_candidate"
TRIAGE_OVERLAPPING_CLUSTER = "overlapping_candidate_cluster"
TRIAGE_CONTRADICTORY_PRODUCTION = "contradictory_production_evidence"
TRIAGE_QUALIFICATION_LIFECYCLE = "qualification_lifecycle_issue"
TRIAGE_LIKELY_NOISY = "likely_noisy_diagnostic"
TRIAGE_MANUAL_CHART_REVIEW = "manual_chart_review"

GRADE_ORDER = {"A": 0, "B": 1, "C": 2, "D": 3}
GRADE_SCORE = {"A": 90, "B": 75, "C": 55, "D": 30}

BULLISH_VSA_CODES = frozenset(
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

BEARISH_VSA_CODES = frozenset(
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

QUALIFICATION_CONFLICT_FLAGS = frozenset(
    {
        "bullish_vsa_against_bearish_qualification",
        "bearish_vsa_against_bullish_qualification",
    }
)

CSV_COLUMNS = (
    "symbol",
    "replay_week",
    "replay_bar_index",
    "candidate_family",
    "candidate_code",
    "priority",
    "direction",
    "qualification",
    "triage_bucket",
    "triage_grade",
    "triage_score",
    "cluster_size",
    "sibling_candidate_families",
    "same_week_candidate_codes",
    "target_event_codes",
    "scoring_event_codes",
    "source_diagnostics",
    "source_audit_flags",
    "triage_reasons",
    "recommended_action",
)


@dataclass(frozen=True, slots=True)
class VSAAuditCandidateTriageRow:
    """Audit-only triage row for one candidate-event review item."""

    symbol: str
    replay_week: str
    replay_bar_index: int
    candidate_family: str
    candidate_code: str
    priority: str
    direction: str
    qualification: str
    triage_bucket: str
    triage_grade: str
    triage_score: int
    cluster_size: int
    sibling_candidate_families: tuple[str, ...]
    same_week_candidate_codes: tuple[str, ...]
    target_event_codes: tuple[str, ...]
    scoring_event_codes: tuple[str, ...]
    source_diagnostics: tuple[str, ...]
    source_audit_flags: tuple[str, ...]
    original_reason: str
    triage_reasons: tuple[str, ...]
    recommended_action: str
    audit_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "replay_week": self.replay_week,
            "replay_bar_index": self.replay_bar_index,
            "candidate_family": self.candidate_family,
            "candidate_code": self.candidate_code,
            "priority": self.priority,
            "direction": self.direction,
            "qualification": self.qualification,
            "triage_bucket": self.triage_bucket,
            "triage_grade": self.triage_grade,
            "triage_score": self.triage_score,
            "cluster_size": self.cluster_size,
            "sibling_candidate_families": list(self.sibling_candidate_families),
            "same_week_candidate_codes": list(self.same_week_candidate_codes),
            "target_event_codes": list(self.target_event_codes),
            "scoring_event_codes": list(self.scoring_event_codes),
            "source_diagnostics": list(self.source_diagnostics),
            "source_audit_flags": list(self.source_audit_flags),
            "original_reason": self.original_reason,
            "triage_reasons": list(self.triage_reasons),
            "recommended_action": self.recommended_action,
            "audit_only": self.audit_only,
        }


@dataclass(frozen=True, slots=True)
class VSAAuditCandidateTriageSummary:
    """Compact audit-only triage summary for candidate-event review output."""

    rows: tuple[VSAAuditCandidateTriageRow, ...]
    total_input_rows: int
    total_triage_rows: int
    min_priority: str
    bucket_counts: dict[str, int] = field(default_factory=dict)
    grade_counts: dict[str, int] = field(default_factory=dict)
    candidate_counts: dict[str, int] = field(default_factory=dict)
    family_counts: dict[str, int] = field(default_factory=dict)
    symbol_counts: dict[str, int] = field(default_factory=dict)
    week_counts: dict[str, int] = field(default_factory=dict)
    top_triage_symbols: tuple[dict[str, Any], ...] = ()
    triage_focus: tuple[dict[str, Any], ...] = ()
    audit_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "audit_only": self.audit_only,
            "min_priority": self.min_priority,
            "total_input_rows": self.total_input_rows,
            "total_triage_rows": self.total_triage_rows,
            "bucket_counts": dict(self.bucket_counts),
            "grade_counts": dict(self.grade_counts),
            "candidate_counts": dict(self.candidate_counts),
            "family_counts": dict(self.family_counts),
            "symbol_counts": dict(self.symbol_counts),
            "week_counts": dict(self.week_counts),
            "top_triage_symbols": [dict(row) for row in self.top_triage_symbols],
            "triage_focus": [dict(row) for row in self.triage_focus],
            "rows": [row.to_dict() for row in self.rows],
        }


def build_vsa_audit_candidate_triage(
    payload: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    *,
    min_priority: str = "high",
) -> VSAAuditCandidateTriageSummary:
    """Triage candidate-event rows into review buckets.

    The triage layer consumes already-saved audit, candidate-event, or batch-review
    JSON. It does not load market data, call providers, replay the scanner,
    persist results, activate detectors, change scanner scoring/ranking, or affect
    frontend/API production behavior.
    """

    batch_review = build_vsa_audit_batch_review(payload, min_priority=min_priority)
    source_rows = tuple(dict(row) for row in batch_review.rows)
    clusters = _cluster_rows(source_rows)
    triage_rows = tuple(
        sorted(
            (
                _triage_candidate_row(row, clusters[_cluster_key(row)])
                for row in source_rows
            ),
            key=_triage_sort_key,
        )
    )

    return VSAAuditCandidateTriageSummary(
        rows=triage_rows,
        total_input_rows=batch_review.source_candidate_rows,
        total_triage_rows=len(triage_rows),
        min_priority=min_priority,
        bucket_counts=_count(row.triage_bucket for row in triage_rows),
        grade_counts=_count(row.triage_grade for row in triage_rows),
        candidate_counts=_count(row.candidate_code for row in triage_rows),
        family_counts=_count(row.candidate_family for row in triage_rows),
        symbol_counts=_count(row.symbol for row in triage_rows),
        week_counts=_count(row.replay_week for row in triage_rows),
        top_triage_symbols=_top_triage_symbols(triage_rows),
        triage_focus=_triage_focus(triage_rows),
    )


def render_vsa_audit_candidate_triage_csv(
    triage: VSAAuditCandidateTriageSummary | Mapping[str, Any],
) -> str:
    """Render triage rows to CSV for manual chart review."""

    rows = _triage_rows(triage)
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(CSV_COLUMNS), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(_csv_row(row))
    return output.getvalue()


def _triage_candidate_row(
    row: Mapping[str, Any],
    cluster_rows: Sequence[Mapping[str, Any]],
) -> VSAAuditCandidateTriageRow:
    target_codes = _string_tuple(row.get("target_event_codes"))
    scoring_codes = _string_tuple(row.get("scoring_event_codes"))
    diagnostics = _string_tuple(row.get("source_diagnostics"))
    flags = _string_tuple(row.get("source_audit_flags"))
    candidate_family = str(row.get("candidate_family", ""))
    candidate_code = str(row.get("candidate_code", ""))
    direction = str(row.get("direction", ""))
    qualification = str(row.get("qualification", ""))
    cluster_families = tuple(sorted(_unique(item.get("candidate_family") for item in cluster_rows)))
    sibling_families = tuple(family for family in cluster_families if family != candidate_family)
    cluster_codes = tuple(sorted(_unique(item.get("candidate_code") for item in cluster_rows)))
    bucket, grade, reasons = _classify_row(
        candidate_family=candidate_family,
        direction=direction,
        qualification=qualification,
        target_codes=target_codes,
        scoring_codes=scoring_codes,
        flags=flags,
        cluster_size=len(cluster_rows),
        cluster_families=cluster_families,
    )
    score = _triage_score(grade, len(cluster_rows), bucket)

    return VSAAuditCandidateTriageRow(
        symbol=str(row.get("symbol", "")),
        replay_week=str(row.get("replay_week", "")),
        replay_bar_index=_int_or_default(row.get("replay_bar_index"), -1),
        candidate_family=candidate_family,
        candidate_code=candidate_code,
        priority=str(row.get("priority", "")),
        direction=direction,
        qualification=qualification,
        triage_bucket=bucket,
        triage_grade=grade,
        triage_score=score,
        cluster_size=len(cluster_rows),
        sibling_candidate_families=sibling_families,
        same_week_candidate_codes=cluster_codes,
        target_event_codes=target_codes,
        scoring_event_codes=scoring_codes,
        source_diagnostics=diagnostics,
        source_audit_flags=flags,
        original_reason=str(row.get("reason", row.get("original_reason", ""))),
        triage_reasons=reasons,
        recommended_action=_recommended_action(bucket),
    )


def _classify_row(
    *,
    candidate_family: str,
    direction: str,
    qualification: str,
    target_codes: tuple[str, ...],
    scoring_codes: tuple[str, ...],
    flags: tuple[str, ...],
    cluster_size: int,
    cluster_families: tuple[str, ...],
) -> tuple[str, str, tuple[str, ...]]:
    all_codes = set(target_codes).union(scoring_codes)
    has_bullish_vsa = bool(all_codes.intersection(BULLISH_VSA_CODES))
    has_bearish_vsa = bool(all_codes.intersection(BEARISH_VSA_CODES))
    is_bullish_reversal = direction == "bullish_reversal_review"
    has_qualification_conflict = bool(set(flags).intersection(QUALIFICATION_CONFLICT_FLAGS))

    if candidate_family == "qualification_lifecycle" or has_qualification_conflict:
        return (
            TRIAGE_QUALIFICATION_LIFECYCLE,
            "A",
            (
                "active qualification conflicts with current VSA evidence",
                "review lifecycle expiry or invalidation before adding detector weight",
            ),
        )

    if cluster_size >= 3 or len(cluster_families) >= 3:
        return (
            TRIAGE_OVERLAPPING_CLUSTER,
            "B",
            (
                "multiple candidate families appear on the same symbol/week",
                "review as a cluster instead of treating one detector in isolation",
            ),
        )

    if is_bullish_reversal and has_bearish_vsa and has_bullish_vsa:
        return (
            TRIAGE_MANUAL_CHART_REVIEW,
            "C",
            (
                "same row has both bullish and bearish production evidence",
                "manual chart review is needed before changing production rules",
            ),
        )

    if is_bullish_reversal and has_bearish_vsa and not has_bullish_vsa:
        return (
            TRIAGE_CONTRADICTORY_PRODUCTION,
            "C",
            (
                "candidate is bullish reversal review but production evidence is bearish",
                "treat as contradiction until detector gates are inspected",
            ),
        )

    if is_bullish_reversal and qualification == "persistent_bullish" and not has_bearish_vsa:
        return (
            TRIAGE_LIKELY_NOISY,
            "D",
            (
                "bullish reversal candidate appears while qualification is already bullish",
                "likely continuation or redundant diagnostic rather than a reversal event",
            ),
        )

    if not target_codes and not scoring_codes:
        return (
            TRIAGE_MANUAL_CHART_REVIEW,
            "C",
            (
                "candidate row has no same-week or scoring evidence context",
                "manual chart review is needed before treating this as a clean miss",
            ),
        )

    return (
        TRIAGE_CLEAN_CANDIDATE,
        "B" if not has_bullish_vsa else "A",
        (
            "candidate has no immediate contradiction from production evidence",
            "review as a cleaner calibration candidate before production activation",
        ),
    )


def _recommended_action(bucket: str) -> str:
    if bucket == TRIAGE_QUALIFICATION_LIFECYCLE:
        return "prioritize lifecycle/qualification invalidation rules"
    if bucket == TRIAGE_OVERLAPPING_CLUSTER:
        return "review the full same-week candidate cluster on the chart"
    if bucket == TRIAGE_CONTRADICTORY_PRODUCTION:
        return "inspect production detector gates and bearish evidence context"
    if bucket == TRIAGE_CLEAN_CANDIDATE:
        return "use as candidate for detector calibration after chart confirmation"
    if bucket == TRIAGE_LIKELY_NOISY:
        return "deprioritize unless chart review shows a real reversal setup"
    return "manual chart review before production rule changes"


def _triage_score(grade: str, cluster_size: int, bucket: str) -> int:
    score = GRADE_SCORE.get(grade, 50)
    if bucket == TRIAGE_OVERLAPPING_CLUSTER:
        score += min(cluster_size, 5)
    if bucket == TRIAGE_QUALIFICATION_LIFECYCLE:
        score += 5
    return min(score, 99)


def _cluster_rows(rows: Sequence[Mapping[str, Any]]) -> dict[tuple[str, str], tuple[Mapping[str, Any], ...]]:
    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(_cluster_key(row), []).append(row)
    return {key: tuple(value) for key, value in grouped.items()}


def _cluster_key(row: Mapping[str, Any]) -> tuple[str, str]:
    return str(row.get("symbol", "")), str(row.get("replay_week", ""))


def _top_triage_symbols(rows: tuple[VSAAuditCandidateTriageRow, ...]) -> tuple[dict[str, Any], ...]:
    grouped: dict[str, list[VSAAuditCandidateTriageRow]] = {}
    for row in rows:
        grouped.setdefault(row.symbol, []).append(row)

    selected: list[dict[str, Any]] = []
    for symbol, symbol_rows in grouped.items():
        selected.append(
            {
                "symbol": symbol,
                "total_rows": len(symbol_rows),
                "grade_counts": _count(row.triage_grade for row in symbol_rows),
                "bucket_counts": _count(row.triage_bucket for row in symbol_rows),
                "candidate_counts": _count(row.candidate_code for row in symbol_rows),
                "highest_grade": min((row.triage_grade for row in symbol_rows), key=_grade_rank),
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


def _triage_focus(rows: tuple[VSAAuditCandidateTriageRow, ...]) -> tuple[dict[str, Any], ...]:
    grouped: dict[str, list[VSAAuditCandidateTriageRow]] = {}
    for row in rows:
        grouped.setdefault(row.triage_bucket, []).append(row)

    selected: list[dict[str, Any]] = []
    for bucket, bucket_rows in grouped.items():
        selected.append(
            {
                "triage_bucket": bucket,
                "total_rows": len(bucket_rows),
                "grade_counts": _count(row.triage_grade for row in bucket_rows),
                "symbols": sorted(_unique(row.symbol for row in bucket_rows)),
                "candidate_families": sorted(_unique(row.candidate_family for row in bucket_rows)),
                "recommended_action": _recommended_action(bucket),
            }
        )
    return tuple(
        sorted(
            selected,
            key=lambda item: (
                _bucket_rank(str(item["triage_bucket"])),
                -int(item["total_rows"]),
            ),
        )
    )


def _triage_rows(triage: VSAAuditCandidateTriageSummary | Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    if isinstance(triage, VSAAuditCandidateTriageSummary):
        return tuple(row.to_dict() for row in triage.rows)
    raw_rows = triage.get("rows", ())
    return tuple(dict(row) for row in raw_rows if isinstance(row, Mapping))


def _csv_row(row: Mapping[str, Any]) -> dict[str, str]:
    return {
        column: _format_csv_value(row.get(column, "")) for column in CSV_COLUMNS
    }


def _triage_sort_key(row: VSAAuditCandidateTriageRow) -> tuple[int, int, str, str, str, str]:
    return (
        _grade_rank(row.triage_grade),
        _bucket_rank(row.triage_bucket),
        row.symbol,
        row.replay_week,
        row.candidate_family,
        row.candidate_code,
    )


def _grade_rank(grade: str) -> int:
    return GRADE_ORDER.get(grade, 99)


def _bucket_rank(bucket: str) -> int:
    order = {
        TRIAGE_QUALIFICATION_LIFECYCLE: 0,
        TRIAGE_CLEAN_CANDIDATE: 1,
        TRIAGE_OVERLAPPING_CLUSTER: 2,
        TRIAGE_CONTRADICTORY_PRODUCTION: 3,
        TRIAGE_MANUAL_CHART_REVIEW: 4,
        TRIAGE_LIKELY_NOISY: 5,
    }
    return order.get(bucket, 99)


def _string_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,) if value else ()
    try:
        return _unique(str(item) for item in value if str(item))
    except TypeError:
        text = str(value)
        return (text,) if text else ()


def _format_csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return "|".join(str(item) for item in value)
    except TypeError:
        return str(value)


def _int_or_default(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _count(values: Iterable[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        text = str(value or "")
        if not text:
            continue
        counts[text] = counts.get(text, 0) + 1
    return counts


def _unique(values: Iterable[Any]) -> tuple[str, ...]:
    selected: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "")
        if not text or text in seen:
            continue
        selected.append(text)
        seen.add(text)
    return tuple(selected)
