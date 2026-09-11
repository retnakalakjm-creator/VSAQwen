from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from vsa_absorption_background_labels import (
    ABSORPTION_BACKGROUND_BLOCKER_CODES,
    ABSORPTION_BACKGROUND_CODES,
    ABSORPTION_DIAGNOSTIC_HINT_CODES,
    DEMAND_REVERSAL_FOLLOW_THROUGH_CODES,
    PRIOR_SUPPLY_CONTEXT_CODES,
    AbsorptionBackgroundReviewLabel,
    label_absorption_background_review,
)

DEFAULT_LOOKBACK_ROWS = 3
DEFAULT_LOOKAHEAD_ROWS = 3

CODE_FIELDS = (
    "target_event_codes",
    "scoring_event_codes",
    "qualifying_event_codes",
    "campaign_event_codes",
    "structural_event_codes",
    "vsa_event_codes",
)

DIAGNOSTIC_FIELDS = (
    "detector_diagnostics",
    "source_diagnostics",
    "diagnostic_hint_codes",
    "candidate_code",
    "source_audit_flags",
)

SEED_TYPE_ABSORPTION = "absorption_seed"
SEED_TYPE_DIAGNOSTIC = "diagnostic_seed"

CASE_ABSORPTION_BACKGROUND_REVIEW = "absorption_background_review"
CASE_ABSORPTION_BACKGROUND_BLOCKED = "absorption_background_blocked"
CASE_ABSORPTION_BACKGROUND_NEEDS_FOLLOW_THROUGH = "absorption_background_needs_follow_through"
CASE_ABSORPTION_BACKGROUND_NONE = "absorption_background_none"

RECOMMENDED_ACTION_REVIEW = "chart_review_absorption_background_candidate"
RECOMMENDED_ACTION_BLOCKED = "chart_review_absorption_background_blockers"
RECOMMENDED_ACTION_FOLLOW_THROUGH = "wait_for_absorption_background_follow_through"
RECOMMENDED_ACTION_NONE = "no_absorption_background_casebook_action"

CSV_COLUMNS = (
    "casebook_id",
    "symbol",
    "seed_type",
    "replay_week",
    "start_week",
    "end_week",
    "replay_bar_index",
    "start_bar_index",
    "end_bar_index",
    "case_type",
    "absorption_background_status",
    "review_marker",
    "frontend_label",
    "plain_english",
    "recommended_casebook_action",
    "qualification",
    "prior_supply_codes",
    "absorption_codes",
    "follow_through_codes",
    "blocker_codes",
    "diagnostic_hint_codes",
    "ignored_audit_only_codes",
    "follow_through_evidence_age",
    "used_fallback_evidence",
    "source_event_family",
    "source_priority",
    "manual_review_notes",
    "case_read",
    "audit_note",
)


@dataclass(frozen=True, slots=True)
class VSAAbsorptionBackgroundCasebookRow:
    """Audit-only casebook row for one 6D absorption-background review item."""

    casebook_id: str
    symbol: str
    seed_type: str
    replay_week: str
    start_week: str
    end_week: str
    replay_bar_index: int
    start_bar_index: int
    end_bar_index: int
    case_type: str
    absorption_background_status: str
    review_marker: str | None
    frontend_label: str | None
    plain_english: str
    recommended_casebook_action: str
    qualification: str
    prior_supply_codes: tuple[str, ...]
    absorption_codes: tuple[str, ...]
    follow_through_codes: tuple[str, ...]
    blocker_codes: tuple[str, ...]
    diagnostic_hint_codes: tuple[str, ...]
    ignored_audit_only_codes: tuple[str, ...]
    follow_through_evidence_age: int | None
    used_fallback_evidence: bool
    source_event_family: str
    source_priority: str
    manual_review_notes: str
    case_read: str
    audit_note: str
    audit_only: bool = True
    production_safe: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "audit_only": self.audit_only,
            "production_safe": self.production_safe,
            "casebook_id": self.casebook_id,
            "symbol": self.symbol,
            "seed_type": self.seed_type,
            "replay_week": self.replay_week,
            "start_week": self.start_week,
            "end_week": self.end_week,
            "replay_bar_index": self.replay_bar_index,
            "start_bar_index": self.start_bar_index,
            "end_bar_index": self.end_bar_index,
            "case_type": self.case_type,
            "absorption_background_status": self.absorption_background_status,
            "review_marker": self.review_marker,
            "frontend_label": self.frontend_label,
            "plain_english": self.plain_english,
            "recommended_casebook_action": self.recommended_casebook_action,
            "qualification": self.qualification,
            "prior_supply_codes": list(self.prior_supply_codes),
            "absorption_codes": list(self.absorption_codes),
            "follow_through_codes": list(self.follow_through_codes),
            "blocker_codes": list(self.blocker_codes),
            "diagnostic_hint_codes": list(self.diagnostic_hint_codes),
            "ignored_audit_only_codes": list(self.ignored_audit_only_codes),
            "follow_through_evidence_age": self.follow_through_evidence_age,
            "used_fallback_evidence": self.used_fallback_evidence,
            "source_event_family": self.source_event_family,
            "source_priority": self.source_priority,
            "manual_review_notes": self.manual_review_notes,
            "case_read": self.case_read,
            "audit_note": self.audit_note,
        }


