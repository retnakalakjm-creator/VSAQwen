"""Review Effort/Result casebook exports before calibration design.

This module is audit/report only. It summarizes exported casebook examples so
manual reviewers can see coverage, forward-outcome availability, and target-level
readiness before any calibration work. It does not change detector activation,
scoring, ranking, actionability, scanner state, persistence, or broker/order
behavior.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from audit.export_effort_result_casebook import (
    DEFAULT_HORIZONS,
    DEFAULT_TARGETS,
    build_effort_result_casebook,
)

REPORT_TYPE = "effort_result_casebook_review"
REPORT_SCHEMA_VERSION = 1

STATUS_READY = "ready_for_manual_visual_review"
STATUS_NEEDS_EXAMPLES = "needs_casebook_examples"
STATUS_NEEDS_FORWARD_OUTCOMES = "needs_forward_outcomes"
STATUS_NEEDS_ATTENTION = "needs_attention"

PRODUCTION_BOUNDARY = {
    "audit_only": True,
    "may_change_scoring": False,
    "may_change_ranking": False,
    "may_change_actionability": False,
    "may_activate_detector": False,
    "requires_manual_case_review": True,
    "requires_separate_production_pr": True,
}


def build_casebook_review_report(
    casebook_report: Mapping[str, Any],
) -> dict[str, object]:
    """Summarize an Effort/Result casebook export for manual review.

    A ready target in this report is ready only for manual visual review. It is
    not permission to calibrate, score, rank, activate, or change production
    behavior.
    """

    casebooks = _mapping_rows(casebook_report.get("casebooks", []))
    horizons = _int_list(casebook_report.get("horizons", []))
    if not horizons:
        horizons = list(DEFAULT_HORIZONS)

    target_reviews = [
        _target_review(row, horizons=horizons) for row in casebooks
    ]
    ready_count = sum(
        1 for row in target_reviews if row["review_status"] == STATUS_READY
    )
    blocked_count = len(target_reviews) - ready_count

    return {
        "report_type": REPORT_TYPE,
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "source": casebook_report.get("source"),
        "source_report_type": casebook_report.get("report_type"),
        "rows": int(casebook_report.get("rows", 0)),
        "targets": [str(target) for target in casebook_report.get("targets", [])],
        "horizons": horizons,
        "target_count": len(target_reviews),
        "ready_target_count": ready_count,
        "blocked_target_count": blocked_count,
        "total_matched_bars": sum(
            int(row.get("matched_bars", 0)) for row in target_reviews
        ),
        "total_exported_examples": sum(
            int(row.get("exported_examples", 0)) for row in target_reviews
        ),
        "review_status": (
            STATUS_READY
            if target_reviews and ready_count == len(target_reviews)
            else STATUS_NEEDS_ATTENTION
        ),
        "target_reviews": target_reviews,
        **PRODUCTION_BOUNDARY,
    }


def render_casebook_review_markdown(report: Mapping[str, Any]) -> str:
    """Render a casebook-review report as human-readable Markdown."""

    lines = [
        "# Effort/Result Casebook Review",
        "",
        "## Summary",
        "",
        f"- Source: `{_display(report.get('source'))}`",
        f"- Rows: {int(report.get('rows', 0))}",
        f"- Targets reviewed: {int(report.get('target_count', 0))}",
        f"- Ready targets: {int(report.get('ready_target_count', 0))}",
        f"- Blocked targets: {int(report.get('blocked_target_count', 0))}",
        f"- Matched bars: {int(report.get('total_matched_bars', 0))}",
        f"- Exported examples: {int(report.get('total_exported_examples', 0))}",
        f"- Review status: `{_display(report.get('review_status'))}`",
        "",
        "## Production Boundary",
        "",
        "- Audit/report only: true",
        "- May change scoring: false",
        "- May change ranking: false",
        "- May change actionability: false",
        "- May activate detector: false",
        "- Requires manual case review: true",
        "- Requires separate production PR: true",
        "",
        "## Target Review",
        "",
    ]

    target_reviews = _mapping_rows(report.get("target_reviews", []))
    if not target_reviews:
        lines.append("_No casebook targets were available for review._")
        lines.append("")
        return "\n".join(lines)

    lines.extend(
        [
            "| Target | Status | Matched bars | Exported examples | Symbols | Horizon mean returns | Reason |",
            "| --- | --- | ---: | ---: | --- | --- | --- |",
        ]
    )
    for row in target_reviews:
        lines.append(
            "| "
            f"`{_display(row.get('target'))}` | "
            f"`{_display(row.get('review_status'))}` | "
            f"{int(row.get('matched_bars', 0))} | "
            f"{int(row.get('exported_examples', 0))} | "
            f"{_csv(row.get('symbols', []))} | "
            f"{_horizon_mean_summary(row.get('horizon_summaries', []))} | "
            f"{_display(row.get('reason'))} |"
        )
    lines.append("")
    return "\n".join(lines)


def _target_review(
    target_report: Mapping[str, Any],
    *,
    horizons: Sequence[int],
) -> dict[str, object]:
    target = str(target_report.get("target", ""))
    examples = _mapping_rows(target_report.get("examples", []))
    matched_bars = int(target_report.get("matched_bars", 0))
    exported_examples = int(target_report.get("exported_examples", len(examples)))
    horizon_summaries = [
        _horizon_summary(examples, horizon=int(horizon)) for horizon in horizons
    ]
    forward_count = sum(
        int(row["examples_with_forward_return"]) for row in horizon_summaries
    )
    status = _review_status(
        matched_bars=matched_bars,
        exported_examples=exported_examples,
        forward_count=forward_count,
    )

    return {
        "target": target,
        "review_status": status,
        "matched_bars": matched_bars,
        "exported_examples": exported_examples,
        "symbols": _symbols(examples),
        "first_week": _week_bound(examples, first=True),
        "last_week": _week_bound(examples, first=False),
        "horizon_summaries": horizon_summaries,
        "reason": _review_reason(status),
        **PRODUCTION_BOUNDARY,
    }


def _horizon_summary(
    examples: Sequence[Mapping[str, Any]],
    *,
    horizon: int,
) -> dict[str, object]:
    key = f"forward_return_{horizon}"
    values = [_to_float(example.get(key)) for example in examples if key in example]
    values = [value for value in values if value is not None]
    positives = sum(1 for value in values if value > 0)
    negatives = sum(1 for value in values if value < 0)
    flats = len(values) - positives - negatives
    return {
        "horizon": horizon,
        "examples_with_forward_return": len(values),
        "mean_forward_return": _mean(values),
        "positive_count": positives,
        "negative_count": negatives,
        "flat_count": flats,
    }


def _review_status(
    *,
    matched_bars: int,
    exported_examples: int,
    forward_count: int,
) -> str:
    if matched_bars <= 0 or exported_examples <= 0:
        return STATUS_NEEDS_EXAMPLES
    if forward_count <= 0:
        return STATUS_NEEDS_FORWARD_OUTCOMES
    return STATUS_READY


def _review_reason(status: str) -> str:
    if status == STATUS_READY:
        return "bounded examples and forward outcomes are available for manual visual review"
    if status == STATUS_NEEDS_FORWARD_OUTCOMES:
        return "examples exist but no forward-return fields were available"
    return "no exported examples are available for this target"


def _symbols(examples: Sequence[Mapping[str, Any]]) -> list[str]:
    return sorted({str(example.get("symbol")) for example in examples if example.get("symbol")})


def _week_bound(examples: Sequence[Mapping[str, Any]], *, first: bool) -> str:
    weeks = sorted(str(example.get("week_beginning")) for example in examples if example.get("week_beginning"))
    if not weeks:
        return ""
    return weeks[0] if first else weeks[-1]


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


def _mean(values: Sequence[float]) -> float | None:
    if not values:
        return None
    return float(sum(values) / len(values))


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
        description="Review audit-only Effort/Result casebook examples."
    )
    parser.add_argument("path", type=Path)
    parser.add_argument(
        "--targets",
        default=",".join(DEFAULT_TARGETS),
        help="Comma-separated casebook target conditions.",
    )
    parser.add_argument("--horizons", default=",".join(str(h) for h in DEFAULT_HORIZONS))
    parser.add_argument("--max-examples-per-target", type=int, default=20)
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="markdown",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    casebook = build_effort_result_casebook(
        args.path,
        targets=_parse_csv(args.targets),
        horizons=_parse_horizons(args.horizons),
        max_examples_per_target=args.max_examples_per_target,
    )
    report = build_casebook_review_report(casebook)
    rendered = (
        render_casebook_review_markdown(report)
        if args.format == "markdown"
        else json.dumps(report, indent=2, sort_keys=True)
    )
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
