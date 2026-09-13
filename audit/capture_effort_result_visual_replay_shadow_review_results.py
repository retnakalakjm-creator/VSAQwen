"""Capture manual Effort/Result visual replay shadow review results.

This module is audit/review-result-capture only. It consumes the offline shadow
coverage plan and manually supplied review outcomes for each replay case. It
does not read live data, call APIs, persist scanner state, activate detectors,
change scoring/ranking/actionability, emit alerts, or place orders.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

REPORT_TYPE = "effort_result_visual_replay_shadow_review_results"
REPORT_SCHEMA_VERSION = 1

SOURCE_REPORT_TYPE = "effort_result_visual_replay_shadow_coverage_plan"
SOURCE_READY_STATUS = "visual_replay_shadow_coverage_plan_ready"
SOURCE_READY_DECISION = "ready_for_manual_shadow_replay_coverage_review"
SOURCE_ALLOWED_NEXT_STEP = "perform_manual_shadow_replay_case_review"

REVIEW_RESULTS_READY_STATUS = "visual_replay_shadow_review_results_ready"
REVIEW_RESULTS_BLOCKED_STATUS = "visual_replay_shadow_review_results_blocked"
READY_DECISION = "ready_for_reviewer_pass_fail_summary"
BLOCKED_DECISION = "blocked_from_reviewer_pass_fail_summary"

PASS = "pass"
FAIL = "fail"
UNDECIDED = "undecided"
ALLOWED_REVIEW_OUTCOMES = (PASS, FAIL, UNDECIDED)

DEFAULT_REQUIRED_SYMBOLS = ("LT.NS",)
DEFAULT_MIN_REVIEWED_CASES = 2

REQUIRED_REVIEW_LANES = (
    "marker_alignment_recheck",
    "pre_event_context_recheck",
    "post_event_follow_through_recheck",
    "counterfactual_quality_check",
    "vsa_smc_quality_judgment",
    "evidence_artifact_traceability",
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
    "review_result_capture_only": True,
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
    "requires_shadow_coverage_plan": True,
    "requires_manual_reviewer_input": True,
    "requires_reviewer_pass_fail_summary": True,
    "requires_separate_production_pr": True,
}


def capture_effort_result_visual_replay_shadow_review_results(
    shadow_coverage_plan: Mapping[str, Any],
    manual_review_results: Sequence[Mapping[str, Any]],
    *,
    required_symbols: Sequence[str] = DEFAULT_REQUIRED_SYMBOLS,
    min_reviewed_cases: int = DEFAULT_MIN_REVIEWED_CASES,
) -> dict[str, object]:
    """Capture manual pass/fail/undecided outcomes for shadow replay cases.

    A ready report means every selected coverage case has a real manual outcome
    and all required review lanes are decided. It does not authorize live scanner
    integration, production UI activation, scoring, ranking, actionability,
    detector activation, persistence, alerts, or orders.
    """

    if min_reviewed_cases <= 0:
        raise ValueError("min_reviewed_cases must be positive")

    symbols = _normalize_symbols(required_symbols)
    source_cases = _mapping_rows(shadow_coverage_plan.get("coverage_cases", []))
    selected_source_cases = [
        case
        for case in source_cases
        if not symbols or _display(case.get("symbol")).strip() in symbols
    ]

    reviews_by_case_id = _review_results_by_case_id(manual_review_results)
    reviewed_cases = [
        _build_review_case(case, reviews_by_case_id.get(_display(case.get("case_id")).strip()))
        for case in selected_source_cases
    ]

    passed_count = sum(1 for case in reviewed_cases if case.get("review_outcome") == PASS)
    failed_count = sum(1 for case in reviewed_cases if case.get("review_outcome") == FAIL)
    undecided_count = sum(1 for case in reviewed_cases if case.get("review_outcome") == UNDECIDED)
    completed_count = passed_count + failed_count

    blockers = _review_results_blockers(
        shadow_coverage_plan,
        selected_source_cases=selected_source_cases,
        reviewed_cases=reviewed_cases,
        required_symbols=symbols,
        min_reviewed_cases=min_reviewed_cases,
    )
    ready = not blockers

    return {
        "report_type": REPORT_TYPE,
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "source_report_type": shadow_coverage_plan.get("report_type"),
        "source_coverage_status": shadow_coverage_plan.get("coverage_status"),
        "source_coverage_decision": shadow_coverage_plan.get("coverage_decision"),
        "source_shadow_coverage_ready": shadow_coverage_plan.get("shadow_coverage_ready"),
        "source_allowed_next_step": shadow_coverage_plan.get("allowed_next_step"),
        "required_symbols": symbols,
        "minimum_reviewed_cases": int(min_reviewed_cases),
        "source_case_count": len(source_cases),
        "selected_case_count": len(selected_source_cases),
        "manual_review_input_count": len(_mapping_rows(manual_review_results)),
        "completed_review_count": completed_count,
        "passed_case_count": passed_count,
        "failed_case_count": failed_count,
        "undecided_case_count": undecided_count,
        "review_results_status": REVIEW_RESULTS_READY_STATUS if ready else REVIEW_RESULTS_BLOCKED_STATUS,
        "review_results_decision": READY_DECISION if ready else BLOCKED_DECISION,
        "review_results_ready": ready,
        "blockers": blockers,
        "required_review_lanes": list(REQUIRED_REVIEW_LANES),
        "review_cases": reviewed_cases,
        "disallowed_production_surfaces": list(DISALLOWED_PRODUCTION_SURFACES),
        "allowed_next_step": (
            "run_visual_replay_reviewer_pass_fail_summary"
            if ready
            else "complete_manual_shadow_replay_reviews"
        ),
        "manual_revalidation_required": True,
        "production_pr_required_after_shadow_validation": True,
        "automatic_promotion_allowed": False,
        **PRODUCTION_BOUNDARY,
    }


def render_effort_result_visual_replay_shadow_review_results_markdown(
    report: Mapping[str, Any],
) -> str:
    """Render the manual shadow replay review result report as Markdown."""

    lines = [
        "# Effort/Result Visual Replay Shadow Review Results",
        "",
        "## Decision",
        "",
        f"- Review decision: `{_display(report.get('review_results_decision'))}`",
        f"- Review results ready: {_bool_text(report.get('review_results_ready'))}",
        f"- Review status: `{_display(report.get('review_results_status'))}`",
        f"- Allowed next step: `{_display(report.get('allowed_next_step'))}`",
        f"- Required symbols: {_csv(report.get('required_symbols', []))}",
        f"- Selected cases: {int(report.get('selected_case_count', 0))}",
        f"- Completed reviews: {int(report.get('completed_review_count', 0))}",
        f"- Passed cases: {int(report.get('passed_case_count', 0))}",
        f"- Failed cases: {int(report.get('failed_case_count', 0))}",
        f"- Undecided cases: {int(report.get('undecided_case_count', 0))}",
        "",
        "## Source Shadow Coverage Plan",
        "",
        f"- Source report type: `{_display(report.get('source_report_type'))}`",
        f"- Source coverage status: `{_display(report.get('source_coverage_status'))}`",
        f"- Source coverage decision: `{_display(report.get('source_coverage_decision'))}`",
        f"- Source shadow coverage ready: {_bool_text(report.get('source_shadow_coverage_ready'))}",
        f"- Source allowed next step: `{_display(report.get('source_allowed_next_step'))}`",
        "",
        "## Production Boundary",
        "",
        "- Audit/review-result-capture only: true",
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
        "## Review Cases",
        "",
    ]

    cases = _mapping_rows(report.get("review_cases", []))
    if not cases:
        lines.append("_No shadow replay review cases were selected._")
        lines.append("")
    else:
        lines.extend(
            [
                "| Case | Target | Symbol | Week | Outcome | Reviewer | Evidence | Blockers |",
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
                f"`{_display(row.get('review_outcome'))}` | "
                f"{_display(row.get('reviewer'))} | "
                f"{_display(row.get('evidence_artifact'))} | "
                f"{_csv(row.get('blockers', []))} |"
            )
        lines.append("")

    lines.extend(["## Required Manual Review Lanes", ""])
    for lane in _string_rows(report.get("required_review_lanes", [])):
        lines.append(f"- [ ] {lane}")

    blockers = _string_rows(report.get("blockers", []))
    lines.extend(["", "## Blockers", ""])
    if blockers:
        lines.extend(f"- {blocker}" for blocker in blockers)
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Review Rules",
            "",
            "- Record pass, fail, or undecided for every required review lane.",
            "- Keep undecided until a human has inspected marker alignment, pre-event context, follow-through, counterfactual quality, VSA/SMC quality, and evidence traceability.",
            "- Failed cases may proceed to reviewer-summary reporting, but must block integration gates downstream.",
            "- This report does not approve production behavior changes.",
            "- A separate production PR is required before any scoring, ranking, actionability, detector, API, frontend, persistence, alert, or order behavior can change.",
            "",
        ]
    )
    return "\n".join(lines)


def _build_review_case(
    source_case: Mapping[str, Any],
    manual_review: Mapping[str, Any] | None,
) -> dict[str, object]:
    review = manual_review or {}
    blockers: list[str] = []

    case_id = _display(source_case.get("case_id")).strip()
    source_required_lanes = _string_rows(source_case.get("review_lanes", [])) or list(REQUIRED_REVIEW_LANES)
    lane_results = _normalize_lane_results(review.get("lane_results", {}))
    review_outcome = _normalize_outcome(review.get("review_outcome", UNDECIDED))
    reviewer = _display(review.get("reviewer")).strip()
    reviewed_at = _display(review.get("reviewed_at")).strip()
    reviewer_notes = _display(review.get("reviewer_notes")).strip()
    evidence_artifact = _display(review.get("evidence_artifact")).strip()

    if source_case.get("coverage_case_ready") is not True:
        blockers.append("source_coverage_case_not_ready")
    if not manual_review:
        blockers.append("missing_manual_review_result")
    if review_outcome not in ALLOWED_REVIEW_OUTCOMES:
        blockers.append("invalid_review_outcome")
        review_outcome = UNDECIDED
    if review_outcome == UNDECIDED:
        blockers.append("manual_review_outcome_undecided")
    if not reviewer:
        blockers.append("missing_reviewer")
    if not reviewed_at:
        blockers.append("missing_reviewed_at")
    if not reviewer_notes:
        blockers.append("missing_reviewer_notes")
    if not evidence_artifact:
        blockers.append("missing_evidence_artifact")

    missing_lanes = [lane for lane in source_required_lanes if lane not in lane_results]
    undecided_lanes = [lane for lane in source_required_lanes if lane_results.get(lane) == UNDECIDED]
    invalid_lanes = [
        lane
        for lane, outcome in lane_results.items()
        if outcome not in ALLOWED_REVIEW_OUTCOMES
    ]

    if missing_lanes:
        blockers.append("missing_required_lane_results")
    if undecided_lanes:
        blockers.append("undecided_required_lane_results")
    if invalid_lanes:
        blockers.append("invalid_required_lane_results")
    if review_outcome == PASS and any(lane_results.get(lane) == FAIL for lane in source_required_lanes):
        blockers.append("pass_outcome_conflicts_with_failed_lane")
    if review_outcome == FAIL and not any(lane_results.get(lane) == FAIL for lane in source_required_lanes):
        blockers.append("fail_outcome_requires_failed_lane")
    if _has_truthy_unsafe_fields(review) or _has_truthy_unsafe_fields(source_case):
        blockers.append("review_production_boundary_open")

    return {
        "case_id": case_id,
        "symbol": source_case.get("symbol", ""),
        "event_week_beginning": source_case.get("event_week_beginning", ""),
        "target": source_case.get("target", ""),
        "expected_marker_labels": _string_rows(source_case.get("expected_marker_labels", [])),
        "review_lanes": source_required_lanes,
        "lane_results": lane_results,
        "missing_lane_results": missing_lanes,
        "undecided_lane_results": undecided_lanes,
        "invalid_lane_results": invalid_lanes,
        "review_outcome": review_outcome,
        "reviewer": reviewer,
        "reviewed_at": reviewed_at,
        "reviewer_notes_recorded": bool(reviewer_notes),
        "evidence_artifact": evidence_artifact,
        "review_case_ready": not blockers,
        "blockers": _dedupe(blockers),
        "manual_review_only": True,
        "automatic_promotion_allowed": False,
        **PRODUCTION_BOUNDARY,
    }


def _review_results_blockers(
    shadow_coverage_plan: Mapping[str, Any],
    *,
    selected_source_cases: Sequence[Mapping[str, Any]],
    reviewed_cases: Sequence[Mapping[str, Any]],
    required_symbols: Sequence[str],
    min_reviewed_cases: int,
) -> list[str]:
    blockers: list[str] = []

    if shadow_coverage_plan.get("report_type") != SOURCE_REPORT_TYPE:
        blockers.append("source_report_type_mismatch")
    if shadow_coverage_plan.get("coverage_status") != SOURCE_READY_STATUS:
        blockers.append("source_coverage_status_not_ready")
    if shadow_coverage_plan.get("coverage_decision") != SOURCE_READY_DECISION:
        blockers.append("source_coverage_decision_not_ready")
    if shadow_coverage_plan.get("shadow_coverage_ready") is not True:
        blockers.append("source_shadow_coverage_ready_false")
    if shadow_coverage_plan.get("allowed_next_step") != SOURCE_ALLOWED_NEXT_STEP:
        blockers.append("source_allowed_next_step_not_manual_review")
    if _string_rows(shadow_coverage_plan.get("blockers", [])):
        blockers.append("source_coverage_blockers_present")
    if _has_truthy_unsafe_fields(shadow_coverage_plan):
        blockers.append("source_production_boundary_open")
    if not required_symbols:
        blockers.append("missing_required_symbols")
    if not selected_source_cases:
        blockers.append("missing_selected_coverage_cases")

    ready_review_count = sum(1 for case in reviewed_cases if case.get("review_case_ready") is True)
    undecided_count = sum(1 for case in reviewed_cases if case.get("review_outcome") == UNDECIDED)
    if ready_review_count < min_reviewed_cases:
        blockers.append("not_enough_completed_manual_reviews")
    if any(case.get("review_case_ready") is not True for case in reviewed_cases):
        blockers.append("manual_review_case_blockers_present")
    if undecided_count:
        blockers.append("undecided_review_results_present")

    return _dedupe(blockers)


def _review_results_by_case_id(
    review_results: Sequence[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for review in _mapping_rows(review_results):
        case_id = _display(review.get("case_id")).strip()
        if case_id:
            result[case_id] = review
    return result


def _normalize_lane_results(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    return {
        _display(lane).strip(): _normalize_outcome(outcome)
        for lane, outcome in value.items()
        if _display(lane).strip()
    }


def _normalize_outcome(value: Any) -> str:
    normalized = _display(value).strip().lower()
    return normalized if normalized in ALLOWED_REVIEW_OUTCOMES else normalized


def _normalize_symbols(symbols: Sequence[str]) -> list[str]:
    return sorted({_display(symbol).strip() for symbol in symbols if _display(symbol).strip()})


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
    parser.add_argument("shadow_coverage_plan", type=Path)
    parser.add_argument("manual_review_results", type=Path)
    parser.add_argument("--symbol", action="append", dest="symbols")
    parser.add_argument("--min-reviewed-cases", type=int, default=DEFAULT_MIN_REVIEWED_CASES)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    coverage_plan = json.loads(args.shadow_coverage_plan.read_text(encoding="utf-8"))
    reviews = json.loads(args.manual_review_results.read_text(encoding="utf-8"))
    report = capture_effort_result_visual_replay_shadow_review_results(
        coverage_plan,
        _mapping_rows(reviews),
        required_symbols=args.symbols or DEFAULT_REQUIRED_SYMBOLS,
        min_reviewed_cases=args.min_reviewed_cases,
    )
    rendered = (
        render_effort_result_visual_replay_shadow_review_results_markdown(report)
        if args.format == "markdown"
        else json.dumps(report, indent=2, sort_keys=True)
    )
    _write_output(rendered, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