@dataclass(frozen=True, slots=True)
class VSAAbsorptionBackgroundCasebookSummary:
    """Audit-only summary for 6D absorption-background casebook rows."""

    rows: tuple[VSAAbsorptionBackgroundCasebookRow, ...]
    total_input_rows: int
    total_casebook_rows: int
    status_counts: dict[str, int] = field(default_factory=dict)
    case_type_counts: dict[str, int] = field(default_factory=dict)
    seed_type_counts: dict[str, int] = field(default_factory=dict)
    recommended_action_counts: dict[str, int] = field(default_factory=dict)
    diagnostic_hint_counts: dict[str, int] = field(default_factory=dict)
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
            "seed_type_counts": dict(self.seed_type_counts),
            "recommended_action_counts": dict(self.recommended_action_counts),
            "diagnostic_hint_counts": dict(self.diagnostic_hint_counts),
            "top_casebook_items": [dict(item) for item in self.top_casebook_items],
            "rows": [row.to_dict() for row in self.rows],
        }


def build_vsa_absorption_background_casebook(
    payload: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    *,
    lookback_rows: int = DEFAULT_LOOKBACK_ROWS,
    lookahead_rows: int = DEFAULT_LOOKAHEAD_ROWS,
    include_diagnostic_hints: bool = True,
) -> VSAAbsorptionBackgroundCasebookSummary:
    """Create audit-only 6D absorption-background casebook rows from saved output.

    The builder consumes saved audit/replay rows and derives review rows from
    already-present production codes plus separately reported diagnostic hints.
    It does not load market data, call providers, replay scanners, mutate scanner
    state, activate detectors, alter scoring/ranking, write persistence, or touch
    API/frontend behavior.
    """

    safe_lookback = max(0, int(lookback_rows))
    safe_lookahead = max(0, int(lookahead_rows))
    replay_rows = tuple(_flatten_replay_rows(payload))
    grouped = _group_by_symbol(replay_rows)
    casebook_rows = tuple(
        sorted(
            (
                row
                for symbol_rows in grouped.values()
                for row in _casebook_rows_for_symbol(
                    symbol_rows,
                    lookback_rows=safe_lookback,
                    lookahead_rows=safe_lookahead,
                    include_diagnostic_hints=include_diagnostic_hints,
                )
            ),
            key=_casebook_sort_key,
        )
    )
    return VSAAbsorptionBackgroundCasebookSummary(
        rows=casebook_rows,
        total_input_rows=len(replay_rows),
        total_casebook_rows=len(casebook_rows),
        status_counts=_count(row.absorption_background_status for row in casebook_rows),
        case_type_counts=_count(row.case_type for row in casebook_rows),
        seed_type_counts=_count(row.seed_type for row in casebook_rows),
        recommended_action_counts=_count(row.recommended_casebook_action for row in casebook_rows),
        diagnostic_hint_counts=_count(
            hint for row in casebook_rows for hint in row.diagnostic_hint_codes
        ),
        top_casebook_items=_top_casebook_items(casebook_rows),
    )


