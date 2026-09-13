"""Review Effort/Result visual replay workflow readiness.

This module is audit/report only. It prepares a manual visual replay
workflow for offline Effort/Result shadow replay datasets. It does not activate
detectors or change scoring, ranking, actionability, scanner state,
persistence, broker/order/account behavior, API behavior, or frontend behavior.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

REPORT_TYPE = "effort_result_visual_replay_workflow_review"
REPORT_SCHEMA_VERSION = 1

SOURCE_READY_STATUS = "shadow_replay_dataset_ready"
WORKFLOW_READY_STATUS = "ready_for_manual_visual_replay"
WORKFLOW_BLOCKED_STATUS = "blocked_pending_visual_replay_fixes"
WORKFLOW_NEEDS_ATTENTION_STATUS = "needs_attention"

VISUAL_REPLAY_REVIEW_LANES = (
    "pre_event_context",
    "event_marker_alignment",
    "post_event_follow_through",
    "counterfactual_scan",
    "reviewer_notes_and_screenshot",
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
    "visual_replay_workflow_only": True,
    "manual_review_only": True,
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
    "requires_shadow_replay_dataset": True,
    "requires_separate_frontend_pr": True,
    "requires_separate_production_pr": True,
}


def build_effort_result_visual_replay_workflow_review(
    replay_dataset_report: Mapping[str, Any],
    *,
    min_sequences: int = 1,
) -> dict[str, object]:
    """Build an audit-only manual visual replay workflow review.

    A ready report means the replay dataset has enough offline structure for a
    human to review in a replay UI. It does not authorize scoring, ranking,
    actionability, API exposure, route exposure, frontend activation, alerts, or
    broker/order behavior.
    """

    if min_sequences <= 0:
        raise ValueError("min_sequences must be positive")

    sequences = _mapping_rows(replay_dataset_report.get("replay_sequences", []))
    sequence_reviews = [_sequence_visual_replay_review(sequence) for sequence in sequences]
    ready_sequences = [
        row for row in sequence_reviews if row["workflow_status"] == WORKFLOW_READY_STATUS
    ]
    blockers = _report_blockers(
        replay_dataset_report,
        sequence_reviews,
        min_sequences=min_sequences,
    )
    ready = not blockers

    return {
        "report_type": REPORT_TYPE,
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "source_report_type": replay_dataset_report.get("report_type"),
        "source_replay_dataset_status": replay_dataset_report.get("replay_dataset_status"),
        "source_sequence_count": int(replay_dataset_report.get("sequence_count", len(sequences)) or 0),
        "reviewed_sequence_count": len(sequence_reviews),
        "ready_sequence_count": len(ready_sequences),
        "blocked_sequence_count": len(sequence_reviews) - len(ready_sequences),
        "minimum_sequences": int(min_sequences),
        "workflow_status": WORKFLOW_READY_STATUS if ready else WORKFLOW_NEEDS_ATTENTION_STATUS,
        "blockers": blockers,
        "sequence_reviews": sequence_reviews,
        "visual_replay_review_lanes": list(VISUAL_REPLAY_REVIEW_LANES),
        "manual_review_required": True,
        "next_stage": "manual_visual_replay_review" if ready else "fix_visual_replay_workflow_inputs",
        "automatic_promotion_allowed": False,
        **PRODUCTION_BOUNDARY,
    }


def render_effort_result_visual_replay_workflow_markdown(report: Mapping[str, Any]) -> str:
    """Render the visual replay workflow review as Markdown."""

    lines = [
        "# Effort/Result Visual Replay Workflow Review",
        "",
        "## Summary",
        "",
        f"- Source report type: `{_display(report.get('source_report_type'))}`",
        f"- Source replay status: `{_display(report.get('source_replay_dataset_status'))}`",
        f"- Reviewed sequences: {int(report.get('reviewed_sequence_count', 0))}",
        f"- Ready sequences: {int(report.get('ready_sequence_count', 0))}",
        f"- Blocked sequences: {int(report.get('blocked_sequence_count', 0))}",
        f"- Workflow status: `{_display(report.get('workflow_status'))}`",
        f"- Next stage: `{_display(report.get('next_stage'))}`",
        "",
        "## Production Boundary",
        "",
        "- Audit/manual review only: true",
        "- Shadow mode only: true",
        "- Production change allowed: false",
        "- Automatic promotion allowed: false",
        "- May change scoring: false",
        "- May change ranking: false",
        "- May change actionability: false",
        "- May activate detector: false",
        "- May change API/frontend behavior: false",
        "- Requires separate frontend PR: true",
        "- Requires separate production PR: true",
        "",
        "## Sequence Reviews",
        "",
    ]

    reviews = _mapping_rows(report.get("sequence_reviews", []))
    if not reviews:
        lines.append("_No replay sequences were available for workflow review._")
        lines.append("")
    else:
        lines.extend(
            [
                "| Sequence | Target | Symbol | Status | Frames | Event markers | Pre | Post | Blockers |",
                "| --- | --- | --- | --- | ---: | ---: | --- | --- | --- |",
            ]
        )
        for row in reviews:
            lines.append(
                "| "
                f"`{_display(row.get('sequence_id'))}` | "
                f"`{_display(row.get('target'))}` | "
                f"{_display(row.get('symbol'))} | "
                f"`{_display(row.get('workflow_status'))}` | "
                f"{int(row.get('frame_count', 0))} | "
                f"{int(row.get('event_marker_count', 0))} | "
                f"{_yes_no(row.get('has_pre_event_context'))} | "
                f"{_yes_no(row.get('has_post_event_context'))} | "
                f"{_csv(row.get('blockers', []))} |"
            )
        lines.append("")

    lines.extend(
        [
            "## Manual Visual Replay Checklist",
            "",
        ]
    )
    for lane in report.get("visual_replay_review_lanes", []):
        lines.append(f"- [ ] {_display(lane)}")
    lines.extend(
        [
            "",
            "## Review Rules",
            "",
            "- Use only offline replay sequences and committed demo/fixture data.",
            "- Record whether the marker appears on the intended event bar.",
            "- Review pre-event context before judging the event marker.",
            "- Review post-event follow-through without promoting any signal.",
            "- A separate production PR is required before any scoring, ranking, actionability, API, frontend route, alert, or order behavior can change.",
            "",
        ]
    )
    return "\n".join(lines)


def _sequence_visual_replay_review(sequence: Mapping[str, Any]) -> dict[str, object]:
    frames = _mapping_rows(sequence.get("frames", []))
    event_frames = [frame for frame in frames if frame.get("is_event_bar") is True]
    marker_frames = [
        frame
        for frame in frames
        if frame.get("has_shadow_marker") is True and isinstance(frame.get("shadow_marker"), Mapping)
    ]
    has_pre_context = any(_number(frame.get("replay_offset")) < 0 for frame in frames)
    has_post_context = any(_number(frame.get("replay_offset")) > 0 for frame in frames)
    blockers: list[str] = []

    if not frames:
        blockers.append("missing_replay_frames")
    if not event_frames:
        blockers.append("missing_event_frame")
    if len(event_frames) > 1:
        blockers.append("multiple_event_frames")
    if not marker_frames:
        blockers.append("missing_shadow_marker")
    if len(marker_frames) > 1:
        blockers.append("multiple_shadow_markers")
    if not has_pre_context:
        blockers.append("missing_pre_event_context")
    if not has_post_context:
        blockers.append("missing_post_event_context")
    if _has_truthy_unsafe_fields(sequence):
        blockers.append("sequence_production_boundary_open")
    for frame in frames:
        marker = frame.get("shadow_marker")
        if isinstance(marker, Mapping) and _has_truthy_unsafe_fields(marker):
            blockers.append("marker_production_boundary_open")
            break

    return {
        "sequence_id": sequence.get("sequence_id", ""),
        "target": sequence.get("target", ""),
        "symbol": sequence.get("symbol", ""),
        "event_bar_index": sequence.get("event_bar_index", ""),
        "event_week_beginning": sequence.get("event_week_beginning", ""),
        "frame_count": len(frames),
        "event_frame_count": len(event_frames),
        "event_marker_count": len(marker_frames),
        "has_pre_event_context": has_pre_context,
        "has_post_event_context": has_post_context,
        "manual_visual_review_required": True,
        "workflow_status": WORKFLOW_READY_STATUS if not blockers else WORKFLOW_BLOCKED_STATUS,
        "blockers": blockers,
        "review_lanes": list(VISUAL_REPLAY_REVIEW_LANES),
    }


def _report_blockers(
    replay_dataset_report: Mapping[str, Any],
    sequence_reviews: Sequence[Mapping[str, Any]],
    *,
    min_sequences: int,
) -> list[str]:
    blockers: list[str] = []
    if replay_dataset_report.get("report_type") != "effort_result_shadow_replay_dataset":
        blockers.append("source_report_type_mismatch")
    if replay_dataset_report.get("replay_dataset_status") != SOURCE_READY_STATUS:
        blockers.append("source_replay_dataset_not_ready")
    if len(sequence_reviews) < min_sequences:
        blockers.append("not_enough_replay_sequences")
    if not any(row.get("workflow_status") == WORKFLOW_READY_STATUS for row in sequence_reviews):
        blockers.append("no_ready_visual_replay_sequences")
    if _has_truthy_unsafe_fields(replay_dataset_report):
        blockers.append("report_production_boundary_open")
    blocked_sequences = [
        _display(row.get("sequence_id")) or "<unknown>"
        for row in sequence_reviews
        if row.get("workflow_status") != WORKFLOW_READY_STATUS
    ]
    if blocked_sequences:
        blockers.append("sequence_workflow_blockers_present")
    return blockers


def _mapping_rows(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes, Mapping)):
        return []
    return [row for row in value if isinstance(row, Mapping)]


def _has_truthy_unsafe_fields(mapping: Mapping[str, Any]) -> bool:
    return any(mapping.get(field) is True for field in UNSAFE_TRUTHY_FIELDS)


def _number(value: Any) -> float:
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return 0.0
    return 0.0


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


def _yes_no(value: Any) -> str:
    return "yes" if value is True else "no"


def _write_output(content: str, output: Path | None) -> None:
    if output is None:
        print(content)
    else:
        output.write_text(content, encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replay_dataset_report", type=Path)
    parser.add_argument("--min-sequences", type=int, default=1)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    report = json.loads(args.replay_dataset_report.read_text(encoding="utf-8"))
    review = build_effort_result_visual_replay_workflow_review(
        report,
        min_sequences=args.min_sequences,
    )

    if args.format == "json":
        _write_output(json.dumps(review, indent=2, sort_keys=True), args.output)
    else:
        _write_output(render_effort_result_visual_replay_workflow_markdown(review), args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
