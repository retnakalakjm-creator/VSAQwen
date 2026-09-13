"""Export Effort/Result shadow-mode observations for offline review.

This module is audit/shadow only. It converts approved shadow-mode integration
proposals into observation rows over historical validation data. It does not
activate detectors or change scoring, ranking, actionability, scanner state,
persistence, broker/order/account behavior, API behavior, or frontend behavior.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd

from audit.export_effort_result_casebook import _load_validation_frame, _target_mask

REPORT_TYPE = "effort_result_shadow_observations"
REPORT_SCHEMA_VERSION = 1
SHADOW_PROPOSAL_READY_STATUS = "ready_for_shadow_mode_pr_review"
SHADOW_OBSERVATION_STATUS = "shadow_observation_ready"
SHADOW_OBSERVATION_BLOCKED_STATUS = "blocked_pending_shadow_mode_proposal"
DEFAULT_HORIZONS = (1, 2, 4)

PRODUCTION_BOUNDARY = {
    "audit_only": True,
    "shadow_mode_only": True,
    "observation_only": True,
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

DISABLED_PRODUCTION_SURFACES = (
    "production_scoring",
    "ranking",
    "actionability",
    "alerts",
    "orders",
    "scanner_state",
    "persistence_as_signal",
    "api_responses",
    "frontend_display",
)

OBSERVATION_PAYLOAD_FIELDS = (
    "target",
    "symbol",
    "bar_index",
    "week_beginning",
    "relationship",
    "effort_result_candidate",
    "event_labels",
    "shadow_signal_role",
    "source_gate_status",
    "manual_review_status",
    "observation_status",
)


def build_effort_result_shadow_observations(
    validation_csv_path: Path,
    shadow_proposal_report: Mapping[str, Any],
    *,
    horizons: Sequence[int] = DEFAULT_HORIZONS,
    max_observations_per_target: int | None = None,
) -> dict[str, object]:
    """Build audit-only shadow observations from a passed shadow proposal."""

    normalized_horizons = _normalize_horizons(horizons)
    if max_observations_per_target is not None and max_observations_per_target <= 0:
        raise ValueError("max_observations_per_target must be positive when provided")

    df = _load_validation_frame(validation_csv_path)
    proposals = _ready_target_proposals(shadow_proposal_report)
    summaries: list[dict[str, object]] = []
    observations: list[dict[str, object]] = []

    for proposal in proposals:
        target = _display(proposal.get("target")).strip().upper()
        if not target:
            continue
        matched = df[_target_mask(df, target)].sort_values(["symbol", "bar_index"])
        if max_observations_per_target is not None:
            matched = matched.head(max_observations_per_target)
        target_observations = [
            _observation(df, row, proposal=proposal, horizons=normalized_horizons)
            for _, row in matched.iterrows()
        ]
        observations.extend(target_observations)
        summaries.append(_target_summary(proposal, target_observations))

    has_observations = bool(summaries) and bool(observations)
    return {
        "report_type": REPORT_TYPE,
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "source": str(validation_csv_path),
        "source_report_type": shadow_proposal_report.get("report_type"),
        "source_proposal_status": shadow_proposal_report.get("proposal_status"),
        "rows": int(len(df)),
        "horizons": list(normalized_horizons),
        "target_count": len(summaries),
        "ready_target_count": len(summaries),
        "blocked_target_count": _blocked_target_count(shadow_proposal_report),
        "total_observations": len(observations),
        "observation_payload_fields": list(OBSERVATION_PAYLOAD_FIELDS),
        "disabled_production_surfaces": list(DISABLED_PRODUCTION_SURFACES),
        "target_summaries": summaries,
        "observations": observations,
        "shadow_observation_status": (
            SHADOW_OBSERVATION_STATUS if has_observations else SHADOW_OBSERVATION_BLOCKED_STATUS
        ),
        "next_stage": (
            "shadow_replay_dataset_builder"
            if has_observations
            else "complete_shadow_mode_integration_proposal"
        ),
        "automatic_promotion_allowed": False,
        **PRODUCTION_BOUNDARY,
    }


def render_shadow_observations_markdown(report: Mapping[str, Any]) -> str:
    """Render shadow observations as Markdown."""

    lines = [
        "# Effort/Result Shadow Observations",
        "",
        "## Summary",
        "",
        f"- Source: `{_display(report.get('source'))}`",
        f"- Source report type: `{_display(report.get('source_report_type'))}`",
        f"- Source proposal status: `{_display(report.get('source_proposal_status'))}`",
        f"- Targets observed: {int(report.get('target_count', 0))}",
        f"- Total observations: {int(report.get('total_observations', 0))}",
        f"- Horizons: {_csv(report.get('horizons', []))}",
        f"- Shadow observation status: `{_display(report.get('shadow_observation_status'))}`",
        f"- Next stage: `{_display(report.get('next_stage'))}`",
        "",
        "## Production Boundary",
        "",
        "- Audit/shadow only: true",
        "- Observation only: true",
        "- Production change allowed: false",
        "- Automatic promotion allowed: false",
        "- May change scoring: false",
        "- May change ranking: false",
        "- May change actionability: false",
        "- May activate detector: false",
        "- May change scanner/API/frontend behavior: false",
        "",
        "## Target Summaries",
        "",
    ]
    summaries = _mapping_rows(report.get("target_summaries", []))
    if not summaries:
        lines.append("_No ready shadow-mode targets produced observations._")
        lines.append("")
        return "\n".join(lines)

    lines.extend(
        [
            "| Target | Role | Observations | Symbols | Week span | Production surfaces disabled |",
            "| --- | --- | ---: | --- | --- | --- |",
        ]
    )
    for row in summaries:
        lines.append(
            "| "
            f"`{_display(row.get('target'))}` | "
            f"`{_display(row.get('shadow_signal_role'))}` | "
            f"{int(row.get('matched_observations', 0))} | "
            f"{_csv(row.get('symbols', []))} | "
            f"{_display(row.get('first_week'))} to {_display(row.get('last_week'))} | "
            f"{_bool_text(row.get('production_surfaces_disabled'))} |"
        )
    lines.extend(
        [
            "",
            "## Shadow Contract",
            "",
            "- These rows are replay/review observations only.",
            "- They must not be included in scoring, ranking, alerts, orders, API responses, or frontend display.",
            "- A separate production PR is required before any user-facing behavior changes.",
            "",
        ]
    )
    return "\n".join(lines)


def write_shadow_observations_csv(report: Mapping[str, Any], path: Path) -> None:
    """Write flattened shadow observations as CSV."""

    observations = [dict(row) for row in _mapping_rows(report.get("observations", []))]
    fieldnames = _csv_fieldnames(observations)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in observations:
            writer.writerow({key: _csv_cell(row.get(key)) for key in fieldnames})


def _ready_target_proposals(report: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    ready = []
    for proposal in _mapping_rows(report.get("target_proposals", [])):
        observation = proposal.get("shadow_mode_observation")
        emit = bool(observation.get("emit_observation")) if isinstance(observation, Mapping) else True
        if proposal.get("proposal_status") == SHADOW_PROPOSAL_READY_STATUS and emit:
            ready.append(proposal)
    return ready


def _blocked_target_count(report: Mapping[str, Any]) -> int:
    return sum(
        1
        for proposal in _mapping_rows(report.get("target_proposals", []))
        if proposal.get("proposal_status") != SHADOW_PROPOSAL_READY_STATUS
    )


def _observation(
    df: pd.DataFrame,
    row: pd.Series,
    *,
    proposal: Mapping[str, Any],
    horizons: Sequence[int],
) -> dict[str, object]:
    target = _display(proposal.get("target")).strip().upper()
    by_bar_index = {
        int(candidate.bar_index): candidate
        for _, candidate in df[df.symbol == row.symbol].sort_values("bar_index").iterrows()
    }
    bar_index = int(row.bar_index)
    base_close = float(row.close)
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
        "event_labels": sorted(str(code) for code in row.events),
        "shadow_signal_role": _display(proposal.get("shadow_signal_role")),
        "source_gate_status": _display(proposal.get("source_gate_status")),
        "manual_review_status": _display(proposal.get("manual_review_status")),
        "source_proposal_status": _display(proposal.get("proposal_status")),
        "reviewed_examples": _int_or_zero(proposal.get("reviewed_examples")),
        "reviewed_symbols": _list_value(proposal.get("reviewed_symbols", [])),
        "reviewed_weeks": _list_value(proposal.get("reviewed_weeks", [])),
        "observation_status": SHADOW_OBSERVATION_STATUS,
        "shadow_mode": True,
        "observation_only": True,
        "include_in_scoring": False,
        "include_in_ranking": False,
        "include_in_actionability": False,
        "emit_alert": False,
        "place_order": False,
        "activate_detector": False,
        "api_visible": False,
        "frontend_visible": False,
        "persist_as_production_signal": False,
        "production_change_allowed": False,
        "automatic_promotion_allowed": False,
        **_forward_outcomes(by_bar_index, bar_index, base_close, horizons),
    }


def _forward_outcomes(
    by_bar_index: Mapping[int, Any],
    base_bar_index: int,
    base_close: float,
    horizons: Sequence[int],
) -> dict[str, object]:
    forward = {}
    for horizon in horizons:
        future = by_bar_index.get(base_bar_index + int(horizon))
        if future is None:
            continue
        future_close = float(future.close)
        forward[f"forward_close_{int(horizon)}"] = future_close
        forward[f"forward_return_{int(horizon)}"] = future_close / base_close - 1.0
        forward[f"forward_up_{int(horizon)}"] = future_close > base_close
    return forward


def _target_summary(proposal: Mapping[str, Any], observations: Sequence[Mapping[str, Any]]) -> dict[str, object]:
    weeks = _sorted_unique(row.get("week_beginning") for row in observations)
    return {
        "target": _display(proposal.get("target")).strip().upper(),
        "shadow_signal_role": _display(proposal.get("shadow_signal_role")),
        "source_gate_status": _display(proposal.get("source_gate_status")),
        "manual_review_status": _display(proposal.get("manual_review_status")),
        "source_proposal_status": _display(proposal.get("proposal_status")),
        "reviewed_examples": _int_or_zero(proposal.get("reviewed_examples")),
        "matched_observations": len(observations),
        "symbols": _sorted_unique(row.get("symbol") for row in observations),
        "first_week": weeks[0] if weeks else "",
        "last_week": weeks[-1] if weeks else "",
        "production_surfaces_disabled": True,
        "disabled_production_surfaces": list(DISABLED_PRODUCTION_SURFACES),
        "automatic_promotion_allowed": False,
        **PRODUCTION_BOUNDARY,
    }


def _normalize_horizons(horizons: Sequence[int]) -> tuple[int, ...]:
    normalized = tuple(sorted({int(horizon) for horizon in horizons}))
    if not normalized or normalized[0] <= 0:
        raise ValueError("horizons must contain positive integers")
    return normalized


def _parse_horizons(value: str) -> tuple[int, ...]:
    return _normalize_horizons(tuple(int(part.strip()) for part in value.split(",") if part.strip()))


def _mapping_rows(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
        return []
    return [row for row in value if isinstance(row, Mapping)]


def _list_value(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (str, bytes)):
        return [_display(value)] if _display(value) else []
    if isinstance(value, Iterable):
        return sorted({_display(item) for item in value if _display(item)})
    return []


def _sorted_unique(values: Iterable[object]) -> list[str]:
    return sorted({_display(value) for value in values if _display(value)})


def _int_or_zero(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _display(value: object) -> str:
    return "" if value is None else str(value)


def _csv(value: object) -> str:
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
        return ""
    return ", ".join(str(item) for item in value)


def _csv_cell(value: object) -> object:
    if isinstance(value, (list, tuple, set)):
        return ",".join(str(item) for item in value)
    return value


def _csv_fieldnames(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    preferred = [
        "target",
        "symbol",
        "bar_index",
        "week_beginning",
        "relationship",
        "effort_result_candidate",
        "event_labels",
        "shadow_signal_role",
        "source_gate_status",
        "manual_review_status",
        "observation_status",
        "include_in_scoring",
        "include_in_ranking",
        "include_in_actionability",
        "activate_detector",
        "api_visible",
        "frontend_visible",
        "production_change_allowed",
    ]
    discovered = []
    for row in rows:
        for key in row:
            if key not in preferred and key not in discovered:
                discovered.append(key)
    return preferred + discovered


def _bool_text(value: object) -> str:
    return "true" if bool(value) else "false"


def main() -> None:
    parser = argparse.ArgumentParser(description="Export audit-only Effort/Result shadow observations.")
    parser.add_argument("validation_csv_path", type=Path)
    parser.add_argument("shadow_proposal_path", type=Path)
    parser.add_argument("--horizons", default="1,2,4")
    parser.add_argument("--max-observations-per-target", type=int, default=0)
    parser.add_argument("--format", choices=("json", "markdown", "csv"), default="json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    proposal = json.loads(args.shadow_proposal_path.read_text(encoding="utf-8"))
    report = build_effort_result_shadow_observations(
        args.validation_csv_path,
        proposal,
        horizons=_parse_horizons(args.horizons),
        max_observations_per_target=args.max_observations_per_target or None,
    )

    if args.format == "csv":
        if not args.output:
            raise ValueError("--output is required for csv format")
        write_shadow_observations_csv(report, args.output)
        return

    rendered = render_shadow_observations_markdown(report) if args.format == "markdown" else json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
