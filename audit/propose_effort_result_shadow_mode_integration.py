"""Proposal-only Effort/Result shadow-mode integration plan.

This module is design/proposal only. It consumes the calibration-proposal gate
output and prepares a shadow-mode integration plan for manually approved
Effort/Result targets. It does not activate detectors, change scoring, ranking,
actionability, scanner state, persistence, broker/order/account behavior, API,
or frontend behavior.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

REPORT_TYPE = "effort_result_shadow_mode_integration_proposal"
REPORT_SCHEMA_VERSION = 1

GATE_READY_STATUS = "ready_for_separate_production_pr_review"
APPROVED_MANUAL_REVIEW_STATUS = "approved_for_calibration_experiment"
SHADOW_PROPOSAL_READY_STATUS = "ready_for_shadow_mode_pr_review"
SHADOW_PROPOSAL_BLOCKED_STATUS = "blocked_pending_passed_gate"
SHADOW_PROPOSAL_NEEDS_ATTENTION_STATUS = "needs_attention"

DEFAULT_TARGET_ROLES = {
    "RESULT_GT_EFFORT": "direction_sensitive_shadow_observation",
    "EFFORT_RESULT+SUPPLY_COMING_IN": "bearish_shadow_observation",
}

PRODUCTION_BOUNDARY = {
    "proposal_only": True,
    "shadow_mode_only": True,
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
    "requires_manual_case_review": True,
    "requires_passed_calibration_gate": True,
    "requires_separate_production_pr": True,
}


def build_shadow_mode_integration_proposal(
    gate_report: Mapping[str, Any],
    *,
    target_roles: Mapping[str, str] | None = None,
    min_reviewed_examples_per_target: int = 5,
) -> dict[str, object]:
    """Build a proposal-only shadow-mode integration plan from gate output.

    A ready proposal means the target has passed the audit gate and can be
    reviewed in a separate PR for shadow-mode observation only. It does not
    authorize production scoring, ranking, actionability, or detector activation.
    """

    if min_reviewed_examples_per_target <= 0:
        raise ValueError("min_reviewed_examples_per_target must be positive")

    roles = {**DEFAULT_TARGET_ROLES, **dict(target_roles or {})}
    gates = _mapping_rows(gate_report.get("target_gates", []))
    target_proposals = [
        _target_shadow_proposal(
            gate,
            role=roles.get(str(gate.get("target", "")).strip(), "manual_shadow_observation"),
            min_reviewed_examples_per_target=min_reviewed_examples_per_target,
        )
        for gate in gates
    ]
    ready_count = sum(
        1
        for row in target_proposals
        if row["proposal_status"] == SHADOW_PROPOSAL_READY_STATUS
    )
    blocked_count = len(target_proposals) - ready_count
    all_ready = bool(target_proposals) and ready_count == len(target_proposals)

    return {
        "report_type": REPORT_TYPE,
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "source_report_type": gate_report.get("report_type"),
        "source_gate_status": gate_report.get("gate_status"),
        "target_count": len(target_proposals),
        "ready_target_count": ready_count,
        "blocked_target_count": blocked_count,
        "proposal_status": (
            SHADOW_PROPOSAL_READY_STATUS
            if all_ready
            else SHADOW_PROPOSAL_NEEDS_ATTENTION_STATUS
        ),
        "minimum_reviewed_examples_per_target": min_reviewed_examples_per_target,
        "target_proposals": target_proposals,
        "integration_contract": _integration_contract(target_proposals),
        "next_stage": (
            "separate_shadow_mode_pr_review"
            if all_ready
            else "complete_calibration_gate_evidence"
        ),
        "automatic_promotion_allowed": False,
        **PRODUCTION_BOUNDARY,
    }


def render_shadow_mode_integration_markdown(report: Mapping[str, Any]) -> str:
    """Render a shadow-mode integration proposal as Markdown."""

    lines = [
        "# Effort/Result Shadow-Mode Integration Proposal",
        "",
        "## Summary",
        "",
        f"- Source report type: `{_display(report.get('source_report_type'))}`",
        f"- Source gate status: `{_display(report.get('source_gate_status'))}`",
        f"- Targets proposed: {int(report.get('target_count', 0))}",
        f"- Ready targets: {int(report.get('ready_target_count', 0))}",
        f"- Blocked targets: {int(report.get('blocked_target_count', 0))}",
        f"- Proposal status: `{_display(report.get('proposal_status'))}`",
        f"- Next stage: `{_display(report.get('next_stage'))}`",
        "",
        "## Production Boundary",
        "",
        "- Proposal only: true",
        "- Shadow mode only: true",
        "- Production change allowed: false",
        "- Automatic promotion allowed: false",
        "- May change scoring: false",
        "- May change ranking: false",
        "- May change actionability: false",
        "- May activate detector: false",
        "- May change scanner state: false",
        "- May change persistence: false",
        "- May change broker/orders/account state: false",
        "- May change API/frontend behavior: false",
        "",
        "## Target Proposals",
        "",
    ]

    targets = _mapping_rows(report.get("target_proposals", []))
    if not targets:
        lines.append("_No gated targets were available for shadow-mode proposal._")
        lines.append("")
        return "\n".join(lines)

    lines.extend(
        [
            "| Target | Status | Role | Reviewed examples | Symbols | Weeks | Blockers |",
            "| --- | --- | --- | ---: | --- | --- | --- |",
        ]
    )
    for row in targets:
        lines.append(
            "| "
            f"`{_display(row.get('target'))}` | "
            f"`{_display(row.get('proposal_status'))}` | "
            f"`{_display(row.get('shadow_signal_role'))}` | "
            f"{int(row.get('reviewed_examples', 0))} | "
            f"{_csv(row.get('reviewed_symbols', []))} | "
            f"{_csv(row.get('reviewed_weeks', []))} | "
            f"{_csv(row.get('blockers', []))} |"
        )

    lines.extend(
        [
            "",
            "## Shadow-Mode Contract",
            "",
            "- Emit observation-only Effort/Result facts.",
            "- Keep any detector activation behind a disabled shadow flag.",
            "- Do not include the shadow facts in production scores, ranks, alerts, or actionability.",
            "- Do not change API/frontend behavior in this proposal.",
            "- Require a later, separate production PR before any user-facing behavior changes.",
            "",
        ]
    )
    return "\n".join(lines)


def _target_shadow_proposal(
    gate: Mapping[str, Any],
    *,
    role: str,
    min_reviewed_examples_per_target: int,
) -> dict[str, object]:
    target = str(gate.get("target", "")).strip()
    gate_status = str(gate.get("gate_status", "")).strip()
    evidence = gate.get("manual_review_evidence") if isinstance(gate.get("manual_review_evidence"), Mapping) else {}

    reviewed_examples = _int_or_zero(
        gate.get("reviewed_examples", _mapping_value(evidence, "reviewed_examples", 0))
    )
    reviewed_symbols = _list_value(
        gate.get("reviewed_symbols", _mapping_value(evidence, "reviewed_symbols", []))
    )
    reviewed_weeks = _list_value(
        gate.get("reviewed_weeks", _mapping_value(evidence, "reviewed_weeks", []))
    )
    manual_review_status = str(
        gate.get("manual_review_status", _mapping_value(evidence, "manual_review_status", ""))
    ).strip()

    readiness_checks = {
        "gate_ready": gate_status == GATE_READY_STATUS,
        "manual_review_approved": manual_review_status == APPROVED_MANUAL_REVIEW_STATUS,
        "minimum_reviewed_examples": reviewed_examples >= min_reviewed_examples_per_target,
        "symbols_reviewed": bool(reviewed_symbols),
        "weeks_reviewed": bool(reviewed_weeks),
    }
    blockers = [name for name, passed in readiness_checks.items() if not passed]
    ready = not blockers

    return {
        "target": target,
        "proposal_status": (
            SHADOW_PROPOSAL_READY_STATUS if ready else SHADOW_PROPOSAL_BLOCKED_STATUS
        ),
        "source_gate_status": gate_status,
        "manual_review_status": manual_review_status,
        "shadow_signal_role": role,
        "reviewed_examples": reviewed_examples,
        "reviewed_symbols": reviewed_symbols,
        "reviewed_weeks": reviewed_weeks,
        "reviewer": _display(gate.get("reviewer", _mapping_value(evidence, "reviewer", ""))),
        "review_date": _display(gate.get("review_date", _mapping_value(evidence, "review_date", ""))),
        "readiness_checks": readiness_checks,
        "blockers": blockers,
        "shadow_mode_observation": {
            "emit_observation": ready,
            "include_in_scoring": False,
            "include_in_ranking": False,
            "include_in_actionability": False,
            "activate_detector": False,
            "api_visible": False,
            "frontend_visible": False,
            "persist_as_production_signal": False,
        },
        "required_later_pr_checks": [
            "wire behind disabled shadow-mode flag",
            "observe output on historical and live-replay data",
            "compare against manual casebook expectations",
            "require separate production PR before any scoring or actionability use",
        ],
        **PRODUCTION_BOUNDARY,
    }


def _integration_contract(targets: Sequence[Mapping[str, Any]]) -> dict[str, object]:
    ready_targets = [
        str(row.get("target", ""))
        for row in targets
        if row.get("proposal_status") == SHADOW_PROPOSAL_READY_STATUS
    ]
    return {
        "ready_targets": ready_targets,
        "observation_payload_fields": [
            "target",
            "symbol",
            "week_beginning",
            "relationship",
            "event_label",
            "shadow_signal_role",
            "source_gate_status",
            "manual_review_status",
        ],
        "must_remain_disabled_for": [
            "production_scoring",
            "ranking",
            "actionability",
            "alerts",
            "orders",
            "api_responses",
            "frontend_display",
        ],
        "recommended_shadow_checks": [
            "casebook replay agreement",
            "symbol/week coverage",
            "duplicate emission guard",
            "no production payload inclusion",
        ],
        "production_change_allowed": False,
        "automatic_promotion_allowed": False,
    }


def _mapping_rows(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
        return []
    return [row for row in value if isinstance(row, Mapping)]


def _mapping_value(mapping: object, key: str, default: object) -> object:
    if isinstance(mapping, Mapping):
        return mapping.get(key, default)
    return default


def _list_value(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (str, bytes)):
        return [_display(value)] if _display(value) else []
    if isinstance(value, Iterable):
        return sorted({_display(item) for item in value if _display(item)})
    return []


def _int_or_zero(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _display(value: object) -> str:
    if value is None:
        return ""
    return str(value)


def _csv(value: object) -> str:
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
        return ""
    return ", ".join(str(item) for item in value)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a proposal-only Effort/Result shadow-mode integration plan."
    )
    parser.add_argument("gate_report_path", type=Path)
    parser.add_argument("--min-reviewed-examples-per-target", type=int, default=5)
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="markdown",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    gate_report = json.loads(args.gate_report_path.read_text(encoding="utf-8"))
    report = build_shadow_mode_integration_proposal(
        gate_report,
        min_reviewed_examples_per_target=args.min_reviewed_examples_per_target,
    )
    rendered = (
        render_shadow_mode_integration_markdown(report)
        if args.format == "markdown"
        else json.dumps(report, indent=2, sort_keys=True)
    )

    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