def render_vsa_absorption_background_casebook_csv(
    summary: VSAAbsorptionBackgroundCasebookSummary | Mapping[str, Any],
) -> str:
    """Render 6D absorption-background casebook rows to CSV."""

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(CSV_COLUMNS), lineterminator="\n")
    writer.writeheader()
    for row in _summary_rows(summary):
        writer.writerow(_csv_row(row))
    return output.getvalue()


def _casebook_rows_for_symbol(
    symbol_rows: Sequence[Mapping[str, Any]],
    *,
    lookback_rows: int,
    lookahead_rows: int,
    include_diagnostic_hints: bool,
) -> tuple[VSAAbsorptionBackgroundCasebookRow, ...]:
    ordered = tuple(sorted(symbol_rows, key=_raw_row_sort_key))
    rows: list[VSAAbsorptionBackgroundCasebookRow] = []
    for index, row in enumerate(ordered):
        if not _is_casebook_seed(row, include_diagnostic_hints=include_diagnostic_hints):
            continue
        start = max(0, index - lookback_rows)
        end = min(len(ordered), index + lookahead_rows + 1)
        rows.append(
            _casebook_row(
                seed_row=row,
                prior_window=ordered[start : index + 1],
                forward_window=ordered[index:end],
            )
        )
    return tuple(rows)


def _casebook_row(
    *,
    seed_row: Mapping[str, Any],
    prior_window: Sequence[Mapping[str, Any]],
    forward_window: Sequence[Mapping[str, Any]],
) -> VSAAbsorptionBackgroundCasebookRow:
    symbol = str(seed_row.get("symbol", ""))
    replay_bar_index = _int_or_default(
        seed_row.get("replay_bar_index", seed_row.get("bar_index")), -1
    )
    replay_week = _week_text(seed_row.get("replay_week", seed_row.get("week_beginning", "")))
    start_bar_index = _int_or_default(
        prior_window[0].get("replay_bar_index", prior_window[0].get("bar_index", replay_bar_index)),
        replay_bar_index,
    )
    end_bar_index = _int_or_default(
        forward_window[-1].get("replay_bar_index", forward_window[-1].get("bar_index", replay_bar_index)),
        replay_bar_index,
    )
    start_week = _week_text(prior_window[0].get("replay_week", prior_window[0].get("week_beginning", replay_week)))
    end_week = _week_text(forward_window[-1].get("replay_week", forward_window[-1].get("week_beginning", replay_week)))
    qualification = _qualification(seed_row, prior_window)
    source_event_family = str(seed_row.get("event_family", seed_row.get("source_event_family", "")))
    source_priority = str(seed_row.get("priority", seed_row.get("source_priority", "")))

    prior_supply_codes = _window_codes(prior_window, PRIOR_SUPPLY_CONTEXT_CODES)
    absorption_codes = _window_codes((seed_row,), ABSORPTION_BACKGROUND_CODES)
    follow_through_codes = _window_codes(forward_window, DEMAND_REVERSAL_FOLLOW_THROUGH_CODES)
    blocker_codes = _window_codes((seed_row,), ABSORPTION_BACKGROUND_BLOCKER_CODES)
    diagnostic_hint_codes = _diagnostic_hints(seed_row)
    follow_through_rows = _rows_with_codes(forward_window, DEMAND_REVERSAL_FOLLOW_THROUGH_CODES)
    used_fallback_evidence = any(
        _bool(row.get("used_fallback_evidence", False)) for row in follow_through_rows
    )
    follow_through_evidence_age = 0 if follow_through_codes else None

    result = label_absorption_background_review(
        qualification=qualification,
        prior_evidence=prior_supply_codes,
        absorption_evidence=absorption_codes,
        follow_through_evidence=follow_through_codes,
        same_window_evidence=blocker_codes,
        diagnostic_evidence=diagnostic_hint_codes,
        follow_through_evidence_age=follow_through_evidence_age,
        used_fallback_evidence=used_fallback_evidence,
    )
    seed_type = _seed_type(seed_row)
    case_type = _case_type(result.status)
    recommended_action = _recommended_action(result.status)
    casebook_id = f"{symbol}:6d_absorption:{case_type}:{replay_week or replay_bar_index}"

    return VSAAbsorptionBackgroundCasebookRow(
        casebook_id=casebook_id,
        symbol=symbol,
        seed_type=seed_type,
        replay_week=replay_week,
        start_week=start_week,
        end_week=end_week,
        replay_bar_index=replay_bar_index,
        start_bar_index=start_bar_index,
        end_bar_index=end_bar_index,
        case_type=case_type,
        absorption_background_status=result.status.value,
        review_marker=result.review_marker,
        frontend_label=result.frontend_label,
        plain_english=result.plain_english,
        recommended_casebook_action=recommended_action,
        qualification=result.qualification,
        prior_supply_codes=result.prior_supply_codes,
        absorption_codes=result.absorption_codes,
        follow_through_codes=result.follow_through_codes,
        blocker_codes=result.blocker_codes,
        diagnostic_hint_codes=result.diagnostic_hint_codes,
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
            status=result.status.value,
            plain_english=result.plain_english,
            start_week=start_week,
            end_week=end_week,
            prior_supply_codes=result.prior_supply_codes,
            absorption_codes=result.absorption_codes,
            follow_through_codes=result.follow_through_codes,
            blocker_codes=result.blocker_codes,
        ),
        audit_note=_audit_note(
            status=result.status,
            diagnostic_hint_codes=result.diagnostic_hint_codes,
            blocker_codes=result.blocker_codes,
        ),
    )


