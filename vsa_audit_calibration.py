from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

EFFORT_ABSORPTION_DIAGNOSTICS = frozenset(
    {
        "review_potential_effort_gt_result",
        "review_potential_absorption",
        "review_high_volume_reversal_without_bullish_event",
        "review_potential_stopping_volume",
        "review_potential_spring_or_shakeout",
    }
)

CONTEXT_MISMATCH_FLAGS = frozenset(
    {
        "bullish_vsa_against_bearish_qualification",
        "bearish_vsa_against_bullish_qualification",
        "structural_event_without_vsa_confirmation",
        "stale_scoring_evidence",
    }
)

HIGH_PRIORITY_DIAGNOSTICS = frozenset(
    {
        "review_potential_effort_gt_result",
        "review_potential_absorption",
        "review_high_volume_reversal_without_bullish_event",
    }
)

HIGH_PRIORITY_FLAGS = frozenset(
    {
        "bullish_vsa_against_bearish_qualification",
        "bearish_vsa_against_bullish_qualification",
    }
)

PRODUCTION_EVENT_CODES = frozenset(
    {
        "effort_gt_result",
        "absorption",
        "stopping_volume",
        "spring",
        "shakeout",
    }
)


@dataclass(frozen=True, slots=True)
class VSAAuditCalibrationRow:
    """One audit row selected for detector calibration review.

    This is an audit-only summary object. It never changes scanner evidence,
    score, qualification, ranking, state persistence, or any broker/order scope.
    """

    symbol: str
    replay_week: str
    replay_bar_index: int
    priority: str
    calibration_tags: tuple[str, ...]
    detector_diagnostics: tuple[str, ...]
    audit_flags: tuple[str, ...]
    target_event_codes: tuple[str, ...]
    scoring_event_codes: tuple[str, ...]
    qualification: str
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "replay_week": self.replay_week,
            "replay_bar_index": self.replay_bar_index,
            "priority": self.priority,
            "calibration_tags": list(self.calibration_tags),
            "detector_diagnostics": list(self.detector_diagnostics),
            "audit_flags": list(self.audit_flags),
            "target_event_codes": list(self.target_event_codes),
            "scoring_event_codes": list(self.scoring_event_codes),
            "qualification": self.qualification,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class VSAAuditCalibrationSummary:
    """Compact calibration summary across one audit response."""

    rows: tuple[VSAAuditCalibrationRow, ...]
    priority_counts: dict[str, int] = field(default_factory=dict)
    diagnostic_counts: dict[str, int] = field(default_factory=dict)
    tag_counts: dict[str, int] = field(default_factory=dict)
    symbol_counts: dict[str, int] = field(default_factory=dict)
    audit_only: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "rows": [row.to_dict() for row in self.rows],
            "priority_counts": dict(self.priority_counts),
            "diagnostic_counts": dict(self.diagnostic_counts),
            "tag_counts": dict(self.tag_counts),
            "symbol_counts": dict(self.symbol_counts),
            "audit_only": self.audit_only,
        }


def build_effort_absorption_calibration_summary(
    audit_payload: Mapping[str, Any] | Sequence[Mapping[str, Any]],
) -> VSAAuditCalibrationSummary:
    """Summarize audit output into Effort-vs-Result calibration review rows.

    Input can be the JSON returned by `/api/vsa-audit/events`, a list of symbol
    result dictionaries, or a list of already-flattened row dictionaries. The
    function is intentionally pure and bounded: it loops over the supplied rows
    once and emits compact review rows only.
    """

    selected_rows = tuple(
        calibration_row
        for audit_row in _iter_audit_rows(audit_payload)
        if (calibration_row := _to_calibration_row(audit_row)) is not None
    )
    return VSAAuditCalibrationSummary(
        rows=selected_rows,
        priority_counts=_count_values(row.priority for row in selected_rows),
        diagnostic_counts=_count_values(
            diagnostic
            for row in selected_rows
            for diagnostic in row.detector_diagnostics
        ),
        tag_counts=_count_values(
            tag for row in selected_rows for tag in row.calibration_tags
        ),
        symbol_counts=_count_values(row.symbol for row in selected_rows),
    )


def _iter_audit_rows(
    audit_payload: Mapping[str, Any] | Sequence[Mapping[str, Any]],
) -> Iterable[Mapping[str, Any]]:
    if isinstance(audit_payload, Mapping):
        if "results" in audit_payload:
            for result in audit_payload.get("results", []):
                yield from _iter_result_rows(result)
            return
        if "rows" in audit_payload:
            yield from _iter_result_rows(audit_payload)
            return
        yield audit_payload
        return

    for item in audit_payload:
        if "rows" in item or "results" in item:
            yield from _iter_audit_rows(item)
        else:
            yield item


