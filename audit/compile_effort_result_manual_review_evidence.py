"""Compile Effort/Result manual-review rows into gate evidence.

This module is audit/evidence only. It converts filled manual visual-review
template rows into the JSON evidence shape consumed by the calibration-proposal
gate. It does not change detector activation, scoring, ranking, actionability,
scanner state, persistence, or broker/order behavior.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

REPORT_TYPE = "effort_result_manual_review_evidence"
REPORT_SCHEMA_VERSION = 1

APPROVED_MANUAL_REVIEW_STATUS = "approved_for_calibration_experiment"
REVIEW_STATUS_PENDING = "pending_manual_review"
REVIEW_STATUS_NEEDS_MORE = "needs_more_review"

PRODUCTION_BOUNDARY = {
    "audit_only": True,
    "evidence_only": True,
    "production_change_allowed": False,
    "may_change_scoring": False,
    "may_change_ranking": False,
    "may_change_actionability": False,
    "may_activate_detector": False,
    "requires_manual_case_review": True,
    "requires_separate_production_pr": True,
}

TRUE_VALUES = {"1", "true", "yes", "y", "approved"}
FALSE_VALUES = {"0", "false", "no", "n", "rejected", ""}


def compile_manual_review_evidence(
    review_rows: Sequence[Mapping[str, Any]],
    *,
    min_approved_examples_per_target: int = 5,
) -> dict[str, object]:
    """Compile filled manual-review template rows into gate evidence.

    A target is marked approved only when enough manually approved examples are
    present. The output remains evidence for a separate gate/review step and
    cannot authorize production changes by itself.
    """

    if min_approved_examples_per_target <= 0:
        raise ValueError("min_approved_examples_per_target must be positive")

    rows = [dict(row) for row in review_rows if isinstance(row, Mapping)]
    grouped = _group_by_target(rows)
    targets = [
        _compile_target_evidence(
            target,
            target_rows,
            min_approved_examples_per_target=min_approved_examples_per_target,
        )
        for target, target_rows in sorted(grouped.items())
    ]
    approved_count = sum(
        1
        for target in targets
        if target["manual_review_status"] == APPROVED_MANUAL_REVIEW_STATUS
    )
    needs_review_count = len(targets) - approved_count

    return {
        "report_type": REPORT_TYPE,
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "target_count": len(targets),
        "approved_target_count": approved_count,
        "needs_review_target_count": needs_review_count,
        "minimum_approved_examples_per_target": min_approved_examples_per_target,
        "targets": targets,
        "gate_evidence_ready": bool(targets) and approved_count == len(targets),
        "next_stage": (
            "calibration_proposal_gate"
            if targets and approved_count == len(targets)
            else "manual_visual_review_completion"
        ),
        "automatic_promotion_allowed": False,
        **PRODUCTION_BOUNDARY,
    }


def render_manual_review_evidence_markdown(report: Mapping[str, Any]) -> str:
    """Render compiled manual-review evidence as Markdown."""

    lines = [
        "# Effort/Result Manual Review Evidence",
        "",
        "## Summary",
        "",
        f"- Targets: {int(report.get('target_count', 0))}",
        f"- Approved targets: {int(report.get('approved_target_count', 0))}",
        f"- Needs-review targets: {int(report.get('needs_review_target_count', 0))}",
        f"- Minimum approved examples per target: {int(report.get('minimum_approved_examples_per_target', 0))}",
        f"- Gate evidence ready: {_bool_text(report.get('gate_evidence_ready'))}",
        f"- Next stage: `{_display(report.get('next_stage'))}`",
        "",
        "## Production Boundary",
        "",
        "- Audit/report only: true",
        "- Evidence only: true",
        "- Production change allowed: false",
        "- Automatic promotion allowed: false",
        "- May change scoring: false",
        "- May change ranking: false",
        "- May change actionability: false",
        "- May activate detector: false",
        "- Requires manual case review: true",
        "- Requires separate production PR: true",
        "",
        "## Target Evidence",
        "",
    ]

    targets = _mapping_rows(report.get("targets", []))
    if not targets:
        lines.append("_No manual-review evidence targets were compiled._")
        lines.append("")
        return "\n".join(lines)

    lines.extend(
        [
            "| Target | Manual status | Approved examples | Reviewed examples | Symbols | Weeks | Failed checks |",
            "| --- | --- | ---: | ---: | --- | --- | --- |",
        ]
    )
    for row in targets:
        lines.append(
            "| "
            f"`{_display(row.get('target'))}` | "
            f"`{_display(row.get('manual_review_status'))}` | "
            f"{int(row.get('approved_examples', 0))} | "
            f"{int(row.get('reviewed_examples_total', 0))} | "
            f"{_csv(row.get('reviewed_symbols', []))} | "
            f"{_csv(row.get('reviewed_weeks', []))} | "
            f"{_csv(row.get('failed_evidence_checks', []))} |"
        )

    lines.extend(["", "## Notes", ""])
    lines.append(
        "Use the JSON form of this report as `--manual-review-evidence` input for "
        "the calibration-proposal gate after manual review is complete."
    )
    lines.append("")
    return "\n".join(lines)


def load_review_rows_csv(path: Path) -> list[dict[str, str]]:
    """Load filled manual-review template rows from CSV."""

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


def _compile_target_evidence(
    target: str,
    rows: Sequence[Mapping[str, Any]],
    *,
    min_approved_examples_per_target: int,
) -> dict[str, object]:
    reviewable_rows = [_normalize_row(row) for row in rows]
    reviewed_rows = [row for row in reviewable_rows if _is_reviewed(row)]
    approved_rows = [row for row in reviewed_rows if _is_approved(row)]

    reviewers = _sorted_unique(row.get("reviewer", "") for row in approved_rows)
    review_dates = _sorted_unique(row.get("review_date", "") for row in approved_rows)
    symbols = _sorted_unique(row.get("symbol", "") for row in approved_rows)
    weeks = _sorted_unique(row.get("week_beginning", "") for row in approved_rows)

    quality_checks = {
        "has_minimum_approved_examples": len(approved_rows)
        >= min_approved_examples_per_target,
        "reviewer_recorded": bool(reviewers),
        "review_date_recorded": bool(review_dates),
        "symbols_reviewed": bool(symbols),
        "weeks_reviewed": bool(weeks),
        "approved_rows_have_true_positive_label": all(
            _has_true_positive_label(row) for row in approved_rows
        )
        and bool(approved_rows),
    }
    failed_checks = [name for name, passed in quality_checks.items() if not passed]
    target_ready = not failed_checks

    return {
        "target": target,
        "manual_review_status": (
            APPROVED_MANUAL_REVIEW_STATUS if target_ready else REVIEW_STATUS_NEEDS_MORE
        ),
        "reviewer": ", ".join(reviewers),
        "review_date": ", ".join(review_dates),
        "reviewed_examples": len(approved_rows),
        "reviewed_symbols": symbols,
        "reviewed_weeks": weeks,
        "approved_examples": len(approved_rows),
        "reviewed_examples_total": len(reviewed_rows),
        "source_rows": len(reviewable_rows),
        "true_positive_examples": sum(
            1 for row in reviewed_rows if _has_true_positive_label(row)
        ),
        "false_positive_examples": sum(
            1
            for row in reviewed_rows
            if _label(row, "true_false_positive_label") == "false_positive"
        ),
        "uncertain_examples": sum(
            1 for row in reviewed_rows if _label(row, "true_false_positive_label") == "uncertain"
        ),
        "failed_evidence_checks": failed_checks,
        "evidence_quality_checks": quality_checks,
        "example_reviews": [
            _example_review(row, approved=_is_approved(row)) for row in reviewed_rows
        ],
        "automatic_promotion_allowed": False,
        **PRODUCTION_BOUNDARY,
    }


def _example_review(row: Mapping[str, str], *, approved: bool) -> dict[str, object]:
    return {
        "example_rank": _display(row.get("example_rank")),
        "symbol": _display(row.get("symbol")),
        "week_beginning": _display(row.get("week_beginning")),
        "manual_review_status": _display(row.get("manual_review_status")),
        "visual_label": _display(row.get("visual_label")),
        "true_false_positive_label": _display(row.get("true_false_positive_label")),
        "structure_context": _display(row.get("structure_context")),
        "reviewer_notes": _display(row.get("reviewer_notes")),
        "approved_for_calibration_design": approved,
    }


def _group_by_target(rows: Sequence[Mapping[str, Any]]) -> dict[str, list[Mapping[str, Any]]]:
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        target = str(row.get("target", "")).strip()
        if not target:
            continue
        grouped.setdefault(target, []).append(row)
    return grouped


def _normalize_row(row: Mapping[str, Any]) -> dict[str, str]:
    return {str(key): _display(value).strip() for key, value in row.items()}


def _is_reviewed(row: Mapping[str, str]) -> bool:
    status = _display(row.get("manual_review_status")).strip()
    return status not in {"", REVIEW_STATUS_PENDING}


def _is_approved(row: Mapping[str, str]) -> bool:
    return (
        _display(row.get("manual_review_status")).strip()
        == APPROVED_MANUAL_REVIEW_STATUS
        and _truthy(row.get("approved_for_calibration_design"))
        and _has_true_positive_label(row)
        and bool(_display(row.get("reviewer")).strip())
        and bool(_display(row.get("review_date")).strip())
    )


def _has_true_positive_label(row: Mapping[str, str]) -> bool:
    return (
        _label(row, "true_false_positive_label") == "true_positive"
        or _label(row, "visual_label") == "true_positive"
    )


def _label(row: Mapping[str, str], key: str) -> str:
    return _display(row.get(key)).strip().lower()


def _truthy(value: object) -> bool:
    normalized = _display(value).strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    return False


def _sorted_unique(values: Iterable[object]) -> list[str]:
    return sorted({_display(value).strip() for value in values if _display(value).strip()})


def _mapping_rows(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
        return []
    return [row for row in value if isinstance(row, Mapping)]


def _display(value: object) -> str:
    if value is None:
        return ""
    return str(value)


def _csv(value: object) -> str:
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
        return ""
    return ", ".join(str(item) for item in value)


def _bool_text(value: object) -> str:
    return "true" if bool(value) else "false"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compile Effort/Result manual-review evidence for gate input."
    )
    parser.add_argument("review_csv_path", type=Path)
    parser.add_argument("--min-approved-examples-per-target", type=int, default=5)
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="json",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    rows = load_review_rows_csv(args.review_csv_path)
    report = compile_manual_review_evidence(
        rows,
        min_approved_examples_per_target=args.min_approved_examples_per_target,
    )
    rendered = (
        render_manual_review_evidence_markdown(report)
        if args.format == "markdown"
        else json.dumps(report, indent=2, sort_keys=True)
    )
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
