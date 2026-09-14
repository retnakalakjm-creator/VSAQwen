"""Index the Effort/Result visual replay shadow validation package.

This module is audit/reporting only. It consumes the final visual replay shadow
integration-gate report and emits a validation-package index for manual review
handoff. It does not read market data, call services, change persistence,
activate detectors, change scoring, ranking, actionability, scanner state,
alerts, or orders.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

REPORT_TYPE = "effort_result_visual_replay_shadow_validation_package_index"
REPORT_SCHEMA_VERSION = 1

SOURCE_REPORT_TYPE = "effort_result_visual_replay_shadow_integration_gate_report"
SOURCE_READY_STATUS = "visual_replay_shadow_integration_gate_passed"
SOURCE_READY_DECISION = "shadow_visual_replay_validation_passed"
SOURCE_ALLOWED_NEXT_STEP = "open_separate_production_pr_after_manual_approval"

READY_STATUS = "visual_replay_shadow_validation_package_index_ready"
BLOCKED_STATUS = "visual_replay_shadow_validation_package_index_blocked"
READY_DECISION = "ready_for_separate_production_pr_review_packet"
BLOCKED_DECISION = "blocked_from_shadow_validation_package_index"

PASS = "pass"
FAIL = "fail"
UNDECIDED = "undecided"
DEFAULT_REQUIRED_SYMBOLS = ("LT.NS",)
DEFAULT_MIN_PACKAGE_CASES = 2

DEFAULT_PACKAGE_ARTIFACTS = (
    {
        "artifact_id": "lt_shadow_coverage_cases",
        "path": "audit/fixtures/effort_result_visual_replay_shadow_coverage_lt_cases.json",
        "required": True,
        "description": "Manual LT replay case definitions selected for shadow validation.",
    },
    {
        "artifact_id": "lt_shadow_coverage_plan",
        "path": "audit/fixtures/effort_result_visual_replay_shadow_coverage_lt_plan.json",
        "required": True,
        "description": "Coverage plan proving the LT cases are selected for shadow review.",
    },
    {
        "artifact_id": "manual_shadow_review_results_pending",
        "path": "audit/fixtures/effort_result_visual_replay_shadow_review_results_pending.json",
        "required": True,
        "description": "Pending manual review capture file that must be replaced with real outcomes.",
    },
    {
        "artifact_id": "shadow_review_completion_pending",
        "path": "audit/fixtures/effort_result_visual_replay_shadow_review_completion_pending.json",
        "required": True,
        "description": "Completion gate fixture showing pending manual outcomes block summary.",
    },
    {
        "artifact_id": "shadow_summary_input_pending",
        "path": "audit/fixtures/effort_result_visual_replay_shadow_summary_input_pending.json",
        "required": True,
        "description": "Reviewer-summary input fixture blocked until manual review is complete.",
    },
    {
        "artifact_id": "shadow_reviewer_summary_pending",
        "path": "audit/fixtures/effort_result_visual_replay_shadow_reviewer_summary_pending.json",
        "required": True,
        "description": "Reviewer pass/fail summary fixture blocked by undecided LT cases.",
    },
    {
        "artifact_id": "shadow_integration_gate_input_pending",
        "path": "audit/fixtures/effort_result_visual_replay_shadow_integration_gate_input_pending.json",
        "required": True,
        "description": "Integration-gate input fixture blocked until the reviewer summary is all-pass.",
    },
    {
        "artifact_id": "shadow_integration_gate_pending",
        "path": "audit/fixtures/effort_result_visual_replay_shadow_integration_gate_pending.json",
        "required": True,
        "description": "Final shadow integration-gate fixture blocked until validation passes.",
    },
)

MANUAL_REVIEW_STEPS = (
    "open_dev_only_visual_replay_route",
    "load_offline_lt_shadow_case_fixture",
    "review_effort_result_marker_alignment",
    "review_volume_spread_price_context",
    "review_follow_through_or_counterfactual_context",
    "attach_visual_evidence_artifact",
    "record_reviewer_identity_and_timestamp",
    "mark_each_case_pass_or_fail",
    "rerun_shadow_review_completion_summary_and_gate_reports",
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
    "validation_package_index_only": True,
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
    "requires_shadow_integration_gate": True,
    "requires_manual_evidence": True,
    "requires_separate_production_pr": True,
}


def index_effort_result_visual_replay_shadow_validation_package(
    shadow_gate_report: Mapping[str, Any],
    *,
    required_symbols: Sequence[str] = DEFAULT_REQUIRED_SYMBOLS,
    min_package_cases: int = DEFAULT_MIN_PACKAGE_CASES,
    package_artifacts: Sequence[Mapping[str, Any]] = DEFAULT_PACKAGE_ARTIFACTS,
) -> dict[str, object]:
    """Build an audit-only validation package index from the shadow gate report."""

    if min_package_cases <= 0:
        raise ValueError("min_package_cases must be positive")

    symbols = _normalize_symbols(required_symbols)
    source_cases = _mapping_rows(shadow_gate_report.get("integration_cases", []))
    selected_cases = [
        case for case in source_cases if not symbols or _display(case.get("symbol")).strip() in symbols
    ]
    package_cases = [_package_case(case) for case in selected_cases]
    artifacts = [_package_artifact(artifact) for artifact in package_artifacts]

    accepted_count = sum(1 for case in package_cases if case.get("source_shadow_gate_case_accepted") is True)
    passed_count = sum(1 for case in package_cases if case.get("review_outcome") == PASS)
    failed_count = sum(1 for case in package_cases if case.get("review_outcome") == FAIL)
    undecided_count = sum(1 for case in package_cases if case.get("review_outcome") == UNDECIDED)
    evidence_count = sum(1 for case in package_cases if bool(case.get("evidence_artifact")))
    ready_case_count = sum(1 for case in package_cases if case.get("package_case_ready") is True)

    blockers = _blockers(
        shadow_gate_report,
        selected_cases=selected_cases,
        package_cases=package_cases,
        artifacts=artifacts,
        required_symbols=symbols,
        min_package_cases=min_package_cases,
    )
    ready = not blockers

    return {
        "report_type": REPORT_TYPE,
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "source_report_type": shadow_gate_report.get("report_type"),
        "source_shadow_integration_gate_status": shadow_gate_report.get("shadow_integration_gate_status"),
        "source_shadow_integration_gate_decision": shadow_gate_report.get("shadow_integration_gate_decision"),
        "source_shadow_integration_gate_passed": shadow_gate_report.get("shadow_integration_gate_passed"),
        "source_shadow_validation_passed": shadow_gate_report.get("shadow_validation_passed"),
        "source_downstream_production_blocked": shadow_gate_report.get("downstream_production_blocked"),
        "source_allowed_next_step": shadow_gate_report.get("allowed_next_step"),
        "required_symbols": symbols,
        "minimum_package_cases": int(min_package_cases),
        "source_case_count": len(source_cases),
        "selected_case_count": len(selected_cases),
        "ready_case_count": ready_case_count,
        "accepted_case_count": accepted_count,
        "passed_case_count": passed_count,
        "failed_case_count": failed_count,
        "undecided_case_count": undecided_count,
        "evidence_artifact_count": evidence_count,
        "package_artifact_count": len(artifacts),
        "required_package_artifact_count": sum(1 for artifact in artifacts if artifact.get("required") is True),
        "manual_review_step_count": len(MANUAL_REVIEW_STEPS),
        "validation_package_index_status": READY_STATUS if ready else BLOCKED_STATUS,
        "validation_package_index_decision": READY_DECISION if ready else BLOCKED_DECISION,
        "validation_package_index_ready": ready,
        "shadow_validation_passed": shadow_gate_report.get("shadow_validation_passed") is True and ready,
        "downstream_production_blocked": True,
        "blockers": blockers,
        "package_cases": package_cases,
        "package_artifacts": artifacts,
        "manual_review_steps": list(MANUAL_REVIEW_STEPS),
        "disallowed_production_surfaces": list(DISALLOWED_PRODUCTION_SURFACES),
        "allowed_next_step": "prepare_separate_production_pr_review_packet" if ready else "resolve_shadow_validation_package_index_blockers",
        "automatic_promotion_allowed": False,
        "production_pr_required_after_shadow_validation": True,
        **PRODUCTION_BOUNDARY,
    }


def render_effort_result_visual_replay_shadow_validation_package_index_markdown(
    report: Mapping[str, Any],
) -> str:
    """Render the validation package index as Markdown."""

    lines = [
        "# Effort/Result Visual Replay Shadow Validation Package Index",
        "",
        "## Decision",
        "",
        f"- Validation package decision: `{_display(report.get('validation_package_index_decision'))}`",
        f"- Validation package ready: {_bool_text(report.get('validation_package_index_ready'))}",
        f"- Validation package status: `{_display(report.get('validation_package_index_status'))}`",
        f"- Shadow validation passed: {_bool_text(report.get('shadow_validation_passed'))}",
        f"- Downstream production blocked: {_bool_text(report.get('downstream_production_blocked'))}",
        f"- Allowed next step: `{_display(report.get('allowed_next_step'))}`",
        f"- Selected cases: {int(report.get('selected_case_count', 0))}",
        f"- Ready package cases: {int(report.get('ready_case_count', 0))}",
        f"- Evidence artifacts: {int(report.get('evidence_artifact_count', 0))}",
        f"- Package artifacts: {int(report.get('package_artifact_count', 0))}",
        "",
        "## Source Shadow Gate",
        "",
        f"- Source report type: `{_display(report.get('source_report_type'))}`",
        f"- Source gate passed: {_bool_text(report.get('source_shadow_integration_gate_passed'))}",
        f"- Source shadow validation passed: {_bool_text(report.get('source_shadow_validation_passed'))}",
        f"- Source downstream production blocked: {_bool_text(report.get('source_downstream_production_blocked'))}",
        f"- Source decision: `{_display(report.get('source_shadow_integration_gate_decision'))}`",
        f"- Source allowed next step: `{_display(report.get('source_allowed_next_step'))}`",
        "",
        "## Production Boundary",
        "",
        "- Audit/validation-package-index only: true",
        "- Manual review only: true",
        "- Offline replay only: true",
        "- Production change allowed: false",
        "- Automatic promotion allowed: false",
        "- Downstream production remains blocked until a separate production PR is reviewed: true",
        "- May change scoring/ranking/actionability/detector/scanner/API/frontend/persistence/orders: false",
        "",
        "## Package Cases",
        "",
    ]

    cases = _mapping_rows(report.get("package_cases", []))
    if not cases:
        lines.append("_No package cases selected._")
    else:
        lines.extend([
            "| Case | Symbol | Week | Target | Outcome | Package Ready | Evidence |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ])
        for case in cases:
            lines.append(
                "| "
                f"`{_display(case.get('case_id'))}` | "
                f"{_display(case.get('symbol'))} | "
                f"{_display(case.get('event_week_beginning'))} | "
                f"`{_display(case.get('target'))}` | "
                f"`{_display(case.get('review_outcome'))}` | "
                f"{_bool_text(case.get('package_case_ready'))} | "
                f"{_display(case.get('evidence_artifact'))} |"
            )

    lines.extend(["", "## Package Artifacts", ""])
    artifacts = _mapping_rows(report.get("package_artifacts", []))
    if not artifacts:
        lines.append("_No package artifacts listed._")
    else:
        lines.extend([
            "| Artifact | Required | Path | Description |",
            "| --- | --- | --- | --- |",
        ])
        for artifact in artifacts:
            lines.append(
                "| "
                f"`{_display(artifact.get('artifact_id'))}` | "
                f"{_bool_text(artifact.get('required'))} | "
                f"`{_display(artifact.get('path'))}` | "
                f"{_display(artifact.get('description'))} |"
            )

    lines.extend(["", "## Manual Review Steps", ""])
    steps = _string_rows(report.get("manual_review_steps", []))
    if steps:
        lines.extend(f"{index}. `{step}`" for index, step in enumerate(steps, start=1))
    else:
        lines.append("- none")

    lines.extend(["", "## Blockers", ""])
    blockers = _string_rows(report.get("blockers", []))
    lines.extend(f"- {blocker}" for blocker in blockers) if blockers else lines.append("- none")
    lines.extend([
        "",
        "## Package Rules",
        "",
        "- This index is ready only after the shadow integration gate passes.",
        "- Every selected LT case must have pass outcome, reviewer metadata, and visual evidence artifact.",
        "- Pending or failed cases keep the package index blocked.",
        "- A ready package index still does not change production behavior.",
        "- A separate production PR is required before scanner, detector, scoring, ranking, actionability, API, frontend, persistence, alert, or order behavior can change.",
        "",
    ])
    return "\n".join(lines)


def _package_case(case: Mapping[str, Any]) -> dict[str, object]:
    outcome = _normalize_outcome(case.get("review_outcome", UNDECIDED))
    source_blockers = _string_rows(case.get("blockers", []))
    source_accepted = case.get("shadow_gate_case_accepted") is True
    production_blocked = case.get("production_blocked") is True
    evidence_artifact = _display(case.get("evidence_artifact")).strip()
    reviewer = _display(case.get("reviewer")).strip()
    reviewed_at = _display(case.get("reviewed_at")).strip()
    case_unsafe = _has_truthy_unsafe_fields(case)

    blockers: list[str] = []
    if not source_accepted:
        blockers.append("source_shadow_gate_case_not_accepted")
    if outcome == FAIL:
        blockers.append("failed_review_outcome")
    if outcome == UNDECIDED:
        blockers.append("undecided_review_outcome")
    if not production_blocked:
        blockers.append("case_production_boundary_not_blocked")
    if not evidence_artifact:
        blockers.append("missing_case_evidence_artifact")
    if not reviewer:
        blockers.append("missing_case_reviewer")
    if not reviewed_at:
        blockers.append("missing_case_reviewed_at")
    if source_blockers:
        blockers.append("source_shadow_gate_case_blockers_present")
    if case_unsafe:
        blockers.append("case_production_boundary_open")

    ready = not blockers and outcome == PASS and production_blocked
    return {
        "case_id": _display(case.get("case_id")).strip(),
        "symbol": _display(case.get("symbol")).strip(),
        "event_week_beginning": _display(case.get("event_week_beginning")).strip(),
        "target": _display(case.get("target")).strip(),
        "review_outcome": outcome,
        "reviewer": reviewer,
        "reviewed_at": reviewed_at,
        "evidence_artifact": evidence_artifact,
        "source_shadow_gate_case_accepted": source_accepted,
        "production_blocked": production_blocked,
        "package_case_ready": ready,
        "blockers": _dedupe(blockers),
        "automatic_promotion_allowed": False,
        **PRODUCTION_BOUNDARY,
    }


def _package_artifact(artifact: Mapping[str, Any]) -> dict[str, object]:
    path = _display(artifact.get("path")).strip()
    artifact_id = _display(artifact.get("artifact_id")).strip()
    required = artifact.get("required") is True
    blockers: list[str] = []
    if not artifact_id:
        blockers.append("missing_artifact_id")
    if not path:
        blockers.append("missing_artifact_path")
    return {
        "artifact_id": artifact_id,
        "path": path,
        "required": required,
        "description": _display(artifact.get("description")).strip(),
        "artifact_ready": not blockers,
        "blockers": blockers,
    }


def _blockers(
    source: Mapping[str, Any],
    *,
    selected_cases: Sequence[Mapping[str, Any]],
    package_cases: Sequence[Mapping[str, Any]],
    artifacts: Sequence[Mapping[str, Any]],
    required_symbols: Sequence[str],
    min_package_cases: int,
) -> list[str]:
    blockers: list[str] = []
    if source.get("report_type") != SOURCE_REPORT_TYPE:
        blockers.append("source_report_type_mismatch")
    if source.get("shadow_integration_gate_status") != SOURCE_READY_STATUS:
        blockers.append("source_shadow_integration_gate_status_not_passed")
    if source.get("shadow_integration_gate_decision") != SOURCE_READY_DECISION:
        blockers.append("source_shadow_integration_gate_decision_not_passed")
    if source.get("shadow_integration_gate_passed") is not True:
        blockers.append("source_shadow_integration_gate_not_passed")
    if source.get("shadow_validation_passed") is not True:
        blockers.append("source_shadow_validation_not_passed")
    if source.get("downstream_production_blocked") is not True:
        blockers.append("source_downstream_production_not_blocked")
    if source.get("allowed_next_step") != SOURCE_ALLOWED_NEXT_STEP:
        blockers.append("source_allowed_next_step_not_package_ready")
    if _string_rows(source.get("blockers", [])):
        blockers.append("source_shadow_gate_blockers_present")
    if _has_truthy_unsafe_fields(source):
        blockers.append("source_production_boundary_open")
    if not required_symbols:
        blockers.append("missing_required_symbols")
    if not selected_cases:
        blockers.append("missing_selected_shadow_gate_cases")
    if sum(1 for case in package_cases if case.get("package_case_ready") is True) < min_package_cases:
        blockers.append("not_enough_ready_package_cases")
    if any(case.get("package_case_ready") is not True for case in package_cases):
        blockers.append("package_case_blockers_present")
    if any(case.get("review_outcome") == FAIL for case in package_cases):
        blockers.append("failed_package_cases_present")
    if any(case.get("review_outcome") == UNDECIDED for case in package_cases):
        blockers.append("undecided_package_cases_present")
    if any(not artifact.get("artifact_ready") for artifact in artifacts):
        blockers.append("package_artifact_blockers_present")
    if not artifacts:
        blockers.append("missing_package_artifacts")
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
    parser.add_argument("shadow_gate_report", type=Path)
    parser.add_argument("--symbol", action="append", dest="symbols")
    parser.add_argument("--min-package-cases", type=int, default=DEFAULT_MIN_PACKAGE_CASES)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    source = json.loads(args.shadow_gate_report.read_text(encoding="utf-8"))
    report = index_effort_result_visual_replay_shadow_validation_package(
        source,
        required_symbols=args.symbols or DEFAULT_REQUIRED_SYMBOLS,
        min_package_cases=args.min_package_cases,
    )
    rendered = (
        render_effort_result_visual_replay_shadow_validation_package_index_markdown(report)
        if args.format == "markdown"
        else json.dumps(report, indent=2, sort_keys=True)
    )
    _write_output(rendered, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
