from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from vsa_recovery_sequence_labels import (
    DEMAND_FOLLOW_THROUGH_CODES,
    PRIOR_WEAKNESS_CODES,
    RECOVERY_SEQUENCE_BLOCKER_CODES,
    SPRING_SHAKEOUT_TEST_CODES,
    STOPPING_VOLUME_ANCHOR_CODES,
    RecoverySequenceReviewLabel,
    label_stopping_volume_spring_shakeout_review,
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

DIAGNOSTIC_HINT_CODES = {
    "review_potential_absorption",
    "review_potential_spring_or_shakeout",
    "review_potential_stopping_volume",
}

STAGE_SEED_ANCHOR = "anchor_seed"
STAGE_SEED_TEST = "spring_shakeout_seed"
STAGE_SEED_DIAGNOSTIC = "diagnostic_seed"

CSV_COLUMNS = (
    "casebook_id",
    "symbol",
    "stage_seed_type",
    "replay_week",
    "start_week",
    "end_week",
    "replay_bar_index",
    "start_bar_index",
    "end_bar_index",
    "qualification",
    "prior_weakness_codes",
    "stopping_volume_codes",
    "spring_shakeout_codes",
    "follow_through_codes",
    "same_window_evidence_codes",
    "diagnostic_hint_codes",
    "follow_through_evidence_age",
    "used_fallback_evidence",
    "recovery_sequence_status",
    "review_marker",
    "audit_note",
)


@dataclass(frozen=True, slots=True)
class VSARecoverySequenceStageSeedRow:
    """Normalized audit-only 6C stage row built from saved replay output."""

    casebook_id: str
    symbol: str
    stage_seed_type: str
    replay_week: str
    start_week: str
    end_week: str
    replay_bar_index: int
    start_bar_index: int
    end_bar_index: int
    qualification: str
    prior_weakness_codes: tuple[str, ...]
    stopping_volume_codes: tuple[str, ...]
    spring_shakeout_codes: tuple[str, ...]
    follow_through_codes: tuple[str, ...]
    same_window_evidence_codes: tuple[str, ...]
    diagnostic_hint_codes: tuple[str, ...]
    follow_through_evidence_age: int | None
    used_fallback_evidence: bool
    recovery_sequence_status: str
    review_marker: str | None
    audit_note: str
    audit_only: bool = True
    production_safe: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "audit_only": self.audit_only,
            "production_safe": self.production_safe,
            "casebook_id": self.casebook_id,
            "symbol": self.symbol,
            "stage_seed_type": self.stage_seed_type,
            "replay_week": self.replay_week,
            "start_week": self.start_week,
            "end_week": self.end_week,
            "replay_bar_index": self.replay_bar_index,
            "start_bar_index": self.start_bar_index,
            "end_bar_index": self.end_bar_index,
            "qualification": self.qualification,
            "prior_weakness_codes": list(self.prior_weakness_codes),
            "stopping_volume_codes": list(self.stopping_volume_codes),
            "spring_shakeout_codes": list(self.spring_shakeout_codes),
            "follow_through_codes": list(self.follow_through_codes),
            "same_window_evidence_codes": list(self.same_window_evidence_codes),
            "diagnostic_hint_codes": list(self.diagnostic_hint_codes),
            "follow_through_evidence_age": self.follow_through_evidence_age,
            "used_fallback_evidence": self.used_fallback_evidence,
            "recovery_sequence_status": self.recovery_sequence_status,
            "review_marker": self.review_marker,
            "audit_note": self.audit_note,
        }


