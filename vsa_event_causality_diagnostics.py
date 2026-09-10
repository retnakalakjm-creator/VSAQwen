from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

DEFAULT_CAUSALITY_HORIZON_ROWS = 8

OUTCOME_FOLLOW_THROUGH_VISIBLE = "follow_through_visible"
OUTCOME_MIXED_FOLLOW_THROUGH_CONFLICT = "mixed_follow_through_conflict"
OUTCOME_INVALIDATED_BY_LATER_EVIDENCE = "invalidated_by_later_evidence"
OUTCOME_NO_FOLLOW_THROUGH_VISIBLE = "no_follow_through_visible"
OUTCOME_NO_LATER_SELECTED_AUDIT_ROWS = "no_later_selected_audit_rows"
OUTCOME_PENDING_INSUFFICIENT_FUTURE_ROWS = "pending_insufficient_future_rows"
OUTCOME_LIFECYCLE_TRANSITION_REVIEW = "lifecycle_transition_review"
OUTCOME_CONTEXT_ONLY_REVIEW = "context_only_review"

BULLISH_EVENT_CODES = frozenset(
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
        "structural_progression_improving",
    }
)

BEARISH_EVENT_CODES = frozenset(
    {
        "buying_climax",
        "upthrust",
        "no_demand",
        "hidden_supply",
        "increasing_supply",
        "supply_coming_in",
        "effort_gt_result",
        "structural_progression_weakening",
    }
)

LIFECYCLE_ACTIONS = frozenset(
    {
        "invalidate_qualification",
        "expire_qualification",
        "mark_conflicted",
        "wait_for_follow_through",
        "keep_active",
    }
)

INVALIDATING_LIFECYCLE_ACTIONS = frozenset(
    {
        "invalidate_qualification",
        "mark_conflicted",
    }
)

CSV_COLUMNS = (
    "symbol",
    "replay_week",
    "replay_bar_index",
    "event_code",
    "event_family",
    "event_direction",
    "qualification",
    "source_bucket",
    "source_priority",
    "outcome_label",
    "future_rows_checked",
    "review_horizon_rows",
    "future_supporting_event_codes",
    "future_opposing_event_codes",
    "future_lifecycle_actions",
    "source_target_event_codes",
    "source_scoring_event_codes",
    "source_reasons",
    "causal_read",
    "recommended_action",
)


@dataclass(frozen=True, slots=True)
class VSAEventCausalityDiagnosticRow:
    """Audit-only causal review row for one important VSA event or context row."""

    symbol: str
    replay_week: str
    replay_bar_index: int
    event_code: str
    event_family: str
    event_direction: str
    qualification: str
    source_bucket: str
    source_priority: str
    source_reasons: tuple[str, ...]
    source_target_event_codes: tuple[str, ...]
    source_scoring_event_codes: tuple[str, ...]
    future_supporting_event_codes: tuple[str, ...]
    future_opposing_event_codes: tuple[str, ...]
    future_lifecycle_actions: tuple[str, ...]
    outcome_label: str
    causal_read: str
    recommended_action: str
    review_horizon_rows: int
    future_rows_checked: int
    audit_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "replay_week": self.replay_week,
            "replay_bar_index": self.replay_bar_index,
            "event_code": self.event_code,
            "event_family": self.event_family,
            "event_direction": self.event_direction,
            "qualification": self.qualification,
            "source_bucket": self.source_bucket,
            "source_priority": self.source_priority,
            "source_reasons": list(self.source_reasons),
            "source_target_event_codes": list(self.source_target_event_codes),
            "source_scoring_event_codes": list(self.source_scoring_event_codes),
            "future_supporting_event_codes": list(self.future_supporting_event_codes),
            "future_opposing_event_codes": list(self.future_opposing_event_codes),
            "future_lifecycle_actions": list(self.future_lifecycle_actions),
            "outcome_label": self.outcome_label,
            "causal_read": self.causal_read,
            "recommended_action": self.recommended_action,
            "review_horizon_rows": self.review_horizon_rows,
            "future_rows_checked": self.future_rows_checked,
            "audit_only": self.audit_only,
        }


