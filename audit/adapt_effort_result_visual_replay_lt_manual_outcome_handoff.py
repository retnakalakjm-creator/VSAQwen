"""Adapt LT visual replay manual evidence completion into review-result input.

This module is audit/manual-outcome-handoff only. It consumes the LT manual
evidence completion gate and emits a normalized manual review-results payload for
the existing shadow review-result capture step. It does not read live data, call
APIs, persist scanner state, activate detectors, change scoring/ranking/
actionability, alerts, orders, frontend, or account behavior.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

REPORT_TYPE = "effort_result_visual_replay_lt_manual_outcome_handoff"
REPORT_SCHEMA_VERSION = 1

SOURCE_REPORT_TYPE = "effort_result_visual_replay_lt_manual_evidence_completion_gate"
SOURCE_READY_STATUS = "lt_visual_replay_manual_evidence_completion_ready"
SOURCE_READY_DECISION = "ready_to_capture_manual_lt_visual_replay_results"
SOURCE_ALLOWED_NEXT_STEP = "run_manual_lt_visual_replay_review_result_capture"

HANDOFF_READY_STATUS = "lt_visual_replay_manual_outcome_handoff_ready"
HANDOFF_BLOCKED_STATUS = "lt_visual_replay_manual_outcome_handoff_blocked"
READY_DECISION = "ready_to_run_shadow_review_result_capture"
BLOCKED_DECISION = "blocked_from_shadow_review_result_capture"

PASS = "pass"
FAIL = "fail"
UNDECIDED = "undecided"
COMPLETED_OUTCOMES = (PASS, FAIL)
ALLOWED_OUTCOMES = (PASS, FAIL, UNDECIDED)

DEFAULT_REQUIRED_SYMBOLS = ("LT.NS",)
DEFAULT_MIN_HANDOFF_CASES = 2

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
    "manual_outcome_handoff_only": True,
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
    "requires_manual_evidence_completion_gate": True,
    "requires_review_result_capture": True,
    "requires_shadow_gates": True,
    "requires_separate_production_pr": True,
}


def adapt_effort_result_visual_replay_lt_manual_outcome_handoff(
    manual_evidence_completion_gate: Mapping[str, Any],
    *,
    required_symbols: Sequence[str] = DEFAULT_REQUIRED_SYMBOLS,
    min_handoff_cases: int = DEFAULT_MIN_HANDOFF_CASES,
) -> dict[str, object]:
    """Build the normalized handoff payload for shadow review-result capture.

    Handoff readiness means every selected LT case is completed as pass or fail
    with evidence, reviewer, timestamp, lane results, and notes traceability. A
    failed completed case may be handed to review-result capture so downstream
    reports can preserve the failure, but it does not authorize integration or
    production behavior changes.
    """

    if min_handoff_cases <= 0:
        raise ValueError("min_handoff_cases must be positive")

    symbols = _normalize_symbols(required_symbols)
    source_cases = _mapping_rows(manual_evidence_completion_gate.get("completion_cases", []))
    selected_cases = [
        case
        for case in source_cases
        if not symbols or _display(case.get("symbol")).strip() in symbols
    ]

    handoff_cases = [_handoff_case(case) for case in selected_cases]
    payload_cases = [_payload_case(case) for case in handoff_cases]

    handoff_case_count = sum(1 for case in handoff_cases if case.get("handoff_case_ready") is True)
    passed_count = sum(1 for case in handoff_cases if case.get("review_outcome") == PASS)
    failed_count = sum(1 for case in handoff_cases if case.get("review_outcome") == FAIL)
    undecided_count = sum(1 for case in handoff_cases if case.get("review_outcome") == UNDECIDED)
    evidence_count = sum(1 for case in handoff_cases if bool(_display(case.get("evidence_artifact")).strip()))

    blockers = _handoff_blockers(
        manual_evidence_completion_gate,
        selected_cases=selected_cases,
        handoff_cases=handoff_cases,
        required_symbols=symbols,
        min_handoff_cases=min_handoff_cases,
    )
    handoff_ready = not blockers
    shadow_validation_candidate_ready = handoff_ready and failed_count == 0
    downstream_blocked = not shadow_validation_candidate_ready

    return {
        "report_type": REPORT_TYPE,
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "source_report_type": manual_evidence_completion_gate.get("report_type"),
        "source_completion_status": manual_evidence_completion_gate.get("completion_status"),
        "source_completion_decision": manual_evidence_completion_gate.get("completion_decision"),
        "source_completion_ready": manual_evidence_completion_gate.get("completion_ready"),
        "source_manual_review_complete": manual_evidence_completion_gate.get("manual_review_complete"),
        "source_shadow_validation_candidate_ready": manual_evidence_completion_gate.get(
            "shadow_validation_candidate_ready"
        ),
        "source_downstream_integration_blocked": manual_evidence_completion_gate.get(
            "downstream_integration_blocked"
        ),
        "source_allowed_next_step": manual_evidence_completion_gate.get("allowed_next_step"),
        "required_symbols": symbols,
        "minimum_handoff_cases": int(min_handoff_cases),
        "source_case_count": len(source_cases),
        "selected_case_count": len(selected_cases),
        "handoff_case_count": handoff_case_count,
        "manual_review_payload_count": len(payload_cases),
        "passed_case_count": passed_count,
        "failed_case_count": failed_count,
        "undecided_case_count": undecided_count,
        "evidence_artifact_count": evidence_count,
        "handoff_status": HANDOFF_READY_STATUS if handoff_ready else HANDOFF_BLOCKED_STATUS,
        "handoff_decision": READY_DECISION if handoff_ready else BLOCKED_DECISION,
        "handoff_ready": handoff_ready,
        "shadow_validation_candidate_ready": shadow_validation_candidate_ready,
        "downstream_integration_blocked": downstream_blocked,
        "failed_cases_require_resolution": failed_count > 0,
        "blockers": blockers,
        "handoff_cases": handoff_cases,
        "manual_review_results_payload": payload_cases,
        "required_review_lanes": list(REQUIRED_REVIEW_LANES),
        "disallowed_production_surfaces": list(DISALLOWED_PRODUCTION_SURFACES),
        "allowed_next_step": (
            "run_visual_replay_reviewer_pass_fail_summary"
            if handoff_ready
            else "complete_manual_lt_visual_replay_evidence_packet"
        ),
        "manual_revalidation_required": True,
        "production_pr_required_after_shadow_validation": True,
        "automatic_promotion_allowed": False,
        **PRODUCTION_BOUNDARY,
    }


def render_effort_result_visual_replay_lt_manual_outcome_handoff_markdown(
    report: Mapping[str, Any],
) -> str:
    """Render the manual outcome handoff report as Markdown."""

    lines = [
        "# LT Visual Replay Manual Outcome Handoff",
        "",
        "## Decision",
        "",
        f"- Handoff decision: `{_display(report.get('handoff_decision'))}`",
        f"- Handoff ready: {_bool_text(report.get('handoff_ready'))}",
        f"- Handoff status: `{_display(report.get('handoff_status'))}`",
        f"- Shadow validation candidate ready: {_bool_text(report.get('shadow_validation_candidate_ready'))}",
        f"- Downstream integration blocked: {_bool_text(report.get('downstream_integration_blocked'))}",
        f"- Allowed next step: `{_display(report.get('allowed_next_step'))}`",
        f"- Handoff cases: {int(report.get('handoff_case_count', 0))}",
        f"- Payload cases: {int(report.get('manual_review_payload_count', 0))}",
        f"- Passed cases: {int(report.get('passed_case_count', 0))}",
        f"- Failed cases: {int(report.get('failed_case_count', 0))}",
        f"- Undecided cases: {int(report.get('undecided_case_count', 0))}",
        "",
        "## Source Manual Evidence Completion Gate",
        "",
        f"- Source report type: `{_display(report.get('source_report_type'))}`",
        f"- Source completion status: `{_display(report.get('source_completion_status'))}`",
        f"- Source completion decision: `{_display(report.get('source_completion_decision'))}`",
        f"- Source completion ready: {_bool_text(report.get('source_completion_ready'))}",
        f"- Source allowed next step: `{_display(report.get('source_allowed_next_step'))}`",
        "",
        "## Handoff Cases",
        "",
    ]

    cases = _mapping_rows(report.get("handoff_cases", []))
    if not cases:
        lines.extend(["_No LT manual outcome cases were selected._", ""])
    else:
        lines.extend(
            [
                "| Case | Target | Week | Outcome | Ready | Evidence | Blockers |",
                "| --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for row in cases:
            lines.append(
                "| "
                f"`{_display(row.get('case_id'))}` | "
                f"`{_display(row.get('target'))}` | "
                f"{_display(row.get('event_week_beginning'))} | "
                f"`{_display(row.get('review_outcome'))}` | "
                f"{_bool_text(row.get('handoff_case_ready'))} | "
                f"{_display(row.get('evidence_artifact'))} | "
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
            "## Production Boundary",
            "",
            "- Audit/manual-outcome-handoff only: true",
            "- Manual review only: true",
            "- Offline replay only: true",
            "- Production change allowed: false",
            "- Automatic promotion allowed: false",
            "- May change scoring/ranking/actionability/detectors: false",
            "- May change scanner/API/frontend/persistence/broker/account behavior: false",
            "- Requires review-result capture and downstream shadow gates before any promotion decision.",
            "- Requires a separate production PR before any production behavior change.",
            "",
        ]
    )
    return "\n".join(lines)


def _handoff_case(completion_case: Mapping[str, Any]) -> dict[str, object]:
    blockers: list[str] = []

    review_outcome = _normalize_outcome(completion_case.get("review_outcome", UNDECIDED))
    lane_results = _normalize_lane_results(completion_case.get("lane_results", {}))
    required_lanes = _string_rows(completion_case.get("review_lanes", [])) or list(REQUIRED_REVIEW_LANES)
    missing_lanes = [lane for lane in required_lanes if lane not in lane_results]
    undecided_lanes = [lane for lane in required_lanes if lane_results.get(lane) == UNDECIDED]
    invalid_lanes = [
        lane
        for lane, outcome in lane_results.items()
        if outcome not in ALLOWED_OUTCOMES
    ]

    reviewer = _display(completion_case.get("reviewer")).strip()
    reviewed_at = _display(completion_case.get("reviewed_at")).strip()
    evidence_artifact = _display(completion_case.get("evidence_artifact")).strip()
    reviewer_notes = _reviewer_notes_value(completion_case, evidence_artifact)

    if completion_case.get("completion_case_ready") is not True:
        blockers.append("source_completion_case_not_ready")
    if completion_case.get("manual_review_complete") is not True:
        blockers.append("source_manual_review_not_complete")
    if review_outcome not in COMPLETED_OUTCOMES:
        blockers.append("review_outcome_not_completed")
    if not reviewer:
        blockers.append("missing_reviewer")
    if not reviewed_at:
        blockers.append("missing_reviewed_at")
    if not evidence_artifact:
        blockers.append("missing_evidence_artifact")
    if not reviewer_notes:
        blockers.append("missing_reviewer_notes")
    if missing_lanes:
        blockers.append("missing_required_lane_results")
    if undecided_lanes:
        blockers.append("undecided_required_lane_results")
    if invalid_lanes:
        blockers.append("invalid_required_lane_results")
    if completion_case.get("blockers"):
        blockers.append("source_completion_case_blockers_present")
    if completion_case.get("downstream_integration_blocked") is True and review_outcome != FAIL:
        blockers.append("source_downstream_integration_blocked")
    if review_outcome == PASS and any(lane_results.get(lane) == FAIL for lane in required_lanes):
        blockers.append("pass_outcome_conflicts_with_failed_lane")
    if review_outcome == FAIL and not any(lane_results.get(lane) == FAIL for lane in required_lanes):
        blockers.append("fail_outcome_requires_failed_lane")
    if _has_truthy_unsafe_fields(completion_case):
        blockers.append("case_production_boundary_open")

    return {
        "case_id": _display(completion_case.get("case_id")).strip(),
        "symbol": completion_case.get("symbol", ""),
        "event_week_beginning": completion_case.get("event_week_beginning", ""),
        "target": completion_case.get("target", ""),
        "expected_marker_labels": _string_rows(completion_case.get("expected_marker_labels", [])),
        "review_lanes": required_lanes,
        "lane_results": lane_results,
        "missing_lane_results": missing_lanes,
        "undecided_lane_results": undecided_lanes,
        "invalid_lane_results": invalid_lanes,
        "review_outcome": review_outcome,
        "reviewer": reviewer,
        "reviewed_at": reviewed_at,
        "reviewer_notes": reviewer_notes,
        "reviewer_notes_recorded": bool(reviewer_notes),
        "evidence_artifact": evidence_artifact,
        "source_completion_case_ready": completion_case.get("completion_case_ready") is True,
        "source_manual_review_complete": completion_case.get("manual_review_complete") is True,
        "source_downstream_integration_blocked": completion_case.get("downstream_integration_blocked") is True,
        "handoff_case_ready": not blockers,
        "blockers": _dedupe(blockers),
        "downstream_integration_blocked": review_outcome == FAIL,
        "manual_review_only": True,
        "automatic_promotion_allowed": False,
        **PRODUCTION_BOUNDARY,
    }


def _payload_case(handoff_case: Mapping[str, Any]) -> dict[str, object]:
    return {
        "case_id": handoff_case.get("case_id", ""),
        "review_outcome": handoff_case.get("review_outcome", UNDECIDED),
        "lane_results": dict(_mapping_or_empty(handoff_case.get("lane_results", {}))),
        "reviewer": handoff_case.get("reviewer", ""),
        "reviewed_at": handoff_case.get("reviewed_at", ""),
        "reviewer_notes": handoff_case.get("reviewer_notes", ""),
        "evidence_artifact": handoff_case.get("evidence_artifact", ""),
        "automatic_promotion_allowed": False,
        "production_change_allowed": False,
        "manual_review_only": True,
        "offline_replay_only": True,
    }


def _reviewer_notes_value(completion_case: Mapping[str, Any], evidence_artifact: str) -> str:
    explicit_notes = _display(completion_case.get("reviewer_notes")).strip()
    if explicit_notes:
        return explicit_notes

    if completion_case.get("reviewer_notes_recorded") is True and evidence_artifact:
        return f"Reviewer notes recorded in evidence artifact: {evidence_artifact}"

    return ""


def _handoff_blockers(
    completion_gate: Mapping[str, Any],
    *,
    selected_cases: Sequence[Mapping[str, Any]],
    handoff_cases: Sequence[Mapping[str, Any]],
    required_symbols: Sequence[str],
    min_handoff_cases: int,
) -> list[str]:
    blockers: list[str] = []

    if completion_gate.get("report_type") != SOURCE_REPORT_TYPE:
        blockers.append("source_report_type_mismatch")
    if completion_gate.get("completion_status") != SOURCE_READY_STATUS:
        blockers.append("source_completion_status_not_ready")
    if completion_gate.get("completion_decision") != SOURCE_READY_DECISION:
        blockers.append("source_completion_decision_not_ready")
    if completion_gate.get("completion_ready") is not True:
        blockers.append("source_completion_ready_false")
    if completion_gate.get("manual_review_complete") is not True:
        blockers.append("source_manual_review_complete_false")
    if completion_gate.get("allowed_next_step") != SOURCE_ALLOWED_NEXT_STEP:
        blockers.append("source_allowed_next_step_not_result_capture")
    if completion_gate.get("blockers"):
        blockers.append("source_completion_gate_blockers_present")
    if _has_truthy_unsafe_fields(completion_gate):
        blockers.append("source_production_boundary_open")

    selected_symbols = {_display(case.get("symbol")).strip() for case in selected_cases}
    missing_symbols = [symbol for symbol in required_symbols if symbol not in selected_symbols]
    if missing_symbols:
        blockers.append("missing_required_symbols")
    if not selected_cases:
        blockers.append("no_manual_outcome_cases_selected")

    ready_count = sum(1 for case in handoff_cases if case.get("handoff_case_ready") is True)
    if ready_count < min_handoff_cases:
        blockers.append("not_enough_handoff_cases")
    if any(case.get("blockers") for case in handoff_cases):
        blockers.append("handoff_case_blockers_present")
    if any(case.get("review_outcome") == UNDECIDED for case in handoff_cases):
        blockers.append("undecided_handoff_cases_present")

    return _dedupe(blockers)


def _normalize_outcome(value: object) -> str:
    outcome = _display(value).strip().lower()
    if outcome in ALLOWED_OUTCOMES:
        return outcome
    return UNDECIDED


def _normalize_lane_results(value: object) -> dict[str, str]:
    results = _mapping_or_empty(value)
    return {str(key): _normalize_outcome(outcome) for key, outcome in results.items()}


def _has_truthy_unsafe_fields(value: object) -> bool:
    if isinstance(value, Mapping):
        for field in UNSAFE_TRUTHY_FIELDS:
            if value.get(field) is True:
                return True
        return any(_has_truthy_unsafe_fields(child) for child in value.values())
    if isinstance(value, list | tuple):
        return any(_has_truthy_unsafe_fields(child) for child in value)
    return False


def _normalize_symbols(symbols: Sequence[str]) -> list[str]:
    return _dedupe(_display(symbol).strip() for symbol in symbols if _display(symbol).strip())


def _mapping_rows(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _string_rows(value: object) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [_display(item).strip() for item in value if _display(item).strip()]


def _mapping_or_empty(value: object) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


def _dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value)
        if text and text not in seen:
            result.append(text)
            seen.add(text)
    return result


def _display(value: object) -> str:
    if value is None:
        return ""
    return str(value)


def _csv(value: object) -> str:
    rows = _string_rows(value)
    return ", ".join(rows) if rows else "none"


def _bool_text(value: object) -> str:
    return "true" if value is True else "false"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_output(report: Mapping[str, Any], *, output: Path | None, fmt: str) -> None:
    if fmt == "json":
        text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    else:
        text = render_effort_result_visual_replay_lt_manual_outcome_handoff_markdown(report)

    if output is None:
        print(text, end="" if text.endswith("\n") else "\n")
    else:
        output.write_text(text, encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Adapt LT manual evidence completion into review-result capture payload."
    )
    parser.add_argument("completion_gate", type=Path)
    parser.add_argument("--symbol", action="append", dest="symbols")
    parser.add_argument("--min-handoff-cases", type=int, default=DEFAULT_MIN_HANDOFF_CASES)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    report = adapt_effort_result_visual_replay_lt_manual_outcome_handoff(
        _load_json(args.completion_gate),
        required_symbols=args.symbols or DEFAULT_REQUIRED_SYMBOLS,
        min_handoff_cases=args.min_handoff_cases,
    )
    _write_output(report, output=args.output, fmt=args.format)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
