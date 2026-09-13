"""Plan an offline Effort/Result visual replay shadow coverage run.

This module is audit/coverage-planning only. It consumes the shadow workflow
manifest from the visual replay integration chain and turns manually supplied
offline replay cases into a guarded coverage run report. It does not read live
data, call APIs, persist scanner state, activate detectors, change scoring,
ranking, actionability, emit alerts, or place orders.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

REPORT_TYPE = "effort_result_visual_replay_shadow_coverage_plan"
REPORT_SCHEMA_VERSION = 1

SOURCE_REPORT_TYPE = "effort_result_visual_replay_shadow_workflow_manifest"
SOURCE_READY_STATUS = "visual_replay_shadow_workflow_manifest_ready"
SOURCE_READY_DECISION = "ready_to_run_shadow_dev_replay_workflow"
SOURCE_ALLOWED_NEXT_STEP = "run_shadow_dev_visual_replay_workflow"

COVERAGE_READY_STATUS = "visual_replay_shadow_coverage_plan_ready"
COVERAGE_BLOCKED_STATUS = "visual_replay_shadow_coverage_plan_blocked"
READY_DECISION = "ready_for_manual_shadow_replay_coverage_review"
BLOCKED_DECISION = "blocked_from_manual_shadow_replay_coverage_review"

DEFAULT_REQUIRED_SYMBOLS = ("LT.NS",)
DEFAULT_REQUIRED_CASES = 2

REQUIRED_CASE_FIELDS = (
    "case_id",
    "symbol",
    "event_week_beginning",
    "target",
    "offline_dataset_fixture",
    "expected_marker_labels",
    "review_lanes",
)

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
    "shadow_coverage_plan_only": True,
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
    "requires_shadow_workflow_manifest": True,
    "requires_offline_dataset_fixture": True,
    "requires_manual_review_after_run": True,
    "requires_separate_production_pr": True,
}


def plan_effort_result_visual_replay_shadow_coverage(
    shadow_workflow_manifest: Mapping[str, Any],
    candidate_cases: Sequence[Mapping[str, Any]],
    *,
    required_symbols: Sequence[str] = DEFAULT_REQUIRED_SYMBOLS,
    min_cases: int = DEFAULT_REQUIRED_CASES,
) -> dict[str, object]:
    """Build a guarded manual shadow replay coverage plan.

    A ready report means the listed offline cases are ready for manual visual
    replay review. It never authorizes live scanner integration, production UI
    activation, scoring, ranking, actionability, detector activation,
    persistence, alerts, or orders.
    """

    if min_cases <= 0:
        raise ValueError("min_cases must be positive")

    symbols = _normalize_symbols(required_symbols)
    cases = [_normalize_case(row) for row in _mapping_rows(candidate_cases)]
    selected_cases = [case for case in cases if not symbols or case["symbol"] in symbols]
    ready_cases = [_build_coverage_case(case) for case in selected_cases]
    ready_count = sum(1 for case in ready_cases if case["coverage_case_ready"] is True)

    blockers = _coverage_blockers(
        shadow_workflow_manifest,
        cases=cases,
        selected_cases=selected_cases,
        coverage_cases=ready_cases,
        required_symbols=symbols,
        min_cases=min_cases,
    )
    ready = not blockers

    return {
        "report_type": REPORT_TYPE,
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "source_report_type": shadow_workflow_manifest.get("report_type"),
        "source_workflow_status": shadow_workflow_manifest.get("workflow_status"),
        "source_workflow_decision": shadow_workflow_manifest.get("workflow_decision"),
        "source_shadow_workflow_ready": shadow_workflow_manifest.get("shadow_workflow_ready"),
        "source_allowed_next_step": shadow_workflow_manifest.get("allowed_next_step"),
        "required_symbols": symbols,
        "minimum_cases": int(min_cases),
        "candidate_case_count": len(cases),
        "selected_case_count": len(selected_cases),
        "ready_case_count": ready_count,
        "blocked_case_count": len(ready_cases) - ready_count,
        "coverage_status": COVERAGE_READY_STATUS if ready else COVERAGE_BLOCKED_STATUS,
        "coverage_decision": READY_DECISION if ready else BLOCKED_DECISION,
        "shadow_coverage_ready": ready,
        "blockers": blockers,
        "required_review_lanes": list(REQUIRED_REVIEW_LANES),
        "coverage_cases": ready_cases,
        "disallowed_production_surfaces": list(DISALLOWED_PRODUCTION_SURFACES),
        "allowed_next_step": (
            "perform_manual_shadow_replay_case_review"
            if ready
            else "resolve_shadow_coverage_plan_blockers"
        ),
        "manual_revalidation_required_after_run": True,
        "production_pr_required_after_shadow_validation": True,
        "automatic_promotion_allowed": False,
        **PRODUCTION_BOUNDARY,
    }


def render_effort_result_visual_replay_shadow_coverage_markdown(report: Mapping[str, Any]) -> str:
    """Render the shadow replay coverage report as Markdown."""

    lines = [
        "# Effort/Result Visual Replay Shadow Coverage Plan",
        "",
        "## Decision",
        "",
        f"- Coverage decision: `{_display(report.get('coverage_decision'))}`",
        f"- Shadow coverage ready: {_bool_text(report.get('shadow_coverage_ready'))}",
        f"- Coverage status: `{_display(report.get('coverage_status'))}`",
        f"- Allowed next step: `{_display(report.get('allowed_next_step'))}`",
        f"- Required symbols: {_csv(report.get('required_symbols', []))}",
        f"- Minimum cases: {int(report.get('minimum_cases', 0))}",
        f"- Selected cases: {int(report.get('selected_case_count', 0))}",
        f"- Ready cases: {int(report.get('ready_case_count', 0))}",
        f"- Blocked cases: {int(report.get('blocked_case_count', 0))}",
        "",
        "## Source Shadow Workflow Manifest",
        "",
        f"- Source report type: `{_display(report.get('source_report_type'))}`",
        f"- Source workflow status: `{_display(report.get('source_workflow_status'))}`",
        f"- Source workflow decision: `{_display(report.get('source_workflow_decision'))}`",
        f"- Source shadow workflow ready: {_bool_text(report.get('source_shadow_workflow_ready'))}",
        f"- Source allowed next step: `{_display(report.get('source_allowed_next_step'))}`",
        "",
        "## Production Boundary",
        "",
        "- Audit/coverage-plan only: true",
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
        "## Coverage Cases",
        "",
    ]

    cases = _mapping_rows(report.get("coverage_cases", []))
    if not cases:
        lines.append("_No candidate cases were selected._")
        lines.append("")
    else:
        lines.extend(
            [
                "| Case | Target | Symbol | Week | Fixture | Ready | Review lanes | Blockers |",
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
                f"{_display(row.get('offline_dataset_fixture'))} | "
                f"{_bool_text(row.get('coverage_case_ready'))} | "
                f"{_csv(row.get('review_lanes', []))} | "
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
            "- Use only offline dataset fixtures and dev-only replay references.",
            "- Validate marker alignment, pre-event context, post-event follow-through, counterfactual quality, VSA/SMC judgment, and evidence traceability.",
            "- Feed reviewed results back into the visual replay evidence chain before any broader integration decision.",
            "- A separate production PR is required before any scoring, ranking, actionability, detector, API, frontend, persistence, alert, or order behavior can change.",
            "",
        ]
    )
    return "\n".join(lines)


def _coverage_blockers(
    shadow_workflow_manifest: Mapping[str, Any],
    *,
    cases: Sequence[Mapping[str, Any]],
    selected_cases: Sequence[Mapping[str, Any]],
    coverage_cases: Sequence[Mapping[str, Any]],
    required_symbols: Sequence[str],
    min_cases: int,
) -> list[str]:
    blockers: list[str] = []

    if shadow_workflow_manifest.get("report_type") != SOURCE_REPORT_TYPE:
        blockers.append("source_report_type_mismatch")
    if shadow_workflow_manifest.get("workflow_status") != SOURCE_READY_STATUS:
        blockers.append("source_workflow_status_not_ready")
    if shadow_workflow_manifest.get("workflow_decision") != SOURCE_READY_DECISION:
        blockers.append("source_workflow_decision_not_ready")
    if shadow_workflow_manifest.get("shadow_workflow_ready") is not True:
        blockers.append("source_shadow_workflow_ready_false")
    if shadow_workflow_manifest.get("allowed_next_step") != SOURCE_ALLOWED_NEXT_STEP:
        blockers.append("source_allowed_next_step_not_shadow_workflow")
    if _string_rows(shadow_workflow_manifest.get("blockers", [])):
        blockers.append("source_workflow_blockers_present")
    if _has_truthy_unsafe_fields(shadow_workflow_manifest):
        blockers.append("source_production_boundary_open")
    if not required_symbols:
        blockers.append("missing_required_symbols")
    if not cases:
        blockers.append("missing_candidate_cases")
    if cases and not selected_cases:
        blockers.append("no_matching_symbol_cases")

    ready_count = sum(1 for case in coverage_cases if case.get("coverage_case_ready") is True)
    if ready_count < min_cases:
        blockers.append("not_enough_ready_coverage_cases")
    if any(case.get("coverage_case_ready") is not True for case in coverage_cases):
        blockers.append("coverage_case_blockers_present")

    return _dedupe(blockers)


def _normalize_case(case: Mapping[str, Any]) -> dict[str, object]:
    expected_marker_labels = _string_rows(case.get("expected_marker_labels", []))
    review_lanes = _string_rows(case.get("review_lanes", []))
    normalized = {
        "case_id": _display(case.get("case_id")).strip(),
        "symbol": _display(case.get("symbol")).strip(),
        "event_week_beginning": _display(case.get("event_week_beginning")).strip(),
        "target": _display(case.get("target")).strip(),
        "offline_dataset_fixture": _display(case.get("offline_dataset_fixture")).strip(),
        "expected_marker_labels": expected_marker_labels,
        "review_lanes": review_lanes,
        "notes": _display(case.get("notes")).strip(),
        "automatic_promotion_allowed": case.get("automatic_promotion_allowed", False),
        "production_change_allowed": case.get("production_change_allowed", False),
    }
    for field in UNSAFE_TRUTHY_FIELDS:
        if field in case:
            normalized[field] = case.get(field)
    return normalized


def _build_coverage_case(case: Mapping[str, Any]) -> dict[str, object]:
    blockers: list[str] = []

    for field in REQUIRED_CASE_FIELDS:
        value = case.get(field)
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            if not _string_rows(value):
                blockers.append(f"missing_{field}")
        elif not _display(value).strip():
            blockers.append(f"missing_{field}")

    lanes = _string_rows(case.get("review_lanes", []))
    missing_lanes = [lane for lane in REQUIRED_REVIEW_LANES if lane not in lanes]
    if missing_lanes:
        blockers.append("missing_required_review_lanes")
    if _has_truthy_unsafe_fields(case):
        blockers.append("case_production_boundary_open")

    return {
        "case_id": case.get("case_id", ""),
        "symbol": case.get("symbol", ""),
        "event_week_beginning": case.get("event_week_beginning", ""),
        "target": case.get("target", ""),
        "offline_dataset_fixture": case.get("offline_dataset_fixture", ""),
        "expected_marker_labels": _string_rows(case.get("expected_marker_labels", [])),
        "review_lanes": lanes,
        "missing_review_lanes": missing_lanes,
        "notes": case.get("notes", ""),
        "coverage_case_ready": not blockers,
        "blockers": blockers,
        "manual_review_only": True,
        "automatic_promotion_allowed": False,
        **PRODUCTION_BOUNDARY,
    }


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
    parser.add_argument("shadow_workflow_manifest", type=Path)
    parser.add_argument("candidate_cases", type=Path)
    parser.add_argument("--symbol", action="append", dest="symbols")
    parser.add_argument("--min-cases", type=int, default=DEFAULT_REQUIRED_CASES)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    manifest = json.loads(args.shadow_workflow_manifest.read_text(encoding="utf-8"))
    cases = json.loads(args.candidate_cases.read_text(encoding="utf-8"))
    report = plan_effort_result_visual_replay_shadow_coverage(
        manifest,
        _mapping_rows(cases),
        required_symbols=args.symbols or DEFAULT_REQUIRED_SYMBOLS,
        min_cases=args.min_cases,
    )
    rendered = (
        render_effort_result_visual_replay_shadow_coverage_markdown(report)
        if args.format == "markdown"
        else json.dumps(report, indent=2, sort_keys=True)
    )
    _write_output(rendered, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
