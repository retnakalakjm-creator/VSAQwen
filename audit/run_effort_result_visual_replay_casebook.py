"""Run an offline Effort/Result visual replay casebook from compiled evidence.

This module is audit/casebook only. It consumes the compiled manual visual
replay evidence report and organizes confirmed LT replay sequences into a
manual casebook review. It does not read live data, call APIs, persist scanner
state, activate detectors, change scoring/ranking/actionability, emit alerts,
or place orders.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

REPORT_TYPE = "effort_result_visual_replay_casebook"
REPORT_SCHEMA_VERSION = 1

SOURCE_REPORT_TYPE = "effort_result_visual_replay_evidence_compilation"
SOURCE_READY_STATUS = "visual_replay_evidence_ready"
SOURCE_SEQUENCE_CONFIRMED_STATUS = "confirmed_visual_replay_evidence"

DEFAULT_SYMBOL_FILTER = ("LT.NS",)
CASEBOOK_READY_STATUS = "visual_replay_casebook_ready"
CASEBOOK_NEEDS_ATTENTION_STATUS = "visual_replay_casebook_needs_attention"
CASE_READY_STATUS = "ready_for_casebook_review"
CASE_NEEDS_ATTENTION_STATUS = "casebook_case_needs_attention"

REQUIRED_REPLAY_STATUS_FIELDS = (
    "marker_alignment_status",
    "pre_event_context_status",
    "post_event_follow_through_status",
    "counterfactual_scan_status",
    "vsa_smc_quality_status",
)
CONFIRMED_STATUS = "confirmed"

CASEBOOK_REVIEW_LANES = (
    "marker_alignment_recheck",
    "pre_event_context_recheck",
    "post_event_follow_through_recheck",
    "counterfactual_quality_check",
    "vsa_smc_quality_judgment",
    "evidence_artifact_traceability",
)

UNSAFE_TRUTHY_FIELDS = (
    "include_in_scoring",
    "include_in_ranking",
    "include_in_actionability",
    "emit_alert",
    "place_order",
    "activate_detector",
    "api_visible",
    "frontend_visible",
    "persist_as_production_signal",
    "production_change_allowed",
    "automatic_promotion_allowed",
    "persistence_allowed",
    "upload_allowed",
    "live_data_allowed",
    "scoring_allowed",
    "ranking_allowed",
    "actionability_allowed",
    "detector_activation_allowed",
    "alerting_allowed",
    "order_execution_allowed",
    "may_change_scoring",
    "may_change_ranking",
    "may_change_actionability",
    "may_activate_detector",
    "may_change_scanner_state",
    "may_change_persistence",
    "may_change_broker_orders",
    "may_change_account_state",
    "may_change_api",
    "may_change_frontend",
)

PRODUCTION_BOUNDARY = {
    "audit_only": True,
    "casebook_only": True,
    "manual_review_only": True,
    "offline_replay_only": True,
    "lt_sample_casebook_only": True,
    "production_change_allowed": False,
    "may_change_scoring": False,
    "may_change_ranking": False,
    "may_change_actionability": False,
    "may_activate_detector": False,
    "may_change_scanner_state": False,
    "may_change_persistence": False,
    "may_change_broker_orders": False,
    "may_change_account_state": False,
    "may_change_api": False,
    "may_change_frontend": False,
    "requires_visual_replay_evidence_compilation": True,
    "requires_separate_reviewer_summary_pr": True,
    "requires_separate_production_pr": True,
}


def run_effort_result_visual_replay_casebook(
    evidence_compilation_report: Mapping[str, Any],
    *,
    symbols: Sequence[str] = DEFAULT_SYMBOL_FILTER,
    min_cases: int = 1,
) -> dict[str, object]:
    """Build an audit-only casebook report from compiled visual replay evidence.

    A ready casebook means confirmed LT replay sequences are organized for a
    human pass/fail review. It does not authorize live scanner integration,
    production signal promotion, scoring, ranking, actionability, alerts, or
    orders.
    """

    if min_cases <= 0:
        raise ValueError("min_cases must be positive")

    symbol_filter = _normalize_symbols(symbols)
    source_sequences = _mapping_rows(evidence_compilation_report.get("sequence_reviews", []))
    selected_sequences = [
        sequence
        for sequence in source_sequences
        if not symbol_filter or _display(sequence.get("symbol")).strip() in symbol_filter
    ]
    cases = [_build_casebook_case(sequence) for sequence in selected_sequences]
    ready_cases = [case for case in cases if case["case_status"] == CASE_READY_STATUS]

    blockers = _report_blockers(
        evidence_compilation_report,
        source_sequences,
        selected_sequences,
        cases,
        symbol_filter=symbol_filter,
        min_cases=min_cases,
    )
    ready = not blockers

    return {
        "report_type": REPORT_TYPE,
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "source_report_type": evidence_compilation_report.get("report_type"),
        "source_evidence_compilation_status": evidence_compilation_report.get(
            "evidence_compilation_status"
        ),
        "source_evidence_ready": evidence_compilation_report.get("evidence_ready"),
        "source_reviewed_sequence_count": int(
            evidence_compilation_report.get("reviewed_sequence_count", len(source_sequences)) or 0
        ),
        "source_confirmed_sequence_count": int(
            evidence_compilation_report.get("confirmed_sequence_count", 0) or 0
        ),
        "symbol_filter": symbol_filter,
        "source_sequence_count": len(source_sequences),
        "selected_sequence_count": len(selected_sequences),
        "casebook_case_count": len(cases),
        "ready_case_count": len(ready_cases),
        "blocked_case_count": len(cases) - len(ready_cases),
        "minimum_cases": int(min_cases),
        "casebook_status": CASEBOOK_READY_STATUS if ready else CASEBOOK_NEEDS_ATTENTION_STATUS,
        "casebook_ready": ready,
        "blockers": blockers,
        "casebook_review_lanes": list(CASEBOOK_REVIEW_LANES),
        "casebook_cases": cases,
        "next_stage": "reviewer_pass_fail_summary_report" if ready else "complete_visual_replay_casebook_inputs",
        "automatic_promotion_allowed": False,
        **PRODUCTION_BOUNDARY,
    }


def render_effort_result_visual_replay_casebook_markdown(report: Mapping[str, Any]) -> str:
    """Render the offline visual replay casebook report as Markdown."""

    lines = [
        "# Effort/Result Visual Replay Casebook",
        "",
        "## Summary",
        "",
        f"- Source report type: `{_display(report.get('source_report_type'))}`",
        f"- Source evidence status: `{_display(report.get('source_evidence_compilation_status'))}`",
        f"- Source evidence ready: {_bool_text(report.get('source_evidence_ready'))}",
        f"- Symbol filter: {_csv(report.get('symbol_filter', []))}",
        f"- Selected sequences: {int(report.get('selected_sequence_count', 0))}",
        f"- Ready cases: {int(report.get('ready_case_count', 0))}",
        f"- Blocked cases: {int(report.get('blocked_case_count', 0))}",
        f"- Casebook ready: {_bool_text(report.get('casebook_ready'))}",
        f"- Casebook status: `{_display(report.get('casebook_status'))}`",
        f"- Next stage: `{_display(report.get('next_stage'))}`",
        "",
        "## Production Boundary",
        "",
        "- Audit/casebook only: true",
        "- Manual review only: true",
        "- Offline replay only: true",
        "- LT sample casebook only: true",
        "- Production change allowed: false",
        "- Automatic promotion allowed: false",
        "- May change scoring: false",
        "- May change ranking: false",
        "- May change actionability: false",
        "- May activate detector: false",
        "- May change scanner/API/frontend/persistence/broker behavior: false",
        "- Requires separate reviewer summary PR: true",
        "- Requires separate production PR: true",
        "",
        "## Casebook Cases",
        "",
    ]

    cases = _mapping_rows(report.get("casebook_cases", []))
    if not cases:
        lines.append("_No replay cases matched the casebook filter._")
        lines.append("")
    else:
        lines.extend(
            [
                "| Case | Target | Symbol | Week | Status | Markers | Evidence artifact | Blockers |",
                "| --- | --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for row in cases:
            lines.append(
                "| "
                f"`{_display(row.get('case_id'))}` | "
                f"`{_display(row.get('target'))}` | "
                f"{_display(row.get('symbol'))} | "
                f"{_display(row.get('event_week_beginning'))} | "
                f"`{_display(row.get('case_status'))}` | "
                f"{_csv(row.get('marker_labels', []))} | "
                f"{_display(row.get('evidence_artifact'))} | "
                f"{_csv(row.get('blockers', []))} |"
            )
        lines.append("")

    lines.extend(["## Manual Review Lanes", ""])
    for lane in report.get("casebook_review_lanes", []):
        lines.append(f"- [ ] {_display(lane)}")

    lines.extend(
        [
            "",
            "## Review Rules",
            "",
            "- Use only compiled visual replay evidence from the offline evidence compiler.",
            "- Use this casebook to review LT sample replay cases manually.",
            "- Preserve marker labels, reviewer notes, and screenshot traceability for each case.",
            "- Feed this output only into the reviewer pass/fail summary step.",
            "- A separate production PR is required before any scoring, ranking, actionability, detector, API, frontend, persistence, alert, or order behavior can change.",
            "",
        ]
    )
    return "\n".join(lines)


def _build_casebook_case(sequence: Mapping[str, Any]) -> dict[str, object]:
    blockers: list[str] = []

    marker_labels = _string_rows(sequence.get("marker_labels", []))
    required_statuses = _required_statuses(sequence.get("required_statuses", {}))
    notes_recorded = sequence.get("reviewer_notes_recorded") is True or bool(
        _display(sequence.get("reviewer_notes")).strip()
    )
    screenshot_recorded = sequence.get("screenshot_filename_recorded") is True or bool(
        _display(sequence.get("screenshot_filename")).strip()
    )

    if sequence.get("evidence_status") != SOURCE_SEQUENCE_CONFIRMED_STATUS:
        blockers.append("source_sequence_not_confirmed")
    missing_status_fields = [field for field in REQUIRED_REPLAY_STATUS_FIELDS if field not in required_statuses]
    if missing_status_fields:
        blockers.append("missing_required_replay_statuses")
    unconfirmed_fields = [
        field for field in REQUIRED_REPLAY_STATUS_FIELDS if required_statuses.get(field) != CONFIRMED_STATUS
    ]
    if unconfirmed_fields:
        blockers.append("required_replay_status_not_confirmed")
    if not marker_labels:
        blockers.append("missing_marker_labels")
    if not notes_recorded and not screenshot_recorded:
        blockers.append("missing_evidence_artifact_trace")
    if not _display(sequence.get("sequence_id")).strip():
        blockers.append("missing_sequence_id")
    if not _display(sequence.get("target")).strip():
        blockers.append("missing_target")
    if not _display(sequence.get("symbol")).strip():
        blockers.append("missing_symbol")
    if not _display(sequence.get("event_week_beginning")).strip():
        blockers.append("missing_event_week_beginning")
    if _has_truthy_unsafe_fields(sequence):
        blockers.append("sequence_production_boundary_open")

    case_id = "|".join(
        [
            _display(sequence.get("symbol")).strip(),
            _display(sequence.get("event_week_beginning")).strip(),
            _display(sequence.get("target")).strip(),
        ]
    )
    evidence_artifact = _display(sequence.get("screenshot_filename")).strip() or (
        "reviewer_notes" if notes_recorded else ""
    )

    return {
        "case_id": case_id,
        "source_sequence_id": sequence.get("sequence_id", ""),
        "target": sequence.get("target", ""),
        "symbol": sequence.get("symbol", ""),
        "event_week_beginning": sequence.get("event_week_beginning", ""),
        "marker_labels": marker_labels,
        "required_replay_statuses": required_statuses,
        "reviewer_notes_recorded": notes_recorded,
        "screenshot_filename_recorded": screenshot_recorded,
        "evidence_artifact": evidence_artifact,
        "case_status": CASE_READY_STATUS if not blockers else CASE_NEEDS_ATTENTION_STATUS,
        "blockers": blockers,
        "manual_review_only": True,
        "automatic_promotion_allowed": False,
        **PRODUCTION_BOUNDARY,
    }


def _report_blockers(
    evidence_compilation_report: Mapping[str, Any],
    source_sequences: Sequence[Mapping[str, Any]],
    selected_sequences: Sequence[Mapping[str, Any]],
    cases: Sequence[Mapping[str, Any]],
    *,
    symbol_filter: Sequence[str],
    min_cases: int,
) -> list[str]:
    blockers: list[str] = []

    if evidence_compilation_report.get("report_type") != SOURCE_REPORT_TYPE:
        blockers.append("source_report_type_mismatch")
    if evidence_compilation_report.get("evidence_compilation_status") != SOURCE_READY_STATUS:
        blockers.append("source_evidence_compilation_not_ready")
    if evidence_compilation_report.get("evidence_ready") is not True:
        blockers.append("source_evidence_not_ready")
    if not source_sequences:
        blockers.append("missing_source_sequence_reviews")
    if source_sequences and not selected_sequences:
        blockers.append("no_matching_symbol_sequences")
    if _has_truthy_unsafe_fields(evidence_compilation_report):
        blockers.append("report_production_boundary_open")

    ready_count = sum(1 for case in cases if case.get("case_status") == CASE_READY_STATUS)
    if ready_count < min_cases:
        blockers.append("not_enough_ready_casebook_cases")
    if any(case.get("case_status") != CASE_READY_STATUS for case in cases):
        blockers.append("casebook_case_blockers_present")
    if not symbol_filter:
        blockers.append("missing_symbol_filter")

    return blockers


def _normalize_symbols(symbols: Sequence[str]) -> list[str]:
    return sorted({_display(symbol).strip() for symbol in symbols if _display(symbol).strip()})


def _required_statuses(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): _display(status).strip() for key, status in value.items()}


def _mapping_rows(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes, Mapping)):
        return []
    return [row for row in value if isinstance(row, Mapping)]


def _string_rows(value: Any) -> list[str]:
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes, Mapping)):
        return []
    return [_display(row).strip() for row in value if _display(row).strip()]


def _has_truthy_unsafe_fields(mapping: Mapping[str, Any]) -> bool:
    return any(mapping.get(field) is True for field in UNSAFE_TRUTHY_FIELDS)


def _display(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _csv(values: Any) -> str:
    if not values:
        return ""
    if isinstance(values, str):
        return values
    if isinstance(values, Iterable):
        return ", ".join(_display(value) for value in values)
    return _display(values)


def _bool_text(value: Any) -> str:
    return "true" if bool(value) else "false"


def _write_output(content: str, output: Path | None) -> None:
    if output is None:
        print(content)
    else:
        output.write_text(content, encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence_compilation_report", type=Path)
    parser.add_argument("--symbol", action="append", dest="symbols")
    parser.add_argument("--min-cases", type=int, default=1)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    source_report = json.loads(args.evidence_compilation_report.read_text(encoding="utf-8"))
    report = run_effort_result_visual_replay_casebook(
        source_report,
        symbols=args.symbols or DEFAULT_SYMBOL_FILTER,
        min_cases=args.min_cases,
    )
    rendered = (
        render_effort_result_visual_replay_casebook_markdown(report)
        if args.format == "markdown"
        else json.dumps(report, indent=2, sort_keys=True)
    )
    _write_output(rendered, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
