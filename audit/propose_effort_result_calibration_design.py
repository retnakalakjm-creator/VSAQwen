"""Propose Effort/Result calibration design from reviewed casebooks.

This module is audit/proposal only. It converts casebook-review summaries into
bounded calibration-design proposals so reviewers can decide what to inspect
next. It does not change detector activation, scoring, ranking, actionability,
scanner state, persistence, or broker/order behavior.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

REPORT_TYPE = "effort_result_calibration_design_proposal"
REPORT_SCHEMA_VERSION = 1

DEFAULT_TARGETS = (
    "RESULT_GT_EFFORT",
    "EFFORT_RESULT+SUPPLY_COMING_IN",
)
DEFAULT_HORIZONS = (1, 2, 4)

CASEBOOK_READY_STATUS = "ready_for_manual_visual_review"
PROPOSAL_READY_STATUS = "ready_for_calibration_design_review"
PROPOSAL_BLOCKED_STATUS = "blocked_pending_manual_review_inputs"
PROPOSAL_NEEDS_ATTENTION_STATUS = "needs_attention"

PRODUCTION_BOUNDARY = {
    "audit_only": True,
    "proposal_only": True,
    "may_change_scoring": False,
    "may_change_ranking": False,
    "may_change_actionability": False,
    "may_activate_detector": False,
    "requires_manual_case_review": True,
    "requires_separate_production_pr": True,
}


def build_calibration_design_proposal(
    casebook_review_report: Mapping[str, Any],
    *,
    min_examples_per_target: int = 5,
) -> dict[str, object]:
    """Build a proposal-only calibration design report.

    A ready proposal is permission to design a calibration experiment only. It is
    not permission to change production scoring, ranking, actionability,
    detector activation, persistence, or broker/order behavior.
    """

    if min_examples_per_target <= 0:
        raise ValueError("min_examples_per_target must be positive")

    target_reviews = _mapping_rows(casebook_review_report.get("target_reviews", []))
    proposals = [
        _target_proposal(row, min_examples_per_target=min_examples_per_target)
        for row in target_reviews
    ]
    ready_count = sum(
        1 for row in proposals if row["proposal_status"] == PROPOSAL_READY_STATUS
    )
    blocked_count = len(proposals) - ready_count

    return {
        "report_type": REPORT_TYPE,
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "source": casebook_review_report.get("source"),
        "source_report_type": casebook_review_report.get("report_type"),
        "rows": int(casebook_review_report.get("rows", 0)),
        "targets": [str(target) for target in casebook_review_report.get("targets", [])],
        "horizons": _int_list(casebook_review_report.get("horizons", DEFAULT_HORIZONS)),
        "target_count": len(proposals),
        "ready_proposal_count": ready_count,
        "blocked_proposal_count": blocked_count,
        "proposal_status": (
            PROPOSAL_READY_STATUS
            if proposals and ready_count == len(proposals)
            else PROPOSAL_NEEDS_ATTENTION_STATUS
        ),
        "minimum_examples_per_target": min_examples_per_target,
        "target_proposals": proposals,
        "next_stage": "manual_calibration_design_review",
        "production_change_allowed": False,
        **PRODUCTION_BOUNDARY,
    }


def render_calibration_design_markdown(report: Mapping[str, Any]) -> str:
    """Render a calibration-design proposal as human-readable Markdown."""

    lines = [
        "# Effort/Result Calibration Design Proposal",
        "",
        "## Summary",
        "",
        f"- Source: `{_display(report.get('source'))}`",
        f"- Rows: {int(report.get('rows', 0))}",
        f"- Targets proposed: {int(report.get('target_count', 0))}",
        f"- Ready proposals: {int(report.get('ready_proposal_count', 0))}",
        f"- Blocked proposals: {int(report.get('blocked_proposal_count', 0))}",
        f"- Proposal status: `{_display(report.get('proposal_status'))}`",
        f"- Next stage: `{_display(report.get('next_stage'))}`",
        "",
        "## Production Boundary",
        "",
        "- Audit/report only: true",
        "- Proposal only: true",
        "- Production change allowed: false",
        "- May change scoring: false",
        "- May change ranking: false",
        "- May change actionability: false",
        "- May activate detector: false",
        "- Requires manual case review: true",
        "- Requires separate production PR: true",
        "",
        "## Target Proposals",
        "",
    ]

    proposals = _mapping_rows(report.get("target_proposals", []))
    if not proposals:
        lines.append("_No target proposals were available._")
        lines.append("")
        return "\n".join(lines)

    lines.extend(
        [
            "| Target | Status | Direction | Role | Examples | Symbols | Horizon means | Reason |",
            "| --- | --- | --- | --- | ---: | --- | --- | --- |",
        ]
    )
    for row in proposals:
        lines.append(
            "| "
            f"`{_display(row.get('target'))}` | "
            f"`{_display(row.get('proposal_status'))}` | "
            f"{_display(row.get('candidate_direction'))} | "
            f"{_display(row.get('proposed_signal_role'))} | "
            f"{int(row.get('exported_examples', 0))} | "
            f"{_csv(row.get('symbols', []))} | "
            f"{_horizon_mean_summary(row.get('horizon_summaries', []))} | "
            f"{_display(row.get('reason'))} |"
        )

    lines.extend(["", "## Required Review Steps", ""])
    for row in proposals:
        lines.append(f"### {_display(row.get('target'))}")
        lines.append("")
        for step in row.get("proposed_calibration_work", []):
            lines.append(f"- {_display(step)}")
        lines.append("")

    return "\n".join(lines)


def _target_proposal(
    target_review: Mapping[str, Any],
    *,
    min_examples_per_target: int,
) -> dict[str, object]:
    target = str(target_review.get("target", ""))
    exported_examples = int(target_review.get("exported_examples", 0))
    review_status = str(target_review.get("review_status", ""))
    horizon_summaries = _mapping_rows(target_review.get("horizon_summaries", []))
    direction = _candidate_direction(horizon_summaries)
    readiness_checks = {
        "casebook_ready": review_status == CASEBOOK_READY_STATUS,
        "has_minimum_examples": exported_examples >= min_examples_per_target,
        "has_forward_outcomes": any(
            int(row.get("examples_with_forward_return", 0)) > 0
            for row in horizon_summaries
        ),
        "direction_review_available": direction in {"positive", "negative", "mixed"},
    }
    ready = all(readiness_checks.values())

    return {
        "target": target,
        "proposal_status": PROPOSAL_READY_STATUS if ready else PROPOSAL_BLOCKED_STATUS,
        "source_review_status": review_status,
        "matched_bars": int(target_review.get("matched_bars", 0)),
        "exported_examples": exported_examples,
        "minimum_examples_required": min_examples_per_target,
        "symbols": [str(symbol) for symbol in target_review.get("symbols", [])],
        "first_week": _display(target_review.get("first_week")),
        "last_week": _display(target_review.get("last_week")),
        "horizon_summaries": [dict(row) for row in horizon_summaries],
        "candidate_direction": direction,
        "proposed_signal_role": _signal_role(direction),
        "readiness_checks": readiness_checks,
        "proposed_calibration_work": _calibration_work(target=target, direction=direction),
        "calibration_design_constraints": [
            "manual_visual_case_review_required_before_calibration",
            "candidate_thresholds_must_be_validated_out_of_sample",
            "do_not_change_existing_detector_output_in_this_stage",
            "do_not_change_scoring_ranking_or_actionability_in_this_stage",
            "use_a_separate_production_pr_for_any_activation_or_weighting",
        ],
        "reason": _proposal_reason(ready=ready, readiness_checks=readiness_checks),
        **PRODUCTION_BOUNDARY,
    }


def _candidate_direction(horizon_summaries: Sequence[Mapping[str, Any]]) -> str:
    signs = []
    for row in horizon_summaries:
        examples = int(row.get("examples_with_forward_return", 0))
        mean_return = _to_float(row.get("mean_forward_return"))
        if examples <= 0 or mean_return is None:
            continue
        if mean_return > 0:
            signs.append("positive")
        elif mean_return < 0:
            signs.append("negative")
        else:
            signs.append("flat")
    non_flat = {sign for sign in signs if sign != "flat"}
    if len(non_flat) == 1:
        return next(iter(non_flat))
    if len(non_flat) > 1:
        return "mixed"
    if signs:
        return "flat"
    return "unknown"


def _signal_role(direction: str) -> str:
    if direction == "negative":
        return "bearish_calibration_candidate"
    if direction == "positive":
        return "bullish_calibration_candidate"
    if direction == "mixed":
        return "direction_sensitive_calibration_candidate"
    return "manual_direction_review_required"


def _calibration_work(*, target: str, direction: str) -> list[str]:
    role = _signal_role(direction)
    return [
        f"Review bounded chart examples for `{target}` and mark true/false positives.",
        f"Treat the target as `{role}` only for calibration-design review.",
        "Compare candidate weeks against nearby non-candidate bars for false-positive pressure.",
        "Stress-test relationship/event thresholds across horizons before proposing weights.",
        "Document any proposed scoring or activation change in a separate production PR.",
    ]


def _proposal_reason(*, ready: bool, readiness_checks: Mapping[str, bool]) -> str:
    if ready:
        return "manual-review inputs are sufficient to design a calibration experiment"
    failed = [name for name, passed in readiness_checks.items() if not passed]
    return "blocked until these checks pass: " + ", ".join(failed)


def _mapping_rows(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
        return []
    return [row for row in value if isinstance(row, Mapping)]


def _int_list(value: object) -> list[int]:
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
        return []
    return sorted({int(item) for item in value})


def _to_float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _display(value: object) -> str:
    if value is None:
        return ""
    return str(value)


def _csv(value: object) -> str:
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
        return ""
    return ", ".join(str(item) for item in value)


def _fmt_float(value: object) -> str:
    converted = _to_float(value)
    if converted is None:
        return ""
    return f"{converted:.4f}"


def _horizon_mean_summary(value: object) -> str:
    rows = _mapping_rows(value)
    parts = []
    for row in rows:
        parts.append(
            f"{int(row.get('horizon', 0))}w: {_fmt_float(row.get('mean_forward_return'))}"
        )
    return "<br>".join(parts)


def _parse_csv(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


def _parse_horizons(value: str) -> tuple[int, ...]:
    horizons = tuple(int(part.strip()) for part in value.split(",") if part.strip())
    if not horizons:
        raise ValueError("at least one horizon is required")
    return horizons


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Propose audit-only Effort/Result calibration design."
    )
    parser.add_argument("path", type=Path)
    parser.add_argument(
        "--targets",
        default=",".join(DEFAULT_TARGETS),
        help="Comma-separated casebook target conditions.",
    )
    parser.add_argument("--horizons", default=",".join(str(h) for h in DEFAULT_HORIZONS))
    parser.add_argument("--max-examples-per-target", type=int, default=20)
    parser.add_argument("--min-examples-per-target", type=int, default=5)
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="markdown",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    from audit.export_effort_result_casebook import build_effort_result_casebook
    from audit.review_effort_result_casebook import build_casebook_review_report

    casebook = build_effort_result_casebook(
        args.path,
        targets=_parse_csv(args.targets),
        horizons=_parse_horizons(args.horizons),
        max_examples_per_target=args.max_examples_per_target,
    )
    casebook_review = build_casebook_review_report(casebook)
    proposal = build_calibration_design_proposal(
        casebook_review,
        min_examples_per_target=args.min_examples_per_target,
    )
    rendered = (
        render_calibration_design_markdown(proposal)
        if args.format == "markdown"
        else json.dumps(proposal, indent=2, sort_keys=True)
    )
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
