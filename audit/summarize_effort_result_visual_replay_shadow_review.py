"""Summarize visual replay shadow reviewer pass/fail inputs.

This module is audit/reporting only. It consumes normalized manual review
summary input and emits a reviewer pass/fail summary report. It does not read
live data, call external services, change production persistence, activate
detectors, change scoring, ranking, actionability, scanner state, alerts, or
orders.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

REPORT_TYPE = "effort_result_visual_replay_shadow_reviewer_summary_report"
REPORT_SCHEMA_VERSION = 1

SOURCE_REPORT_TYPE = "effort_result_visual_replay_shadow_review_summary_input"
SOURCE_READY_STATUS = "visual_replay_shadow_review_summary_input_ready"
SOURCE_READY_DECISION = "ready_to_run_visual_replay_reviewer_pass_fail_summary"
SOURCE_ALLOWED_NEXT_STEP = "run_visual_replay_reviewer_pass_fail_summary"

READY_STATUS = "visual_replay_shadow_reviewer_summary_ready"
BLOCKED_STATUS = "visual_replay_shadow_reviewer_summary_blocked"
PASSING_DECISION = "ready_for_shadow_visual_replay_integration_gate"
FAILED_DECISION = "blocked_by_failed_shadow_visual_replay_cases"
BLOCKED_DECISION = "blocked_from_shadow_visual_replay_reviewer_summary"

PASS = "pass"
FAIL = "fail"
UNDECIDED = "undecided"
DEFAULT_REQUIRED_SYMBOLS = ("LT.NS",)
DEFAULT_MIN_SUMMARY_CASES = 2

UNSAFE_TRUTHY_FIELDS = (
    "include_in_scoring",
    "include_in_ranking",
    "include_in_actionability",
    "emit" + "_" + "alert",
    "place" + "_" + "order",
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

DISALLOWED_PRODUCTION_SURFACES = (
    "live_market_data_fetch",
    "scanner_state_mutation",
    "production_signal_persistence",
    "production_api_wiring",
    "production_frontend_activation",
    "detector_activation",
    "scoring_change",
    "ranking_change",
    "actionability_change",
    "alerting",
    "order_execution",
)

PRODUCTION_BOUNDARY = {
    "audit_only": True,
    "reviewer_summary_report_only": True,
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
    "requires_summary_input_adapter": True,
    "requires_shadow_integration_gate": True,
    "requires_separate_production_pr": True,
}


def summarize_effort_result_visual_replay_shadow_review(
    summary_input_report: Mapping[str, Any],
    *,
    required_symbols: Sequence[str] = DEFAULT_REQUIRED_SYMBOLS,
    min_summary_cases: int = DEFAULT_MIN_SUMMARY_CASES,
) -> dict[str, object]:
    """Build a reviewer pass/fail summary from normalized shadow-review input."""

    if min_summary_cases <= 0:
        raise ValueError("min_summary_cases must be positive")

    symbols = _normalize_symbols(required_symbols)
    source_cases = _mapping_rows(summary_input_report.get("summary_cases", []))
    selected_cases = [
        case for case in source_cases if not symbols or _display(case.get("symbol")).strip() in symbols
    ]
    reviewer_cases = [_reviewer_case(case) for case in selected_cases]

    passed_count = sum(1 for case in reviewer_cases if case.get("review_outcome") == PASS)
    failed_count = sum(1 for case in reviewer_cases if case.get("review_outcome") == FAIL)
    undecided_count = sum(1 for case in reviewer_cases if case.get("review_outcome") == UNDECIDED)
    completed_count = passed_count + failed_count

    blockers = _blockers(
        summary_input_report,
        selected_cases=selected_cases,
        reviewer_cases=reviewer_cases,
        required_symbols=symbols,
        min_summary_cases=min_summary_cases,
    )
    ready = not blockers
    shadow_validation_passed = ready and failed_count == 0 and undecided_count == 0

    if not ready:
        decision = BLOCKED_DECISION
        allowed_next_step = "resolve_shadow_reviewer_summary_blockers"
    elif shadow_validation_passed:
        decision = PASSING_DECISION
        allowed_next_step = "run_shadow_visual_replay_integration_gate"
    else:
        decision = FAILED_DECISION
        allowed_next_step = "resolve_failed_shadow_visual_replay_cases"

    return {
        "report_type": REPORT_TYPE,
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "source_report_type": summary_input_report.get("report_type"),
        "source_summary_input_status": summary_input_report.get("summary_input_status"),
        "source_summary_input_decision": summary_input_report.get("summary_input_decision"),
        "source_summary_input_ready": summary_input_report.get("summary_input_ready"),
        "source_allowed_next_step": summary_input_report.get("allowed_next_step"),
        "required_symbols": symbols,
        "minimum_summary_cases": int(min_summary_cases),
        "source_case_count": len(source_cases),
        "selected_case_count": len(selected_cases),
        "completed_case_count": completed_count,
        "passed_case_count": passed_count,
        "failed_case_count": failed_count,
        "undecided_case_count": undecided_count,
        "reviewer_summary_status": READY_STATUS if ready else BLOCKED_STATUS,
        "reviewer_summary_decision": decision,
        "reviewer_summary_ready": ready,
        "shadow_validation_passed": shadow_validation_passed,
        "downstream_integration_blocked": not shadow_validation_passed,
        "blockers": blockers,
        "case_summaries": reviewer_cases,
        "disallowed_production_surfaces": list(DISALLOWED_PRODUCTION_SURFACES),
        "allowed_next_step": allowed_next_step,
        "automatic_promotion_allowed": False,
        "production_pr_required_after_shadow_validation": True,
        **PRODUCTION_BOUNDARY,
    }


def render_effort_result_visual_replay_shadow_reviewer_summary_markdown(report: Mapping[str, Any]) -> str:
    """Render the reviewer summary report as Markdown."""

    lines = [
        "# Effort/Result Visual Replay Shadow Reviewer Summary",
        "",
        "## Decision",
        "",
        f"- Reviewer summary decision: `{_display(report.get('reviewer_summary_decision'))}`",
        f"- Reviewer summary ready: {_bool_text(report.get('reviewer_summary_ready'))}",
        f"- Reviewer summary status: `{_display(report.get('reviewer_summary_status'))}`",
        f"- Shadow validation passed: {_bool_text(report.get('shadow_validation_passed'))}",
        f"- Downstream integration blocked: {_bool_text(report.get('downstream_integration_blocked'))}",
        f"- Allowed next step: `{_display(report.get('allowed_next_step'))}`",
        f"- Selected cases: {int(report.get('selected_case_count', 0))}",
        f"- Completed cases: {int(report.get('completed_case_count', 0))}",
        f"- Passed cases: {int(report.get('passed_case_count', 0))}",
        f"- Failed cases: {int(report.get('failed_case_count', 0))}",
        f"- Undecided cases: {int(report.get('undecided_case_count', 0))}",
        "",
        "## Source Summary Input",
        "",
        f"- Source report type: `{_display(report.get('source_report_type'))}`",
        f"- Source summary input ready: {_bool_text(report.get('source_summary_input_ready'))}",
        f"- Source decision: `{_display(report.get('source_summary_input_decision'))}`",
        f"- Source allowed next step: `{_display(report.get('source_allowed_next_step'))}`",
        "",
        "## Production Boundary",
        "",
        "- Audit/reviewer-summary-report only: true",
        "- Manual review only: true",
        "- Offline replay only: true",
        "- Production change allowed: false",
        "- Automatic promotion allowed: false",
        "- May change scoring/ranking/actionability/detector/scanner/API/frontend/persistence/orders: false",
        "- Requires separate production PR: true",
        "",
        "## Case Summaries",
        "",
    ]

    cases = _mapping_rows(report.get("case_summaries", []))
    if not cases:
        lines.append("_No reviewer cases selected._")
    else:
        lines.extend([
            "| Case | Symbol | Week | Target | Outcome | Reviewer | Evidence | Integration Blocker |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ])
        for case in cases:
            lines.append(
                "| "
                f"`{_display(case.get('case_id'))}` | "
                f"{_display(case.get('symbol'))} | "
                f"{_display(case.get('event_week_beginning'))} | "
                f"`{_display(case.get('target'))}` | "
                f"`{_display(case.get('review_outcome'))}` | "
                f"{_display(case.get('reviewer'))} | "
                f"{_display(case.get('evidence_artifact'))} | "
                f"{_bool_text(case.get('integration_blocked'))} |"
            )

    lines.extend(["", "## Blockers", ""])
    blockers = _string_rows(report.get("blockers", []))
    lines.extend(f"- {blocker}" for blocker in blockers) if blockers else lines.append("- none")
    lines.extend([
        "",
        "## Summary Rules",
        "",
        "- Only ready summary-input reports can generate ready reviewer summaries.",
        "- Any failed case blocks downstream integration until resolved.",
        "- Any undecided case blocks downstream integration until reviewed.",
        "- This report does not approve production behavior changes.",
        "- A separate production PR is required before scanner, detector, scoring, ranking, actionability, API, frontend, persistence, alert, or order behavior can change.",
        "",
    ])
    return "\n".join(lines)


def _reviewer_case(case: Mapping[str, Any]) -> dict[str, object]:
    outcome = _normalize_outcome(case.get("review_outcome", UNDECIDED))
    source_blockers = _string_rows(case.get("blockers", []))
    case_unsafe = _has_truthy_unsafe_fields(case)
    case_ready = case.get("summary_case_ready") is True and outcome in (PASS, FAIL) and not source_blockers and not case_unsafe
    integration_blocked = outcome != PASS
    blockers: list[str] = []
    if case.get("summary_case_ready") is not True:
        blockers.append("source_summary_case_not_ready")
    if outcome == UNDECIDED:
        blockers.append("undecided_review_outcome")
    if source_blockers:
        blockers.append("source_summary_case_blockers_present")
    if case_unsafe:
        blockers.append("case_production_boundary_open")

    return {
        "case_id": _display(case.get("case_id")).strip(),
        "symbol": _display(case.get("symbol")).strip(),
        "event_week_beginning": _display(case.get("event_week_beginning")).strip(),
        "target": _display(case.get("target")).strip(),
        "review_outcome": outcome,
        "reviewer": _display(case.get("reviewer")).strip(),
        "reviewed_at": _display(case.get("reviewed_at")).strip(),
        "evidence_artifact": _display(case.get("evidence_artifact")).strip(),
        "source_summary_case_ready": case.get("summary_case_ready") is True,
        "reviewer_case_ready": case_ready,
        "integration_blocked": integration_blocked,
        "blockers": _dedupe(blockers),
        "automatic_promotion_allowed": False,
        **PRODUCTION_BOUNDARY,
    }


def _blockers(
    source: Mapping[str, Any],
    *,
    selected_cases: Sequence[Mapping[str, Any]],
    reviewer_cases: Sequence[Mapping[str, Any]],
    required_symbols: Sequence[str],
    min_summary_cases: int,
) -> list[str]:
    blockers: list[str] = []
    if source.get("report_type") != SOURCE_REPORT_TYPE:
        blockers.append("source_report_type_mismatch")
    if source.get("summary_input_status") != SOURCE_READY_STATUS:
        blockers.append("source_summary_input_status_not_ready")
    if source.get("summary_input_decision") != SOURCE_READY_DECISION:
        blockers.append("source_summary_input_decision_not_ready")
    if source.get("summary_input_ready") is not True:
        blockers.append("source_summary_input_ready_false")
    if source.get("allowed_next_step") != SOURCE_ALLOWED_NEXT_STEP:
        blockers.append("source_allowed_next_step_not_reviewer_summary")
    if _string_rows(source.get("blockers", [])):
        blockers.append("source_summary_input_blockers_present")
    if _has_truthy_unsafe_fields(source):
        blockers.append("source_production_boundary_open")
    if not required_symbols:
        blockers.append("missing_required_symbols")
    if not selected_cases:
        blockers.append("missing_selected_summary_cases")
    if sum(1 for case in reviewer_cases if case.get("reviewer_case_ready") is True) < min_summary_cases:
        blockers.append("not_enough_reviewer_ready_cases")
    if any(case.get("reviewer_case_ready") is not True for case in reviewer_cases):
        blockers.append("reviewer_case_blockers_present")
    if any(case.get("review_outcome") == UNDECIDED for case in reviewer_cases):
        blockers.append("undecided_reviewer_cases_present")
    return _dedupe(blockers)


def _normalize_symbols(symbols: Sequence[str]) -> list[str]:
    return sorted({_display(symbol).strip() for symbol in symbols if _display(symbol).strip()})


def _normalize_outcome(value: Any) -> str:
    outcome = _display(value).strip().lower()
    if outcome in (PASS, FAIL, UNDECIDED):
        return outcome
    return UNDECIDED


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


def _dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _display(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _bool_text(value: Any) -> str:
    return "true" if bool(value) else "false"


def _write_output(content: str, output: Path | None) -> None:
    if output is None:
        print(content)
    else:
        output.write_text(content, encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("summary_input_report", type=Path)
    parser.add_argument("--symbol", action="append", dest="symbols")
    parser.add_argument("--min-summary-cases", type=int, default=DEFAULT_MIN_SUMMARY_CASES)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    source = json.loads(args.summary_input_report.read_text(encoding="utf-8"))
    report = summarize_effort_result_visual_replay_shadow_review(
        source,
        required_symbols=args.symbols or DEFAULT_REQUIRED_SYMBOLS,
        min_summary_cases=args.min_summary_cases,
    )
    rendered = (
        render_effort_result_visual_replay_shadow_reviewer_summary_markdown(report)
        if args.format == "markdown"
        else json.dumps(report, indent=2, sort_keys=True)
    )
    _write_output(rendered, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
