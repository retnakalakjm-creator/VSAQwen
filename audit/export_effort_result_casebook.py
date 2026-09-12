"""Audit-only Effort/Result casebook export for manual visual review.

The exporter turns historical validation rows into bounded examples for selected
Effort/Result review candidates. It is intentionally offline/report-only and
does not change detector activation, scoring, ranking, actionability, scanner
state, persistence, or broker/order behavior.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd

from audit.audit_effort_result_decision_value import (
    EFFORT_RESULT_EVENT_SET,
    classify,
    effort_result_candidate,
    events,
    should_derive_effort_result_relationships,
)

REPORT_TYPE = "effort_result_casebook"
REPORT_SCHEMA_VERSION = 1
DEFAULT_TARGETS = (
    "RESULT_GT_EFFORT",
    "EFFORT_RESULT+SUPPLY_COMING_IN",
)
DEFAULT_HORIZONS = (1, 2, 4)
REQUIRED_COLUMNS = {
    "symbol",
    "bar_index",
    "close",
    "volume_ratio",
    "spread_ratio",
    "existing_events",
}


def build_effort_result_casebook(
    path: Path,
    *,
    targets: Sequence[str] = DEFAULT_TARGETS,
    horizons: Sequence[int] = DEFAULT_HORIZONS,
    max_examples_per_target: int = 20,
) -> dict[str, object]:
    """Build bounded casebook examples for Effort/Result review candidates.

    The casebook is permission for manual chart/case review only. It does not
    authorize scoring, ranking, actionability, detector, or production changes.
    """

    if max_examples_per_target <= 0:
        raise ValueError("max_examples_per_target must be positive")
    normalized_targets = tuple(_normalize_targets(targets))
    if not normalized_targets:
        raise ValueError("at least one target is required")
    normalized_horizons = tuple(sorted({int(horizon) for horizon in horizons}))
    if not normalized_horizons or normalized_horizons[0] <= 0:
        raise ValueError("horizons must contain positive integers")

    df = _load_validation_frame(path)
    target_reports = [
        _target_casebook(
            df,
            target=target,
            horizons=normalized_horizons,
            max_examples=max_examples_per_target,
        )
        for target in normalized_targets
    ]

    return {
        "report_type": REPORT_TYPE,
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "source": str(path),
        "rows": int(len(df)),
        "targets": list(normalized_targets),
        "horizons": list(normalized_horizons),
        "target_count": len(target_reports),
        "total_matched_bars": sum(
            int(report["matched_bars"]) for report in target_reports
        ),
        "casebooks": target_reports,
        "audit_only": True,
        "may_change_scoring": False,
        "may_change_ranking": False,
        "may_change_actionability": False,
        "may_activate_detector": False,
        "requires_manual_case_review": True,
        "requires_separate_production_pr": True,
    }


def render_casebook_markdown(report: Mapping[str, Any]) -> str:
    """Render a casebook report as Markdown for manual visual review."""

    lines = [
        "# Effort/Result Casebook",
        "",
        "## Summary",
        "",
        f"- Source: `{_display(report.get('source'))}`",
        f"- Rows: {int(report.get('rows', 0))}",
        f"- Targets: {_csv(report.get('targets', []))}",
        f"- Horizons: {_csv(report.get('horizons', []))}",
        f"- Total matched bars: {int(report.get('total_matched_bars', 0))}",
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
    ]

    for target_report in _mapping_rows(report.get("casebooks", [])):
        target = _display(target_report.get("target"))
        lines.extend(
            [
                f"## {target}",
                "",
                f"- Matched bars: {int(target_report.get('matched_bars', 0))}",
                f"- Exported examples: {int(target_report.get('exported_examples', 0))}",
                "",
            ]
        )
        examples = _mapping_rows(target_report.get("examples", []))
        if not examples:
            lines.append("_No examples matched this target._")
            lines.append("")
            continue
        lines.extend(
            [
                "| Symbol | Week | Bar | Close | Volume ratio | Spread ratio | Relationship | Forward returns | Events |",
                "| --- | --- | ---: | ---: | ---: | ---: | --- | --- | --- |",
            ]
        )
        for example in examples:
            lines.append(
                "| "
                f"{_display(example.get('symbol'))} | "
                f"{_display(example.get('week_beginning'))} | "
                f"{int(example.get('bar_index', 0))} | "
                f"{_fmt_float(example.get('close'))} | "
                f"{_fmt_float(example.get('volume_ratio'))} | "
                f"{_fmt_float(example.get('spread_ratio'))} | "
                f"`{_display(example.get('relationship'))}` | "
                f"{_forward_returns(example)} | "
                f"{_csv(example.get('events', []))} |"
            )
        lines.append("")

    return "\n".join(lines)


def write_casebook_csv(report: Mapping[str, Any], path: Path) -> None:
    """Write flattened casebook examples for spreadsheet review."""

    rows: list[dict[str, object]] = []
    for target_report in _mapping_rows(report.get("casebooks", [])):
        target = str(target_report.get("target", ""))
        for example in _mapping_rows(target_report.get("examples", [])):
            row = {"target": target, **dict(example)}
            row["events"] = ",".join(str(item) for item in example.get("events", []))
            rows.append(row)
    pd.DataFrame(rows).to_csv(path, index=False)


def _load_validation_frame(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    df = df.sort_values(["symbol", "bar_index"]).copy()
    for col in ("close", "volume_ratio", "spread_ratio"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["close", "volume_ratio", "spread_ratio"])
    df = df[(df.close > 0) & (df.volume_ratio > 0) & (df.spread_ratio > 0)]
    df["relationship"] = [
        classify(effort, result)
        for effort, result in zip(df.volume_ratio, df.spread_ratio)
    ]
    df["events"] = df.existing_events.map(events)
    derive_relationships = should_derive_effort_result_relationships(df["events"])
    if derive_relationships:
        df["effort_result_candidate"] = df.relationship.map(effort_result_candidate)
    else:
        df["effort_result_candidate"] = [
            _explicit_effort_result_candidate(codes) for codes in df.events
        ]
    return df


def _explicit_effort_result_candidate(codes: set[str]) -> str | None:
    for code in sorted(codes):
        if code in EFFORT_RESULT_EVENT_SET:
            return code
    return None


def _target_casebook(
    df: pd.DataFrame,
    *,
    target: str,
    horizons: Sequence[int],
    max_examples: int,
) -> dict[str, object]:
    mask = _target_mask(df, target)
    matched = df[mask].copy()
    examples: list[dict[str, object]] = []
    if not matched.empty:
        for _, row in matched.head(max_examples).iterrows():
            examples.append(_example(df, row, target=target, horizons=horizons))

    return {
        "target": target,
        "matched_bars": int(len(matched)),
        "exported_examples": len(examples),
        "examples": examples,
        "audit_only": True,
        "may_change_scoring": False,
        "may_change_ranking": False,
        "may_change_actionability": False,
        "may_activate_detector": False,
        "requires_manual_case_review": True,
        "requires_separate_production_pr": True,
    }


def _target_mask(df: pd.DataFrame, target: str) -> pd.Series:
    parts = [part.strip().upper() for part in target.split("+") if part.strip()]
    if not parts:
        raise ValueError("target must not be empty")
    candidate, required_events = parts[0], parts[1:]
    mask = df.effort_result_candidate == candidate
    for event in required_events:
        mask = mask & df.events.map(lambda codes, event=event: event in codes)
    return mask


def _example(
    df: pd.DataFrame,
    row: pd.Series,
    *,
    target: str,
    horizons: Sequence[int],
) -> dict[str, object]:
    symbol_rows = df[df.symbol == row.symbol].sort_values("bar_index")
    by_bar_index = {
        int(candidate.bar_index): candidate
        for _, candidate in symbol_rows.iterrows()
    }
    bar_index = int(row.bar_index)
    base_close = float(row.close)
    forward: dict[str, object] = {}
    for horizon in horizons:
        future = by_bar_index.get(bar_index + int(horizon))
        if future is None:
            continue
        future_close = float(future.close)
        forward[f"forward_close_{int(horizon)}"] = future_close
        forward[f"forward_return_{int(horizon)}"] = future_close / base_close - 1.0

    return {
        "target": target,
        "symbol": str(row.symbol),
        "bar_index": bar_index,
        "week_beginning": _display(row.get("week_beginning", "")),
        "close": base_close,
        "volume_ratio": float(row.volume_ratio),
        "spread_ratio": float(row.spread_ratio),
        "relationship": str(row.relationship),
        "effort_result_candidate": _display(row.effort_result_candidate),
        "events": sorted(str(code) for code in row.events),
        **forward,
    }


def _normalize_targets(targets: Sequence[str]) -> list[str]:
    return [target.strip().upper() for target in targets if target and target.strip()]


def _parse_csv(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


def _parse_horizons(value: str) -> tuple[int, ...]:
    horizons = tuple(int(part.strip()) for part in value.split(",") if part.strip())
    if not horizons:
        raise ValueError("at least one horizon is required")
    return horizons


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


def _fmt_float(value: object) -> str:
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return ""


def _forward_returns(example: Mapping[str, Any]) -> str:
    items = []
    for key, value in sorted(example.items()):
        if key.startswith("forward_return_"):
            horizon = key.rsplit("_", 1)[-1]
            items.append(f"{horizon}w: {_fmt_float(value)}")
    return "<br>".join(items)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export audit-only Effort/Result casebook examples."
    )
    parser.add_argument("path", type=Path)
    parser.add_argument(
        "--targets",
        default=",".join(DEFAULT_TARGETS),
        help="Comma-separated target conditions.",
    )
    parser.add_argument("--horizons", default="1,2,4")
    parser.add_argument("--max-examples-per-target", type=int, default=20)
    parser.add_argument(
        "--format",
        choices=("json", "markdown", "csv"),
        default="markdown",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    report = build_effort_result_casebook(
        args.path,
        targets=_parse_csv(args.targets),
        horizons=_parse_horizons(args.horizons),
        max_examples_per_target=args.max_examples_per_target,
    )

    if args.format == "csv":
        if not args.output:
            raise ValueError("--output is required for csv format")
        write_casebook_csv(report, args.output)
        return

    rendered = (
        render_casebook_markdown(report)
        if args.format == "markdown"
        else json.dumps(report, indent=2, sort_keys=True)
    )
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