@dataclass(frozen=True, slots=True)
class VSARecoverySequenceStageSeedSummary:
    """Audit-only stage-seed normalization summary for 6C validation."""

    rows: tuple[VSARecoverySequenceStageSeedRow, ...]
    total_input_rows: int
    total_stage_seed_rows: int
    status_counts: dict[str, int] = field(default_factory=dict)
    stage_seed_type_counts: dict[str, int] = field(default_factory=dict)
    diagnostic_hint_counts: dict[str, int] = field(default_factory=dict)
    top_stage_seed_items: tuple[dict[str, Any], ...] = ()
    audit_only: bool = True
    production_safe: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "audit_only": self.audit_only,
            "production_safe": self.production_safe,
            "total_input_rows": self.total_input_rows,
            "total_stage_seed_rows": self.total_stage_seed_rows,
            "status_counts": dict(self.status_counts),
            "stage_seed_type_counts": dict(self.stage_seed_type_counts),
            "diagnostic_hint_counts": dict(self.diagnostic_hint_counts),
            "top_stage_seed_items": [dict(item) for item in self.top_stage_seed_items],
            "rows": [row.to_dict() for row in self.rows],
        }


def build_vsa_recovery_sequence_stage_seed(
    payload: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    *,
    lookback_rows: int = DEFAULT_LOOKBACK_ROWS,
    lookahead_rows: int = DEFAULT_LOOKAHEAD_ROWS,
    include_diagnostic_hints: bool = True,
) -> VSARecoverySequenceStageSeedSummary:
    """Normalize saved replay rows into explicit 6C stage fields.

    The helper consumes saved audit/replay output and only derives stage rows
    from already-present codes. It does not load market data, call providers,
    replay scanners, mutate scanner state, activate detectors, alter scoring or
    ranking, persist data, or touch API/frontend behavior.
    """

    safe_lookback = max(0, int(lookback_rows))
    safe_lookahead = max(0, int(lookahead_rows))
    replay_rows = tuple(_flatten_replay_rows(payload))
    grouped = _group_by_symbol(replay_rows)
    stage_rows = tuple(
        sorted(
            (
                row
                for symbol_rows in grouped.values()
                for row in _stage_rows_for_symbol(
                    symbol_rows,
                    lookback_rows=safe_lookback,
                    lookahead_rows=safe_lookahead,
                    include_diagnostic_hints=include_diagnostic_hints,
                )
            ),
            key=_stage_seed_sort_key,
        )
    )
    return VSARecoverySequenceStageSeedSummary(
        rows=stage_rows,
        total_input_rows=len(replay_rows),
        total_stage_seed_rows=len(stage_rows),
        status_counts=_count(row.recovery_sequence_status for row in stage_rows),
        stage_seed_type_counts=_count(row.stage_seed_type for row in stage_rows),
        diagnostic_hint_counts=_count(
            hint for row in stage_rows for hint in row.diagnostic_hint_codes
        ),
        top_stage_seed_items=_top_stage_seed_items(stage_rows),
    )


def render_vsa_recovery_sequence_stage_seed_csv(
    summary: VSARecoverySequenceStageSeedSummary | Mapping[str, Any],
) -> str:
    """Render 6C stage-seed rows to CSV."""

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(CSV_COLUMNS), lineterminator="\n")
    writer.writeheader()
    for row in _summary_rows(summary):
        writer.writerow(_csv_row(row))
    return output.getvalue()


def _stage_rows_for_symbol(
    symbol_rows: Sequence[Mapping[str, Any]],
    *,
    lookback_rows: int,
    lookahead_rows: int,
    include_diagnostic_hints: bool,
) -> tuple[VSARecoverySequenceStageSeedRow, ...]:
    ordered = tuple(sorted(symbol_rows, key=_raw_row_sort_key))
    rows: list[VSARecoverySequenceStageSeedRow] = []
    for index, row in enumerate(ordered):
        if not _is_stage_seed(row, include_diagnostic_hints=include_diagnostic_hints):
            continue
        start = max(0, index - lookback_rows)
        end = min(len(ordered), index + lookahead_rows + 1)
        prior_window = ordered[start : index + 1]
        forward_window = ordered[index:end]
        seed_window = (row,)

        stage_row = _stage_seed_row(
            seed_row=row,
            prior_window=prior_window,
            forward_window=forward_window,
            seed_window=seed_window,
        )
        rows.append(stage_row)
    return tuple(rows)