def _is_casebook_seed(row: Mapping[str, Any], *, include_diagnostic_hints: bool) -> bool:
    production_codes = set(_production_codes(row))
    if production_codes & ABSORPTION_BACKGROUND_CODES:
        return True
    return include_diagnostic_hints and bool(_diagnostic_hints(row))


def _seed_type(row: Mapping[str, Any]) -> str:
    production_codes = set(_production_codes(row))
    if production_codes & ABSORPTION_BACKGROUND_CODES:
        return SEED_TYPE_ABSORPTION
    return SEED_TYPE_DIAGNOSTIC


def _case_type(status: AbsorptionBackgroundReviewLabel) -> str:
    if status is AbsorptionBackgroundReviewLabel.REVIEW:
        return CASE_ABSORPTION_BACKGROUND_REVIEW
    if status is AbsorptionBackgroundReviewLabel.BLOCKED:
        return CASE_ABSORPTION_BACKGROUND_BLOCKED
    if status is AbsorptionBackgroundReviewLabel.NEEDS_FOLLOW_THROUGH:
        return CASE_ABSORPTION_BACKGROUND_NEEDS_FOLLOW_THROUGH
    return CASE_ABSORPTION_BACKGROUND_NONE


def _recommended_action(status: AbsorptionBackgroundReviewLabel) -> str:
    if status is AbsorptionBackgroundReviewLabel.REVIEW:
        return RECOMMENDED_ACTION_REVIEW
    if status is AbsorptionBackgroundReviewLabel.BLOCKED:
        return RECOMMENDED_ACTION_BLOCKED
    if status is AbsorptionBackgroundReviewLabel.NEEDS_FOLLOW_THROUGH:
        return RECOMMENDED_ACTION_FOLLOW_THROUGH
    return RECOMMENDED_ACTION_NONE


def _case_read(
    *,
    symbol: str,
    case_type: str,
    recommended_action: str,
    status: str,
    plain_english: str,
    start_week: str,
    end_week: str,
    prior_supply_codes: Sequence[str],
    absorption_codes: Sequence[str],
    follow_through_codes: Sequence[str],
    blocker_codes: Sequence[str],
) -> str:
    period = start_week if start_week == end_week else f"{start_week} to {end_week}"
    return (
        f"{symbol} 6D absorption-background casebook item is {case_type} for {period}. "
        f"Status: {status}. "
        f"Plain English: {plain_english} "
        f"Prior supply context: {_join_or_none(prior_supply_codes)}. "
        f"Absorption evidence: {_join_or_none(absorption_codes)}. "
        f"Follow-through: {_join_or_none(follow_through_codes)}. "
        f"Blockers: {_join_or_none(blocker_codes)}. "
        f"Next action: {recommended_action}."
    )


