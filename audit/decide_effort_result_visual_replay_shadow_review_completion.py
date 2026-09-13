"""Decide whether manual Effort/Result visual replay shadow reviews are complete.

This module is audit/review-completion-gate only. It consumes the manual shadow
review result capture report and decides whether the results are complete enough
to move into reviewer pass/fail summary reporting. It does not read live data,
call APIs, persist scanner state, activate detectors, change scoring/ranking/
actionability, emit alerts, or place orders.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

REPORT_TYPE = "effort_result_visual_replay_shadow_review_completion_gate"
REPORT_SCHEMA_VERSION = 1

SOURCE_REPORT_TYPE = "effort_result_visual_replay_shadow_review_results"
SOURCE_READY_STATUS = "visual_replay_shadow_review_results_ready"
SOURCE_READY_DECISION = "ready_for_reviewer_pass_fail_summary"
SOURCE_ALLOWED_NEXT_STEP = "run_visual_replay_reviewer_pass_fail_summary"

COMPLETION_READY_STATUS = "visual_replay_shadow_review_completion_ready"
COMPLETION_BLOCKED_STATUS = "visual_replay_shadow_review_completion_blocked"
READY_DECISION = "ready_to_summarize_manual_shadow_replay_results"
BLOCKED_DECISION = "blocked_from_manual_shadow_replay_result_summary"

PASS = "pass"
FAIL = "fail"
UNDECIDED = "undecided"
COMPLETED_OUTCOMES = (PASS, FAIL)

DEFAULT_MIN_COMPLETED_CASES = 2

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
    "review_completion_gate_only": True,
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
    "requires_shadow_review_results": True,
    "requires_completed_manual_reviews": True,
    "requires_reviewer_pass_fail_summary": True,
    "requires_separate_production_pr": True,
}


def decide_effort_result_visual_replay_shadow_review_completion(
    review_results_report: Mapping[str, Any],
    *,
    min_completed_cases: int = DEFAULT_MIN_COMPLETED_CASES,
    require_zero_failed_cases: bool = False,
) -> dict[str, object]:
    """Build a guarded completion gate decision for manual replay review results.

    A ready completion gate means all selected manual shadow replay reviews are
    no longer pending and can be summarized. Failed cases are allowed to flow
    into reviewer-summary reporting so the summary can preserve failures, but
    failed cases must block later integration gates downstream.
    """

    if min_completed_cases <= 0:
        raise ValueError("min_completed_cases must be positive")

    review_cases = _mapping_rows(review_results_report.get("review_cases", []))
    case_rows = [_build_completion_case(row) for row in review_cases]

    source_completed_count = _count(review_results_report, "completed_review_count", 0)
    source_passed_count = _count(review_results_report, "passed_case_count", 0)
    source_failed_count = _count(review_results_report, "failed_case_count", 0)
    source_undecided_count = _count(review_results_report, "undecided_case_count", 0)
    computed_completed_count = sum(
        1 for row in case_rows if row.get("review_outcome") in COMPLETED_OUTCOMES
    )
    completed_count = max(source_completed_count, computed_completed_count)
    failed_count = max(
        source_failed_count,
        sum(1 for row in case_rows if row.get("review_outcome") == FAIL),
    )
    passed_count = max(
        source_passed_count,
        sum(1 for row in case_rows if row.get("review_outcome") == PASS),
    )
    undecided_count = max(
        source_undecided_count,
        sum(1 for row in case_rows if row.get("review_outcome") == UNDECIDED),
    )

    blockers = _completion_blockers(
        review_results_report,
        case_rows=case_rows,
        completed_count=completed_count,
        failed_count=failed_count,
        undecided_count=undecided_count,
        min_completed_cases=min_completed_cases,
        require_zero_failed_cases=require_zero_failed_cases,
    )
    ready = not blockers
    failed_cases_present = failed_count > 0

    return {
        "report_type": REPORT_TYPE,
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "source_report_type": review_results_report.get("report_type"),
        "source_review_results_status": review_results_report.get("review_results_status"),
        "source_review_results_decision": review_results_report.get("review_results_decision"),
        "source_review_results_ready": review_results_report.get("review_results_ready"),
        "source_allowed_next_step": review_results_report.get("allowed_next_step"),
        "minimum_completed_cases": int(min_completed_cases),
        "source_selected_case_count": _count(
            review_results_report, "selected_case_count", len(case_rows)
        ),
        "source_completed_review_count": source_completed_count,
        "computed_completed_review_count": computed_completed_count,
        "completed_review_count": completed_count,
        "passed_case_count": passed_count,
        "failed_case_count": failed_count,
        "undecided_case_count": undecided_count,
        "failed_cases_present": failed_cases_present,
        "require_zero_failed_cases": bool(require_zero_failed_cases),
        "review_completion_status": (
            COMPLETION_READY_STATUS if ready else COMPLETION_BLOCKED_STATUS
        ),
        "review_completion_decision": READY_DECISION if ready else BLOCKED_DECISION,
        "review_completion_ready": ready,
        "blockers": blockers,
        "completion_cases": case_rows,
        "disallowed_production_surfaces": list(DISALLOWED_PRODUCTION_SURFACES),
        "allowed_next_step": (
            "run_visual_replay_reviewer_pass_fail_summary"
            if ready
            else "complete_manual_shadow_replay_reviews_before_summary"
        ),
        "downstream_reviewer_summary_allowed": ready,
        "downstream_integration_gate_should_block": (not ready) or failed_cases_present,
        "failed_cases_must_be_preserved_in_summary": failed_cases_present,
        "manual_revalidation_required": True,
        "production_pr_required_after_shadow_validation": True,
        "automatic_promotion_allowed": False,
        **PRODUCTION_BOUNDARY,
    }


def render_effort_result_visual_replay_shadow_review_completion_markdown(
    report: Mapping[str, Any],
) -> str:
    """Render the manual shadow replay review completion gate as Markdown."""

    lines = [
        "# Effort/Result Visual Replay Shadow Review Completion Gate",
        "",
        "## Decision",
        "",
        f"- Completion decision: `{_display(report.get('review_completion_decision'))}`",
        f"- Review completion ready: {_bool_text(report.get('review_completion_ready'))}",
        f"- Completion status: `{_display(report.get('review_completion_status'))}`",
        f"- Allowed next step: `{_display(report.get('allowed_next_step'))}`",
        f"- Completed reviews: {int(report.get('completed_review_count', 0))}",
        f"- Passed cases: {int(report.get('passed_case_count', 0))}",
        f"- Failed cases: {int(report.get('failed_case_count', 0))}",
        f"- Undecided cases: {int(report.get('undecided_case_count', 0))}",
        "- Downstream reviewer summary allowed: "
        f"{_bool_text(report.get('downstream_reviewer_summary_allowed'))}",
        "- Downstream integration gate should block: "
        f"{_bool_text(report.get('downstream_integration_gate_should_block'))}",
        "",
        "## Source Review Results",
        "",
        f"- Source report type: `{_display(report.get('source_report_type'))}`",
        f"- Source review status: `{_display(report.get('source_review_results_status'))}`",
        f"- Source review decision: `{_display(report.get('source_review_results_decision'))}`",
        f"- Source review results ready: {_bool_text(report.get('source_review_results_ready'))}",
        f"- Source allowed next step: `{_display(report.get('source_allowed_next_step'))}`",
        "",
        "## Production Boundary",
        "",
        "- Audit/review-completion-gate only: true",
        "- Manual review only: true",
        "- Offline replay only: true",
        "- Production change allowed: false",
        "- Automatic promotion allowed: false",
        "- May change scoring: false",
        "- May change ranking: false",
        "- May change actionability: false",
        "- May activate detector: false",
        "- May change scanner/API/frontend/persistence/broker behavior: false",
        "- Requires separate production PR: true",
        "",
        "## Completion Cases",
        "",
    ]

    cases = _mapping_rows(report.get("completion_cases", []))
    if not cases:
        lines.append("_No review-result cases were selected._")
        lines.append("")
    else:
        lines.extend(
            [
                "| Case | Target | Symbol | Week | Outcome | Ready | Blockers |",
                "| --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for row in cases:
            lines.append(
                "| "
                f"`{_display(row.get('case_id'))}` | "
                f"`{_display(row.get('target'))}` | "
                f"{_display(row.get('symbol'))} | "
                f"{_display(row.get('event_week_beginning'))} | "
                f"`{_display(row.get('review_outcome'))}` | "
                f"{_bool_text(row.get('review_case_ready'))} | "
                f"{_csv(row.get('blockers', []))} |"
            )
        lines.append("")

    blockers = _string_rows(report.get("blockers", []))
    lines.extend(["## Blockers", ""])
    if blockers:
        lines.extend(f"- {blocker}" for blocker in blockers)
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Gate Rules",
            "",
            "- Do not run reviewer pass/fail summary while any review outcome is undecided.",
            "- Preserve failed cases in reviewer-summary reporting; do not hide them.",
            "- Failed completed cases must block later integration gates downstream.",
            "- This gate does not approve production behavior changes.",
            "- A separate production PR is required before any scoring, ranking, actionability, detector, API, frontend, persistence, alert, or order behavior can change.",
            "",
        ]
    )
    return "\n".join(lines)


def _build_completion_case(review_case: Mapping[str, Any]) -> dict[str, object]:
    blockers = _string_rows(review_case.get("blockers", []))
    review_outcome = _display(review_case.get("review_outcome")).strip().lower()
    review_case_ready = review_case.get("review_case_ready") is True

    if not _display(review_case.get("case_id")).strip():
        blockers.append("missing_case_id")
    if review_outcome not in (PASS, FAIL, UNDECIDED):
        blockers.append("invalid_review_outcome")
    if review_outcome == UNDECIDED:
        blockers.append("manual_review_outcome_undecided")
    if not review_case_ready:
        blockers.append("source_review_case_not_ready")
    if _has_truthy_unsafe_fields(review_case):
        blockers.append("case_production_boundary_open")

    return {
        "case_id": review_case.get("case_id", ""),
        "symbol": review_case.get("symbol", ""),
        "event_week_beginning": review_case.get("event_week_beginning", ""),
        "target": review_case.get("target", ""),
        "review_outcome": review_outcome,
        "review_case_ready": review_case_ready and not blockers,
        "blockers": _dedupe(blockers),
        "manual_review_only": True,
        "automatic_promotion_allowed": False,
        **PRODUCTION_BOUNDARY,
    }


def _completion_blockers(
    review_results_report: Mapping[str, Any],
    *,
    case_rows: Sequence[Mapping[str, Any]],
    completed_count: int,
    failed_count: int,
    undecided_count: int,
    min_completed_cases: int,
    require_zero_failed_cases: bool,
) -> list[str]:
    blockers: list[str] = []

    if review_results_report.get("report_type") != SOURCE_REPORT_TYPE:
        blockers.append("source_report_type_mismatch")
    if review_results_report.get("review_results_status") != SOURCE_READY_STATUS:
        blockers.append("source_review_results_status_not_ready")
    if review_results_report.get("review_results_decision") != SOURCE_READY_DECISION:
        blockers.append("source_review_results_decision_not_ready")
    if review_results_report.get("review_results_ready") is not True:
        blockers.append("source_review_results_ready_false")
    if review_results_report.get("allowed_next_step") != SOURCE_ALLOWED_NEXT_STEP:
        blockers.append("source_allowed_next_step_not_reviewer_summary")
    if _string_rows(review_results_report.get("blockers", [])):
        blockers.append("source_review_result_blockers_present")
    if _has_truthy_unsafe_fields(review_results_report):
        blockers.append("source_production_boundary_open")

    source_completed_count = _count(review_results_report, "completed_review_count", 0)
    source_passed_count = _count(review_results_report, "passed_case_count", 0)
    source_failed_count = _count(review_results_report, "failed_case_count", 0)
    source_undecided_count = _count(review_results_report, "undecided_case_count", 0)
    computed_completed_count = sum(
        1 for case in case_rows if case.get("review_outcome") in COMPLETED_OUTCOMES
    )
    computed_passed_count = sum(1 for case in case_rows if case.get("review_outcome") == PASS)
    computed_failed_count = sum(1 for case in case_rows if case.get("review_outcome") == FAIL)
    computed_undecided_count = sum(
        1 for case in case_rows if case.get("review_outcome") == UNDECIDED
    )

    if not case_rows:
        blockers.append("missing_review_cases")
    if completed_count < min_completed_cases:
        blockers.append("not_enough_completed_manual_reviews")
    if source_completed_count != computed_completed_count:
        blockers.append("completed_review_count_mismatch")
    if source_passed_count != computed_passed_count:
        blockers.append("passed_case_count_mismatch")
    if source_failed_count != computed_failed_count:
        blockers.append("failed_case_count_mismatch")
    if source_undecided_count != computed_undecided_count:
        blockers.append("undecided_case_count_mismatch")
    if undecided_count:
        blockers.append("undecided_review_results_present")
    if any(case.get("review_case_ready") is not True for case in case_rows):
        blockers.append("review_case_completion_blockers_present")
    if require_zero_failed_cases and failed_count:
        blockers.append("failed_review_cases_present")

    return _dedupe(blockers)


def _count(mapping: Mapping[str, Any], key: str, default: int) -> int:
    try:
        return int(mapping.get(key, default) or 0)
    except (TypeError, ValueError):
        return int(default)


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
    parser.add_argument("review_results_report", type=Path)
    parser.add_argument("--min-completed-cases", type=int, default=DEFAULT_MIN_COMPLETED_CASES)
    parser.add_argument("--require-zero-failed-cases", action="store_true")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    source_report = json.loads(args.review_results_report.read_text(encoding="utf-8"))
    report = decide_effort_result_visual_replay_shadow_review_completion(
        source_report,
        min_completed_cases=args.min_completed_cases,
        require_zero_failed_cases=args.require_zero_failed_cases,
    )
    rendered = (
        render_effort_result_visual_replay_shadow_review_completion_markdown(report)
        if args.format == "markdown"
        else json.dumps(report, indent=2, sort_keys=True)
    )
    _write_output(rendered, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
