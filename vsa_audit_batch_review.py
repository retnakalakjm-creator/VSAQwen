from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from vsa_audit_candidate_events import build_audit_candidate_event_summary

PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
DEFAULT_MIN_PRIORITY = "medium"
CSV_COLUMNS = (
    "symbol",
    "replay_week",
    "replay_bar_index",
    "candidate_family",
    "candidate_code",
    "priority",
    "direction",
    "qualification",
    "production_status",
    "target_event_codes",
    "scoring_event_codes",
    "source_diagnostics",
    "source_audit_flags",
    "reason",
)


@dataclass(frozen=True, slots=True)
class VSAAuditBatchReview:
    """Compact audit-only basket review for VSA candidate events.

    The batch review consumes already-saved VSA audit or candidate-event JSON.
    It does not load market data, replay the scanner, persist state, or change
    detector/scoring behavior. It exists so a 30-stock basket can be filtered
    into the few symbols/weeks that deserve manual chart review.
    """

    rows: tuple[dict[str, Any], ...]
    source_candidate_rows: int
    total_review_rows: int
    high_priority_rows: int
    medium_priority_rows: int
    symbols_with_candidates: tuple[str, ...]
    candidate_counts: dict[str, int] = field(default_factory=dict)
    family_counts: dict[str, int] = field(default_factory=dict)
    priority_counts: dict[str, int] = field(default_factory=dict)
    symbol_counts: dict[str, int] = field(default_factory=dict)
    week_counts: dict[str, int] = field(default_factory=dict)
    top_review_symbols: tuple[dict[str, Any], ...] = ()
    review_focus: tuple[dict[str, Any], ...] = ()
    audit_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "audit_only": self.audit_only,
            "source_candidate_rows": self.source_candidate_rows,
            "total_review_rows": self.total_review_rows,
            "high_priority_rows": self.high_priority_rows,
            "medium_priority_rows": self.medium_priority_rows,
            "symbols_with_candidates": list(self.symbols_with_candidates),
            "candidate_counts": dict(self.candidate_counts),
            "family_counts": dict(self.family_counts),
            "priority_counts": dict(self.priority_counts),
            "symbol_counts": dict(self.symbol_counts),
            "week_counts": dict(self.week_counts),
            "top_review_symbols": [dict(row) for row in self.top_review_symbols],
            "review_focus": [dict(row) for row in self.review_focus],
            "rows": [dict(row) for row in self.rows],
        }


def build_vsa_audit_batch_review(
    payload: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    *,
    min_priority: str = DEFAULT_MIN_PRIORITY,
) -> VSAAuditBatchReview:
    """Build a compact basket review from audit JSON or candidate-event JSON.

    Input may be a full `/api/vsa-audit/events` response, a flat/listed audit
    row payload, a candidate-event summary, or a flat list of candidate-event
    rows. Candidate rows are filtered by `min_priority` and sorted in a stable
    review order.
    """

    _validate_min_priority(min_priority)
    candidate_summary = _coerce_candidate_summary(payload)
    source_rows = tuple(_candidate_rows(candidate_summary.get("rows", ())))
    filtered_rows = tuple(
        sorted(
            (row for row in source_rows if _priority_rank(row.get("priority")) <= _priority_rank(min_priority)),
            key=_review_sort_key,
        )
    )

    return VSAAuditBatchReview(
        rows=filtered_rows,
        source_candidate_rows=len(source_rows),
        total_review_rows=len(filtered_rows),
        high_priority_rows=sum(1 for row in filtered_rows if row.get("priority") == "high"),
        medium_priority_rows=sum(1 for row in filtered_rows if row.get("priority") == "medium"),
        symbols_with_candidates=tuple(sorted(_unique(row.get("symbol") for row in filtered_rows))),
        candidate_counts=_count(row.get("candidate_code") for row in filtered_rows),
        family_counts=_count(row.get("candidate_family") for row in filtered_rows),
        priority_counts=_count(row.get("priority") for row in filtered_rows),
        symbol_counts=_count(row.get("symbol") for row in filtered_rows),
        week_counts=_count(row.get("replay_week") for row in filtered_rows),
        top_review_symbols=_top_review_symbols(filtered_rows),
        review_focus=_review_focus(filtered_rows),
    )


def render_vsa_audit_batch_review_csv(review: VSAAuditBatchReview | Mapping[str, Any]) -> str:
    """Render review rows to CSV for spreadsheet/manual chart review."""

    rows = _review_rows(review)
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(CSV_COLUMNS), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(_csv_row(row))
    return output.getvalue()


