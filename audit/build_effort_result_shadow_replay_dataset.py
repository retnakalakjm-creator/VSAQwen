"""Build Effort/Result shadow replay datasets for offline visual backtesting.

This module is audit/shadow/replay only. It converts shadow observation reports
into replay-ready symbol/week timelines for visual backtesting. It does not
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

REPORT_TYPE = "effort_result_shadow_replay_dataset"
REPORT_SCHEMA_VERSION = 1
SHADOW_OBSERVATION_STATUS = "shadow_observation_ready"
REPLAY_DATASET_READY_STATUS = "shadow_replay_dataset_ready"
REPLAY_DATASET_BLOCKED_STATUS = "blocked_pending_shadow_observations"
DEFAULT_LOOKBACK_BARS = 8
DEFAULT_FORWARD_BARS = 4

REQUIRED_VALIDATION_COLUMNS = {
    "symbol",
    "bar_index",
    "close",
    "volume_ratio",
    "spread_ratio",
}

OPTIONAL_CANDLE_COLUMNS = (
    "week_beginning",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "volume_ratio",
    "spread_ratio",
    "relationship",
    "effort_result_candidate",
    "existing_events",
)

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

PRODUCTION_BOUNDARY = {
    "audit_only": True,
    "shadow_mode_only": True,
    "replay_dataset_only": True,
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
    "requires_shadow_observation_report": True,
    "requires_separate_frontend_pr": True,
    "requires_separate_production_pr": True,
}


def build_effort_result_shadow_replay_dataset(
    validation_csv_path: Path,
    shadow_observations_report: Mapping[str, Any],
    *,
    lookback_bars: int = DEFAULT_LOOKBACK_BARS,
    forward_bars: int = DEFAULT_FORWARD_BARS,
    max_sequences: int | None = None,
) -> dict[str, object]:
    """Build a replay-ready dataset from audit-only shadow observations.

    The returned dataset is for offline visual backtesting and replay-contract
    review only. It must not be treated as a production signal feed.
    """

    if lookback_bars < 0:
        raise ValueError("lookback_bars must be non-negative")
    if forward_bars < 0:
        raise ValueError("forward_bars must be non-negative")
    if max_sequences is not None and max_sequences <= 0:
        raise ValueError("max_sequences must be positive when provided")

    df = _load_validation_frame(validation_csv_path)
    observations = _ready_shadow_observations(shadow_observations_report)
    if max_sequences is not None:
        observations = observations[:max_sequences]

    by_symbol = {
        str(symbol): symbol_rows.sort_values("bar_index").copy()
        for symbol, symbol_rows in df.groupby("symbol", sort=True)
    }

    sequences = [
        _replay_sequence(
            by_symbol=by_symbol,
            observation=observation,
            lookback_bars=lookback_bars,
            forward_bars=forward_bars,
        )
        for observation in observations
    ]
    sequences = [sequence for sequence in sequences if sequence["frames"]]
    target_summaries = _target_summaries(sequences)
    total_frames = sum(len(sequence["frames"]) for sequence in sequences)
    ready = bool(sequences)

    return {
        "report_type": REPORT_TYPE,
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "source": str(validation_csv_path),
        "source_report_type": shadow_observations_report.get("report_type"),
        "source_shadow_observation_status": shadow_observations_report.get("shadow_observation_status"),
        "rows": int(len(df)),
        "lookback_bars": int(lookback_bars),
        "forward_bars": int(forward_bars),
        "sequence_count": len(sequences),
        "total_frames": total_frames,
        "targets": sorted({str(sequence["target"]) for sequence in sequences}),
        "target_summaries": target_summaries,
        "replay_sequences": sequences,
        "disabled_production_surfaces": list(DISABLED_PRODUCTION_SURFACES),
        "replay_dataset_status": (
            REPLAY_DATASET_READY_STATUS if ready else REPLAY_DATASET_BLOCKED_STATUS
        ),
        "next_stage": (
            "shadow_replay_contract_review"
            if ready
            else "complete_shadow_observation_export"
        ),
        "automatic_promotion_allowed": False,
        **PRODUCTION_BOUNDARY,
    }


def render_shadow_replay_dataset_markdown(report: Mapping[str, Any]) -> str:
    """Render the replay dataset summary as Markdown."""

    lines = [
        "# Effort/Result Shadow Replay Dataset",
        "",
        "## Summary",
        "",
        f"- Source: `{_display(report.get('source'))}`",
        f"- Source report type: `{_display(report.get('source_report_type'))}`",
        f"- Source shadow status: `{_display(report.get('source_shadow_observation_status'))}`",
        f"- Replay dataset status: `{_display(report.get('replay_dataset_status'))}`",
        f"- Sequences: {int(report.get('sequence_count', 0))}",
        f"- Total frames: {int(report.get('total_frames', 0))}",
        f"- Lookback bars: {int(report.get('lookback_bars', 0))}",
        f"- Forward bars: {int(report.get('forward_bars', 0))}",
        f"- Next stage: `{_display(report.get('next_stage'))}`",
        "",
        "## Production Boundary",
        "",
        "- Audit/shadow/replay only: true",
        "- Production change allowed: false",
        "- Automatic promotion allowed: false",
        "- May change scoring: false",
        "- May change ranking: false",
        "- May change actionability: false",
        "- May activate detector: false",
        "- May change scanner/API/frontend behavior: false",
        "- Requires separate frontend PR: true",
        "- Requires separate production PR: true",
        "",
        "## Target Summaries",
        "",
    ]

    summaries = _mapping_rows(report.get("target_summaries", []))
    if not summaries:
        lines.append("_No ready shadow observations were available for replay._")
        lines.append("")
        return "\n".join(lines)

    lines.extend(
        [
            "| Target | Role | Sequences | Frames | Symbols | Week span |",
            "| --- | --- | ---: | ---: | --- | --- |",
        ]
    )
    for row in summaries:
        lines.append(
            "| "
            f"`{_display(row.get('target'))}` | "
            f"`{_display(row.get('shadow_signal_role'))}` | "
            f"{int(row.get('sequence_count', 0))} | "
            f"{int(row.get('frame_count', 0))} | "
            f"{_csv(row.get('symbols', []))} | "
            f"{_display(row.get('first_event_week'))} to {_display(row.get('last_event_week'))} |"
        )

    lines.extend(
        [
            "",
            "## Replay Contract",
            "",
            "- Each sequence is keyed by target, symbol, and event bar index.",
            "- Frames include candle/volume context and exactly one shadow marker at the event bar.",
            "- Shadow markers stay disabled for scoring, ranking, alerts, orders, API responses, and frontend display.",
            "- A later frontend PR can consume this dataset shape without changing production behavior.",
            "",
        ]
    )
    return "\n".join(lines)


def write_shadow_replay_dataset_csv(report: Mapping[str, Any], path: Path) -> None:
    """Write flattened replay frames as CSV."""

    rows: list[dict[str, object]] = []
    for sequence in _mapping_rows(report.get("replay_sequences", [])):
        sequence_id = _display(sequence.get("sequence_id"))
        for frame in _mapping_rows(sequence.get("frames", [])):
            row = {
                "sequence_id": sequence_id,
                "target": sequence.get("target", ""),
                "symbol": sequence.get("symbol", ""),
                "event_bar_index": sequence.get("event_bar_index", ""),
                "event_week_beginning": sequence.get("event_week_beginning", ""),
                **dict(frame),
            }
            marker = frame.get("shadow_marker")
            if isinstance(marker, Mapping):
                row.update(
                    {
                        "marker_target": marker.get("target", ""),
                        "marker_shadow_signal_role": marker.get("shadow_signal_role", ""),
                        "marker_event_labels": marker.get("event_labels", []),
                        "marker_observation_status": marker.get("observation_status", ""),
                    }
                )
            rows.append(row)

    fieldnames = _csv_fieldnames(rows)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_cell(row.get(key)) for key in fieldnames})


def _load_validation_frame(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = REQUIRED_VALIDATION_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    df = df.copy()
    df["symbol"] = df["symbol"].map(str)
    df["bar_index"] = pd.to_numeric(df["bar_index"], errors="coerce")
    for col in ("open", "high", "low", "close", "volume", "volume_ratio", "spread_ratio"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["symbol", "bar_index", "close", "volume_ratio", "spread_ratio"])
    df = df[(df.close > 0) & (df.volume_ratio > 0) & (df.spread_ratio > 0)]
    df["bar_index"] = df["bar_index"].astype(int)
    return df.sort_values(["symbol", "bar_index"]).reset_index(drop=True)


def _ready_shadow_observations(report: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    seen: set[tuple[str, str, int]] = set()
    for observation in _mapping_rows(report.get("observations", [])):
        if observation.get("observation_status") != SHADOW_OBSERVATION_STATUS:
            continue
        if not _shadow_boundary_is_closed(observation):
            continue
        target = _display(observation.get("target")).strip().upper()
        symbol = _display(observation.get("symbol")).strip()
        bar_index = _int_or_none(observation.get("bar_index"))
        if not target or not symbol or bar_index is None:
            continue
        key = (target, symbol, bar_index)
        if key in seen:
            continue
        seen.add(key)
        rows.append(observation)
    return sorted(rows, key=lambda row: (_display(row.get("target")), _display(row.get("symbol")), _int_or_none(row.get("bar_index")) or -1))


def _shadow_boundary_is_closed(observation: Mapping[str, Any]) -> bool:
    unsafe_truthy_fields = (
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
    return all(not bool(observation.get(field)) for field in unsafe_truthy_fields)


def _replay_sequence(
    *,
    by_symbol: Mapping[str, pd.DataFrame],
    observation: Mapping[str, Any],
    lookback_bars: int,
    forward_bars: int,
) -> dict[str, object]:
    target = _display(observation.get("target")).strip().upper()
    symbol = _display(observation.get("symbol")).strip()
    event_bar_index = _int_or_none(observation.get("bar_index"))
    if event_bar_index is None:
        return {"frames": []}

    symbol_rows = by_symbol.get(symbol)
    if symbol_rows is None or symbol_rows.empty:
        return {"frames": []}

    start_bar = event_bar_index - int(lookback_bars)
    end_bar = event_bar_index + int(forward_bars)
    window = symbol_rows[
        (symbol_rows.bar_index >= start_bar) & (symbol_rows.bar_index <= end_bar)
    ].sort_values("bar_index")
    frames = [
        _replay_frame(row, observation=observation, event_bar_index=event_bar_index)
        for _, row in window.iterrows()
    ]

    return {
        "sequence_id": f"{target}|{symbol}|{event_bar_index}",
        "target": target,
        "symbol": symbol,
        "event_bar_index": event_bar_index,
        "event_week_beginning": _display(observation.get("week_beginning")),
        "shadow_signal_role": _display(observation.get("shadow_signal_role")),
        "source_gate_status": _display(observation.get("source_gate_status")),
        "manual_review_status": _display(observation.get("manual_review_status")),
        "lookback_bars": int(lookback_bars),
        "forward_bars": int(forward_bars),
        "frame_count": len(frames),
        "frames": frames,
        "production_change_allowed": False,
        "automatic_promotion_allowed": False,
        **PRODUCTION_BOUNDARY,
    }


def _replay_frame(
    row: pd.Series,
    *,
    observation: Mapping[str, Any],
    event_bar_index: int,
) -> dict[str, object]:
    bar_index = int(row.bar_index)
    is_event_bar = bar_index == event_bar_index
    frame = {
        "bar_index": bar_index,
        "replay_offset": bar_index - event_bar_index,
        "week_beginning": _display(row.get("week_beginning", "")),
        "open": _numeric_or_blank(row.get("open", row.close)),
        "high": _numeric_or_blank(row.get("high", row.close)),
        "low": _numeric_or_blank(row.get("low", row.close)),
        "close": _numeric_or_blank(row.get("close", "")),
        "volume": _numeric_or_blank(row.get("volume", "")),
        "volume_ratio": _numeric_or_blank(row.get("volume_ratio", "")),
        "spread_ratio": _numeric_or_blank(row.get("spread_ratio", "")),
        "relationship": _display(row.get("relationship", "")),
        "effort_result_candidate": _display(row.get("effort_result_candidate", "")),
        "existing_events": _display(row.get("existing_events", "")),
        "is_event_bar": is_event_bar,
        "has_shadow_marker": is_event_bar,
        "shadow_marker": _shadow_marker(observation) if is_event_bar else None,
        "production_change_allowed": False,
        "include_in_scoring": False,
        "include_in_ranking": False,
        "include_in_actionability": False,
        "activate_detector": False,
        "api_visible": False,
        "frontend_visible": False,
    }
    return frame


def _shadow_marker(observation: Mapping[str, Any]) -> dict[str, object]:
    marker = {
        "target": _display(observation.get("target")).strip().upper(),
        "symbol": _display(observation.get("symbol")),
        "bar_index": _int_or_none(observation.get("bar_index")),
        "week_beginning": _display(observation.get("week_beginning")),
        "relationship": _display(observation.get("relationship")),
        "effort_result_candidate": _display(observation.get("effort_result_candidate")),
        "event_labels": _list_value(observation.get("event_labels", [])),
        "shadow_signal_role": _display(observation.get("shadow_signal_role")),
        "source_gate_status": _display(observation.get("source_gate_status")),
        "manual_review_status": _display(observation.get("manual_review_status")),
        "observation_status": _display(observation.get("observation_status")),
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
    }
    for key, value in observation.items():
        if str(key).startswith("forward_return_") or str(key).startswith("forward_up_"):
            marker[str(key)] = value
    return marker


def _target_summaries(sequences: Sequence[Mapping[str, Any]]) -> list[dict[str, object]]:
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for sequence in sequences:
        grouped.setdefault(_display(sequence.get("target")), []).append(sequence)

    summaries: list[dict[str, object]] = []
    for target, rows in sorted(grouped.items()):
        event_weeks = _sorted_unique(row.get("event_week_beginning") for row in rows)
        role_values = _sorted_unique(row.get("shadow_signal_role") for row in rows)
        summaries.append(
            {
                "target": target,
                "shadow_signal_role": role_values[0] if len(role_values) == 1 else ",".join(role_values),
                "sequence_count": len(rows),
                "frame_count": sum(int(row.get("frame_count", 0)) for row in rows),
                "symbols": _sorted_unique(row.get("symbol") for row in rows),
                "first_event_week": event_weeks[0] if event_weeks else "",
                "last_event_week": event_weeks[-1] if event_weeks else "",
                "production_surfaces_disabled": True,
                "disabled_production_surfaces": list(DISABLED_PRODUCTION_SURFACES),
                "automatic_promotion_allowed": False,
                **PRODUCTION_BOUNDARY,
            }
        )
    return summaries


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


def _int_or_none(value: object) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _display(value: object) -> str:
    return "" if value is None else str(value)


def _numeric_or_blank(value: object) -> float | str:
    try:
        if pd.isna(value):
            return ""
        return float(value)
    except (TypeError, ValueError):
        return ""


def _csv(value: object) -> str:
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
        return ""
    return ", ".join(str(item) for item in value)


def _csv_cell(value: object) -> object:
    if isinstance(value, Mapping):
        return json.dumps(value, sort_keys=True)
    if isinstance(value, (list, tuple, set)):
        return ",".join(str(item) for item in value)
    return value


def _csv_fieldnames(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    preferred = [
        "sequence_id",
        "target",
        "symbol",
        "event_bar_index",
        "event_week_beginning",
        "bar_index",
        "replay_offset",
        "week_beginning",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "volume_ratio",
        "spread_ratio",
        "relationship",
        "effort_result_candidate",
        "existing_events",
        "is_event_bar",
        "has_shadow_marker",
        "marker_target",
        "marker_shadow_signal_role",
        "marker_event_labels",
        "marker_observation_status",
        "include_in_scoring",
        "include_in_ranking",
        "include_in_actionability",
        "activate_detector",
        "api_visible",
        "frontend_visible",
        "production_change_allowed",
    ]
    discovered: list[str] = []
    for row in rows:
        for key in row:
            if key not in preferred and key not in discovered:
                discovered.append(key)
    return preferred + discovered


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build audit-only Effort/Result shadow replay datasets."
    )
    parser.add_argument("validation_csv_path", type=Path)
    parser.add_argument("shadow_observations_path", type=Path)
    parser.add_argument("--lookback-bars", type=int, default=DEFAULT_LOOKBACK_BARS)
    parser.add_argument("--forward-bars", type=int, default=DEFAULT_FORWARD_BARS)
    parser.add_argument("--max-sequences", type=int, default=0)
    parser.add_argument("--format", choices=("json", "markdown", "csv"), default="json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    observations_report = json.loads(args.shadow_observations_path.read_text(encoding="utf-8"))
    report = build_effort_result_shadow_replay_dataset(
        args.validation_csv_path,
        observations_report,
        lookback_bars=args.lookback_bars,
        forward_bars=args.forward_bars,
        max_sequences=args.max_sequences or None,
    )

    if args.format == "csv":
        if not args.output:
            raise ValueError("--output is required for csv format")
        write_shadow_replay_dataset_csv(report, args.output)
        return

    rendered = (
        render_shadow_replay_dataset_markdown(report)
        if args.format == "markdown"
        else json.dumps(report, indent=2, sort_keys=True)
    )
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