def _audit_note(
    *,
    status: AbsorptionBackgroundReviewLabel,
    diagnostic_hint_codes: tuple[str, ...],
    blocker_codes: tuple[str, ...],
) -> str:
    diagnostic_note = (
        f" Diagnostic hints: {_join_or_none(diagnostic_hint_codes)}."
        if diagnostic_hint_codes
        else ""
    )
    if status is AbsorptionBackgroundReviewLabel.REVIEW:
        return f"6D seed produced a review-only absorption-background candidate.{diagnostic_note}"
    if status is AbsorptionBackgroundReviewLabel.BLOCKED:
        return (
            "6D seed had absorption and follow-through but remained blocked by same-window "
            f"evidence: {_join_or_none(blocker_codes)}.{diagnostic_note}"
        )
    if status is AbsorptionBackgroundReviewLabel.NEEDS_FOLLOW_THROUGH:
        return f"6D seed needs fresh non-fallback demand or reversal follow-through.{diagnostic_note}"
    return f"6D seed did not satisfy clean absorption-background review.{diagnostic_note}"


def _flatten_replay_rows(
    payload: Mapping[str, Any] | Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    if isinstance(payload, Mapping):
        if "results" in payload:
            rows: list[dict[str, Any]] = []
            for result in _mapping_sequence(payload.get("results")):
                result_symbol = str(result.get("symbol", ""))
                for row in _mapping_sequence(result.get("rows")):
                    item = dict(row)
                    if result_symbol and not item.get("symbol"):
                        item["symbol"] = result_symbol
                    rows.append(item)
            return tuple(rows)
        for key in ("rows", "replay_rows", "audit_rows", "casebook_rows", "review_rows"):
            if key in payload:
                return tuple(dict(row) for row in _mapping_sequence(payload.get(key)))
        return (dict(payload),)

    flattened: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, Mapping):
            continue
        if "rows" in item:
            result_symbol = str(item.get("symbol", ""))
            for row in _mapping_sequence(item.get("rows")):
                output = dict(row)
                if result_symbol and not output.get("symbol"):
                    output["symbol"] = result_symbol
                flattened.append(output)
        else:
            flattened.append(dict(item))
    return tuple(flattened)


def _group_by_symbol(rows: Sequence[Mapping[str, Any]]) -> dict[str, tuple[Mapping[str, Any], ...]]:
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get("symbol", "")), []).append(row)
    return {symbol: tuple(items) for symbol, items in grouped.items()}


def _qualification(seed_row: Mapping[str, Any], prior_window: Sequence[Mapping[str, Any]]) -> str:
    seed_qualification = str(seed_row.get("qualification", seed_row.get("source_qualification", "")))
    if seed_qualification:
        return seed_qualification
    for row in reversed(prior_window):
        qualification = str(row.get("qualification", row.get("source_qualification", "")))
        if qualification:
            return qualification
    return ""


def _window_codes(rows: Sequence[Mapping[str, Any]], allowed_codes: frozenset[str]) -> tuple[str, ...]:
    selected: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for code in _production_codes(row):
            if code in allowed_codes and code not in seen:
                selected.append(code)
                seen.add(code)
    return tuple(selected)


def _rows_with_codes(
    rows: Sequence[Mapping[str, Any]],
    allowed_codes: frozenset[str],
) -> tuple[Mapping[str, Any], ...]:
    return tuple(row for row in rows if set(_production_codes(row)) & allowed_codes)


def _production_codes(row: Mapping[str, Any]) -> tuple[str, ...]:
    selected: list[str] = []
    seen: set[str] = set()
    for field in CODE_FIELDS:
        for code in _string_tuple(row.get(field)):
            normalized = _normalize_code(code)
            if normalized and normalized not in seen:
                selected.append(normalized)
                seen.add(normalized)
    return tuple(selected)


def _diagnostic_hints(row: Mapping[str, Any]) -> tuple[str, ...]:
    selected: list[str] = []
    seen: set[str] = set()
    for field in DIAGNOSTIC_FIELDS:
        for code in _string_tuple(row.get(field)):
            normalized = _normalize_code(code)
            if normalized in ABSORPTION_DIAGNOSTIC_HINT_CODES and normalized not in seen:
                selected.append(normalized)
                seen.add(normalized)
    return tuple(selected)


