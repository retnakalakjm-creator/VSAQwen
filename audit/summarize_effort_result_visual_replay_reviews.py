"""Summarize Effort/Result visual replay casebook pass/fail decisions.

This module is audit/report only. It consumes an offline visual replay
casebook after manual reviewer pass/fail decisions are added to each case and
summarizes whether the casebook is an integration-gate candidate. It does not
read live data, call APIs, persist scanner state, activate detectors, change
scoring/ranking/actionability, emit alerts, or place orders.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

REPORT_TYPE = "effort_result_visual_replay_reviewer_summary"
REPORT_SCHEMA_VERSION = 1

SOURCE_REPORT_TYPE = "effort_result_visual_replay_casebook"
SOURCE_READY_STATUS = "visual_replay_casebook_ready"
SOURCE_CASE_READY_STATUS = "ready_for_casebook_review"

REVIEW_SUMMARY_READY_STATUS = "reviewer_pass_fail_summary_ready"
REVIEW_SUMMARY_NEEDS_ATTENTION_STATUS = "reviewer_pass_fail_summary_needs_attention"

CASE_PASSED_STATUS = "passed_visual_replay_review"
CASE_FAILED_STATUS = "failed_visual_replay_review"
CASE_NEEDS_ATTENTION_STATUS = "case_review_decision_needs_attention"

PASS_DECISION = "pass"
FAIL_DECISION = "fail"
VALID_REVIEW_DECISIONS = (PASS_DECISION, FAIL_DECISION)

DECISION_FIELDS = (
    "review_decision",
    "manual_review_decision",
    "reviewer_decision",
)
RATIONALE_FIELDS = (
    "review_rationale",
    "reviewer_notes",
    "review_notes",
    "pass_rationale",
    "failure_reason",
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
    "reviewer_summary_only": True,
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
    "requires_visual_replay_casebook": True,
    "requires_manual_pass_fail_decisions": True,
    "requires_separate_integration_gate_pr": True,
    "requires_separate_production_pr": True,
}


def summarize_effort_result_visual_replay_reviews(
    casebook_report: Mapping[str, Any],
    *,
    min_passed_cases: int = 1,
    max_failed_cases: int = 0,
) -> dict[str, object]:
    """Build an audit-only pass/fail summary from a reviewed replay casebook.

    A ready summary means every case has a valid manual reviewer decision. An
    integration candidate additionally needs enough passed cases and no more
    failed cases than allowed by ``max_failed_cases``. This function never
    promotes signals, changes production code, updates scanner state, or
    authorizes alerts/orders.
    """

    if min_passed_cases <= 0:
        raise ValueError("min_passed_cases must be positive")
    if max_failed_cases < 0:
        raise ValueError("max_failed_cases must be non-negative")

    case_rows = _mapping_rows(casebook_report.get("casebook_cases", []))
    case_reviews = [_summarize_case_review(row) for row in case_rows]

    passed_cases = [row for row in case_reviews if row["case_review_status"] == CASE_PASSED_STATUS]
    failed_cases = [row for row in case_reviews if row["case_review_status"] == CASE_FAILED_STATUS]
    undecided_cases = [
        row for row in case_reviews if row["case_review_status"] == CASE_NEEDS_ATTENTION_STATUS
    ]

    blockers = _report_blockers(casebook_report, case_reviews)
    integration_blockers = _integration_blockers(
        passed_count=len(passed_cases),
        failed_count=len(failed_cases),
        min_passed_cases=min_passed_cases,
        max_failed_cases=max_failed_cases,
    )
    summary_ready = not blockers
    integration_candidate_ready = summary_ready and not integration_blockers

    return {
        "report_type": REPORT_TYPE,
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "source_report_type": casebook_report.get("report_type"),
        "source_casebook_status": casebook_report.get("casebook_status"),
        "source_casebook_ready": casebook_report.get("casebook_ready"),
        "source_casebook_case_count": int(
            casebook_report.get("casebook_case_count", len(case_rows)) or 0
        ),
        "reviewed_case_count": len(case_reviews),
        "passed_case_count": len(passed_cases),
        "failed_case_count": len(failed_cases),
        "undecided_case_count": len(undecided_cases),
        "minimum_passed_cases": int(min_passed_cases),
        "maximum_failed_cases": int(max_failed_cases),
        "review_summary_status": (
            REVIEW_SUMMARY_READY_STATUS if summary_ready else REVIEW_SUMMARY_NEEDS_ATTENTION_STATUS
        ),
        "review_summary_ready": summary_ready,
        "integration_candidate_ready": integration_candidate_ready,
        "blockers": blockers,
        "integration_blockers": integration_blockers,
        "case_reviews": case_reviews,
        "next_stage": _next_stage(summary_ready, integration_candidate_ready),
        "automatic_promotion_allowed": False,
        **PRODUCTION_BOUNDARY,
    }


def render_effort_result_visual_replay_reviewer_summary_markdown(
    report: Mapping[str, Any],
) -> str:
    """Render the visual replay reviewer pass/fail summary as Markdown."""

    lines = [
        "# Effort/Result Visual Replay Reviewer Pass/Fail Summary",
        "",
        "## Summary",
        "",
        f"- Source report type: `{_display(report.get('source_report_type'))}`",
        f"- Source casebook status: `{_display(report.get('source_casebook_status'))}`",
        f"- Source casebook ready: {_bool_text(report.get('source_casebook_ready'))}",
        f"- Reviewed cases: {int(report.get('reviewed_case_count', 0))}",
        f"- Passed cases: {int(report.get('passed_case_count', 0))}",
        f"- Failed cases: {int(report.get('failed_case_count', 0))}",
        f"- Undecided cases: {int(report.get('undecided_case_count', 0))}",
        f"- Review summary ready: {_bool_text(report.get('review_summary_ready'))}",
        f"- Integration candidate ready: {_bool_text(report.get('integration_candidate_ready'))}",
        f"- Review summary status: `{_display(report.get('review_summary_status'))}`",
        f"- Next stage: `{_display(report.get('next_stage'))}`",
        "",
        "## Production Boundary",
        "",
        "- Audit/report only: true",
        "- Reviewer summary only: true",
        "- Manual review only: true",
        "- Offline replay only: true",
        "- Production change allowed: false",
        "- Automatic promotion allowed: false",
        "- May change scoring: false",
        "- May change ranking: false",
        "- May change actionability: false",
        "- May activate detector: false",
        "- May change scanner/API/frontend/persistence/broker behavior: false",
        "- Requires separate integration gate PR: true",
        "- Requires separate production PR: true",
        "",
        "## Case Reviews",
        "",
    ]

    case_reviews = _mapping_rows(report.get("case_reviews", []))
    if not case_reviews:
        lines.append("_No case reviews were summarized._")
        lines.append("")
    else:
        lines.extend(
            [
                "| Case | Target | Symbol | Week | Decision | Status | Rationale | Blockers |",
                "| --- | --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for row in case_reviews:
            lines.append(
                "| "
                f"`{_display(row.get('case_id'))}` | "
                f"`{_display(row.get('target'))}` | "
                f"{_display(row.get('symbol'))} | "
                f"{_display(row.get('event_week_beginning'))} | "
                f"`{_display(row.get('review_decision'))}` | "
                f"`{_display(row.get('case_review_status'))}` | "
                f"{_display(row.get('review_rationale'))} | "
                f"{_csv(row.get('blockers', []))} |"
            )
        lines.append("")

    report_blockers = report.get("blockers", [])
    integration_blockers = report.get("integration_blockers", [])
    lines.extend(["## Blockers", ""])
    if report_blockers:
        for blocker in report_blockers:
            lines.append(f"- {blocker}")
    else:
        lines.append("- none")

    lines.extend(["", "## Integration Candidate Blockers", ""])
    if integration_blockers:
        for blocker in integration_blockers:
            lines.append(f"- {blocker}")
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Review Rules",
            "",
            "- Use only the offline visual replay casebook from the casebook runner.",
            "- Every case must have a manual `pass` or `fail` decision before the summary is ready.",
            "- Failed cases do not change production behavior; they block integration-candidate readiness.",
            "- This report can feed only the separate integration gate decision step.",
            "- A separate production PR is required before any scoring, ranking, actionability, detector, API, frontend, persistence, alert, or order behavior can change.",
            "",
        ]
    )
    return "\n".join(lines)


def _summarize_case_review(case: Mapping[str, Any]) -> dict[str, object]:
    blockers: list[str] = []

    decision = _review_decision(case)
    rationale = _review_rationale(case)
    marker_labels = _string_rows(case.get("marker_labels", []))

    if case.get("case_status") != SOURCE_CASE_READY_STATUS:
        blockers.append("source_case_not_ready_for_review")
    if not _display(case.get("case_id")).strip():
        blockers.append("missing_case_id")
    if not _display(case.get("target")).strip():
        blockers.append("missing_target")
    if not _display(case.get("symbol")).strip():
        blockers.append("missing_symbol")
    if not _display(case.get("event_week_beginning")).strip():
        blockers.append("missing_event_week_beginning")
    if not marker_labels:
        blockers.append("missing_marker_labels")
    if not decision:
        blockers.append("missing_review_decision")
    elif decision not in VALID_REVIEW_DECISIONS:
        blockers.append("invalid_review_decision")
    if not rationale:
        blockers.append("missing_review_rationale")
    if _has_truthy_unsafe_fields(case):
        blockers.append("case_production_boundary_open")

    if blockers:
        status = CASE_NEEDS_ATTENTION_STATUS
    elif decision == PASS_DECISION:
        status = CASE_PASSED_STATUS
    else:
        status = CASE_FAILED_STATUS

    return {
        "case_id": case.get("case_id", ""),
        "source_sequence_id": case.get("source_sequence_id", ""),
        "target": case.get("target", ""),
        "symbol": case.get("symbol", ""),
        "event_week_beginning": case.get("event_week_beginning", ""),
        "marker_labels": marker_labels,
        "review_decision": decision,
        "review_rationale": rationale,
        "case_review_status": status,
        "blockers": blockers,
        "manual_review_only": True,
        "automatic_promotion_allowed": False,
        **PRODUCTION_BOUNDARY,
    }


def _report_blockers(
    casebook_report: Mapping[str, Any],
    case_reviews: Sequence[Mapping[str, Any]],
) -> list[str]:
    blockers: list[str] = []

    if casebook_report.get("report_type") != SOURCE_REPORT_TYPE:
        blockers.append("source_report_type_mismatch")
    if casebook_report.get("casebook_status") != SOURCE_READY_STATUS:
        blockers.append("source_casebook_not_ready")
    if casebook_report.get("casebook_ready") is not True:
        blockers.append("source_casebook_ready_false")
    if not case_reviews:
        blockers.append("missing_casebook_cases")
    if _has_truthy_unsafe_fields(casebook_report):
        blockers.append("report_production_boundary_open")
    if any(row.get("case_review_status") == CASE_NEEDS_ATTENTION_STATUS for row in case_reviews):
        blockers.append("case_review_decision_blockers_present")

    return blockers


def _integration_blockers(
    *,
    passed_count: int,
    failed_count: int,
    min_passed_cases: int,
    max_failed_cases: int,
) -> list[str]:
    blockers: list[str] = []
    if passed_count < min_passed_cases:
        blockers.append("not_enough_passed_cases")
    if failed_count > max_failed_cases:
        blockers.append("failed_cases_exceed_threshold")
    return blockers


def _next_stage(summary_ready: bool, integration_candidate_ready: bool) -> str:
    if integration_candidate_ready:
        return "integration_gate_decision"
    if summary_ready:
        return "resolve_failed_or_insufficient_review_cases"
    return "complete_reviewer_casebook_decisions"


def _review_decision(case: Mapping[str, Any]) -> str:
    for field in DECISION_FIELDS:
        value = _display(case.get(field)).strip().lower()
        if value:
            return value
    return ""


def _review_rationale(case: Mapping[str, Any]) -> str:
    for field in RATIONALE_FIELDS:
        value = _display(case.get(field)).strip()
        if value:
            return value
    return ""


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
    parser.add_argument("casebook_report", type=Path)
    parser.add_argument("--min-passed-cases", type=int, default=1)
    parser.add_argument("--max-failed-cases", type=int, default=0)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    source_report = json.loads(args.casebook_report.read_text(encoding="utf-8"))
    report = summarize_effort_result_visual_replay_reviews(
        source_report,
        min_passed_cases=args.min_passed_cases,
        max_failed_cases=args.max_failed_cases,
    )

    rendered = (
        render_effort_result_visual_replay_reviewer_summary_markdown(report)
        if args.format == "markdown"
        else json.dumps(report, indent=2, sort_keys=True)
    )
    _write_output(rendered, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
