"""Gate Effort/Result calibration proposals before production review.

This module is audit/gate only. It checks that calibration-design proposals have
explicit manual-review evidence before they can move to a separate production PR
review. It does not change detector activation, scoring, ranking, actionability,
scanner state, persistence, or broker/order behavior.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

REPORT_TYPE = "effort_result_calibration_proposal_gate"
REPORT_SCHEMA_VERSION = 1

PROPOSAL_READY_STATUS = "ready_for_calibration_design_review"
GATE_READY_STATUS = "ready_for_separate_production_pr_review"
GATE_BLOCKED_STATUS = "blocked_pending_manual_review_evidence"
GATE_NEEDS_ATTENTION_STATUS = "needs_attention"
APPROVED_MANUAL_REVIEW_STATUS = "approved_for_calibration_experiment"

PRODUCTION_BOUNDARY = {
    "audit_only": True,
    "gate_only": True,
    "production_change_allowed": False,
    "may_change_scoring": False,
    "may_change_ranking": False,
    "may_change_actionability": False,
    "may_activate_detector": False,
    "requires_manual_case_review": True,
    "requires_separate_production_pr": True,
}

REQUIRED_EVIDENCE_FIELDS = (
    "manual_review_status",
    "reviewer",
    "review_date",
    "reviewed_examples",
    "reviewed_symbols",
    "reviewed_weeks",
)


def build_calibration_proposal_gate_report(
    proposal_report: Mapping[str, Any],
    *,
    manual_review_evidence: Mapping[str, Any] | None = None,
    min_reviewed_examples_per_target: int = 5,
) -> dict[str, object]:
    """Build an audit-only gate report for calibration-design proposals.

    Passing this gate means only that the proposal is ready for a separate
    production PR review. It does not authorize production changes in this PR.
    """

    if min_reviewed_examples_per_target <= 0:
        raise ValueError("min_reviewed_examples_per_target must be positive")

    evidence_by_target = _normalize_evidence(manual_review_evidence or {})
    proposals = _mapping_rows(proposal_report.get("target_proposals", []))
    target_gates = [
        _target_gate(
            proposal,
            evidence=evidence_by_target.get(str(proposal.get("target", ""))),
            min_reviewed_examples_per_target=min_reviewed_examples_per_target,
        )
        for proposal in proposals
    ]
    ready_count = sum(1 for row in target_gates if row["gate_status"] == GATE_READY_STATUS)
    blocked_count = len(target_gates) - ready_count

    return {
        "report_type": REPORT_TYPE,
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "source": proposal_report.get("source"),
        "source_report_type": proposal_report.get("report_type"),
        "rows": int(proposal_report.get("rows", 0)),
        "targets": [str(target) for target in proposal_report.get("targets", [])],
        "target_count": len(target_gates),
        "ready_gate_count": ready_count,
        "blocked_gate_count": blocked_count,
        "gate_status": (
            GATE_READY_STATUS
            if target_gates and ready_count == len(target_gates)
            else GATE_NEEDS_ATTENTION_STATUS
        ),
        "minimum_reviewed_examples_per_target": min_reviewed_examples_per_target,
        "target_gates": target_gates,
        "next_stage": "separate_production_pr_review" if target_gates and ready_count == len(target_gates) else "manual_review_evidence_collection",
        "automatic_promotion_allowed": False,
        **PRODUCTION_BOUNDARY,
    }


def render_calibration_proposal_gate_markdown(report: Mapping[str, Any]) -> str:
    """Render a calibration-proposal gate report as Markdown."""

    lines = [
        "# Effort/Result Calibration Proposal Gate",
        "",
        "## Summary",
        "",
        f"- Source: `{_display(report.get('source'))}`",
        f"- Rows: {int(report.get('rows', 0))}",
        f"- Targets gated: {int(report.get('target_count', 0))}",
        f"- Ready gates: {int(report.get('ready_gate_count', 0))}",
        f"- Blocked gates: {int(report.get('blocked_gate_count', 0))}",
        f"- Gate status: `{_display(report.get('gate_status'))}`",
        f"- Next stage: `{_display(report.get('next_stage'))}`",
        "",
        "## Production Boundary",
        "",
        "- Audit/report only: true",
        "- Gate only: true",
        "- Production change allowed: false",
        "- Automatic promotion allowed: false",
        "- May change scoring: false",
        "- May change ranking: false",
        "- May change actionability: false",
        "- May activate detector: false",
        "- Requires manual case review: true",
        "- Requires separate production PR: true",
        "",
        "## Target Gates",
        "",
    ]

    target_gates = _mapping_rows(report.get("target_gates", []))
    if not target_gates:
        lines.append("_No calibration proposals were available for gate review._")
        lines.append("")
        return "\n".join(lines)

    lines.extend(
        [
            "| Target | Gate status | Proposal status | Evidence status | Reviewed examples | Missing evidence | Reason |",
            "| --- | --- | --- | --- | ---: | --- | --- |",
        ]
    )
    for row in target_gates:
        lines.append(
            "| "
            f"`{_display(row.get('target'))}` | "
            f"`{_display(row.get('gate_status'))}` | "
            f"`{_display(row.get('source_proposal_status'))}` | "
            f"`{_display(row.get('manual_review_status'))}` | "
            f"{int(row.get('reviewed_examples', 0))} | "
            f"{_csv(row.get('missing_evidence_fields', []))} | "
            f"{_display(row.get('reason'))} |"
        )

    lines.extend(["", "## Required Next Actions", ""])
    for row in target_gates:
        lines.append(f"### {_display(row.get('target'))}")
        lines.append("")
        for action in row.get("required_next_actions", []):
            lines.append(f"- {_display(action)}")
        lines.append("")

    return "\n".join(lines)


def _target_gate(
    proposal: Mapping[str, Any],
    *,
    evidence: Mapping[str, Any] | None,
    min_reviewed_examples_per_target: int,
) -> dict[str, object]:
    target = str(proposal.get("target", ""))
    evidence = evidence or {}
    missing = _missing_evidence_fields(evidence)
    reviewed_examples = _to_int(evidence.get("reviewed_examples"))
    manual_review_status = str(evidence.get("manual_review_status", ""))
    reviewed_symbols = _string_list(evidence.get("reviewed_symbols", []))
    reviewed_weeks = _string_list(evidence.get("reviewed_weeks", []))

    readiness_checks = {
        "proposal_ready": str(proposal.get("proposal_status", "")) == PROPOSAL_READY_STATUS,
        "manual_evidence_present": bool(evidence),
        "manual_review_status_approved": manual_review_status == APPROVED_MANUAL_REVIEW_STATUS,
        "reviewer_recorded": bool(str(evidence.get("reviewer", "")).strip()),
        "review_date_recorded": bool(str(evidence.get("review_date", "")).strip()),
        "minimum_examples_reviewed": reviewed_examples >= min_reviewed_examples_per_target,
        "symbols_reviewed": bool(reviewed_symbols),
        "weeks_reviewed": bool(reviewed_weeks),
    }
    ready = all(readiness_checks.values())
    missing_checks = [name for name, passed in readiness_checks.items() if not passed]

    return {
        "target": target,
        "gate_status": GATE_READY_STATUS if ready else GATE_BLOCKED_STATUS,
        "source_proposal_status": str(proposal.get("proposal_status", "")),
        "candidate_direction": str(proposal.get("candidate_direction", "")),
        "proposed_signal_role": str(proposal.get("proposed_signal_role", "")),
        "matched_bars": int(proposal.get("matched_bars", 0)),
        "exported_examples": int(proposal.get("exported_examples", 0)),
        "manual_review_status": manual_review_status,
        "reviewer": str(evidence.get("reviewer", "")),
        "review_date": str(evidence.get("review_date", "")),
        "reviewed_examples": reviewed_examples,
        "reviewed_symbols": reviewed_symbols,
        "reviewed_weeks": reviewed_weeks,
        "missing_evidence_fields": missing,
        "failed_gate_checks": missing_checks,
        "readiness_checks": readiness_checks,
        "required_next_actions": _required_next_actions(
            target=target,
            ready=ready,
            failed_gate_checks=missing_checks,
        ),
        "reason": _gate_reason(ready=ready, failed_gate_checks=missing_checks),
        **PRODUCTION_BOUNDARY,
    }


def _missing_evidence_fields(evidence: Mapping[str, Any]) -> list[str]:
    if not evidence:
        return list(REQUIRED_EVIDENCE_FIELDS)
    missing = []
    for field in REQUIRED_EVIDENCE_FIELDS:
        value = evidence.get(field)
        if value is None or value == "" or value == []:
            missing.append(field)
    return missing


def _required_next_actions(
    *, target: str, ready: bool, failed_gate_checks: Sequence[str]
) -> list[str]:
    if ready:
        return [
            f"Keep `{target}` blocked from automatic promotion.",
            "Open a separate production PR if scoring, ranking, actionability, or activation changes are proposed.",
            "Attach manual-review evidence and out-of-sample validation to that separate PR.",
        ]
    return [
        f"Collect manual chart-review evidence for `{target}`.",
        "Record reviewer, review date, reviewed examples, reviewed symbols, and reviewed weeks.",
        "Mark manual_review_status as approved_for_calibration_experiment only after human review.",
        "Keep production scoring, ranking, actionability, and detector activation unchanged.",
        "Failed gate checks: " + ", ".join(failed_gate_checks),
    ]


def _gate_reason(*, ready: bool, failed_gate_checks: Sequence[str]) -> str:
    if ready:
        return "manual-review evidence is complete for separate production PR review"
    return "blocked until these checks pass: " + ", ".join(failed_gate_checks)


def _normalize_evidence(value: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    if "targets" in value:
        targets = _mapping_rows(value.get("targets", []))
        return {
            str(row.get("target", "")): row
            for row in targets
            if str(row.get("target", "")).strip()
        }
    normalized: dict[str, Mapping[str, Any]] = {}
    for target, evidence in value.items():
        if isinstance(evidence, Mapping):
            normalized[str(target)] = evidence
    return normalized


def _mapping_rows(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
        return []
    return [row for row in value if isinstance(row, Mapping)]


def _string_list(value: object) -> list[str]:
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
        return []
    return sorted({str(item) for item in value if str(item).strip()})


def _to_int(value: object) -> int:
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


def _parse_evidence(path: Path | None) -> Mapping[str, Any]:
    if path is None:
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gate audit-only Effort/Result calibration proposals."
    )
    parser.add_argument("proposal_path", type=Path)
    parser.add_argument("--manual-review-evidence", type=Path)
    parser.add_argument("--min-reviewed-examples-per-target", type=int, default=5)
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="markdown",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    proposal = json.loads(args.proposal_path.read_text(encoding="utf-8"))
    evidence = _parse_evidence(args.manual_review_evidence)
    report = build_calibration_proposal_gate_report(
        proposal,
        manual_review_evidence=evidence,
        min_reviewed_examples_per_target=args.min_reviewed_examples_per_target,
    )
    rendered = (
        render_calibration_proposal_gate_markdown(report)
        if args.format == "markdown"
        else json.dumps(report, indent=2, sort_keys=True)
    )
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