def _stage_seed_row(
    *,
    seed_row: Mapping[str, Any],
    prior_window: Sequence[Mapping[str, Any]],
    forward_window: Sequence[Mapping[str, Any]],
    seed_window: Sequence[Mapping[str, Any]],
) -> VSARecoverySequenceStageSeedRow:
    symbol = str(seed_row.get("symbol", ""))
    replay_bar_index = _int_or_default(
        seed_row.get("replay_bar_index", seed_row.get("bar_index")), -1
    )
    replay_week = _week_text(seed_row.get("replay_week", seed_row.get("week_beginning", "")))
    start_bar_index = _int_or_default(
        prior_window[0].get("replay_bar_index", replay_bar_index), replay_bar_index
    )
    end_bar_index = _int_or_default(
        forward_window[-1].get("replay_bar_index", replay_bar_index), replay_bar_index
    )
    start_week = _week_text(prior_window[0].get("replay_week", replay_week))
    end_week = _week_text(forward_window[-1].get("replay_week", replay_week))
    qualification = _qualification(seed_row, prior_window)

    prior_weakness_codes = _window_codes(prior_window, PRIOR_WEAKNESS_CODES)
    stopping_volume_codes = _window_codes(prior_window, STOPPING_VOLUME_ANCHOR_CODES)
    spring_shakeout_codes = _window_codes(forward_window, SPRING_SHAKEOUT_TEST_CODES)
    follow_through_codes = _window_codes(forward_window, DEMAND_FOLLOW_THROUGH_CODES)
    same_window_evidence_codes = _window_codes(seed_window, RECOVERY_SEQUENCE_BLOCKER_CODES)
    diagnostic_hint_codes = _diagnostic_hints(seed_row)
    follow_through_rows = _rows_with_codes(forward_window, DEMAND_FOLLOW_THROUGH_CODES)
    used_fallback_evidence = any(
        _bool(row.get("used_fallback_evidence", False)) for row in follow_through_rows
    )
    follow_through_evidence_age = 0 if follow_through_codes else None

    result = label_stopping_volume_spring_shakeout_review(
        qualification=qualification,
        prior_evidence=prior_weakness_codes,
        stopping_volume_evidence=stopping_volume_codes,
        spring_shakeout_evidence=spring_shakeout_codes,
        follow_through_evidence=follow_through_codes,
        same_window_evidence=same_window_evidence_codes,
        follow_through_evidence_age=follow_through_evidence_age,
        used_fallback_evidence=used_fallback_evidence,
    )
    stage_seed_type = _stage_seed_type(seed_row)
    casebook_id = (
        f"{symbol}:6c_stage_seed:{stage_seed_type}:"
        f"{replay_week or replay_bar_index}"
    )

    return VSARecoverySequenceStageSeedRow(
        casebook_id=casebook_id,
        symbol=symbol,
        stage_seed_type=stage_seed_type,
        replay_week=replay_week,
        start_week=start_week,
        end_week=end_week,
        replay_bar_index=replay_bar_index,
        start_bar_index=start_bar_index,
        end_bar_index=end_bar_index,
        qualification=result.qualification,
        prior_weakness_codes=result.prior_weakness_codes,
        stopping_volume_codes=result.stopping_volume_codes,
        spring_shakeout_codes=result.spring_shakeout_codes,
        follow_through_codes=result.follow_through_codes,
        same_window_evidence_codes=same_window_evidence_codes,
        diagnostic_hint_codes=diagnostic_hint_codes,
        follow_through_evidence_age=result.follow_through_evidence_age,
        used_fallback_evidence=result.used_fallback_evidence,
        recovery_sequence_status=result.status.value,
        review_marker=result.review_marker,
        audit_note=_audit_note(
            status=result.status,
            diagnostic_hint_codes=diagnostic_hint_codes,
            same_window_evidence_codes=same_window_evidence_codes,
        ),
    )


def _is_stage_seed(row: Mapping[str, Any], *, include_diagnostic_hints: bool) -> bool:
    production_codes = set(_production_codes(row))
    if production_codes & STOPPING_VOLUME_ANCHOR_CODES:
        return True
    if production_codes & SPRING_SHAKEOUT_TEST_CODES:
        return True
    return include_diagnostic_hints and bool(_diagnostic_hints(row))