def _summary_rows(
    summary: VSAAbsorptionBackgroundCasebookSummary | Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    if isinstance(summary, VSAAbsorptionBackgroundCasebookSummary):
        return tuple(row.to_dict() for row in summary.rows)
    return tuple(dict(row) for row in _mapping_sequence(summary.get("rows")))


def _csv_row(row: Mapping[str, Any]) -> dict[str, str]:
    output: dict[str, str] = {}
    for column in CSV_COLUMNS:
        value = row.get(column, "")
        if isinstance(value, (list, tuple)):
            output[column] = ";".join(str(item) for item in value)
        else:
            output[column] = "" if value is None else str(value)
    return output


def _top_casebook_items(
    rows: Sequence[VSAAbsorptionBackgroundCasebookRow],
    *,
    limit: int = 10,
) -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "casebook_id": row.casebook_id,
            "symbol": row.symbol,
            "case_type": row.case_type,
            "absorption_background_status": row.absorption_background_status,
            "review_marker": row.review_marker,
            "frontend_label": row.frontend_label,
            "plain_english": row.plain_english,
            "recommended_casebook_action": row.recommended_casebook_action,
            "diagnostic_hint_codes": list(row.diagnostic_hint_codes),
        }
        for row in sorted(rows, key=_casebook_sort_key)[:limit]
    )


def _casebook_sort_key(row: VSAAbsorptionBackgroundCasebookRow) -> tuple[int, str, int, str]:
    rank = {
        CASE_ABSORPTION_BACKGROUND_REVIEW: 0,
        CASE_ABSORPTION_BACKGROUND_BLOCKED: 1,
        CASE_ABSORPTION_BACKGROUND_NEEDS_FOLLOW_THROUGH: 2,
        CASE_ABSORPTION_BACKGROUND_NONE: 3,
    }.get(row.case_type, 9)
    return (rank, row.symbol, row.replay_bar_index, row.casebook_id)


def _raw_row_sort_key(row: Mapping[str, Any]) -> tuple[int, str]:
    return (
        _int_or_default(row.get("replay_bar_index", row.get("bar_index")), -1),
        _week_text(row.get("replay_week", row.get("week_beginning", ""))),
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
    if isinstance(value, Mapping):
        code = value.get("code")
        return (_normalize_code(code),) if code else ()
    if isinstance(value, Iterable):
        return tuple(
            _normalize_code(item.get("code") if isinstance(item, Mapping) else item)
            for item in value
            if _normalize_code(item.get("code") if isinstance(item, Mapping) else item)
        )
    return (str(value),) if str(value) else ()


def _normalize_code(value: Any) -> str:
    return str(getattr(value, "value", value)).strip().lower() if value is not None else ""


def _week_text(value: Any) -> str:
    text = str(value or "")
    if " " in text:
        return text.split(" ", 1)[0]
    return text


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
    "CASE_ABSORPTION_BACKGROUND_BLOCKED",
    "CASE_ABSORPTION_BACKGROUND_NEEDS_FOLLOW_THROUGH",
    "CASE_ABSORPTION_BACKGROUND_NONE",
    "CASE_ABSORPTION_BACKGROUND_REVIEW",
    "DEFAULT_LOOKAHEAD_ROWS",
    "DEFAULT_LOOKBACK_ROWS",
    "DIAGNOSTIC_FIELDS",
    "RECOMMENDED_ACTION_BLOCKED",
    "RECOMMENDED_ACTION_FOLLOW_THROUGH",
    "RECOMMENDED_ACTION_NONE",
    "RECOMMENDED_ACTION_REVIEW",
    "SEED_TYPE_ABSORPTION",
    "SEED_TYPE_DIAGNOSTIC",
    "VSAAbsorptionBackgroundCasebookRow",
    "VSAAbsorptionBackgroundCasebookSummary",
    "build_vsa_absorption_background_casebook",
    "render_vsa_absorption_background_casebook_csv",
]
