"""Prepare an Effort/Result visual replay shadow/dev workflow manifest.

This module is audit/workflow-manifest only. It consumes the integration-gate
report and describes the guarded shadow/dev workflow that may be run next. It
does not read live data, call APIs, persist scanner state, activate detectors,
change scoring/ranking/actionability, emit alerts, or place orders.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

REPORT_TYPE = "effort_result_visual_replay_shadow_workflow_manifest"
REPORT_SCHEMA_VERSION = 1

SOURCE_REPORT_TYPE = "effort_result_visual_replay_integration_gate"
SOURCE_READY_STATUS = "visual_replay_shadow_integration_gate_ready"
SOURCE_READY_DECISION = "ready_for_shadow_integration"
SOURCE_ALLOWED_NEXT_STEP = "separate_shadow_dev_replay_workflow_integration_pr"

WORKFLOW_READY_STATUS = "visual_replay_shadow_workflow_manifest_ready"
WORKFLOW_BLOCKED_STATUS = "visual_replay_shadow_workflow_manifest_blocked"

READY_DECISION = "ready_to_run_shadow_dev_replay_workflow"
BLOCKED_DECISION = "blocked_from_shadow_dev_replay_workflow"

DEFAULT_ALLOWED_DEV_ROUTE = "/replay/effort-result"
DEFAULT_REQUIRED_SYMBOLS = ("LT.NS",)

SHADOW_WORKFLOW_STAGES = (
    "confirm_integration_gate_ready",
    "load_offline_shadow_replay_dataset_fixture",
    "open_dev_only_visual_replay_preview",
    "collect_manual_visual_evidence_draft",
    "compile_visual_replay_evidence",
    "run_visual_replay_casebook",
    "summarize_manual_reviewer_pass_fail_decisions",
    "rerun_visual_replay_integration_gate",
)

ALLOWED_SHADOW_SURFACES = (
    "dev_only_replay_preview_route_reference",
    "offline_dataset_fixture_reference",
    "manual_visual_evidence_export",
    "audit_evidence_compiler_report",
    "audit_casebook_report",
    "audit_reviewer_summary_report",
    "audit_integration_gate_report",
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
    "shadow_workflow_manifest_only": True,
    "manual_review_only": True,
    "offline_replay_only": True,
    "dev_preview_route_reference_only": True,
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
    "requires_visual_replay_integration_gate": True,
    "requires_offline_shadow_dataset_fixture": True,
    "requires_manual_evidence_export": True,
    "requires_separate_production_pr": True,
}


def prepare_effort_result_visual_replay_shadow_workflow(
    integration_gate_report: Mapping[str, Any],
    *,
    required_symbols: Sequence[str] = DEFAULT_REQUIRED_SYMBOLS,
    dev_route: str = DEFAULT_ALLOWED_DEV_ROUTE,
    require_zero_failed_cases: bool = True,
) -> dict[str, object]:
    """Build a guarded shadow/dev workflow manifest from the gate report.

    A ready manifest means the replay work can be exercised inside the existing
    dev-only/offline/manual review workflow. It never authorizes live scanner
    integration, production UI activation, scoring, ranking, actionability,
    detector activation, persistence, alerts, or orders.
    """

    normalized_symbols = _normalize_symbols(required_symbols)
    normalized_route = _normalize_route(dev_route)
    case_review_blockers = _mapping_rows(integration_gate_report.get("case_review_blockers", []))

    blockers = _manifest_blockers(
        integration_gate_report,
        required_symbols=normalized_symbols,
        dev_route=normalized_route,
        require_zero_failed_cases=require_zero_failed_cases,
        case_review_blockers=case_review_blockers,
    )
    ready = not blockers

    reviewed_case_count = _count(integration_gate_report, "reviewed_case_count", 0)
    passed_case_count = _count(integration_gate_report, "passed_case_count", 0)
    failed_case_count = _count(integration_gate_report, "failed_case_count", 0)
    undecided_case_count = _count(integration_gate_report, "undecided_case_count", 0)

    return {
        "report_type": REPORT_TYPE,
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "source_report_type": integration_gate_report.get("report_type"),
        "source_gate_status": integration_gate_report.get("gate_status"),
        "source_gate_decision": integration_gate_report.get("gate_decision"),
        "source_gate_ready": integration_gate_report.get("gate_ready"),
        "source_allowed_next_step": integration_gate_report.get("allowed_next_step"),
        "reviewed_case_count": reviewed_case_count,
        "passed_case_count": passed_case_count,
        "failed_case_count": failed_case_count,
        "undecided_case_count": undecided_case_count,
        "required_symbols": normalized_symbols,
        "dev_route": normalized_route,
        "workflow_status": WORKFLOW_READY_STATUS if ready else WORKFLOW_BLOCKED_STATUS,
        "workflow_decision": READY_DECISION if ready else BLOCKED_DECISION,
        "shadow_workflow_ready": ready,
        "blockers": blockers,
        "case_review_blockers": case_review_blockers,
        "shadow_workflow_stages": list(SHADOW_WORKFLOW_STAGES),
        "allowed_shadow_surfaces": list(ALLOWED_SHADOW_SURFACES),
        "disallowed_production_surfaces": list(DISALLOWED_PRODUCTION_SURFACES),
        "allowed_next_step": (
            "run_shadow_dev_visual_replay_workflow"
            if ready
            else "resolve_shadow_workflow_manifest_blockers"
        ),
        "manual_revalidation_required_after_run": True,
        "production_pr_required_after_shadow_validation": True,
        "automatic_promotion_allowed": False,
        **PRODUCTION_BOUNDARY,
    }


def render_effort_result_visual_replay_shadow_workflow_markdown(report: Mapping[str, Any]) -> str:
    """Render the visual replay shadow/dev workflow manifest as Markdown."""

    lines = [
        "# Effort/Result Visual Replay Shadow Workflow Manifest",
        "",
        "## Decision",
        "",
        f"- Workflow decision: `{_display(report.get('workflow_decision'))}`",
        f"- Shadow workflow ready: {_bool_text(report.get('shadow_workflow_ready'))}",
        f"- Workflow status: `{_display(report.get('workflow_status'))}`",
        f"- Allowed next step: `{_display(report.get('allowed_next_step'))}`",
        f"- Dev route reference: `{_display(report.get('dev_route'))}`",
        "",
        "## Source Gate",
        "",
        f"- Source report type: `{_display(report.get('source_report_type'))}`",
        f"- Source gate status: `{_display(report.get('source_gate_status'))}`",
        f"- Source gate decision: `{_display(report.get('source_gate_decision'))}`",
        f"- Source gate ready: {_bool_text(report.get('source_gate_ready'))}",
        f"- Source allowed next step: `{_display(report.get('source_allowed_next_step'))}`",
        f"- Reviewed cases: {int(report.get('reviewed_case_count', 0))}",
        f"- Passed cases: {int(report.get('passed_case_count', 0))}",
        f"- Failed cases: {int(report.get('failed_case_count', 0))}",
        f"- Undecided cases: {int(report.get('undecided_case_count', 0))}",
        "",
        "## Shadow Workflow Stages",
        "",
    ]
    for stage in _string_rows(report.get("shadow_workflow_stages", [])):
        lines.append(f"- [ ] {stage}")

    lines.extend(["", "## Allowed Shadow Surfaces", ""])
    for surface in _string_rows(report.get("allowed_shadow_surfaces", [])):
        lines.append(f"- {surface}")

    lines.extend(["", "## Disallowed Production Surfaces", ""])
    for surface in _string_rows(report.get("disallowed_production_surfaces", [])):
        lines.append(f"- {surface}")

    lines.extend(["", "## Production Boundary", ""])
    lines.extend(
        [
            "- Audit/workflow-manifest only: true",
            "- Manual review only: true",
            "- Offline replay only: true",
            "- Dev preview route reference only: true",
            "- Production change allowed: false",
            "- Automatic promotion allowed: false",
            "- May change scoring: false",
            "- May change ranking: false",
            "- May change actionability: false",
            "- May activate detector: false",
            "- May change scanner/API/frontend/persistence/broker behavior: false",
            "- Requires separate production PR: true",
        ]
    )

    blockers = _string_rows(report.get("blockers", []))
    lines.extend(["", "## Blockers", ""])
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

    lines.extend(
        [
            "",
            "## Workflow Rules",
            "",
            "- Use only the offline/dev visual replay route and audit reports from the evidence chain.",
            "- Rerun the evidence compiler, casebook runner, reviewer summary, and integration gate after shadow workflow review.",
            "- This manifest does not approve live scanner integration or production UI activation.",
            "- A separate production PR is required before any scoring, ranking, actionability, detector, API, frontend, persistence, alert, or order behavior can change.",
            "",
        ]
    )
    return "\n".join(lines)


def _manifest_blockers(
    integration_gate_report: Mapping[str, Any],
    *,
    required_symbols: Sequence[str],
    dev_route: str,
    require_zero_failed_cases: bool,
    case_review_blockers: Sequence[Mapping[str, Any]],
) -> list[str]:
    blockers: list[str] = []

    if integration_gate_report.get("report_type") != SOURCE_REPORT_TYPE:
        blockers.append("source_report_type_mismatch")
    if integration_gate_report.get("gate_status") != SOURCE_READY_STATUS:
        blockers.append("source_gate_status_not_ready")
    if integration_gate_report.get("gate_decision") != SOURCE_READY_DECISION:
        blockers.append("source_gate_decision_not_ready")
    if integration_gate_report.get("gate_ready") is not True:
        blockers.append("source_gate_ready_false")
    if integration_gate_report.get("allowed_next_step") != SOURCE_ALLOWED_NEXT_STEP:
        blockers.append("source_allowed_next_step_not_shadow_integration_pr")
    if not required_symbols:
        blockers.append("missing_required_symbols")
    if not dev_route.startswith("/replay/"):
        blockers.append("dev_route_not_replay_preview_route")
    if not _display(dev_route).strip():
        blockers.append("missing_dev_route")
    if _count(integration_gate_report, "reviewed_case_count", 0) <= 0:
        blockers.append("missing_reviewed_cases")
    if _count(integration_gate_report, "passed_case_count", 0) <= 0:
        blockers.append("missing_passed_cases")
    if require_zero_failed_cases and _count(integration_gate_report, "failed_case_count", 0) > 0:
        blockers.append("failed_cases_present")
    if _count(integration_gate_report, "undecided_case_count", 0) > 0:
        blockers.append("undecided_cases_present")
    if _string_rows(integration_gate_report.get("blockers", [])):
        blockers.append("source_gate_blockers_present")
    if case_review_blockers:
        blockers.append("source_case_review_blockers_present")
    if _string_rows(integration_gate_report.get("disallowed_next_steps", [])) and (
        "production_scoring_change" not in _string_rows(integration_gate_report.get("disallowed_next_steps", []))
    ):
        blockers.append("source_disallowed_next_steps_unexpected")
    if _has_truthy_unsafe_fields(integration_gate_report):
        blockers.append("source_production_boundary_open")

    return _dedupe(blockers)


def _normalize_symbols(symbols: Sequence[str]) -> list[str]:
    return sorted({_display(symbol).strip() for symbol in symbols if _display(symbol).strip()})


def _normalize_route(route: str) -> str:
    return _display(route).strip()


def _count(report: Mapping[str, Any], field: str, fallback: int) -> int:
    try:
        return int(report.get(field, fallback) or 0)
    except (TypeError, ValueError):
        return fallback


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
    parser.add_argument("integration_gate_report", type=Path)
    parser.add_argument("--symbol", action="append", dest="required_symbols")
    parser.add_argument("--dev-route", default=DEFAULT_ALLOWED_DEV_ROUTE)
    parser.add_argument("--allow-failed-cases", action="store_true")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    source_report = json.loads(args.integration_gate_report.read_text(encoding="utf-8"))
    report = prepare_effort_result_visual_replay_shadow_workflow(
        source_report,
        required_symbols=args.required_symbols or DEFAULT_REQUIRED_SYMBOLS,
        dev_route=args.dev_route,
        require_zero_failed_cases=not args.allow_failed_cases,
    )

    rendered = (
        render_effort_result_visual_replay_shadow_workflow_markdown(report)
        if args.format == "markdown"
        else json.dumps(report, indent=2, sort_keys=True)
    )
    _write_output(rendered, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
