"""Decide whether the LT visual replay manual evidence packet is complete.

This module is audit/completion-gate only. It consumes the offline LT manual
evidence packet produced for the visual replay shadow workflow. It does not read
live data, call APIs, persist scanner state, activate detectors, change scoring,
ranking, actionability, alerts, orders, frontend, or account behavior.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

REPORT_TYPE = "effort_result_visual_replay_lt_manual_evidence_completion_gate"
REPORT_SCHEMA_VERSION = 1

SOURCE_REPORT_TYPE = "effort_result_visual_replay_lt_manual_evidence_review_packet"
SOURCE_READY_STATUS = "lt_visual_replay_manual_evidence_packet_ready"
SOURCE_READY_DECISION = "ready_for_manual_lt_visual_replay_review_result_capture"
SOURCE_ALLOWED_NEXT_STEP = "run_manual_lt_visual_replay_review_result_capture"

COMPLETION_READY_STATUS = "lt_visual_replay_manual_evidence_completion_ready"
COMPLETION_BLOCKED_STATUS = "lt_visual_replay_manual_evidence_completion_blocked"
READY_DECISION = "ready_to_capture_manual_lt_visual_replay_results"
BLOCKED_DECISION = "blocked_from_manual_lt_visual_replay_result_capture"

PASS = "pass"
FAIL = "fail"
UNDECIDED = "undecided"
COMPLETED_OUTCOMES = (PASS, FAIL)
ALLOWED_OUTCOMES = (PASS, FAIL, UNDECIDED)

DEFAULT_REQUIRED_SYMBOLS = ("LT.NS",)
DEFAULT_MIN_COMPLETED_CASES = 2

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
    "manual_evidence_completion_gate_only": True,
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
    "requires_manual_evidence_packet": True,
    "requires_review_result_capture": True,
    "requires_shadow_gates": True,
    "requires_separate_production_pr": True,
}


def decide_effort_result_visual_replay_lt_manual_evidence_completion(
    manual_evidence_packet: Mapping[str, Any],
    *,
    required_symbols: Sequence[str] = DEFAULT_REQUIRED_SYMBOLS,
    min_completed_cases: int = DEFAULT_MIN_COMPLETED_CASES,
) -> dict[str, object]:
    """Gate the handoff from LT manual evidence packet to review-result capture."""

    if min_completed_cases <= 0:
        raise ValueError("min_completed_cases must be positive")

    symbols = _normalize_symbols(required_symbols)
    source_cases = _mapping_rows(manual_evidence_packet.get("case_packets", []))
    selected_cases = [
        case
        for case in source_cases
        if not symbols or _display(case.get("symbol")).strip() in symbols
    ]
    completion_cases = [_completion_case(case) for case in selected_cases]

    completed_count = sum(1 for case in completion_cases if case.get("manual_review_complete") is True)
    passed_count = sum(1 for case in completion_cases if case.get("review_outcome") == PASS)
    failed_count = sum(1 for case in completion_cases if case.get("review_outcome") == FAIL)
    undecided_count = sum(1 for case in completion_cases if case.get("review_outcome") == UNDECIDED)
    evidence_count = sum(1 for case in completion_cases if bool(_display(case.get("evidence_artifact")).strip()))

    blockers = _completion_blockers(
        manual_evidence_packet,
        selected_cases=selected_cases,
        completion_cases=completion_cases,
        required_symbols=symbols,
        min_completed_cases=min_completed_cases,
    )
    completion_ready = not blockers
    shadow_validation_candidate_ready = completion_ready and failed_count == 0
    downstream_blocked = not shadow_validation_candidate_ready

    return {
        "report_type": REPORT_TYPE,
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "source_report_type": manual_evidence_packet.get("report_type"),
        "source_evidence_packet_status": manual_evidence_packet.get("evidence_packet_status"),
        "source_evidence_packet_decision": manual_evidence_packet.get("evidence_packet_decision"),
        "source_evidence_packet_ready": manual_evidence_packet.get("evidence_packet_ready"),
        "source_manual_review_complete": manual_evidence_packet.get("manual_review_complete"),
        "source_shadow_validation_candidate_ready": manual_evidence_packet.get("shadow_validation_candidate_ready"),
        "source_allowed_next_step": manual_evidence_packet.get("allowed_next_step"),
        "required_symbols": symbols,
        "minimum_completed_cases": int(min_completed_cases),
        "source_case_count": len(source_cases),
        "selected_case_count": len(selected_cases),
        "completed_case_count": completed_count,
        "passed_case_count": passed_count,
        "failed_case_count": failed_count,
        "undecided_case_count": undecided_count,
        "evidence_artifact_count": evidence_count,
        "completion_status": COMPLETION_READY_STATUS if completion_ready else COMPLETION_BLOCKED_STATUS,
        "completion_decision": READY_DECISION if completion_ready else BLOCKED_DECISION,
        "completion_ready": completion_ready,
        "manual_review_complete": completion_ready,
        "shadow_validation_candidate_ready": shadow_validation_candidate_ready,
        "downstream_integration_blocked": downstream_blocked,
        "blockers": blockers,
        "completion_cases": completion_cases,
        "required_review_lanes": list(REQUIRED_REVIEW_LANES),
        "disallowed_production_surfaces": list(DISALLOWED_PRODUCTION_SURFACES),
        "allowed_next_step": (
            "run_manual_lt_visual_replay_review_result_capture"
            if completion_ready
            else "complete_manual_lt_visual_replay_evidence_packet"
        ),
        "failed_cases_require_resolution": failed_count > 0,
        "manual_revalidation_required": True,
        "production_pr_required_after_shadow_validation": True,
        "automatic_promotion_allowed": False,
        **PRODUCTION_BOUNDARY,
    }


def render_effort_result_visual_replay_lt_manual_evidence_completion_markdown(
    report: Mapping[str, Any],
) -> str:
    """Render the LT manual evidence completion gate report as Markdown."""

    lines = [
        "# LT Visual Replay Manual Evidence Completion Gate",
        "",
        "## Decision",
        "",
        f"- Completion decision: `{_display(report.get('completion_decision'))}`",
        f"- Completion ready: {_bool_text(report.get('completion_ready'))}",
        f"- Completion status: `{_display(report.get('completion_status'))}`",
        f"- Manual review complete: {_bool_text(report.get('manual_review_complete'))}",
        f"- Shadow validation candidate ready: {_bool_text(report.get('shadow_validation_candidate_ready'))}",
        f"- Downstream integration blocked: {_bool_text(report.get('downstream_integration_blocked'))}",
        f"- Allowed next step: `{_display(report.get('allowed_next_step'))}`",
        f"- Completed cases: {int(report.get('completed_case_count', 0))}",
        f"- Passed cases: {int(report.get('passed_case_count', 0))}",
        f"- Failed cases: {int(report.get('failed_case_count', 0))}",
        f"- Undecided cases: {int(report.get('undecided_case_count', 0))}",
        "",
        "## Source Evidence Packet",
        "",
        f"- Source report type: `{_display(report.get('source_report_type'))}`",
        f"- Source packet status: `{_display(report.get('source_evidence_packet_status'))}`",
        f"- Source packet decision: `{_display(report.get('source_evidence_packet_decision'))}`",
        f"- Source packet ready: {_bool_text(report.get('source_evidence_packet_ready'))}",
        f"- Source manual review complete: {_bool_text(report.get('source_manual_review_complete'))}",
        "",
        "## Completion Cases",
        "",
    ]

    cases = _mapping_rows(report.get("completion_cases", []))
    if not cases:
        lines.extend(["_No LT manual evidence cases were selected._", ""])
    else:
        lines.extend(
            [
                "| Case | Target | Week | Outcome | Complete | Evidence | Blockers |",
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
                f"{_bool_text(row.get('manual_review_complete'))} | "
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
            "- Audit/manual-evidence-completion-gate only: true",
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


def _completion_case(packet_case: Mapping[str, Any]) -> dict[str, object]:
    blockers: list[str] = []

    case_id = _display(packet_case.get("case_id")).strip()
    review_outcome = _normalize_outcome(packet_case.get("review_outcome", UNDECIDED))
    review_lanes = _string_rows(packet_case.get("review_lanes", [])) or list(REQUIRED_REVIEW_LANES)
    lane_results = _normalize_lane_results(packet_case.get("lane_results", {}))

    reviewer = _display(packet_case.get("reviewer")).strip()
    reviewed_at = _display(packet_case.get("reviewed_at")).strip()
    evidence_artifact = _display(packet_case.get("evidence_artifact")).strip()
    reviewer_notes_recorded = packet_case.get("reviewer_notes_recorded") is True

    missing_lanes = [lane for lane in review_lanes if lane not in lane_results]
    undecided_lanes = [lane for lane in review_lanes if lane_results.get(lane) == UNDECIDED]
    invalid_lanes = [lane for lane, outcome in lane_results.items() if outcome not in ALLOWED_OUTCOMES]

    if packet_case.get("evidence_packet_case_ready") is not True:
        blockers.append("source_evidence_packet_case_not_ready")
    if review_outcome not in COMPLETED_OUTCOMES:
        blockers.append("review_outcome_not_completed")
    if not reviewer:
        blockers.append("missing_reviewer")
    if not reviewed_at:
        blockers.append("missing_reviewed_at")
    if not reviewer_notes_recorded:
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
    if packet_case.get("blockers"):
        blockers.append("source_evidence_packet_case_blockers_present")
    if _has_truthy_unsafe_fields(packet_case):
        blockers.append("case_production_boundary_open")

    complete = not blockers

    return {
        "case_id": case_id,
        "symbol": packet_case.get("symbol", ""),
        "event_week_beginning": packet_case.get("event_week_beginning", ""),
        "target": packet_case.get("target", ""),
        "offline_dataset_fixture": packet_case.get("offline_dataset_fixture", ""),
        "expected_marker_labels": _string_rows(packet_case.get("expected_marker_labels", [])),
        "review_lanes": review_lanes,
        "lane_results": lane_results,
        "missing_lane_results": missing_lanes,
        "undecided_lane_results": undecided_lanes,
        "invalid_lane_results": invalid_lanes,
        "review_outcome": review_outcome,
        "reviewer": reviewer,
        "reviewed_at": reviewed_at,
        "reviewer_notes_recorded": reviewer_notes_recorded,
        "evidence_artifact": evidence_artifact,
        "manual_review_complete": complete,
        "completion_case_ready": complete,
        "downstream_integration_blocked": review_outcome != PASS or not complete,
        "blockers": _dedupe(blockers),
        "automatic_promotion_allowed": False,
        **PRODUCTION_BOUNDARY,
    }


def _completion_blockers(
    manual_evidence_packet: Mapping[str, Any],
    *,
    selected_cases: Sequence[Mapping[str, Any]],
    completion_cases: Sequence[Mapping[str, Any]],
    required_symbols: Sequence[str],
    min_completed_cases: int,
) -> list[str]:
    blockers: list[str] = []

    if manual_evidence_packet.get("report_type") != SOURCE_REPORT_TYPE:
        blockers.append("source_report_type_mismatch")
    if manual_evidence_packet.get("evidence_packet_status") != SOURCE_READY_STATUS:
        blockers.append("source_evidence_packet_status_not_ready")
    if manual_evidence_packet.get("evidence_packet_decision") != SOURCE_READY_DECISION:
        blockers.append("source_evidence_packet_decision_not_ready")
    if manual_evidence_packet.get("evidence_packet_ready" ) is not True:
        blockers.append("source_evidence_packet_ready_false")
    if manual_evidence_packet.get("manual_review_complete") is not True:
        blockers.append("source_manual_review_complete_false")
    if manual_evidence_packet.get("allowed_next_step") != SOURCE_ALLOWED_NEXT_STEP:
        blockers.append("source_allowed_next_step_not_result_capture")
    if manual_evidence_packet.get("blockers"):
        blockers.append("source_evidence_packet_blockers_present")
    if _has_truthy_unsafe_fields(manual_evidence_packet):
        blockers.append("source_production_boundary_open")

    if required_symbols:
        selected_symbols = {_display(case.get("symbol")).strip() for case in selected_cases}
        missing_symbols = [symbol for symbol in required_symbols if symbol not in selected_symbols]
        if missing_symbols:
            blockers.append("missing_required_symbol_cases")

    completed_count = sum(1 for case in completion_cases if case.get("manual_review_complete") is True)
    if completed_count < min_completed_cases:
        blockers.append("not_enough_completed_manual_evidence_cases")
    if any(case.get("blockers") for case in completion_cases):
        blockers.append("completion_case_blockers_present")
    if any(case.get("review_outcome") == UNDECIDED for case in completion_cases):
        blockers.append("undecided_completion_cases_present")
    if any(case.get("manual_review_complete") is not True for case in completion_cases):
        blockers.append("incomplete_manual_evidence_cases_present")

    return _dedupe(blockers)


def _normalize_symbols(symbols: Sequence[str]) -> list[str]:
    return sorted({_display(symbol).strip() for symbol in symbols if _display(symbol).strip()})


def _normalize_outcome(value: Any) -> str:
    outcome = _display(value).strip().lower()
    return outcome if outcome in ALLOWED_OUTCOMES else UNDECIDED


def _normalize_lane_results(raw: Any) -> dict[str, str]:
    if not isinstance(raw, Mapping):
        return {}
    return {_display(k).strip(): _normalize_outcome(v) for k, v in raw.items() if _display(k).strip()}


def _has_truthy_unsafe_fields(row: Mapping[str, Any]) -> bool:
    return any(bool(row.get(field)) for field in UNSAFE_TRUTHY_FIELDS)


def _mapping_rows(value: Any) -> list[Mapping[str, Any]]:
    if isinstance(value, (str, bytes, Mapping)) or not isinstance(value, Iterable):
        return []
    return [row for row in value if isinstance(row, Mapping)]


def _string_rows(value: Any) -> list[str]:
    if isinstance(value, (str, bytes, Mapping)) or not isinstance(value, Iterable):
        return []
    return [_display(item).strip() for item in value if _display(item).strip()]


def _dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _display(value: Any) -> str:
    return "" if value is None else str(value)


def _csv(value: Any) -> str:
    rows = _string_rows(value)
    return ", ".join(rows) if rows else "none"


def _bool_text(value: Any) -> str:
    return "true" if value is True else "false"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Gate LT visual replay manual evidence packet completion."
    )
    parser.add_argument("packet_json", type=Path)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-markdown", type=Path)
    parser.add_argument("--min-completed-cases", type=int, default=DEFAULT_MIN_COMPLETED_CASES)
    parser.add_argument("--required-symbol", action="append", dest="required_symbols")
    args = parser.parse_args(argv)

    report = decide_effort_result_visual_replay_lt_manual_evidence_completion(
        _load_json(args.packet_json),
        required_symbols=args.required_symbols or DEFAULT_REQUIRED_SYMBOLS,
        min_completed_cases=args.min_completed_cases,
    )

    if args.output_json:
        _write_json(args.output_json, report)
    else:
        print(json.dumps(report, indent=2, sort_keys=True))

    if args.output_markdown:
        args.output_markdown.write_text(
            render_effort_result_visual_replay_lt_manual_evidence_completion_markdown(report),
            encoding="utf-8",
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
