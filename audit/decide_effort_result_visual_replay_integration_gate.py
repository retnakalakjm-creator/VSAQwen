"""Decide Effort/Result visual replay shadow-integration readiness.

This module is audit/gate only. It consumes the offline reviewer pass/fail
summary report and produces a conservative decision for a separate shadow/dev
integration PR. It does not read live data, call APIs, persist scanner state,
activate detectors, change scoring/ranking/actionability, emit alerts, or place
orders.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

REPORT_TYPE = "effort_result_visual_replay_integration_gate"
REPORT_SCHEMA_VERSION = 1

SOURCE_REPORT_TYPE = "effort_result_visual_replay_reviewer_summary"
SOURCE_READY_STATUS = "reviewer_pass_fail_summary_ready"
SOURCE_NEXT_STAGE = "integration_gate_decision"

GATE_READY_STATUS = "visual_replay_shadow_integration_gate_ready"
GATE_BLOCKED_STATUS = "visual_replay_shadow_integration_gate_blocked"

READY_FOR_SHADOW_INTEGRATION_DECISION = "ready_for_shadow_integration"
NOT_READY_DECISION = "not_ready"
BLOCKED_BY_FAILED_CASES_DECISION = "blocked_by_failed_cases"
BLOCKED_BY_MISSING_MANUAL_REVIEW_DECISION = "blocked_by_missing_manual_review"
BLOCKED_BY_PRODUCTION_BOUNDARY_DECISION = "blocked_by_production_boundary"
BLOCKED_BY_INSUFFICIENT_PASSED_CASES_DECISION = "blocked_by_insufficient_passed_cases"

PASSED_CASE_STATUS = "passed_visual_replay_review"
FAILED_CASE_STATUS = "failed_visual_replay_review"
NEEDS_ATTENTION_CASE_STATUS = "case_review_decision_needs_attention"

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
    "integration_gate_only": True,
    "shadow_integration_gate_only": True,
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
    "requires_visual_replay_reviewer_summary": True,
    "requires_separate_shadow_integration_pr": True,
    "requires_separate_production_pr": True,
}


def decide_effort_result_visual_replay_integration_gate(
    reviewer_summary_report: Mapping[str, Any],
    *,
    min_passed_cases: int = 1,
    max_failed_cases: int = 0,
) -> dict[str, object]:
    """Decide whether visual replay can move to a separate shadow/dev PR.

    A ready gate means the manual replay evidence chain is strong enough to
    start a separate read-only shadow integration. It never authorizes
    production scoring, ranking, actionability, alerts, orders, detector
    activation, persistence, or live scanner behavior changes.
    """

    if min_passed_cases <= 0:
        raise ValueError("min_passed_cases must be positive")
    if max_failed_cases < 0:
        raise ValueError("max_failed_cases must be non-negative")

    case_reviews = _mapping_rows(reviewer_summary_report.get("case_reviews", []))
    reviewed_case_count = _count(reviewer_summary_report, "reviewed_case_count", len(case_reviews))
    passed_case_count = _count(reviewer_summary_report, "passed_case_count", _count_status(case_reviews, PASSED_CASE_STATUS))
    failed_case_count = _count(reviewer_summary_report, "failed_case_count", _count_status(case_reviews, FAILED_CASE_STATUS))
    undecided_case_count = _count(
        reviewer_summary_report,
        "undecided_case_count",
        _count_status(case_reviews, NEEDS_ATTENTION_CASE_STATUS),
    )

    case_review_blockers = _case_review_blockers(case_reviews)
    blockers = _report_blockers(
        reviewer_summary_report,
        case_reviews,
        reviewed_case_count=reviewed_case_count,
        passed_case_count=passed_case_count,
        failed_case_count=failed_case_count,
        undecided_case_count=undecided_case_count,
        min_passed_cases=min_passed_cases,
        max_failed_cases=max_failed_cases,
        case_review_blockers=case_review_blockers,
    )
    gate_decision = _gate_decision(blockers)
    gate_ready = gate_decision == READY_FOR_SHADOW_INTEGRATION_DECISION

    return {
        "report_type": REPORT_TYPE,
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "source_report_type": reviewer_summary_report.get("report_type"),
        "source_review_summary_status": reviewer_summary_report.get("review_summary_status"),
        "source_review_summary_ready": reviewer_summary_report.get("review_summary_ready"),
        "source_integration_candidate_ready": reviewer_summary_report.get("integration_candidate_ready"),
        "source_next_stage": reviewer_summary_report.get("next_stage"),
        "reviewed_case_count": reviewed_case_count,
        "passed_case_count": passed_case_count,
        "failed_case_count": failed_case_count,
        "undecided_case_count": undecided_case_count,
        "minimum_passed_cases": int(min_passed_cases),
        "maximum_failed_cases": int(max_failed_cases),
        "gate_status": GATE_READY_STATUS if gate_ready else GATE_BLOCKED_STATUS,
        "gate_decision": gate_decision,
        "gate_ready": gate_ready,
        "blockers": blockers,
        "case_review_blockers": case_review_blockers,
        "allowed_next_step": (
            "separate_shadow_dev_replay_workflow_integration_pr"
            if gate_ready
            else "resolve_visual_replay_review_gate_blockers"
        ),
        "disallowed_next_steps": [
            "production_scoring_change",
            "production_ranking_change",
            "production_actionability_change",
            "detector_activation",
            "scanner_state_mutation",
            "live_data_api_wiring",
            "alerting_or_order_execution",
        ],
        "automatic_promotion_allowed": False,
        **PRODUCTION_BOUNDARY,
    }


def render_effort_result_visual_replay_integration_gate_markdown(report: Mapping[str, Any]) -> str:
    """Render the visual replay integration gate decision as Markdown."""

    lines = [
        "# Effort/Result Visual Replay Integration Gate",
        "",
        "## Decision",
        "",
        f"- Gate decision: `{_display(report.get('gate_decision'))}`",
        f"- Gate ready: {_bool_text(report.get('gate_ready'))}",
        f"- Gate status: `{_display(report.get('gate_status'))}`",
        f"- Allowed next step: `{_display(report.get('allowed_next_step'))}`",
        "",
        "## Source Summary",
        "",
        f"- Source report type: `{_display(report.get('source_report_type'))}`",
        f"- Source review summary status: `{_display(report.get('source_review_summary_status'))}`",
        f"- Source review summary ready: {_bool_text(report.get('source_review_summary_ready'))}",
        f"- Source integration candidate ready: {_bool_text(report.get('source_integration_candidate_ready'))}",
        f"- Reviewed cases: {int(report.get('reviewed_case_count', 0))}",
        f"- Passed cases: {int(report.get('passed_case_count', 0))}",
        f"- Failed cases: {int(report.get('failed_case_count', 0))}",
        f"- Undecided cases: {int(report.get('undecided_case_count', 0))}",
        "",
        "## Production Boundary",
        "",
        "- Audit/gate only: true",
        "- Shadow integration gate only: true",
        "- Manual review only: true",
        "- Offline replay only: true",
        "- Production change allowed: false",
        "- Automatic promotion allowed: false",
        "- May change scoring: false",
        "- May change ranking: false",
        "- May change actionability: false",
        "- May activate detector: false",
        "- May change scanner/API/frontend/persistence/broker behavior: false",
        "- Requires separate shadow integration PR: true",
        "- Requires separate production PR: true",
        "",
        "## Blockers",
        "",
    ]

    blockers = _string_rows(report.get("blockers", []))
    if blockers:
        lines.extend(f"- {blocker}" for blocker in blockers)
    else:
        lines.append("- none")

    case_blockers = _mapping_rows(report.get("case_review_blockers", []))
    lines.extend(["", "## Case Review Blockers", ""])
    if not case_blockers:
        lines.append("- none")
    else:
        lines.extend(
            f"- `{_display(row.get('case_id'))}`: {_csv(row.get('blockers', []))}"
            for row in case_blockers
        )

    lines.extend(["", "## Disallowed Next Steps", ""])
    for step in _string_rows(report.get("disallowed_next_steps", [])):
        lines.append(f"- {step}")

    lines.extend(
        [
            "",
            "## Gate Rules",
            "",
            "- This gate can approve only a separate read-only shadow/dev replay integration PR.",
            "- It does not approve live scanner integration, production scoring, ranking, actionability, detector activation, persistence, alerts, or orders.",
            "- Any production behavior change still requires a separate production PR after shadow validation.",
            "",
        ]
    )
    return "\n".join(lines)


def _report_blockers(
    reviewer_summary_report: Mapping[str, Any],
    case_reviews: Sequence[Mapping[str, Any]],
    *,
    reviewed_case_count: int,
    passed_case_count: int,
    failed_case_count: int,
    undecided_case_count: int,
    min_passed_cases: int,
    max_failed_cases: int,
    case_review_blockers: Sequence[Mapping[str, Any]],
) -> list[str]:
    blockers: list[str] = []

    if reviewer_summary_report.get("report_type") != SOURCE_REPORT_TYPE:
        blockers.append("source_report_type_mismatch")
    if reviewer_summary_report.get("review_summary_status") != SOURCE_READY_STATUS:
        blockers.append("source_review_summary_not_ready")
    if reviewer_summary_report.get("review_summary_ready") is not True:
        blockers.append("source_review_summary_ready_false")
    if reviewer_summary_report.get("integration_candidate_ready") is not True:
        blockers.append("source_integration_candidate_not_ready")
    if reviewer_summary_report.get("next_stage") != SOURCE_NEXT_STAGE:
        blockers.append("source_next_stage_not_integration_gate_decision")
    if reviewed_case_count <= 0 or not case_reviews:
        blockers.append("missing_case_reviews")
    if passed_case_count < min_passed_cases:
        blockers.append("not_enough_passed_cases")
    if failed_case_count > max_failed_cases:
        blockers.append("failed_cases_exceed_threshold")
    if failed_case_count > 0:
        blockers.append("failed_review_cases_present")
    if undecided_case_count > 0:
        blockers.append("undecided_review_cases_present")
    if _has_truthy_unsafe_fields(reviewer_summary_report):
        blockers.append("report_production_boundary_open")
    if any(
        "case_production_boundary_open" in _string_rows(row.get("blockers", []))
        for row in case_review_blockers
    ):
        blockers.append("case_production_boundary_open_present")
    if case_review_blockers:
        blockers.append("case_review_boundary_or_status_blockers_present")

    source_blockers = _string_rows(reviewer_summary_report.get("blockers", []))
    if source_blockers:
        blockers.append("source_report_blockers_present")
    source_integration_blockers = _string_rows(reviewer_summary_report.get("integration_blockers", []))
    if source_integration_blockers:
        blockers.append("source_integration_blockers_present")

    return _dedupe(blockers)


def _case_review_blockers(case_reviews: Sequence[Mapping[str, Any]]) -> list[dict[str, object]]:
    blocked: list[dict[str, object]] = []
    for row in case_reviews:
        blockers: list[str] = []
        status = _display(row.get("case_review_status")).strip()
        if status not in {PASSED_CASE_STATUS, FAILED_CASE_STATUS}:
            blockers.append("case_review_status_not_final")
        if not _display(row.get("case_id")).strip():
            blockers.append("missing_case_id")
        if _has_truthy_unsafe_fields(row):
            blockers.append("case_production_boundary_open")
        nested_blockers = _string_rows(row.get("blockers", []))
        if nested_blockers:
            blockers.append("case_has_existing_review_blockers")
        if blockers:
            blocked.append(
                {
                    "case_id": row.get("case_id", ""),
                    "case_review_status": status,
                    "blockers": _dedupe(blockers),
                }
            )
    return blocked


def _gate_decision(blockers: Sequence[str]) -> str:
    blocker_set = set(blockers)
    if not blocker_set:
        return READY_FOR_SHADOW_INTEGRATION_DECISION
    if "report_production_boundary_open" in blocker_set or "case_production_boundary_open_present" in blocker_set:
        return BLOCKED_BY_PRODUCTION_BOUNDARY_DECISION
    if "failed_cases_exceed_threshold" in blocker_set or "failed_review_cases_present" in blocker_set:
        return BLOCKED_BY_FAILED_CASES_DECISION
    if "undecided_review_cases_present" in blocker_set or "source_review_summary_not_ready" in blocker_set:
        return BLOCKED_BY_MISSING_MANUAL_REVIEW_DECISION
    if "not_enough_passed_cases" in blocker_set:
        return BLOCKED_BY_INSUFFICIENT_PASSED_CASES_DECISION
    return NOT_READY_DECISION


def _count(report: Mapping[str, Any], field: str, fallback: int) -> int:
    try:
        return int(report.get(field, fallback) or 0)
    except (TypeError, ValueError):
        return fallback


def _count_status(rows: Sequence[Mapping[str, Any]], status: str) -> int:
    return sum(1 for row in rows if row.get("case_review_status") == status)


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


def _dedupe(values: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(values))


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
    parser.add_argument("reviewer_summary_report", type=Path)
    parser.add_argument("--min-passed-cases", type=int, default=1)
    parser.add_argument("--max-failed-cases", type=int, default=0)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    source_report = json.loads(args.reviewer_summary_report.read_text(encoding="utf-8"))
    report = decide_effort_result_visual_replay_integration_gate(
        source_report,
        min_passed_cases=args.min_passed_cases,
        max_failed_cases=args.max_failed_cases,
    )

    rendered = (
        render_effort_result_visual_replay_integration_gate_markdown(report)
        if args.format == "markdown"
        else json.dumps(report, indent=2, sort_keys=True)
    )
    _write_output(rendered, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
