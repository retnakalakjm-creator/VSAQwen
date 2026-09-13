"""Compile visual replay evidence drafts into audit evidence.

This module is audit/report only. It consumes copy-ready evidence exported
from the dev-only Effort/Result replay workbench and compiles it into an
offline manual-review evidence report. It does not read live data, call APIs,
persist scanner state, activate detectors, change scoring/ranking/actionability,
emit alerts, or place orders.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

REPORT_TYPE = "effort_result_visual_replay_evidence_compilation"
REPORT_SCHEMA_VERSION = 1

SOURCE_REPORT_TYPE = "effort_result_visual_replay_evidence_draft"
SOURCE_ALL_CONFIRMED_STATUS = "all_sequences_confirmed"

EVIDENCE_READY_STATUS = "visual_replay_evidence_ready"
EVIDENCE_NEEDS_ATTENTION_STATUS = "visual_replay_evidence_needs_attention"
SEQUENCE_CONFIRMED_STATUS = "confirmed_visual_replay_evidence"
SEQUENCE_NEEDS_ATTENTION_STATUS = "visual_replay_sequence_needs_attention"

REQUIRED_EVIDENCE_STATUS_FIELDS = (
    "marker_alignment_status",
    "pre_event_context_status",
    "post_event_follow_through_status",
    "counterfactual_scan_status",
    "vsa_smc_quality_status",
)

CONFIRMED_STATUS = "confirmed"

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
    "evidence_compilation_only": True,
    "manual_review_only": True,
    "offline_replay_only": True,
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
    "requires_visual_replay_evidence_draft": True,
    "requires_separate_casebook_runner_pr": True,
    "requires_separate_production_pr": True,
}


def compile_effort_result_visual_replay_evidence(
    evidence_draft_report: Mapping[str, Any],
    *,
    min_confirmed_sequences: int = 1,
) -> dict[str, object]:
    """Compile PR #170 evidence drafts into an audit-only report.

    A ready compilation means enough manually reviewed visual replay evidence is
    present for the next offline audit step. It does not authorize any
    production integration, scoring, ranking, actionability, alerts, or orders.
    """

    if min_confirmed_sequences <= 0:
        raise ValueError("min_confirmed_sequences must be positive")

    sequence_rows = _mapping_rows(evidence_draft_report.get("sequence_evidence", []))
    sequence_reviews = [_compile_sequence_evidence(row) for row in sequence_rows]
    confirmed_sequences = [
        row for row in sequence_reviews if row["evidence_status"] == SEQUENCE_CONFIRMED_STATUS
    ]

    blockers = _report_blockers(
        evidence_draft_report,
        sequence_reviews,
        min_confirmed_sequences=min_confirmed_sequences,
    )
    ready = not blockers

    return {
        "report_type": REPORT_TYPE,
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "source_report_type": evidence_draft_report.get("report_type"),
        "source_report_schema_version": evidence_draft_report.get("report_schema_version"),
        "source_evidence_status": evidence_draft_report.get("evidence_status"),
        "source_sequence_count": int(evidence_draft_report.get("sequence_count", len(sequence_rows)) or 0),
        "reviewed_sequence_count": len(sequence_reviews),
        "confirmed_sequence_count": len(confirmed_sequences),
        "needs_attention_sequence_count": len(sequence_reviews) - len(confirmed_sequences),
        "minimum_confirmed_sequences": int(min_confirmed_sequences),
        "evidence_compilation_status": EVIDENCE_READY_STATUS if ready else EVIDENCE_NEEDS_ATTENTION_STATUS,
        "evidence_ready": ready,
        "blockers": blockers,
        "sequence_reviews": sequence_reviews,
        "required_evidence_status_fields": list(REQUIRED_EVIDENCE_STATUS_FIELDS),
        "next_stage": "offline_replay_casebook_runner" if ready else "complete_manual_visual_replay_evidence",
        "automatic_promotion_allowed": False,
        **PRODUCTION_BOUNDARY,
    }


def render_effort_result_visual_replay_evidence_markdown(report: Mapping[str, Any]) -> str:
    """Render the visual replay evidence compilation report as Markdown."""

    lines = [
        "# Effort/Result Visual Replay Evidence Compilation",
        "",
        "## Summary",
        "",
        f"- Source report type: `{_display(report.get('source_report_type'))}`",
        f"- Source evidence status: `{_display(report.get('source_evidence_status'))}`",
        f"- Reviewed sequences: {int(report.get('reviewed_sequence_count', 0))}",
        f"- Confirmed sequences: {int(report.get('confirmed_sequence_count', 0))}",
        f"- Needs-attention sequences: {int(report.get('needs_attention_sequence_count', 0))}",
        f"- Evidence ready: {_bool_text(report.get('evidence_ready'))}",
        f"- Compilation status: `{_display(report.get('evidence_compilation_status'))}`",
        f"- Next stage: `{_display(report.get('next_stage'))}`",
        "",
        "## Production Boundary",
        "",
        "- Audit/report only: true",
        "- Evidence compilation only: true",
        "- Manual review only: true",
        "- Offline replay only: true",
        "- Production change allowed: false",
        "- Automatic promotion allowed: false",
        "- May change scoring: false",
        "- May change ranking: false",
        "- May change actionability: false",
        "- May activate detector: false",
        "- May change scanner/API/frontend/persistence/broker behavior: false",
        "- Requires separate casebook runner PR: true",
        "- Requires separate production PR: true",
        "",
        "## Sequence Evidence",
        "",
    ]

    reviews = _mapping_rows(report.get("sequence_reviews", []))
    if not reviews:
        lines.append("_No visual replay evidence sequences were compiled._")
        lines.append("")
    else:
        lines.extend(
            [
                "| Sequence | Target | Symbol | Week | Status | Marker labels | Notes | Screenshot | Blockers |",
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for row in reviews:
            lines.append(
                "| "
                f"`{_display(row.get('sequence_id'))}` | "
                f"`{_display(row.get('target'))}` | "
                f"{_display(row.get('symbol'))} | "
                f"{_display(row.get('event_week_beginning'))} | "
                f"`{_display(row.get('evidence_status'))}` | "
                f"{_csv(row.get('marker_labels', []))} | "
                f"{_yes_no(row.get('reviewer_notes_recorded'))} | "
                f"{_yes_no(row.get('screenshot_filename_recorded'))} | "
                f"{_csv(row.get('blockers', []))} |"
            )
        lines.append("")

    lines.extend(
        [
            "## Required Confirmations",
            "",
        ]
    )
    for field in report.get("required_evidence_status_fields", []):
        lines.append(f"- {field}: `confirmed`")
    lines.extend(
        [
            "",
            "## Review Rules",
            "",
            "- Use only the copy-ready JSON exported from the dev-only visual replay evidence panel.",
            "- Confirm every required replay evidence field before using this report in the next audit step.",
            "- Reviewer notes or a screenshot filename must be present for each confirmed sequence.",
            "- This report can feed only the next offline replay casebook runner.",
            "- A separate production PR is required before any scoring, ranking, actionability, detector, API, frontend, persistence, alert, or order behavior can change.",
            "",
        ]
    )
    return "\n".join(lines)


def _compile_sequence_evidence(sequence: Mapping[str, Any]) -> dict[str, object]:
    blockers: list[str] = []

    missing_fields = [
        field for field in REQUIRED_EVIDENCE_STATUS_FIELDS if not _display(sequence.get(field)).strip()
    ]
    if missing_fields:
        blockers.append("missing_required_status_fields")

    non_confirmed_fields = [
        field
        for field in REQUIRED_EVIDENCE_STATUS_FIELDS
        if _display(sequence.get(field)).strip() != CONFIRMED_STATUS
    ]
    if non_confirmed_fields:
        blockers.append("required_status_not_confirmed")

    marker_labels = _string_rows(sequence.get("marker_labels", []))
    if not marker_labels:
        blockers.append("missing_marker_labels")

    notes_recorded = bool(_display(sequence.get("reviewer_notes")).strip())
    screenshot_recorded = bool(_display(sequence.get("screenshot_filename")).strip())
    if not notes_recorded and not screenshot_recorded:
        blockers.append("missing_reviewer_notes_or_screenshot")

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

    return {
        "sequence_id": sequence.get("sequence_id", ""),
        "target": sequence.get("target", ""),
        "symbol": sequence.get("symbol", ""),
        "event_week_beginning": sequence.get("event_week_beginning", ""),
        "marker_labels": marker_labels,
        "required_statuses": {
            field: _display(sequence.get(field)).strip() for field in REQUIRED_EVIDENCE_STATUS_FIELDS
        },
        "all_required_statuses_confirmed": not missing_fields and not non_confirmed_fields,
        "reviewer_notes_recorded": notes_recorded,
        "screenshot_filename_recorded": screenshot_recorded,
        "reviewer_notes": _display(sequence.get("reviewer_notes")),
        "screenshot_filename": _display(sequence.get("screenshot_filename")),
        "manual_review_only": True,
        "evidence_status": SEQUENCE_CONFIRMED_STATUS if not blockers else SEQUENCE_NEEDS_ATTENTION_STATUS,
        "blockers": blockers,
        "automatic_promotion_allowed": False,
        **PRODUCTION_BOUNDARY,
    }


def _report_blockers(
    evidence_draft_report: Mapping[str, Any],
    sequence_reviews: Sequence[Mapping[str, Any]],
    *,
    min_confirmed_sequences: int,
) -> list[str]:
    blockers: list[str] = []

    if evidence_draft_report.get("report_type") != SOURCE_REPORT_TYPE:
        blockers.append("source_report_type_mismatch")
    if evidence_draft_report.get("evidence_status") != SOURCE_ALL_CONFIRMED_STATUS:
        blockers.append("source_evidence_not_all_confirmed")
    if not sequence_reviews:
        blockers.append("missing_sequence_evidence")
    if _has_truthy_unsafe_fields(evidence_draft_report):
        blockers.append("report_production_boundary_open")

    confirmed_count = sum(
        1 for row in sequence_reviews if row.get("evidence_status") == SEQUENCE_CONFIRMED_STATUS
    )
    if confirmed_count < min_confirmed_sequences:
        blockers.append("not_enough_confirmed_sequences")

    if any(row.get("evidence_status") != SEQUENCE_CONFIRMED_STATUS for row in sequence_reviews):
        blockers.append("sequence_evidence_blockers_present")

    return blockers


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


def _yes_no(value: Any) -> str:
    return "yes" if value is True else "no"


def _write_output(content: str, output: Path | None) -> None:
    if output is None:
        print(content)
    else:
        output.write_text(content, encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence_draft_report", type=Path)
    parser.add_argument("--min-confirmed-sequences", type=int, default=1)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    source_report = json.loads(args.evidence_draft_report.read_text(encoding="utf-8"))
    report = compile_effort_result_visual_replay_evidence(
        source_report,
        min_confirmed_sequences=args.min_confirmed_sequences,
    )

    rendered = (
        render_effort_result_visual_replay_evidence_markdown(report)
        if args.format == "markdown"
        else json.dumps(report, indent=2, sort_keys=True)
    )
    _write_output(rendered, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
