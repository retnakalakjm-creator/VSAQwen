"""Review Effort/Result shadow replay dataset contracts.

This module is audit/report only. It validates that a shadow replay dataset is
well-formed for a later frontend replay scaffold while keeping all production
and frontend behavior disabled. It does not activate detectors or change
scoring, ranking, actionability, scanner state, persistence, broker/order/account
behavior, API behavior, or frontend behavior.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

REPORT_TYPE = "effort_result_shadow_replay_contract_review"
REPORT_SCHEMA_VERSION = 1

SOURCE_READY_STATUS = "shadow_replay_dataset_ready"
CONTRACT_READY_STATUS = "ready_for_frontend_replay_scaffold_review"
CONTRACT_BLOCKED_STATUS = "blocked_pending_replay_contract_fixes"
CONTRACT_NEEDS_ATTENTION_STATUS = "needs_attention"

REQUIRED_SEQUENCE_FIELDS = (
    "sequence_id",
    "target",
    "symbol",
    "event_bar_index",
    "event_week_beginning",
    "lookback_bars",
    "forward_bars",
    "frame_count",
    "frames",
)

REQUIRED_FRAME_FIELDS = (
    "bar_index",
    "replay_offset",
    "week_beginning",
    "open",
    "high",
    "low",
    "close",
    "volume_ratio",
    "spread_ratio",
    "is_event_bar",
    "has_shadow_marker",
    "shadow_marker",
)

REQUIRED_MARKER_FIELDS = (
    "target",
    "symbol",
    "bar_index",
    "week_beginning",
    "event_labels",
    "shadow_signal_role",
    "observation_status",
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
    "contract_review_only": True,
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


def build_shadow_replay_contract_review(
    replay_dataset_report: Mapping[str, Any],
    *,
    min_sequences: int = 1,
    min_frames_per_sequence: int = 1,
) -> dict[str, object]:
    """Review a shadow replay dataset contract before any frontend work.

    A ready review allows a later, separate frontend scaffold PR to consume the
    dataset shape. It does not authorize production scoring, ranking,
    actionability, API exposure, or frontend behavior changes in this PR.
    """

    if min_sequences <= 0:
        raise ValueError("min_sequences must be positive")
    if min_frames_per_sequence <= 0:
        raise ValueError("min_frames_per_sequence must be positive")

    sequences = _mapping_rows(replay_dataset_report.get("replay_sequences", []))
    sequence_reviews = [
        _sequence_contract_review(sequence, min_frames=min_frames_per_sequence)
        for sequence in sequences
    ]
    ready_sequences = [
        row for row in sequence_reviews if row["contract_status"] == CONTRACT_READY_STATUS
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
        "source_total_frames": int(replay_dataset_report.get("total_frames", 0) or 0),
        "reviewed_sequence_count": len(sequence_reviews),
        "ready_sequence_count": len(ready_sequences),
        "blocked_sequence_count": len(sequence_reviews) - len(ready_sequences),
        "minimum_sequences": int(min_sequences),
        "minimum_frames_per_sequence": int(min_frames_per_sequence),
        "contract_status": CONTRACT_READY_STATUS if ready else CONTRACT_NEEDS_ATTENTION_STATUS,
        "blockers": blockers,
        "sequence_reviews": sequence_reviews,
        "frontend_replay_contract": _frontend_replay_contract(ready),
        "next_stage": (
            "separate_frontend_replay_scaffold_pr"
            if ready
            else "fix_shadow_replay_dataset_contract"
        ),
        "automatic_promotion_allowed": False,
        **PRODUCTION_BOUNDARY,
    }


def render_shadow_replay_contract_review_markdown(report: Mapping[str, Any]) -> str:
    """Render the contract review report as Markdown."""

    lines = [
        "# Effort/Result Shadow Replay Contract Review",
        "",
        "## Summary",
        "",
        f"- Source report type: `{_display(report.get('source_report_type'))}`",
        f"- Source replay status: `{_display(report.get('source_replay_dataset_status'))}`",
        f"- Reviewed sequences: {int(report.get('reviewed_sequence_count', 0))}",
        f"- Ready sequences: {int(report.get('ready_sequence_count', 0))}",
        f"- Blocked sequences: {int(report.get('blocked_sequence_count', 0))}",
        f"- Contract status: `{_display(report.get('contract_status'))}`",
        f"- Next stage: `{_display(report.get('next_stage'))}`",
        "",
        "## Production Boundary",
        "",
        "- Audit/contract review only: true",
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
        lines.append("_No replay sequences were available for contract review._")
        lines.append("")
    else:
        lines.extend(
            [
                "| Sequence | Target | Symbol | Status | Frames | Event markers | Blockers |",
                "| --- | --- | --- | --- | ---: | ---: | --- |",
            ]
        )
        for row in reviews:
            lines.append(
                "| "
                f"`{_display(row.get('sequence_id'))}` | "
                f"`{_display(row.get('target'))}` | "
                f"{_display(row.get('symbol'))} | "
                f"`{_display(row.get('contract_status'))}` | "
                f"{int(row.get('frame_count', 0))} | "
                f"{int(row.get('event_marker_count', 0))} | "
                f"{_csv(row.get('blockers', []))} |"
            )
        lines.append("")

    lines.extend(
        [
            "## Frontend Replay Contract",
            "",
            "- Later UI may consume `replay_sequences[].frames` as an offline replay timeline.",
            "- Exactly one event frame should contain the Effort/Result shadow marker.",
            "- Marker payloads remain disabled for scoring, ranking, actionability, alerts, orders, API visibility, and frontend visibility in this PR.",
            "- This report does not create UI or production behavior.",
            "",
        ]
    )
    return "\n".join(lines)


def _sequence_contract_review(sequence: Mapping[str, Any], *, min_frames: int) -> dict[str, object]:
    frames = _mapping_rows(sequence.get("frames", []))
    event_frames = [frame for frame in frames if bool(frame.get("is_event_bar"))]
    marker_frames = [frame for frame in frames if bool(frame.get("has_shadow_marker"))]
    markers = [
        frame.get("shadow_marker")
        for frame in marker_frames
        if isinstance(frame.get("shadow_marker"), Mapping)
    ]

    checks = {
        "required_sequence_fields": _has_required_fields(sequence, REQUIRED_SEQUENCE_FIELDS),
        "minimum_frames": len(frames) >= min_frames,
        "frame_offsets_are_sorted": _frame_offsets_are_sorted(frames),
        "required_frame_fields": all(_has_required_fields(frame, REQUIRED_FRAME_FIELDS) for frame in frames),
        "exactly_one_event_frame": len(event_frames) == 1,
        "exactly_one_shadow_marker": len(markers) == 1,
        "marker_matches_event_bar": _marker_matches_event(event_frames, markers),
        "marker_required_fields": all(_has_required_fields(marker, REQUIRED_MARKER_FIELDS) for marker in markers),
        "production_boundary_closed": (
            _production_boundary_closed(sequence)
            and all(_production_boundary_closed(frame) for frame in frames)
            and all(_production_boundary_closed(marker) for marker in markers)
        ),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    return {
        "sequence_id": _display(sequence.get("sequence_id")),
        "target": _display(sequence.get("target")),
        "symbol": _display(sequence.get("symbol")),
        "event_bar_index": sequence.get("event_bar_index"),
        "event_week_beginning": _display(sequence.get("event_week_beginning")),
        "frame_count": len(frames),
        "event_frame_count": len(event_frames),
        "event_marker_count": len(markers),
        "contract_status": CONTRACT_READY_STATUS if not blockers else CONTRACT_BLOCKED_STATUS,
        "checks": checks,
        "blockers": blockers,
        "production_change_allowed": False,
        "automatic_promotion_allowed": False,
        **PRODUCTION_BOUNDARY,
    }


def _report_blockers(
    report: Mapping[str, Any],
    sequence_reviews: Sequence[Mapping[str, Any]],
    *,
    min_sequences: int,
) -> list[str]:
    checks = {
        "source_replay_dataset_ready": report.get("replay_dataset_status") == SOURCE_READY_STATUS,
        "minimum_sequences": len(sequence_reviews) >= min_sequences,
        "all_sequences_ready": bool(sequence_reviews)
        and all(row.get("contract_status") == CONTRACT_READY_STATUS for row in sequence_reviews),
        "report_production_boundary_closed": _production_boundary_closed(report),
        "frontend_behavior_still_disabled": not bool(report.get("may_change_frontend"))
        and not bool(report.get("may_change_api")),
    }
    return [name for name, passed in checks.items() if not passed]


def _frontend_replay_contract(ready: bool) -> dict[str, object]:
    return {
        "contract_ready": bool(ready),
        "dataset_root": "replay_sequences",
        "sequence_key_fields": [
            "sequence_id",
            "target",
            "symbol",
            "event_bar_index",
            "event_week_beginning",
        ],
        "frame_array_field": "frames",
        "marker_field": "shadow_marker",
        "required_sequence_fields": list(REQUIRED_SEQUENCE_FIELDS),
        "required_frame_fields": list(REQUIRED_FRAME_FIELDS),
        "required_marker_fields": list(REQUIRED_MARKER_FIELDS),
        "disabled_production_surfaces": [
            "scoring",
            "ranking",
            "actionability",
            "alerts",
            "orders",
            "scanner_state",
            "persistence_as_signal",
            "api_visibility",
            "frontend_visibility",
        ],
        "requires_separate_frontend_pr": True,
        "requires_separate_production_pr": True,
        "production_change_allowed": False,
    }


def _has_required_fields(row: Mapping[str, Any], fields: Sequence[str]) -> bool:
    return all(field in row for field in fields)


def _frame_offsets_are_sorted(frames: Sequence[Mapping[str, Any]]) -> bool:
    offsets = [_int_or_none(frame.get("replay_offset")) for frame in frames]
    if any(offset is None for offset in offsets):
        return False
    return offsets == sorted(offsets)


def _marker_matches_event(
    event_frames: Sequence[Mapping[str, Any]],
    markers: Sequence[Mapping[str, Any]],
) -> bool:
    if len(event_frames) != 1 or len(markers) != 1:
        return False
    event_bar = _int_or_none(event_frames[0].get("bar_index"))
    marker_bar = _int_or_none(markers[0].get("bar_index"))
    return event_bar is not None and event_bar == marker_bar


def _production_boundary_closed(row: Mapping[str, Any]) -> bool:
    return all(not bool(row.get(field)) for field in UNSAFE_TRUTHY_FIELDS)


def _mapping_rows(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
        return []
    return [row for row in value if isinstance(row, Mapping)]


def _int_or_none(value: object) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _display(value: object) -> str:
    return "" if value is None else str(value)


def _csv(value: object) -> str:
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
        return ""
    return ", ".join(str(item) for item in value)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Review audit-only Effort/Result shadow replay dataset contracts."
    )
    parser.add_argument("replay_dataset_path", type=Path)
    parser.add_argument("--min-sequences", type=int, default=1)
    parser.add_argument("--min-frames-per-sequence", type=int, default=1)
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    replay_dataset = json.loads(args.replay_dataset_path.read_text(encoding="utf-8"))
    report = build_shadow_replay_contract_review(
        replay_dataset,
        min_sequences=args.min_sequences,
        min_frames_per_sequence=args.min_frames_per_sequence,
    )
    rendered = (
        render_shadow_replay_contract_review_markdown(report)
        if args.format == "markdown"
        else json.dumps(report, indent=2, sort_keys=True)
    )

    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
