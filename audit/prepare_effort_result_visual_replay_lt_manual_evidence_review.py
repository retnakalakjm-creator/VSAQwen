"""Prepare LT manual evidence review packet for Effort/Result visual replay shadow cases.

This module is audit/manual-review-packet only. It consumes the offline LT shadow
coverage plan plus optional manual review inputs and produces a reviewer-facing
evidence packet. It does not contact external services, persist scanner state,
activate detectors, change scoring/ranking/actionability, send alerts, or alter
broker/order/account/API/frontend behavior.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

REPORT_TYPE = "effort_result_visual_replay_lt_manual_evidence_review_packet"
REPORT_SCHEMA_VERSION = 1

SOURCE_REPORT_TYPE = "effort_result_visual_replay_shadow_coverage_plan"
SOURCE_READY_STATUS = "visual_replay_shadow_coverage_plan_ready"
SOURCE_READY_DECISION = "ready_for_manual_shadow_replay_coverage_review"
SOURCE_ALLOWED_NEXT_STEP = "perform_manual_shadow_replay_case_review"

PACKET_READY_STATUS = "lt_visual_replay_manual_evidence_packet_ready"
PACKET_BLOCKED_STATUS = "lt_visual_replay_manual_evidence_packet_blocked"
READY_DECISION = "ready_for_manual_lt_visual_replay_evidence_capture"
BLOCKED_DECISION = "blocked_from_manual_lt_visual_replay_evidence_capture"

PASS = "pass"
FAIL = "fail"
UNDECIDED = "undecided"
ALLOWED_REVIEW_OUTCOMES = (PASS, FAIL, UNDECIDED)

DEFAULT_REQUIRED_SYMBOLS = ("LT.NS",)
DEFAULT_MIN_CASES = 2

REQUIRED_REVIEW_LANES = (
    "marker_alignment_recheck",
    "pre_event_context_recheck",
    "post_event_follow_through_recheck",
    "counterfactual_quality_check",
    "vsa_smc_quality_judgment",
    "evidence_artifact_traceability",
)

MANUAL_REVIEW_STEPS = (
    "open_dev_only_visual_replay_route",
    "load_offline_lt_shadow_case_fixture",
    "inspect_marker_alignment_against_expected_labels",
    "inspect_pre_event_vsa_smc_context",
    "inspect_post_event_follow_through_or_counterfactual_context",
    "attach_visual_evidence_artifact",
    "record_reviewer_identity_and_timestamp",
    "mark_each_required_lane_pass_or_fail",
    "mark_case_outcome_pass_or_fail_or_leave_undecided",
    "rerun_shadow_review_result_capture_and_downstream_gates",
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

PRODUCTION_BOUNDARY = {
    "audit_only": True,
    "manual_evidence_packet_only": True,
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
    "requires_visual_evidence_artifact": True,
    "requires_review_result_capture": True,
    "requires_separate_production_pr": True,
}


def prepare_effort_result_visual_replay_lt_manual_evidence_review(
    shadow_coverage_plan: Mapping[str, Any],
    manual_review_results: Sequence[Mapping[str, Any]] | None = None,
    *,
    required_symbols: Sequence[str] = DEFAULT_REQUIRED_SYMBOLS,
    min_cases: int = DEFAULT_MIN_CASES,
) -> dict[str, object]:
    """Build a manual LT visual replay evidence packet without deciding outcomes."""

    if min_cases <= 0:
        raise ValueError("min_cases must be positive")

    symbols = _normalize_symbols(required_symbols)
    manual_rows = _mapping_rows(manual_review_results or [])
    reviews_by_case = _reviews_by_case_id(manual_rows)

    source_cases = _mapping_rows(shadow_coverage_plan.get("coverage_cases", []))
    selected_cases = [
        case
        for case in source_cases
        if not symbols or _display(case.get("symbol")).strip() in symbols
    ]

    case_packets = [
        _build_case_packet(case, reviews_by_case.get(_display(case.get("case_id")).strip()))
        for case in selected_cases
    ]

    complete_case_count = sum(1 for case in case_packets if case.get("manual_review_complete") is True)
    ready_case_count = sum(1 for case in case_packets if case.get("evidence_packet_case_ready") is True)
    passed_case_count = sum(1 for case in case_packets if case.get("review_outcome") == PASS)
    failed_case_count = sum(1 for case in case_packets if case.get("review_outcome") == FAIL)
    undecided_case_count = sum(1 for case in case_packets if case.get("review_outcome") == UNDECIDED)
    evidence_artifact_count = sum(1 for case in case_packets if _display(case.get("evidence_artifact")).strip())

    blockers = _packet_blockers(
        shadow_coverage_plan,
        selected_cases=selected_cases,
        case_packets=case_packets,
        required_symbols=symbols,
        min_cases=min_cases,
    )
    packet_ready = not blockers
    manual_review_complete = (
        packet_ready
        and complete_case_count >= min_cases
        and undecided_case_count == 0
        and all(case.get("manual_review_complete") is True for case in case_packets)
    )

    return {
        "report_type": REPORT_TYPE,
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "source_report_type": shadow_coverage_plan.get("report_type"),
        "source_coverage_status": shadow_coverage_plan.get("coverage_status"),
        "source_coverage_decision": shadow_coverage_plan.get("coverage_decision"),
        "source_shadow_coverage_ready": shadow_coverage_plan.get("shadow_coverage_ready"),
        "source_allowed_next_step": shadow_coverage_plan.get("allowed_next_step"),
        "required_symbols": symbols,
        "minimum_cases": int(min_cases),
        "source_case_count": len(source_cases),
        "selected_case_count": len(selected_cases),
        "manual_review_input_count": len(manual_rows),
        "ready_case_count": ready_case_count,
        "complete_case_count": complete_case_count,
        "passed_case_count": passed_case_count,
        "failed_case_count": failed_case_count,
        "undecided_case_count": undecided_case_count,
        "evidence_artifact_count": evidence_artifact_count,
        "required_review_lanes": list(REQUIRED_REVIEW_LANES),
        "manual_review_steps": list(MANUAL_REVIEW_STEPS),
        "manual_review_step_count": len(MANUAL_REVIEW_STEPS),
        "evidence_packet_status": PACKET_READY_STATUS if packet_ready else PACKET_BLOCKED_STATUS,
        "evidence_packet_decision": READY_DECISION if packet_ready else BLOCKED_DECISION,
        "evidence_packet_ready": packet_ready,
        "manual_review_complete": manual_review_complete,
        "shadow_validation_candidate_ready": manual_review_complete and failed_case_count == 0,
        "downstream_integration_blocked": not manual_review_complete or failed_case_count > 0,
        "blockers": blockers,
        "case_packets": case_packets,
        "manual_review_results_template": [_manual_review_template(case) for case in selected_cases],
        "disallowed_production_surfaces": list(DISALLOWED_PRODUCTION_SURFACES),
        "allowed_next_step": (
            "run_shadow_review_result_capture"
            if manual_review_complete
            else "perform_manual_lt_visual_replay_review"
        ),
        "production_pr_required_after_shadow_validation": True,
        "automatic_promotion_allowed": False,
        **PRODUCTION_BOUNDARY,
    }


def render_effort_result_visual_replay_lt_manual_evidence_review_markdown(
    report: Mapping[str, Any],
) -> str:
    """Render the manual evidence review packet as Markdown."""

    lines = [
        "# LT Effort/Result Visual Replay Manual Evidence Review Packet",
        "",
        "## Decision",
        "",
        f"- Packet decision: `{_display(report.get('evidence_packet_decision'))}`",
        f"- Packet ready: {_bool_text(report.get('evidence_packet_ready'))}",
        f"- Manual review complete: {_bool_text(report.get('manual_review_complete'))}",
        f"- Allowed next step: `{_display(report.get('allowed_next_step'))}`",
        f"- Required symbols: {_csv(report.get('required_symbols', []))}",
        f"- Selected cases: {int(report.get('selected_case_count', 0))}",
        f"- Complete cases: {int(report.get('complete_case_count', 0))}",
        f"- Passed cases: {int(report.get('passed_case_count', 0))}",
        f"- Failed cases: {int(report.get('failed_case_count', 0))}",
        f"- Undecided cases: {int(report.get('undecided_case_count', 0))}",
        f"- Evidence artifacts: {int(report.get('evidence_artifact_count', 0))}",
        "",
        "## Source Coverage Plan",
        "",
        f"- Source report type: `{_display(report.get('source_report_type'))}`",
        f"- Source coverage status: `{_display(report.get('source_coverage_status'))}`",
        f"- Source coverage decision: `{_display(report.get('source_coverage_decision'))}`",
        f"- Source shadow coverage ready: {_bool_text(report.get('source_shadow_coverage_ready'))}",
        f"- Source allowed next step: `{_display(report.get('source_allowed_next_step'))}`",
        "",
        "## Production Boundary",
        "",
        "- Audit/manual-evidence-packet only: true",
        "- Manual review only: true",
        "- Offline replay only: true",
        "- Production change allowed: false",
        "- Automatic promotion allowed: false",
        "- May change scoring/ranking/actionability: false",
        "- May activate detector: false",
        "- May change scanner/API/frontend/persistence/broker/account behavior: false",
        "- Requires separate production PR: true",
        "",
        "## LT Case Packets",
        "",
    ]

    cases = _mapping_rows(report.get("case_packets", []))
    if not cases:
        lines.append("_No LT cases were selected._")
        lines.append("")
    else:
        lines.extend(
            [
                "| Case | Target | Fixture | Outcome | Complete | Evidence | Blockers |",
                "| --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for case in cases:
            lines.append(
                "| "
                f"`{_display(case.get('case_id'))}` | "
                f"`{_display(case.get('target'))}` | "
                f"`{_display(case.get('offline_dataset_fixture'))}` | "
                f"`{_display(case.get('review_outcome'))}` | "
                f"{_bool_text(case.get('manual_review_complete'))} | "
                f"{_display(case.get('evidence_artifact'))} | "
                f"{_csv(case.get('blockers', []))} |"
            )
        lines.append("")

    lines.extend(["## Manual Review Steps", ""])
    for step in _string_rows(report.get("manual_review_steps", [])):
        lines.append(f"- [ ] {step}")

    lines.extend(["", "## Required Review Lanes", ""])
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
            "- Do not mark pass/fail until a human reviewer inspects the dev-only replay.",
            "- Every required lane must be pass or fail; undecided lanes keep the case blocked.",
            "- Each case requires reviewer, reviewed_at, reviewer_notes, and evidence_artifact.",
            "- A failed case is still a completed manual review, but it blocks downstream integration.",
            "- This packet does not approve production behavior changes.",
            "",
        ]
    )
    return "\n".join(lines)


def _build_case_packet(
    source_case: Mapping[str, Any],
    manual_review: Mapping[str, Any] | None,
) -> dict[str, object]:
    review = manual_review or {}
    blockers: list[str] = []

    case_id = _display(source_case.get("case_id")).strip()
    review_lanes = _string_rows(source_case.get("review_lanes", [])) or list(REQUIRED_REVIEW_LANES)
    lane_results = _normalize_lane_results(review.get("lane_results", {}))
    review_outcome = _normalize_outcome(review.get("review_outcome", UNDECIDED))
    reviewer = _display(review.get("reviewer")).strip()
    reviewed_at = _display(review.get("reviewed_at")).strip()
    reviewer_notes = _display(review.get("reviewer_notes")).strip()
    evidence_artifact = _display(review.get("evidence_artifact")).strip()

    missing_lanes = [lane for lane in review_lanes if lane not in lane_results]
    undecided_lanes = [lane for lane in review_lanes if lane_results.get(lane) == UNDECIDED]
    invalid_lanes = [lane for lane, outcome in lane_results.items() if outcome not in ALLOWED_REVIEW_OUTCOMES]

    if source_case.get("coverage_case_ready") is not True:
        blockers.append("source_coverage_case_not_ready")
    if manual_review is None:
        blockers.append("missing_manual_review_input")
    if review_outcome not in ALLOWED_REVIEW_OUTCOMES:
        blockers.append("invalid_review_outcome")
        review_outcome = UNDECIDED
    if review_outcome == UNDECIDED:
        blockers.append("review_outcome_undecided")
    if not reviewer:
        blockers.append("missing_reviewer")
    if not reviewed_at:
        blockers.append("missing_reviewed_at")
    if not reviewer_notes:
        blockers.append("missing_reviewer_notes")
    if not evidence_artifact:
        blockers.append("missing_evidence_artifact")
    if missing_lanes:
        blockers.append("missing_required_lane_results")
    if undecided_lanes:
        blockers.append("undecided_required_lane_results")
    if invalid_lanes:
        blockers.append("invalid_required_lane_results")
    if review_outcome == PASS and any(lane_results.get(lane) == FAIL for lane in review_lanes):
        blockers.append("pass_outcome_conflicts_with_failed_lane")
    if review_outcome == FAIL and not any(lane_results.get(lane) == FAIL for lane in review_lanes):
        blockers.append("fail_outcome_requires_failed_lane")
    if _has_truthy_unsafe_fields(source_case) or _has_truthy_unsafe_fields(review):
        blockers.append("case_production_boundary_open")

    case_ready = source_case.get("coverage_case_ready") is True
    manual_review_complete = not blockers

    return {
        "case_id": case_id,
        "symbol": source_case.get("symbol", ""),
        "event_week_beginning": source_case.get("event_week_beginning", ""),
        "target": source_case.get("target", ""),
        "offline_dataset_fixture": source_case.get("offline_dataset_fixture", ""),
        "expected_marker_labels": _string_rows(source_case.get("expected_marker_labels", [])),
        "review_lanes": review_lanes,
        "lane_results": lane_results,
        "missing_lane_results": missing_lanes,
        "undecided_lane_results": undecided_lanes,
        "invalid_lane_results": invalid_lanes,
        "review_outcome": review_outcome,
        "reviewer": reviewer,
        "reviewed_at": reviewed_at,
        "reviewer_notes_recorded": bool(reviewer_notes),
        "evidence_artifact": evidence_artifact,
        "evidence_packet_case_ready": case_ready,
        "manual_review_complete": manual_review_complete,
        "downstream_integration_blocked": not manual_review_complete or review_outcome == FAIL,
        "blockers": _dedupe(blockers),
        "automatic_promotion_allowed": False,
        **PRODUCTION_BOUNDARY,
    }


def _manual_review_template(source_case: Mapping[str, Any]) -> dict[str, object]:
    review_lanes = _string_rows(source_case.get("review_lanes", [])) or list(REQUIRED_REVIEW_LANES)
    return {
        "case_id": _display(source_case.get("case_id")).strip(),
        "review_outcome": UNDECIDED,
        "lane_results": {lane: UNDECIDED for lane in review_lanes},
        "reviewer": "",
        "reviewed_at": "",
        "reviewer_notes": "",
        "evidence_artifact": "",
        "automatic_promotion_allowed": False,
        "production_change_allowed": False,
        "manual_review_only": True,
        "offline_replay_only": True,
        "notes": (
            "Fill only after visually reviewing the dev-only offline replay. "
            "Keep undecided until every required lane has evidence."
        ),
    }


def _packet_blockers(
    shadow_coverage_plan: Mapping[str, Any],
    *,
    selected_cases: Sequence[Mapping[str, Any]],
    case_packets: Sequence[Mapping[str, Any]],
    required_symbols: Sequence[str],
    min_cases: int,
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

    found_symbols = {_display(case.get("symbol")).strip() for case in selected_cases}
    missing_symbols = [symbol for symbol in required_symbols if symbol not in found_symbols]
    if missing_symbols:
        blockers.append("missing_required_symbols")
    if len(selected_cases) < min_cases:
        blockers.append("not_enough_selected_cases")
    if any(case.get("coverage_case_ready") is not True for case in selected_cases):
        blockers.append("selected_coverage_case_not_ready")
    if any(_string_rows(case.get("blockers", [])) for case in case_packets):
        blockers.append("manual_review_evidence_incomplete")
    return _dedupe(blockers)


def _reviews_by_case_id(rows: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    reviews: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        case_id = _display(row.get("case_id")).strip()
        if case_id:
            reviews[case_id] = row
    return reviews


def _normalize_lane_results(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    return {_display(key).strip(): _normalize_outcome(result) for key, result in value.items()}


def _normalize_outcome(value: Any) -> str:
    outcome = _display(value).strip().lower()
    if outcome in ALLOWED_REVIEW_OUTCOMES:
        return outcome
    return outcome or UNDECIDED


def _normalize_symbols(symbols: Sequence[str]) -> list[str]:
    return _dedupe(_display(symbol).strip() for symbol in symbols if _display(symbol).strip())


def _has_truthy_unsafe_fields(payload: Mapping[str, Any]) -> bool:
    for key in UNSAFE_TRUTHY_FIELDS:
        if payload.get(key) is True:
            return True
    return False


def _mapping_rows(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _string_rows(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [_display(item).strip() for item in value if _display(item).strip()]


def _display(value: Any) -> str:
    return "" if value is None else str(value)


def _csv(value: Any) -> str:
    rows = _string_rows(value)
    return ", ".join(rows) if rows else "none"


def _bool_text(value: Any) -> str:
    return "true" if value is True else "false"


def _dedupe(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _display(value).strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _load_json(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_output(path: str | None, text: str) -> None:
    if path:
        Path(path).write_text(text, encoding="utf-8")
    else:
        print(text)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Prepare an LT manual evidence review packet for visual replay shadow validation.",
    )
    parser.add_argument("--coverage-plan", required=True)
    parser.add_argument("--manual-review-results", default=None)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--output", default=None)
    args = parser.parse_args(argv)

    coverage_plan = _load_json(args.coverage_plan)
    manual_reviews = _load_json(args.manual_review_results) if args.manual_review_results else []
    report = prepare_effort_result_visual_replay_lt_manual_evidence_review(
        coverage_plan,
        manual_reviews,
    )

    if args.format == "markdown":
        _write_output(
            args.output,
            render_effort_result_visual_replay_lt_manual_evidence_review_markdown(report),
        )
    else:
        _write_output(args.output, json.dumps(report, indent=2, sort_keys=True) + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