def _coerce_candidate_summary(
    payload: Mapping[str, Any] | Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if isinstance(payload, Mapping):
        if _looks_like_candidate_summary(payload):
            return dict(payload)
        return build_audit_candidate_event_summary(payload).to_dict()

    items = list(payload)
    if items and all(isinstance(item, Mapping) and "candidate_code" in item for item in items):
        return {"rows": [dict(item) for item in items], "audit_only": True}
    return build_audit_candidate_event_summary(items).to_dict()


def _looks_like_candidate_summary(payload: Mapping[str, Any]) -> bool:
    rows = payload.get("rows")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        return False
    return any(isinstance(row, Mapping) and "candidate_code" in row for row in rows)


def _candidate_rows(rows: Iterable[Any]) -> Iterable[dict[str, Any]]:
    for row in rows:
        if isinstance(row, Mapping):
            yield dict(row)


def _review_rows(review: VSAAuditBatchReview | Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    if isinstance(review, VSAAuditBatchReview):
        return review.rows
    return tuple(_candidate_rows(review.get("rows", ())))


def _csv_row(row: Mapping[str, Any]) -> dict[str, str]:
    return {
        "symbol": str(row.get("symbol", "")),
        "replay_week": str(row.get("replay_week", "")),
        "replay_bar_index": str(row.get("replay_bar_index", "")),
        "candidate_family": str(row.get("candidate_family", "")),
        "candidate_code": str(row.get("candidate_code", "")),
        "priority": str(row.get("priority", "")),
        "direction": str(row.get("direction", "")),
        "qualification": str(row.get("qualification", "")),
        "production_status": str(row.get("production_status", "")),
        "target_event_codes": _join_values(row.get("target_event_codes", ())),
        "scoring_event_codes": _join_values(row.get("scoring_event_codes", ())),
        "source_diagnostics": _join_values(row.get("source_diagnostics", ())),
        "source_audit_flags": _join_values(row.get("source_audit_flags", ())),
        "reason": str(row.get("reason", "")),
    }


def _top_review_symbols(rows: tuple[dict[str, Any], ...]) -> tuple[dict[str, Any], ...]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get("symbol", "")), []).append(row)

    selected = []
    for symbol, symbol_rows in grouped.items():
        selected.append(
            {
                "symbol": symbol,
                "total_rows": len(symbol_rows),
                "high_priority_rows": sum(1 for row in symbol_rows if row.get("priority") == "high"),
                "medium_priority_rows": sum(1 for row in symbol_rows if row.get("priority") == "medium"),
                "family_counts": _count(row.get("candidate_family") for row in symbol_rows),
                "candidate_counts": _count(row.get("candidate_code") for row in symbol_rows),
            }
        )
    return tuple(
        sorted(
            selected,
            key=lambda item: (
                -int(item["high_priority_rows"]),
                -int(item["total_rows"]),
                str(item["symbol"]),
            ),
        )
    )


def _review_focus(rows: tuple[dict[str, Any], ...]) -> tuple[dict[str, Any], ...]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get("candidate_code", "")), []).append(row)

    selected = []
    for candidate_code, candidate_rows in grouped.items():
        selected.append(
            {
                "candidate_code": candidate_code,
                "candidate_family": str(candidate_rows[0].get("candidate_family", "")),
                "total_rows": len(candidate_rows),
                "high_priority_rows": sum(1 for row in candidate_rows if row.get("priority") == "high"),
                "medium_priority_rows": sum(1 for row in candidate_rows if row.get("priority") == "medium"),
                "symbols": sorted(_unique(row.get("symbol") for row in candidate_rows)),
                "reason": str(candidate_rows[0].get("reason", "")),
            }
        )
    return tuple(
        sorted(
            selected,
            key=lambda item: (
                -int(item["high_priority_rows"]),
                -int(item["total_rows"]),
                str(item["candidate_family"]),
                str(item["candidate_code"]),
            ),
        )
    )


def _review_sort_key(row: Mapping[str, Any]) -> tuple[int, str, str, str, str]:
    return (
        _priority_rank(row.get("priority")),
        str(row.get("symbol", "")),
        str(row.get("replay_week", "")),
        str(row.get("candidate_family", "")),
        str(row.get("candidate_code", "")),
    )


def _validate_min_priority(priority: str) -> None:
    if priority not in {"medium", "high"}:
        raise ValueError("min_priority must be 'medium' or 'high'")


def _priority_rank(priority: Any) -> int:
    return PRIORITY_ORDER.get(str(priority), PRIORITY_ORDER["medium"])


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


def _join_values(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return "|".join(str(item) for item in value)
    except TypeError:
        return str(value)
