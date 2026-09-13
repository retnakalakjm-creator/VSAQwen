"""Export Effort/Result manual-review evidence templates.

This module is audit/template only. It converts calibration-design proposals and
optional casebook examples into a fillable manual visual-review evidence sheet.
It does not change detector activation, scoring, ranking, actionability,
scanner state, persistence, or broker/order behavior.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

REPORT_TYPE = "effort_result_manual_review_evidence_template"
REPORT_SCHEMA_VERSION = 1

PROPOSAL_READY_STATUS = "ready_for_calibration_design_review"
REVIEW_STATUS_PENDING = "pending_manual_review"
APPROVED_MANUAL_REVIEW_STATUS = "approved_for_calibration_experiment"

PRODUCTION_BOUNDARY = {
    "audit_only": True,
    "template_only": True,
    "production_change_allowed": False,
    "may_change_scoring": False,
    "may_change_ranking": False,
    "may_change_actionability": False,
    "may_activate_detector": False,
    "requires_manual_case_review": True,
    "requires_separate_production_pr": True,
}

REVIEW_COLUMNS = (
    "target",
    "candidate_direction",
    "proposed_signal_role",
    "source_proposal_status",
    "matched_bars",
    "exported_examples",
    "example_rank",
    "symbol",
    "week_beginning",
    "forward_return_1",
    "forward_return_2",
    "forward_return_4",
    "reviewer",
    "review_date",
    "manual_review_status",
    "visual_label",
    "true_false_positive_label",
    "structure_context",
    "reviewer_notes",
    "approved_for_calibration_design",
)

REVIEW_STATUS_OPTIONS = (
    REVIEW_STATUS_PENDING,
    APPROVED_MANUAL_REVIEW_STATUS,
    "rejected_for_calibration_experiment",
    "needs_more_review",
)

VISUAL_LABEL_OPTIONS = (
    "true_positive",
    "false_positive",
    "uncertain",
    "not_applicable",
)

TRUE_FALSE_POSITIVE_OPTIONS = (
    "true_positive",
    "false_positive",
    "uncertain",
)


def build_manual_review_evidence_template(
    proposal_report: Mapping[str, Any],
    *,
    casebook_report: Mapping[str, Any] | None = None,
    max_examples_per_target: int = 20,
) -> dict[str, object]:
    """Build a fillable manual visual-review evidence template.

    The resulting rows are meant to be filled by a reviewer and passed back into
    the calibration-proposal gate. They do not authorize production changes.
    """

    if max_examples_per_target <= 0:
        raise ValueError("max_examples_per_target must be positive")

    proposals = _mapping_rows(proposal_report.get("target_proposals", []))
    casebooks = _casebooks_by_target(casebook_report or {})
    rows: list[dict[str, object]] = []
    target_summaries = []

    for proposal in proposals:
        target = str(proposal.get("target", ""))
        examples = casebooks.get(target, [])[:max_examples_per_target]
        target_rows = _rows_for_target(
            proposal,
            examples=examples,
            max_examples_per_target=max_examples_per_target,
        )
        rows.extend(target_rows)
        target_summaries.append(
            {
                "target": target,
                "source_proposal_status": str(proposal.get("proposal_status", "")),
                "candidate_direction": str(proposal.get("candidate_direction", "")),
                "proposed_signal_role": str(proposal.get("proposed_signal_role", "")),
                "matched_bars": int(proposal.get("matched_bars", 0)),
                "exported_examples": int(proposal.get("exported_examples", 0)),
                "template_rows": len(target_rows),
                "casebook_examples_available": len(examples),
                "requires_manual_review": True,
                **PRODUCTION_BOUNDARY,
            }
        )

    return {
        "report_type": REPORT_TYPE,
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "source": proposal_report.get("source"),
        "source_report_type": proposal_report.get("report_type"),
        "rows": int(proposal_report.get("rows", 0)),
        "targets": [str(target) for target in proposal_report.get("targets", [])],
        "target_count": len(proposals),
        "template_row_count": len(rows),
        "max_examples_per_target": max_examples_per_target,
        "review_columns": list(REVIEW_COLUMNS),
        "review_status_options": list(REVIEW_STATUS_OPTIONS),
        "visual_label_options": list(VISUAL_LABEL_OPTIONS),
        "true_false_positive_options": list(TRUE_FALSE_POSITIVE_OPTIONS),
        "target_summaries": target_summaries,
        "review_rows": rows,
        "next_stage": "manual_visual_review",
        "automatic_promotion_allowed": False,
        **PRODUCTION_BOUNDARY,
    }


def render_manual_review_template_markdown(report: Mapping[str, Any]) -> str:
    """Render a manual-review evidence template as Markdown."""

    lines = [
        "# Effort/Result Manual Review Evidence Template",
        "",
        "## Summary",
        "",
        f"- Source: `{_display(report.get('source'))}`",
        f"- Targets: {int(report.get('target_count', 0))}",
        f"- Template rows: {int(report.get('template_row_count', 0))}",
        f"- Max examples per target: {int(report.get('max_examples_per_target', 0))}",
        f"- Next stage: `{_display(report.get('next_stage'))}`",
        "",
        "## Production Boundary",
        "",
        "- Audit/report only: true",
        "- Template only: true",
        "- Production change allowed: false",
        "- Automatic promotion allowed: false",
        "- May change scoring: false",
        "- May change ranking: false",
        "- May change actionability: false",
        "- May activate detector: false",
        "- Requires manual case review: true",
        "- Requires separate production PR: true",
        "",
        "## Reviewer Instructions",
        "",
        "- Fill reviewer, review_date, manual_review_status, visual_label, true_false_positive_label, structure_context, reviewer_notes, and approved_for_calibration_design.",
        "- Do not set manual_review_status to approved_for_calibration_experiment unless the chart example was manually reviewed.",
        "- This template is evidence collection only and cannot promote a signal automatically.",
        "",
        "## Target Summary",
        "",
    ]

    target_summaries = _mapping_rows(report.get("target_summaries", []))
    if target_summaries:
        lines.extend(
            [
                "| Target | Proposal status | Direction | Role | Matched bars | Exported examples | Template rows |",
                "| --- | --- | --- | --- | ---: | ---: | ---: |",
            ]
        )
        for row in target_summaries:
            lines.append(
                "| "
                f"`{_display(row.get('target'))}` | "
                f"`{_display(row.get('source_proposal_status'))}` | "
                f"{_display(row.get('candidate_direction'))} | "
                f"{_display(row.get('proposed_signal_role'))} | "
                f"{int(row.get('matched_bars', 0))} | "
                f"{int(row.get('exported_examples', 0))} | "
                f"{int(row.get('template_rows', 0))} |"
            )
    else:
        lines.append("_No proposal targets were available._")

    lines.extend(["", "## Review Rows", ""])
    review_rows = _mapping_rows(report.get("review_rows", []))
    if not review_rows:
        lines.append("_No review rows were generated._")
        lines.append("")
        return "\n".join(lines)

    lines.extend(
        [
            "| Target | Rank | Symbol | Week | Direction | 1w | 2w | 4w | Manual status | Visual label | Approved |",
            "| --- | ---: | --- | --- | --- | ---: | ---: | ---: | --- | --- | --- |",
        ]
    )
    for row in review_rows:
        lines.append(
            "| "
            f"`{_display(row.get('target'))}` | "
            f"{int(row.get('example_rank', 0))} | "
            f"{_display(row.get('symbol'))} | "
            f"{_display(row.get('week_beginning'))} | "
            f"{_display(row.get('candidate_direction'))} | "
            f"{_fmt_float(row.get('forward_return_1'))} | "
            f"{_fmt_float(row.get('forward_return_2'))} | "
            f"{_fmt_float(row.get('forward_return_4'))} | "
            f"`{_display(row.get('manual_review_status'))}` | "
            f"{_display(row.get('visual_label'))} | "
            f"{_display(row.get('approved_for_calibration_design'))} |"
        )
    lines.append("")
    return "\n".join(lines)


def render_manual_review_template_csv(report: Mapping[str, Any]) -> str:
    """Render review rows to CSV using the stable evidence-template columns."""

    from io import StringIO

    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(REVIEW_COLUMNS), extrasaction="ignore")
    writer.writeheader()
    for row in _mapping_rows(report.get("review_rows", [])):
        writer.writerow({column: row.get(column, "") for column in REVIEW_COLUMNS})
    return buffer.getvalue()


def _rows_for_target(
    proposal: Mapping[str, Any],
    *,
    examples: Sequence[Mapping[str, Any]],
    max_examples_per_target: int,
) -> list[dict[str, object]]:
    if examples:
        return [
            _review_row(proposal, example=example, rank=rank)
            for rank, example in enumerate(examples[:max_examples_per_target], start=1)
        ]
    return [_review_row(proposal, example={}, rank=1)]


def _review_row(
    proposal: Mapping[str, Any],
    *,
    example: Mapping[str, Any],
    rank: int,
) -> dict[str, object]:
    return {
        "target": str(proposal.get("target", "")),
        "candidate_direction": str(proposal.get("candidate_direction", "")),
        "proposed_signal_role": str(proposal.get("proposed_signal_role", "")),
        "source_proposal_status": str(proposal.get("proposal_status", "")),
        "matched_bars": int(proposal.get("matched_bars", 0)),
        "exported_examples": int(proposal.get("exported_examples", 0)),
        "example_rank": rank,
        "symbol": _display(example.get("symbol")),
        "week_beginning": _display(example.get("week_beginning")),
        "forward_return_1": _display(example.get("forward_return_1")),
        "forward_return_2": _display(example.get("forward_return_2")),
        "forward_return_4": _display(example.get("forward_return_4")),
        "reviewer": "",
        "review_date": "",
        "manual_review_status": REVIEW_STATUS_PENDING,
        "visual_label": "",
        "true_false_positive_label": "",
        "structure_context": "",
        "reviewer_notes": "",
        "approved_for_calibration_design": "false",
    }


def _casebooks_by_target(casebook_report: Mapping[str, Any]) -> dict[str, list[Mapping[str, Any]]]:
    casebooks = _mapping_rows(casebook_report.get("casebooks", []))
    result: dict[str, list[Mapping[str, Any]]] = {}
    for casebook in casebooks:
        target = str(casebook.get("target", ""))
        if not target:
            continue
        result[target] = _mapping_rows(casebook.get("examples", []))
    return result


def _mapping_rows(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
        return []
    return [row for row in value if isinstance(row, Mapping)]


def _display(value: object) -> str:
    if value is None:
        return ""
    return str(value)


def _to_float(value: object) -> float | None:
    try:
        if value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _fmt_float(value: object) -> str:
    converted = _to_float(value)
    if converted is None:
        return ""
    return f"{converted:.4f}"


def _parse_json_file(path: Path | None) -> Mapping[str, Any]:
    if path is None:
        return {}
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, Mapping):
        raise ValueError(f"expected JSON object in {path}")
    return loaded


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export an Effort/Result manual-review evidence template."
    )
    parser.add_argument("proposal_path", type=Path)
    parser.add_argument("--casebook", type=Path)
    parser.add_argument("--max-examples-per-target", type=int, default=20)
    parser.add_argument(
        "--format",
        choices=("json", "markdown", "csv"),
        default="csv",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    proposal = _parse_json_file(args.proposal_path)
    casebook = _parse_json_file(args.casebook)
    report = build_manual_review_evidence_template(
        proposal,
        casebook_report=casebook,
        max_examples_per_target=args.max_examples_per_target,
    )
    if args.format == "markdown":
        rendered = render_manual_review_template_markdown(report)
    elif args.format == "csv":
        rendered = render_manual_review_template_csv(report)
    else:
        rendered = json.dumps(report, indent=2, sort_keys=True)

    if args.output:
        args.output.write_text(rendered + ("" if rendered.endswith("\n") else "\n"), encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
