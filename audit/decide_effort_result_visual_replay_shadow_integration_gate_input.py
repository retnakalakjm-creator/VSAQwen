"""Analyze visual replay shadow reviewer summary readiness for integration-gate input.

This module is audit/reporting only. It consumes the reviewer pass/fail
summary report and emits a guarded integration-gate input report. It does not
read market data, call services, change persistence, activate detectors, change
scoring, ranking, actionability, scanner state, alerts, or orders.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

REPORT_TYPE = "effort_result_visual_replay_shadow_integration_gate_input"
REPORT_SCHEMA_VERSION = 1

SOURCE_REPORT_TYPE = "effort_result_visual_replay_shadow_reviewer_summary_report"
SOURCE_READY_STATUS = "visual_replay_shadow_reviewer_summary_ready"
SOURCE_READY_DECISION = "ready_for_shadow_visual_replay_integration_gate"
SOURCE_ALLOWED_NEXT_STEP = "run_shadow_visual_replay_integration_gate"

READY_STATUS = "visual_replay_shadow_integration_gate_input_ready"
BLOCKED_STATUS = "visual_replay_shadow_integration_gate_input_blocked"
READY_DECISION = "ready_to_run_shadow_visual_replay_integration_gate"
BLOCKED_DECISION = "blocked_from_shadow_visual_replay_integration_gate_input"

PASS = "pass"
FAIL = "fail"
UNDECIDED = "undecided"
DEFAULT_REQUIRED_SYMBOLS = ("LT.NS",)
DEFAULT_MIN_GATE_CASES = 2

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
    "integration_gate_input_only": True,
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
    "requires_reviewer_summary_report": True,
    "requires_shadow_integration_gate": True,
    "requires_separate_production_pr": True,
}


def prepare_effort_result_visual_replay_shadow_integration_gate_input(
    reviewer_summary_report: Mapping[str, Any],
    *,
    required_symbols: Sequence[str] = DEFAULT_REQUIRED_SYMBOLS,
    min_gate_cases: int = DEFAULT_MIN_GATE_CASES,
) -> dict[str, object]:
    """Build the guarded input payload for the shadow visual replay integration gate."""

    if min_gate_cases <= 0:
        raise ValueError("min_gate_cases must be positive")

    symbols = _normalize_symbols(required_symbols)
    source_cases = _mapping_rows(reviewer_summary_report.get("case_summaries", []))
    selected_cases = [
        case for case in source_cases if not symbols or _display(case.get("symbol")).strip() in symbols
    ]
    gate_cases = [_gate_case(case) for case in selected_cases]

    pass_count = sum(1 for case in gate_cases if case.get("review_outcome") == PASS)
    fail_count = sum(1 for case in gate_cases if case.get("review_outcome") == FAIL)
    undecided_count = sum(1 for case in gate_cases if case.get("review_outcome") == UNDECIDED)
    ready_case_count = sum(1 for case in gate_cases if case.get("gate_case_ready") is True)

    blockers = _blockers(
        reviewer_summary_report,
        selected_cases=selected_cases,
        gate_cases=gate_cases,
        required_symbols=symbols,
        min_gate_cases=min_gate_cases,
    )
    ready = not blockers

    return {
        "report_type": REPORT_TYPE,
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "source_report_type": reviewer_summary_report.get("report_type"),
        "source_reviewer_summary_status": reviewer_summary_report.get("reviewer_summary_status"),
        "source_reviewer_summary_decision": reviewer_summary_report.get("reviewer_summary_decision"),
        "source_reviewer_summary_ready": reviewer_summary_report.get("reviewer_summary_ready"),
        "source_shadow_validation_passed": reviewer_summary_report.get("shadow_validation_passed"),
        "source_downstream_integration_blocked": reviewer_summary_report.get("downstream_integration_blocked"),
        "source_allowed_next_step": reviewer_summary_report.get("allowed_next_step"),
        "required_symbols": symbols,
        "minimum_gate_cases": int(min_gate_cases),
        "source_case_count": len(source_cases),
        "selected_case_count": len(selected_cases),
        "ready_case_count": ready_case_count,
        "passed_case_count": pass_count,
        "failed_case_count": fail_count,
        "undecided_case_count": undecided_count,
        "integration_gate_input_status": READY_STATUS if ready else BLOCKED_STATUS,
        "integration_gate_input_decision": READY_DECISION if ready else BLOCKED_DECISION,
        "integration_gate_input_ready": ready,
        "shadow_validation_passed": ready,
        "downstream_integration_blocked": not ready,
        "blockers": blockers,
        "gate_cases": gate_cases,
        "disallowed_production_surfaces": list(DISALLOWED_PRODUCTION_SURFACES),
        "allowed_next_step": "run_shadow_visual_replay_integration_gate" if ready else "resolve_shadow_integration_gate_input_blockers",
        "automatic_promotion_allowed": False,
        "production_pr_required_after_shadow_validation": True,
        **PRODUCTION_BOUNDARY,
    }


def render_effort_result_visual_replay_shadow_integration_gate_input_markdown(report: Mapping[str, Any]) -> str:
    """Render the integration-gate input report as Markdown."""

    lines = [
        "# Effort/Result Visual Replay Shadow Integration Gate Input",
        "",
        "## Decision",
        "",
        f"- Integration gate input decision: `{_display(report.get('integration_gate_input_decision'))}`",
        f"- Integration gate input ready: {_bool_text(report.get('integration_gate_input_ready'))}",
        f"- Integration gate input status: `{_display(report.get('integration_gate_input_status'))}`",
        f"- Shadow validation passed: {_bool_text(report.get('shadow_validation_passed'))}",
        f"- Downstream integration blocked: {_bool_text(report.get('downstream_integration_blocked'))}",
        f"- Allowed next step: `{_display(report.get('allowed_next_step'))}`",
        f"- Selected cases: {int(report.get('selected_case_count', 0))}",
        f"- Ready gate cases: {int(report.get('ready_case_count', 0))}",
        f"- Passed cases: {int(report.get('passed_case_count', 0))}",
        f"- Failed cases: {int(report.get('failed_case_count', 0))}",
        f"- Undecided cases: {int(report.get('undecided_case_count', 0))}",
        "",
        "## Source Reviewer Summary",
        "",
        f"- Source report type: `{_display(report.get('source_report_type'))}`",
        f"- Source reviewer summary ready: {_bool_text(report.get('source_reviewer_summary_ready'))}",
        f"- Source shadow validation passed: {_bool_text(report.get('source_shadow_validation_passed'))}",
        f"- Source downstream integration blocked: {_bool_text(report.get('source_downstream_integration_blocked'))}",
        f"- Source decision: `{_display(report.get('source_reviewer_summary_decision'))}`",
        f"- Source allowed next step: `{_display(report.get('source_allowed_next_step'))}`",
        "",
        "## Production Boundary",
        "",
        "- Audit/integration-gate-input only: true",
        "- Manual review only: true",
        "- Offline replay only: true",
        "- Production change allowed: false",
        "- Automatic promotion allowed: false",
        "- May change scoring/ranking/actionability/detector/scanner/API/frontend/persistence/orders: false",
        "- Requires separate production PR: true",
        "",
        "## Gate Cases",
        "",
    ]

    cases = _mapping_rows(report.get("gate_cases", []))
    if not cases:
        lines.append("_No gate cases selected._")
    else:
        lines.extend([
            "| Case | Symbol | Week | Target | Outcome | Gate Ready | Integration Blocker | Evidence |",
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
                f"{_bool_text(case.get('gate_case_ready'))} | "
                f"{_bool_text(case.get('integration_blocked'))} | "
                f"{_display(case.get('evidence_artifact'))} |"
            )

    lines.extend(["", "## Blockers", ""])
    blockers = _string_rows(report.get("blockers", []))
    lines.extend(f"- {blocker}" for blocker in blockers) if blockers else lines.append("- none")
    lines.extend([
        "",
        "## Gate Input Rules",
        "",
        "- Only all-pass reviewer summaries can become ready integration-gate input.",
        "- Any failed case blocks this input until the failed case is resolved.",
        "- Any undecided case blocks this input until manual review evidence is complete.",
        "- This report does not approve production behavior changes.",
        "- A separate production PR is required before scanner, detector, scoring, ranking, actionability, API, frontend, persistence, alert, or order behavior can change.",
        "",
    ])
    return "\n".join(lines)


def _gate_case(case: Mapping[str, Any]) -> dict[str, object]:
    outcome = _normalize_outcome(case.get("review_outcome", UNDECIDED))
    source_blockers = _string_rows(case.get("blockers", []))
    source_ready = case.get("reviewer_case_ready") is True
    source_integration_blocked = case.get("integration_blocked") is True
    case_unsafe = _has_truthy_unsafe_fields(case)
    gate_ready = source_ready and outcome == PASS and not source_integration_blocked and not source_blockers and not case_unsafe

    blockers: list[str] = []
    if not source_ready:
        blockers.append("source_reviewer_case_not_ready")
    if outcome == FAIL:
        blockers.append("failed_review_outcome")
    if outcome == UNDECIDED:
        blockers.append("undecided_review_outcome")
    if source_integration_blocked:
        blockers.append("source_case_integration_blocked")
    if source_blockers:
        blockers.append("source_reviewer_case_blockers_present")
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
        "source_reviewer_case_ready": source_ready,
        "source_case_integration_blocked": source_integration_blocked,
        "gate_case_ready": gate_ready,
        "integration_blocked": not gate_ready,
        "blockers": _dedupe(blockers),
        "automatic_promotion_allowed": False,
        **PRODUCTION_BOUNDARY,
    }


def _blockers(
    source: Mapping[str, Any],
    *,
    selected_cases: Sequence[Mapping[str, Any]],
    gate_cases: Sequence[Mapping[str, Any]],
    required_symbols: Sequence[str],
    min_gate_cases: int,
) -> list[str]:
    blockers: list[str] = []
    if source.get("report_type") != SOURCE_REPORT_TYPE:
        blockers.append("source_report_type_mismatch")
    if source.get("reviewer_summary_status") != SOURCE_READY_STATUS:
        blockers.append("source_reviewer_summary_status_not_ready")
    if source.get("reviewer_summary_decision") != SOURCE_READY_DECISION:
        blockers.append("source_reviewer_summary_decision_not_ready")
    if source.get("reviewer_summary_ready") is not True:
        blockers.append("source_reviewer_summary_ready_false")
    if source.get("shadow_validation_passed") is not True:
        blockers.append("source_shadow_validation_not_passed")
    if source.get("downstream_integration_blocked") is True:
        blockers.append("source_downstream_integration_blocked")
    if source.get("allowed_next_step") != SOURCE_ALLOWED_NEXT_STEP:
        blockers.append("source_allowed_next_step_not_integration_gate")
    if _string_rows(source.get("blockers", [])):
        blockers.append("source_reviewer_summary_blockers_present")
    if _has_truthy_unsafe_fields(source):
        blockers.append("source_production_boundary_open")
    if not required_symbols:
        blockers.append("missing_required_symbols")
    if not selected_cases:
        blockers.append("missing_selected_reviewer_cases")
    if sum(1 for case in gate_cases if case.get("gate_case_ready") is True) < min_gate_cases:
        blockers.append("not_enough_ready_gate_cases")
    if any(case.get("gate_case_ready") is not True for case in gate_cases):
        blockers.append("gate_case_blockers_present")
    if any(case.get("review_outcome") == FAIL for case in gate_cases):
        blockers.append("failed_gate_cases_present")
    if any(case.get("review_outcome") == UNDECIDED for case in gate_cases):
        blockers.append("undecided_gate_cases_present")
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
    parser.add_argument("reviewer_summary_report", type=Path)
    parser.add_argument("--symbol", action="append", dest="symbols")
    parser.add_argument("--min-gate-cases", type=int, default=DEFAULT_MIN_GATE_CASES)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    source = json.loads(args.reviewer_summary_report.read_text(encoding="utf-8"))
    report = prepare_effort_result_visual_replay_shadow_integration_gate_input(
        source,
        required_symbols=args.symbols or DEFAULT_REQUIRED_SYMBOLS,
        min_gate_cases=args.min_gate_cases,
    )
    rendered = (
        render_effort_result_visual_replay_shadow_integration_gate_input_markdown(report)
        if args.format == "markdown"
        else json.dumps(report, indent=2, sort_keys=True)
    )
    _write_output(rendered, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
