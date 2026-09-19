"""Build an offline replay dataset from frozen K24 shadow semantics.

The builder consumes K24 projection artifacts plus local frozen weekly history.
It resolves each event by exact event_week, never by source row index, and emits
replay-ready windows without changing production behavior.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

from daily_completion import completed_daily_only
from data import completed_weekly_only, daily_to_weekly
from trading_calendar import NSETradingCalendar, TradingCalendar


PROGRESSION_SHADOW_REPLAY_DATASET_ID = (
    "progression-shadow-semantic-replay-dataset-v1"
)
EXPECTED_K24_AUDIT_ID = "progression-shadow-semantic-projection-v1"


@dataclass(frozen=True, slots=True)
class FrozenShadowSemanticRow:
    symbol: str
    source_event_bar_index: int
    event_week: str
    event_code: str
    event_direction: str
    trend_direction: str
    trend_alignment: str
    semantic_role: str
    projected_transition_direction: str | None


@dataclass(frozen=True, slots=True)
class FrozenShadowSemanticArtifact:
    basket_name: str
    requested_symbol_count: int
    event_count: int
    rows_by_symbol: dict[str, tuple[FrozenShadowSemanticRow, ...]]


@dataclass(frozen=True, slots=True)
class ProgressionShadowReplayFrame:
    bar_index: int
    week: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    is_event_bar: bool
    event_direction: str | None
    trend_alignment: str | None
    semantic_role: str | None
    projected_transition_direction: str | None
    reversal_confirmed: bool = False
    persistent_direction_claim: bool = False
    affects_qualification: bool = False
    affects_scoring: bool = False
    is_actionable: bool = False


@dataclass(frozen=True, slots=True)
class ProgressionShadowReplaySequence:
    sequence_id: str
    symbol: str
    source_event_bar_index: int
    resolved_event_bar_index: int
    event_week: str
    event_code: str
    event_direction: str
    trend_alignment: str
    semantic_role: str
    projected_transition_direction: str | None
    lookback_bars: int
    forward_bars: int
    frames: tuple[ProgressionShadowReplayFrame, ...]


@dataclass(frozen=True, slots=True)
class ProgressionShadowReplayFailure:
    symbol: str
    exception_type: str
    reason: str


@dataclass(frozen=True, slots=True)
class ProgressionShadowReplayDatasetAudit:
    audit_id: str
    basket_name: str
    requested_symbol_count: int
    source_event_count: int
    sequence_count: int
    total_frame_count: int
    lookback_bars: int
    forward_bars: int
    sequences: tuple[ProgressionShadowReplaySequence, ...]
    failures: tuple[ProgressionShadowReplayFailure, ...]

    @property
    def is_actionable(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class ProgressionShadowReplayDatasetPaths:
    summary_json: Path
    dataset_json: Path
    sequences_csv: Path
    failures_csv: Path

    def as_dict(self) -> dict[str, str]:
        return {
            "summary_json": str(self.summary_json),
            "dataset_json": str(self.dataset_json),
            "sequences_csv": str(self.sequences_csv),
            "failures_csv": str(self.failures_csv),
        }


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"true", "1"}:
        return True
    if normalized in {"false", "0"}:
        return False
    raise ValueError(f"unsupported boolean value: {value!r}")


def _optional_string(value: object) -> str | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def load_frozen_shadow_semantic_artifact(
    *,
    input_dir: str | Path,
    expected_basket_name: str,
) -> FrozenShadowSemanticArtifact:
    root = Path(input_dir)
    summary_path = root / "progression_shadow_semantic_summary.json"
    rows_path = root / "progression_shadow_semantic_rows.csv"
    if not summary_path.exists():
        raise FileNotFoundError(f"missing K24 summary: {summary_path}")
    if not rows_path.exists():
        raise FileNotFoundError(f"missing K24 rows: {rows_path}")

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("audit_id") != EXPECTED_K24_AUDIT_ID:
        raise ValueError("K24 audit_id does not match expected audit")
    if summary.get("basket_name") != expected_basket_name:
        raise ValueError("K24 basket does not match requested basket")

    frame = pd.read_csv(rows_path)
    required = {
        "symbol",
        "event_bar_index",
        "event_week",
        "event_code",
        "event_direction",
        "trend_direction",
        "trend_alignment",
        "semantic_role",
        "projected_transition_direction",
        "reversal_confirmed",
        "persistent_direction_claim",
        "affects_qualification",
        "affects_scoring",
        "is_actionable",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"K24 rows missing columns: {missing}")
    if len(frame) != int(summary["event_count"]):
        raise ValueError("K24 row count does not match summary event_count")

    unsafe_fields = (
        "reversal_confirmed",
        "persistent_direction_claim",
        "affects_qualification",
        "affects_scoring",
        "is_actionable",
    )
    for field in unsafe_fields:
        if any(_as_bool(value) for value in frame[field]):
            raise ValueError(f"K24 unsafe flag is true: {field}")

    rows_by_symbol: dict[str, list[FrozenShadowSemanticRow]] = {}
    seen: set[tuple[str, str, str]] = set()
    for raw in frame.itertuples(index=False):
        symbol = str(raw.symbol).strip().upper()
        key = (symbol, str(raw.event_week), str(raw.event_code))
        if key in seen:
            raise ValueError(f"duplicate K24 event identity: {key}")
        seen.add(key)
        rows_by_symbol.setdefault(symbol, []).append(
            FrozenShadowSemanticRow(
                symbol=symbol,
                source_event_bar_index=int(raw.event_bar_index),
                event_week=str(raw.event_week),
                event_code=str(raw.event_code),
                event_direction=str(raw.event_direction),
                trend_direction=str(raw.trend_direction),
                trend_alignment=str(raw.trend_alignment),
                semantic_role=str(raw.semantic_role),
                projected_transition_direction=_optional_string(
                    raw.projected_transition_direction
                ),
            )
        )

    return FrozenShadowSemanticArtifact(
        basket_name=expected_basket_name,
        requested_symbol_count=int(summary["requested_symbol_count"]),
        event_count=int(summary["event_count"]),
        rows_by_symbol={
            symbol: tuple(rows)
            for symbol, rows in rows_by_symbol.items()
        },
    )


def _resolve_event_bar_index(
    weekly: pd.DataFrame,
    *,
    symbol: str,
    event_week: str,
) -> int:
    expected = pd.Timestamp(event_week).normalize()
    weeks = pd.to_datetime(weekly["week_beginning"]).dt.normalize()
    matches = weeks[weeks == expected].index.tolist()
    if not matches:
        raise ValueError(
            f"{symbol} event week absent from completed weekly history: "
            f"{expected.date()}"
        )
    if len(matches) != 1:
        raise ValueError(
            f"{symbol} event week is not unique: {expected.date()}"
        )
    return int(weekly.index.get_loc(matches[0]))


def build_symbol_shadow_replay_sequences(
    *,
    symbol: str,
    daily: pd.DataFrame,
    events: tuple[FrozenShadowSemanticRow, ...],
    now: str | pd.Timestamp | None,
    lookback_bars: int = 4,
    forward_bars: int = 4,
    calendar: TradingCalendar | None = None,
) -> tuple[ProgressionShadowReplaySequence, ...]:
    if lookback_bars < 0 or forward_bars < 0:
        raise ValueError("replay window sizes must be non-negative")
    if not events:
        return ()

    exchange_calendar = calendar or NSETradingCalendar()
    completed_daily = completed_daily_only(
        daily,
        now=now,
        calendar=exchange_calendar,
    )
    weekly = completed_weekly_only(
        daily_to_weekly(completed_daily),
        now=now,
    )
    if weekly.empty:
        raise ValueError("no completed weekly bars are available")

    sequences: list[ProgressionShadowReplaySequence] = []
    for event in events:
        if event.symbol != symbol:
            raise ValueError(
                f"{symbol} received event for {event.symbol}"
            )
        resolved = _resolve_event_bar_index(
            weekly,
            symbol=symbol,
            event_week=event.event_week,
        )
        start = max(0, resolved - lookback_bars)
        end = min(len(weekly) - 1, resolved + forward_bars)
        frames: list[ProgressionShadowReplayFrame] = []
        for index in range(start, end + 1):
            raw = weekly.iloc[index]
            is_event = index == resolved
            frames.append(
                ProgressionShadowReplayFrame(
                    bar_index=index,
                    week=str(raw["week_beginning"]),
                    open=float(raw["open"]),
                    high=float(raw["high"]),
                    low=float(raw["low"]),
                    close=float(raw["close"]),
                    volume=float(raw["volume"]),
                    is_event_bar=is_event,
                    event_direction=(
                        event.event_direction if is_event else None
                    ),
                    trend_alignment=(
                        event.trend_alignment if is_event else None
                    ),
                    semantic_role=(
                        event.semantic_role if is_event else None
                    ),
                    projected_transition_direction=(
                        event.projected_transition_direction
                        if is_event
                        else None
                    ),
                )
            )

        if sum(item.is_event_bar for item in frames) != 1:
            raise ValueError(
                f"{symbol} replay window must contain one event bar"
            )

        sequences.append(
            ProgressionShadowReplaySequence(
                sequence_id=(
                    f"{symbol}|{event.event_week}|{event.event_code}"
                ),
                symbol=symbol,
                source_event_bar_index=event.source_event_bar_index,
                resolved_event_bar_index=resolved,
                event_week=event.event_week,
                event_code=event.event_code,
                event_direction=event.event_direction,
                trend_alignment=event.trend_alignment,
                semantic_role=event.semantic_role,
                projected_transition_direction=(
                    event.projected_transition_direction
                ),
                lookback_bars=lookback_bars,
                forward_bars=forward_bars,
                frames=tuple(frames),
            )
        )

    return tuple(sequences)


def build_progression_shadow_replay_dataset_audit(
    *,
    artifact: FrozenShadowSemanticArtifact,
    requested_symbols: tuple[str, ...],
    symbol_sequences: tuple[
        tuple[ProgressionShadowReplaySequence, ...],
        ...,
    ],
    lookback_bars: int,
    forward_bars: int,
    failures: tuple[ProgressionShadowReplayFailure, ...] = (),
) -> ProgressionShadowReplayDatasetAudit:
    if len(symbol_sequences) + len(failures) != len(requested_symbols):
        raise ValueError(
            "successful plus failed symbols must equal requested symbols"
        )

    source_row_count = sum(
        len(rows) for rows in artifact.rows_by_symbol.values()
    )
    if source_row_count != artifact.event_count:
        raise ValueError(
            f"K24 grouped event count mismatch: "
            f"{source_row_count} != {artifact.event_count}"
        )

    failure_symbols = [item.symbol for item in failures]
    if len(set(failure_symbols)) != len(failure_symbols):
        raise ValueError("failure symbols must be unique")
    failed_symbols = set(failure_symbols)
    expected_sequences = sum(
        len(artifact.rows_by_symbol.get(symbol, ()))
        for symbol in requested_symbols
        if symbol not in failed_symbols
    )
    sequences = tuple(
        item for group in symbol_sequences for item in group
    )
    if len(sequences) != expected_sequences:
        raise ValueError(
            f"replay sequence count mismatch: "
            f"{len(sequences)} != {expected_sequences}"
        )

    seen: set[str] = set()
    for sequence in sequences:
        if sequence.sequence_id in seen:
            raise ValueError(
                f"duplicate replay sequence: {sequence.sequence_id}"
            )
        seen.add(sequence.sequence_id)

    return ProgressionShadowReplayDatasetAudit(
        audit_id=PROGRESSION_SHADOW_REPLAY_DATASET_ID,
        basket_name=artifact.basket_name,
        requested_symbol_count=len(requested_symbols),
        source_event_count=artifact.event_count,
        sequence_count=len(sequences),
        total_frame_count=sum(
            len(sequence.frames) for sequence in sequences
        ),
        lookback_bars=lookback_bars,
        forward_bars=forward_bars,
        sequences=sequences,
        failures=tuple(sorted(failures, key=lambda item: item.symbol)),
    )


def write_progression_shadow_replay_dataset(
    audit: ProgressionShadowReplayDatasetAudit,
    output_dir: str | Path,
) -> ProgressionShadowReplayDatasetPaths:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    paths = ProgressionShadowReplayDatasetPaths(
        summary_json=root / "progression_shadow_replay_dataset_summary.json",
        dataset_json=root / "progression_shadow_replay_dataset.json",
        sequences_csv=root / "progression_shadow_replay_sequences.csv",
        failures_csv=root / "progression_shadow_replay_failures.csv",
    )

    summary = {
        "audit_id": audit.audit_id,
        "basket_name": audit.basket_name,
        "requested_symbol_count": audit.requested_symbol_count,
        "source_event_count": audit.source_event_count,
        "sequence_count": audit.sequence_count,
        "total_frame_count": audit.total_frame_count,
        "lookback_bars": audit.lookback_bars,
        "forward_bars": audit.forward_bars,
        "failed_symbol_count": len(audit.failures),
        "dataset_status": (
            "shadow_replay_dataset_ready"
            if not audit.failures
            else "shadow_replay_dataset_partial"
        ),
        "reversal_confirmed": False,
        "persistent_direction_claim": False,
        "affects_qualification": False,
        "affects_scoring": False,
        "is_actionable": False,
    }
    paths.summary_json.write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    dataset = {
        **summary,
        "replay_sequences": [asdict(item) for item in audit.sequences],
    }
    paths.dataset_json.write_text(
        json.dumps(dataset, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            {
                **{
                    key: value
                    for key, value in asdict(item).items()
                    if key != "frames"
                },
                "frame_count": len(item.frames),
            }
            for item in audit.sequences
        ]
    ).to_csv(paths.sequences_csv, index=False)
    pd.DataFrame(
        [asdict(item) for item in audit.failures],
        columns=("symbol", "exception_type", "reason"),
    ).to_csv(paths.failures_csv, index=False)
    return paths


__all__ = [
    "EXPECTED_K24_AUDIT_ID",
    "PROGRESSION_SHADOW_REPLAY_DATASET_ID",
    "FrozenShadowSemanticArtifact",
    "FrozenShadowSemanticRow",
    "ProgressionShadowReplayDatasetAudit",
    "ProgressionShadowReplayDatasetPaths",
    "ProgressionShadowReplayFailure",
    "ProgressionShadowReplayFrame",
    "ProgressionShadowReplaySequence",
    "build_progression_shadow_replay_dataset_audit",
    "build_symbol_shadow_replay_sequences",
    "load_frozen_shadow_semantic_artifact",
    "write_progression_shadow_replay_dataset",
]