@dataclass(frozen=True, slots=True)
class VSAEventCausalityDiagnosticSummary:
    """Compact audit-only causality/outcome summary."""

    rows: tuple[VSAEventCausalityDiagnosticRow, ...]
    total_input_rows: int
    total_diagnostic_rows: int
    review_horizon_rows: int
    outcome_counts: dict[str, int] = field(default_factory=dict)
    event_counts: dict[str, int] = field(default_factory=dict)
    symbol_counts: dict[str, int] = field(default_factory=dict)
    direction_counts: dict[str, int] = field(default_factory=dict)
    top_review_symbols: tuple[dict[str, Any], ...] = ()
    audit_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "audit_only": self.audit_only,
            "review_horizon_rows": self.review_horizon_rows,
            "total_input_rows": self.total_input_rows,
            "total_diagnostic_rows": self.total_diagnostic_rows,
            "outcome_counts": dict(self.outcome_counts),
            "event_counts": dict(self.event_counts),
            "symbol_counts": dict(self.symbol_counts),
            "direction_counts": dict(self.direction_counts),
            "top_review_symbols": [dict(row) for row in self.top_review_symbols],
            "rows": [row.to_dict() for row in self.rows],
        }


def build_vsa_event_causality_diagnostics(
    payload: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    *,
    review_horizon_rows: int = DEFAULT_CAUSALITY_HORIZON_ROWS,
) -> VSAEventCausalityDiagnosticSummary:
    """Build event-sequence causality diagnostics from saved audit JSON.

    This helper consumes already-generated audit, triage, lifecycle, transition,
    or candidate-event JSON. It does not load market data, call providers, replay
    scanners, mutate scanner state, persist output, activate detectors, alter
    scoring/ranking, or affect frontend/API production behavior.
    """

    if review_horizon_rows <= 0:
        raise ValueError("review_horizon_rows must be greater than zero")

    source_rows = tuple(sorted(_extract_rows(payload), key=_row_sort_key))
    diagnostics = tuple(
        sorted(
            (
                _build_diagnostic_row(
                    row,
                    _future_rows(row, source_rows, review_horizon_rows),
                    review_horizon_rows,
                )
                for row in source_rows
                if _is_reviewable_row(row)
            ),
            key=lambda item: (item.symbol, item.replay_bar_index, item.event_code),
        )
    )

    return VSAEventCausalityDiagnosticSummary(
        rows=diagnostics,
        total_input_rows=len(source_rows),
        total_diagnostic_rows=len(diagnostics),
        review_horizon_rows=review_horizon_rows,
        outcome_counts=_count(row.outcome_label for row in diagnostics),
        event_counts=_count(row.event_code for row in diagnostics),
        symbol_counts=_count(row.symbol for row in diagnostics),
        direction_counts=_count(row.event_direction for row in diagnostics),
        top_review_symbols=_top_review_symbols(diagnostics),
    )


def render_vsa_event_causality_diagnostics_csv(
    summary: VSAEventCausalityDiagnosticSummary | Mapping[str, Any],
) -> str:
    """Render causality diagnostic rows to CSV for manual chart review."""

    rows = _diagnostic_rows(summary)
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(CSV_COLUMNS), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(_csv_row(row))
    return output.getvalue()


def _build_diagnostic_row(
    row: Mapping[str, Any],
    future_rows: Sequence[Mapping[str, Any]],
    review_horizon_rows: int,
) -> VSAEventCausalityDiagnosticRow:
    event_code = _event_code(row)
    event_family = _event_family(row, event_code)
    direction = _event_direction(row, event_code)
    target_codes = _string_tuple(row.get("target_event_codes"))
    scoring_codes = _string_tuple(row.get("scoring_event_codes"))
    future_support, future_opposition, future_actions = _future_evidence(
        future_rows,
        direction=direction,
    )
    outcome = _outcome_label(
        row,
        direction=direction,
        future_support=future_support,
        future_opposition=future_opposition,
        future_actions=future_actions,
        future_rows_checked=len(future_rows),
        review_horizon_rows=review_horizon_rows,
    )
    causal_read = _causal_read(
        event_code=event_code,
        direction=direction,
        outcome=outcome,
        future_support=future_support,
        future_opposition=future_opposition,
        future_actions=future_actions,
    )
    return VSAEventCausalityDiagnosticRow(
        symbol=str(row.get("symbol", "")),
        replay_week=str(row.get("replay_week", row.get("week", ""))),
        replay_bar_index=_int_or_default(row.get("replay_bar_index", row.get("bar_index")), -1),
        event_code=event_code,
        event_family=event_family,
        event_direction=direction,
        qualification=str(row.get("qualification", "")),
        source_bucket=str(row.get("triage_bucket", row.get("lifecycle_status", row.get("proposed_action", "")))),
        source_priority=str(row.get("priority", row.get("severity_grade", row.get("confidence", "")))),
        source_reasons=_source_reasons(row),
        source_target_event_codes=target_codes,
        source_scoring_event_codes=scoring_codes,
        future_supporting_event_codes=future_support,
        future_opposing_event_codes=future_opposition,
        future_lifecycle_actions=future_actions,
        outcome_label=outcome,
        causal_read=causal_read,
        recommended_action=_recommended_action(outcome),
        review_horizon_rows=review_horizon_rows,
        future_rows_checked=len(future_rows),
    )