def _stage_seed_type(row: Mapping[str, Any]) -> str:
    production_codes = set(_production_codes(row))
    if production_codes & STOPPING_VOLUME_ANCHOR_CODES:
        return STAGE_SEED_ANCHOR
    if production_codes & SPRING_SHAKEOUT_TEST_CODES:
        return STAGE_SEED_TEST
    return STAGE_SEED_DIAGNOSTIC


def _audit_note(
    *,
    status: RecoverySequenceReviewLabel,
    diagnostic_hint_codes: tuple[str, ...],
    same_window_evidence_codes: tuple[str, ...],
) -> str:
    diagnostic_note = (
        f" Diagnostic hints: {_join_or_none(diagnostic_hint_codes)}."
        if diagnostic_hint_codes
        else ""
    )
    if status is RecoverySequenceReviewLabel.REVIEW:
        return f"6C stage seed produced a review-only recovery-sequence candidate.{diagnostic_note}"
    if status is RecoverySequenceReviewLabel.BLOCKED:
        return (
            "6C stage seed had the sequence but remained blocked by same-window "
            f"evidence: {_join_or_none(same_window_evidence_codes)}.{diagnostic_note}"
        )
    if status is RecoverySequenceReviewLabel.NEEDS_FOLLOW_THROUGH:
        return f"6C stage seed needs fresh non-fallback demand follow-through.{diagnostic_note}"
    return f"6C stage seed did not satisfy the full recovery sequence.{diagnostic_note}"


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
        for key in ("rows", "replay_rows", "audit_rows"):
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


def _window_codes(rows: Sequence[Mapping[str, Any]], allowed_codes: set[str]) -> tuple[str, ...]:
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
    allowed_codes: set[str],
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
    for code in _string_tuple(row.get("detector_diagnostics")):
        normalized = _normalize_code(code)
        if normalized in DIAGNOSTIC_HINT_CODES and normalized not in seen:
            selected.append(normalized)
            seen.add(normalized)
    return tuple(selected)


def _summary_rows(
    summary: VSARecoverySequenceStageSeedSummary | Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    if isinstance(summary, VSARecoverySequenceStageSeedSummary):
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


def _top_stage_seed_items(
    rows: Sequence[VSARecoverySequenceStageSeedRow],
    *,
    limit: int = 10,
) -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "casebook_id": row.casebook_id,
            "symbol": row.symbol,
            "stage_seed_type": row.stage_seed_type,
            "replay_week": row.replay_week,
            "recovery_sequence_status": row.recovery_sequence_status,
            "review_marker": row.review_marker,
            "diagnostic_hint_codes": list(row.diagnostic_hint_codes),
        }
        for row in sorted(rows, key=_stage_seed_sort_key)[:limit]
    )


def _stage_seed_sort_key(row: VSARecoverySequenceStageSeedRow) -> tuple[int, str, int, str]:
    status_rank = {
        RecoverySequenceReviewLabel.REVIEW.value: 0,
        RecoverySequenceReviewLabel.BLOCKED.value: 1,
        RecoverySequenceReviewLabel.NEEDS_FOLLOW_THROUGH.value: 2,
        RecoverySequenceReviewLabel.NONE.value: 3,
    }.get(row.recovery_sequence_status, 9)
    return (status_rank, row.symbol, row.replay_bar_index, row.casebook_id)


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
    if isinstance(value, Iterable):
        return tuple(
            str(getattr(item, "value", item))
            for item in value
            if str(getattr(item, "value", item))
        )
    return (str(value),) if str(value) else ()


def _normalize_code(value: Any) -> str:
    return str(getattr(value, "value", value)).strip().lower()


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
    "DEFAULT_LOOKAHEAD_ROWS",
    "DEFAULT_LOOKBACK_ROWS",
    "DIAGNOSTIC_HINT_CODES",
    "STAGE_SEED_ANCHOR",
    "STAGE_SEED_DIAGNOSTIC",
    "STAGE_SEED_TEST",
    "VSARecoverySequenceStageSeedRow",
    "VSARecoverySequenceStageSeedSummary",
    "build_vsa_recovery_sequence_stage_seed",
    "render_vsa_recovery_sequence_stage_seed_csv",
]