def _iter_result_rows(result: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    for row in result.get("rows", []):
        yield row


def _to_calibration_row(row: Mapping[str, Any]) -> VSAAuditCalibrationRow | None:
    diagnostics = _string_tuple(row.get("detector_diagnostics", ()))
    flags = _string_tuple(row.get("audit_flags", ()))
    target_codes = _string_tuple(row.get("target_event_codes", ()))
    scoring_codes = _string_tuple(row.get("scoring_event_codes", ()))

    selected_diagnostics = tuple(
        diagnostic
        for diagnostic in diagnostics
        if diagnostic in EFFORT_ABSORPTION_DIAGNOSTICS
    )
    selected_flags = tuple(flag for flag in flags if flag in CONTEXT_MISMATCH_FLAGS)

    if not selected_diagnostics and not selected_flags:
        return None

    tags = _calibration_tags(selected_diagnostics, selected_flags, target_codes)
    priority = _priority(selected_diagnostics, selected_flags, target_codes)
    return VSAAuditCalibrationRow(
        symbol=str(row.get("symbol", "")),
        replay_week=str(row.get("replay_week", "")),
        replay_bar_index=_int_or_default(row.get("replay_bar_index"), -1),
        priority=priority,
        calibration_tags=tags,
        detector_diagnostics=selected_diagnostics,
        audit_flags=selected_flags,
        target_event_codes=target_codes,
        scoring_event_codes=scoring_codes,
        qualification=str(row.get("qualification", "")),
        reason=_reason(priority, selected_diagnostics, selected_flags, target_codes),
    )


def _calibration_tags(
    diagnostics: tuple[str, ...],
    flags: tuple[str, ...],
    target_codes: tuple[str, ...],
) -> tuple[str, ...]:
    tags: list[str] = []
    if "review_potential_effort_gt_result" in diagnostics:
        tags.append("effort_gt_result_candidate")
    if "review_potential_absorption" in diagnostics:
        tags.append("absorption_candidate")
    if "review_high_volume_reversal_without_bullish_event" in diagnostics:
        tags.append("missing_bullish_reversal_event")
    if "review_potential_stopping_volume" in diagnostics:
        tags.append("stopping_volume_candidate")
    if "review_potential_spring_or_shakeout" in diagnostics:
        tags.append("spring_shakeout_candidate")
    if any(flag.endswith("_qualification") for flag in flags):
        tags.append("qualification_conflict")
    if "stale_scoring_evidence" in flags:
        tags.append("stale_evidence_review")
    if not set(target_codes).intersection(PRODUCTION_EVENT_CODES):
        tags.append("not_confirmed_by_current_detector")
    return _dedupe(tags)


def _priority(
    diagnostics: tuple[str, ...],
    flags: tuple[str, ...],
    target_codes: tuple[str, ...],
) -> str:
    has_expected_production_event = bool(
        set(target_codes).intersection(PRODUCTION_EVENT_CODES)
    )
    if (
        set(diagnostics).intersection(HIGH_PRIORITY_DIAGNOSTICS)
        and not has_expected_production_event
    ):
        return "high"
    if set(flags).intersection(HIGH_PRIORITY_FLAGS):
        return "high"
    if diagnostics or flags:
        return "medium"
    return "low"


def _reason(
    priority: str,
    diagnostics: tuple[str, ...],
    flags: tuple[str, ...],
    target_codes: tuple[str, ...],
) -> str:
    if priority == "high" and diagnostics:
        return (
            "High-priority calibration row: diagnostics suggest effort, "
            "absorption, or high-volume reversal behavior that current target "
            "events did not confirm."
        )
    if priority == "high" and flags:
        return (
            "High-priority calibration row: audit flags show VSA evidence "
            "conflicting with the active qualification."
        )
    if not set(target_codes).intersection(PRODUCTION_EVENT_CODES):
        return "Review row before changing detector rules; no target calibration event fired."
    return "Review row as a calibration example for existing detector behavior."


def _string_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return _dedupe(str(item) for item in value)


def _int_or_default(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _count_values(values: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def _dedupe(items: Iterable[str]) -> tuple[str, ...]:
    selected: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item not in seen:
            selected.append(item)
            seen.add(item)
    return tuple(selected)