def _future_evidence(
    rows: Sequence[Mapping[str, Any]],
    *,
    direction: str,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    supporting: list[str] = []
    opposing: list[str] = []
    actions: list[str] = []

    for row in rows:
        action = str(row.get("proposed_action", ""))
        if action in LIFECYCLE_ACTIONS:
            actions.append(action)
        for code in _row_event_codes(row):
            code_direction = _direction_from_code(code)
            if direction in {"bullish", "bearish"}:
                if code_direction == direction:
                    supporting.append(code)
                elif code_direction in {"bullish", "bearish"}:
                    opposing.append(code)
            elif code_direction in {"bullish", "bearish"}:
                supporting.append(code)
    return _dedupe(supporting), _dedupe(opposing), _dedupe(actions)


def _outcome_label(
    row: Mapping[str, Any],
    *,
    direction: str,
    future_support: tuple[str, ...],
    future_opposition: tuple[str, ...],
    future_actions: tuple[str, ...],
    future_rows_checked: int,
    review_horizon_rows: int,
) -> str:
    action = str(row.get("proposed_action", ""))
    family = str(row.get("candidate_family", ""))
    bucket = str(row.get("triage_bucket", ""))
    lifecycle_status = str(row.get("lifecycle_status", ""))

    if (
        action in LIFECYCLE_ACTIONS
        or family == "qualification_lifecycle"
        or bucket == "qualification_lifecycle_issue"
        or lifecycle_status
    ):
        return OUTCOME_LIFECYCLE_TRANSITION_REVIEW
    if direction not in {"bullish", "bearish"}:
        return OUTCOME_CONTEXT_ONLY_REVIEW

    has_invalidating_action = any(
        action in INVALIDATING_LIFECYCLE_ACTIONS for action in future_actions
    )
    has_opposition = bool(future_opposition) or has_invalidating_action
    has_support = bool(future_support)

    if has_support and has_opposition:
        return OUTCOME_MIXED_FOLLOW_THROUGH_CONFLICT
    if has_opposition:
        return OUTCOME_INVALIDATED_BY_LATER_EVIDENCE
    if has_support:
        return OUTCOME_FOLLOW_THROUGH_VISIBLE
    if future_rows_checked == 0:
        return OUTCOME_NO_LATER_SELECTED_AUDIT_ROWS
    if future_rows_checked < review_horizon_rows:
        return OUTCOME_PENDING_INSUFFICIENT_FUTURE_ROWS
    return OUTCOME_NO_FOLLOW_THROUGH_VISIBLE


def _causal_read(
    *,
    event_code: str,
    direction: str,
    outcome: str,
    future_support: tuple[str, ...],
    future_opposition: tuple[str, ...],
    future_actions: tuple[str, ...],
) -> str:
    readable_event = _pretty(event_code)
    if outcome == OUTCOME_FOLLOW_THROUGH_VISIBLE:
        return f"{readable_event} has later same-side VSA evidence: {', '.join(future_support)}."
    if outcome == OUTCOME_MIXED_FOLLOW_THROUGH_CONFLICT:
        pieces = [f"same-side VSA evidence: {', '.join(future_support)}"]
        if future_opposition:
            pieces.append(f"opposing VSA evidence: {', '.join(future_opposition)}")
        invalidating_actions = tuple(
            action for action in future_actions if action in INVALIDATING_LIFECYCLE_ACTIONS
        )
        if invalidating_actions:
            pieces.append(f"invalidating lifecycle action: {', '.join(invalidating_actions)}")
        return f"{readable_event} has mixed follow-through and contradiction: {'; '.join(pieces)}."
    if outcome == OUTCOME_INVALIDATED_BY_LATER_EVIDENCE:
        pieces = []
        if future_opposition:
            pieces.append(f"opposing VSA evidence: {', '.join(future_opposition)}")
        if future_actions:
            pieces.append(f"lifecycle action: {', '.join(future_actions)}")
        return f"{readable_event} is contradicted by later {'; '.join(pieces)}."
    if outcome == OUTCOME_NO_FOLLOW_THROUGH_VISIBLE:
        return f"{readable_event} has no visible follow-through inside the completed review window."
    if outcome == OUTCOME_NO_LATER_SELECTED_AUDIT_ROWS:
        return f"{readable_event} has no later selected audit rows in this saved input; rerun with a wider/base audit file before treating it as pending."
    if outcome == OUTCOME_PENDING_INSUFFICIENT_FUTURE_ROWS:
        return f"{readable_event} has later audit rows, but not enough to evaluate through the full review window."
    if outcome == OUTCOME_LIFECYCLE_TRANSITION_REVIEW:
        return "Qualification lifecycle/action row; review how it changes active context rather than treating it as a price event."
    if direction in {"bullish", "bearish"}:
        return f"{readable_event} is a {direction} context row requiring manual chart review."
    return f"{readable_event} is context-only and has no directional follow-through label."


def _recommended_action(outcome: str) -> str:
    if outcome == OUTCOME_FOLLOW_THROUGH_VISIBLE:
        return "review_for_event_continuation_or_active_lifecycle"
    if outcome == OUTCOME_MIXED_FOLLOW_THROUGH_CONFLICT:
        return "review_mixed_event_cluster_before_activation"
    if outcome == OUTCOME_INVALIDATED_BY_LATER_EVIDENCE:
        return "review_for_event_invalidation_or_supersession"
    if outcome == OUTCOME_NO_FOLLOW_THROUGH_VISIBLE:
        return "review_for_failed_event_or_decay_rule"
    if outcome == OUTCOME_NO_LATER_SELECTED_AUDIT_ROWS:
        return "rerun_with_wider_same_symbol_audit_context"
    if outcome == OUTCOME_PENDING_INSUFFICIENT_FUTURE_ROWS:
        return "wait_for_more_completed_bars"
    if outcome == OUTCOME_LIFECYCLE_TRANSITION_REVIEW:
        return "review_context_lifecycle_transition"
    return "manual_chart_review"


def _extract_rows(payload: Mapping[str, Any] | Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    if isinstance(payload, Mapping):
        if "rows" in payload:
            return tuple(dict(row) for row in _mapping_sequence(payload.get("rows")))
        if "results" in payload:
            extracted: list[dict[str, Any]] = []
            for result in _mapping_sequence(payload.get("results")):
                extracted.extend(dict(row) for row in _mapping_sequence(result.get("rows")))
            return tuple(extracted)
        return (dict(payload),)
    return tuple(dict(row) for row in payload)


def _is_reviewable_row(row: Mapping[str, Any]) -> bool:
    return bool(_event_code(row)) or bool(_row_event_codes(row)) or bool(row.get("proposed_action"))


def _future_rows(
    row: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    review_horizon_rows: int,
) -> tuple[Mapping[str, Any], ...]:
    symbol = str(row.get("symbol", ""))
    bar_index = _int_or_default(row.get("replay_bar_index", row.get("bar_index")), -1)
    if not symbol or bar_index < 0:
        return ()
    future = [
        item
        for item in rows
        if str(item.get("symbol", "")) == symbol
        and _int_or_default(item.get("replay_bar_index", item.get("bar_index")), -1) > bar_index
    ]
    return tuple(future[:review_horizon_rows])


def _event_code(row: Mapping[str, Any]) -> str:
    for key in ("candidate_code", "event_code", "proposed_action"):
        value = str(row.get(key, ""))
        if value:
            return value
    codes = _row_event_codes(row)
    return codes[0] if codes else ""


def _event_family(row: Mapping[str, Any], event_code: str) -> str:
    explicit = str(row.get("candidate_family", row.get("event_family", "")))
    if explicit:
        return explicit
    if event_code.startswith("structural_progression"):
        return "structural_progression"
    if event_code in LIFECYCLE_ACTIONS:
        return "qualification_lifecycle"
    if event_code.startswith("audit_") and event_code.endswith("_candidate"):
        return event_code.removeprefix("audit_").removesuffix("_candidate")
    return "vsa_event"


def _event_direction(row: Mapping[str, Any], event_code: str) -> str:
    explicit = str(row.get("direction", row.get("event_direction", ""))).lower()
    if "bull" in explicit or "demand" in explicit or "long" in explicit:
        return "bullish"
    if "bear" in explicit or "supply" in explicit or "short" in explicit:
        return "bearish"
    code_direction = _direction_from_code(event_code)
    if code_direction != "neutral":
        return code_direction
    for code in _row_event_codes(row):
        code_direction = _direction_from_code(code)
        if code_direction != "neutral":
            return code_direction
    return "neutral"


def _direction_from_code(code: str) -> str:
    if code in BULLISH_EVENT_CODES:
        return "bullish"
    if code in BEARISH_EVENT_CODES:
        return "bearish"
    if "bullish" in code or "demand" in code or "no_supply" in code:
        return "bullish"
    if "bearish" in code or "supply" in code or "no_demand" in code:
        return "bearish"
    return "neutral"


def _row_event_codes(row: Mapping[str, Any]) -> tuple[str, ...]:
    values: list[str] = []
    for key in (
        "target_event_codes",
        "scoring_event_codes",
        "qualifying_event_codes",
        "same_week_candidate_codes",
    ):
        values.extend(_string_tuple(row.get(key)))
    event_code = str(row.get("event_code", ""))
    if event_code:
        values.append(event_code)
    candidate_code = str(row.get("candidate_code", ""))
    if candidate_code and not candidate_code.startswith("audit_"):
        values.append(candidate_code)
    return _dedupe(values)


def _source_reasons(row: Mapping[str, Any]) -> tuple[str, ...]:
    values: list[str] = []
    for key in ("triage_reasons", "proposal_reasons", "reason", "original_reason", "notes"):
        raw = row.get(key)
        if isinstance(raw, str) and raw:
            values.append(raw)
        else:
            values.extend(_string_tuple(raw))
    return _dedupe(values)


def _diagnostic_rows(
    summary: VSAEventCausalityDiagnosticSummary | Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    if isinstance(summary, VSAEventCausalityDiagnosticSummary):
        return tuple(row.to_dict() for row in summary.rows)
    return tuple(dict(row) for row in _mapping_sequence(summary.get("rows")))


def _csv_row(row: Mapping[str, Any]) -> dict[str, str]:
    csv_row: dict[str, str] = {}
    for column in CSV_COLUMNS:
        value = row.get(column, "")
        if isinstance(value, (list, tuple)):
            csv_row[column] = ";".join(str(item) for item in value)
        else:
            csv_row[column] = str(value)
    return csv_row


def _top_review_symbols(
    rows: Sequence[VSAEventCausalityDiagnosticRow],
    *,
    limit: int = 10,
) -> tuple[dict[str, Any], ...]:
    counts = _count(row.symbol for row in rows)
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]
    return tuple({"symbol": symbol, "count": count} for symbol, count in ordered)


def _count(values: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = str(value)
        if not key:
            continue
        counts[key] = counts.get(key, 0) + 1
    return counts


def _row_sort_key(row: Mapping[str, Any]) -> tuple[str, int, str]:
    return (
        str(row.get("symbol", "")),
        _int_or_default(row.get("replay_bar_index", row.get("bar_index")), -1),
        str(row.get("replay_week", row.get("week", ""))),
    )


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
        return tuple(str(item) for item in value if str(item))
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


def _int_or_default(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _pretty(value: str) -> str:
    return value.replace("_", " ").strip().capitalize() or "Event"


__all__ = [
    "DEFAULT_CAUSALITY_HORIZON_ROWS",
    "OUTCOME_CONTEXT_ONLY_REVIEW",
    "OUTCOME_FOLLOW_THROUGH_VISIBLE",
    "OUTCOME_INVALIDATED_BY_LATER_EVIDENCE",
    "OUTCOME_LIFECYCLE_TRANSITION_REVIEW",
    "OUTCOME_MIXED_FOLLOW_THROUGH_CONFLICT",
    "OUTCOME_NO_FOLLOW_THROUGH_VISIBLE",
    "OUTCOME_NO_LATER_SELECTED_AUDIT_ROWS",
    "OUTCOME_PENDING_INSUFFICIENT_FUTURE_ROWS",
    "VSAEventCausalityDiagnosticRow",
    "VSAEventCausalityDiagnosticSummary",
    "build_vsa_event_causality_diagnostics",
    "render_vsa_event_causality_diagnostics_csv",
]
