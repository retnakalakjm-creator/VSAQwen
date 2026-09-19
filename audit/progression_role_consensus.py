"""Event-level consensus audit for progression roles across control windows.

K21 consumes frozen K20 role rows and collapses the 26/52/104-window
classifications into one row per event and horizon. This prevents repeated
window-specific rows from being interpreted as independent evidence.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd


PROGRESSION_ROLE_CONSENSUS_AUDIT_ID = (
    "progression-role-window-consensus-v1"
)
EXPECTED_K20_AUDIT_ID = "progression-role-classification-v1"

CONSENSUS_ACTUAL_REVERSAL = "ACTUAL_REVERSAL"
CONSENSUS_DECELERATION = "CONSENSUS_DECELERATION"
CONSENSUS_DECELERATION_UNSTABLE = "WINDOW_SENSITIVE_DECELERATION"
CONSENSUS_FAILED_COUNTERTREND = "FAILED_COUNTERTREND_WARNING"
CONSENSUS_CONTINUATION_OUTPERFORMS = (
    "CONSENSUS_CONTINUATION_OUTPERFORMS"
)
CONSENSUS_CONTINUATION_UNSTABLE = (
    "WINDOW_SENSITIVE_CONTINUATION_OUTPERFORMANCE"
)
CONSENSUS_CONTINUATION_WEAKER = "CONTINUATION_WEAKER_THAN_BASELINE"
CONSENSUS_CONTINUATION_FAILED = "CONTINUATION_FAILED"
CONSENSUS_NEUTRAL = "NEUTRAL_CONTEXT"
CONSENSUS_INCOMPLETE = "INCOMPLETE"


@dataclass(frozen=True, slots=True)
class FrozenProgressionRoleRow:
    symbol: str
    event_week: str
    event_direction: str
    trend_alignment: str
    horizon_weeks: int
    control_window_size: int
    control_count: int
    event_favorable_return: float | None
    baseline_mean_favorable_return: float | None
    favorable_return_lift: float | None
    role: str
    usable: bool
    actual_reversal: bool
    transition_improvement: bool
    continuation_positive: bool
    continuation_outperforms: bool


@dataclass(frozen=True, slots=True)
class FrozenProgressionRoleArtifact:
    basket_name: str
    requested_symbol_count: int
    source_event_count: int
    source_observation_count: int
    source_comparison_row_count: int
    classified_row_count: int
    control_windows: tuple[int, ...]
    rows: tuple[FrozenProgressionRoleRow, ...]


@dataclass(frozen=True, slots=True)
class ProgressionRoleConsensusRow:
    symbol: str
    event_week: str
    event_direction: str
    trend_alignment: str
    horizon_weeks: int
    usable: bool
    event_favorable_return: float | None
    window_count: int
    majority_threshold: int
    positive_transition_windows: int
    positive_continuation_windows: int
    consensus_role: str
    robust_across_windows: bool


@dataclass(frozen=True, slots=True)
class ProgressionRoleConsensusSummary:
    cohort_dimension: str
    cohort_value: str
    horizon_weeks: int
    usable_row_count: int
    symbol_count: int
    actual_reversal_count: int
    actual_reversal_rate: float | None
    consensus_deceleration_count: int
    consensus_deceleration_rate: float | None
    unstable_deceleration_count: int
    unstable_deceleration_rate: float | None
    failed_countertrend_count: int
    failed_countertrend_rate: float | None
    consensus_continuation_outperform_count: int
    consensus_continuation_outperform_rate: float | None
    unstable_continuation_count: int
    unstable_continuation_rate: float | None
    continuation_weaker_count: int
    continuation_weaker_rate: float | None
    continuation_failed_count: int
    continuation_failed_rate: float | None
    robust_role_count: int
    robust_role_rate: float | None


@dataclass(frozen=True, slots=True)
class ProgressionRoleConsensusAudit:
    audit_id: str
    basket_name: str
    requested_symbol_count: int
    source_event_count: int
    source_observation_count: int
    source_comparison_row_count: int
    source_classified_row_count: int
    consensus_row_count: int
    control_windows: tuple[int, ...]
    majority_threshold: int
    rows: tuple[ProgressionRoleConsensusRow, ...]
    summaries: tuple[ProgressionRoleConsensusSummary, ...]

    @property
    def is_actionable(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class ProgressionRoleConsensusAuditPaths:
    summary_json: Path
    rows_csv: Path
    cohorts_csv: Path

    def as_dict(self) -> dict[str, str]:
        return {
            "summary_json": str(self.summary_json),
            "rows_csv": str(self.rows_csv),
            "cohorts_csv": str(self.cohorts_csv),
        }


def _optional_float(value: object) -> float | None:
    if pd.isna(value):
        return None
    return float(value)


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"true", "1"}:
        return True
    if normalized in {"false", "0"}:
        return False
    raise ValueError(f"unsupported boolean value: {value!r}")


def load_frozen_progression_role_artifacts(
    *,
    input_dir: str | Path,
    expected_basket_name: str,
) -> FrozenProgressionRoleArtifact:
    root = Path(input_dir)
    summary_path = root / "progression_role_summary.json"
    rows_path = root / "progression_role_rows.csv"
    if not summary_path.exists():
        raise FileNotFoundError(
            f"missing K20 summary artifact: {summary_path}"
        )
    if not rows_path.exists():
        raise FileNotFoundError(
            f"missing K20 row artifact: {rows_path}"
        )

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("audit_id") != EXPECTED_K20_AUDIT_ID:
        raise ValueError("K20 audit_id does not match expected audit")
    if summary.get("basket_name") != expected_basket_name:
        raise ValueError(
            "K20 basket does not match requested basket: "
            f"{summary.get('basket_name')!r} != "
            f"{expected_basket_name!r}"
        )

    windows = tuple(
        sorted({int(item) for item in summary["control_windows"]})
    )
    if not windows or any(item <= 0 for item in windows):
        raise ValueError("K20 control windows must be positive")

    frame = pd.read_csv(rows_path)
    required = {
        "symbol",
        "event_week",
        "event_direction",
        "trend_alignment",
        "horizon_weeks",
        "control_window_size",
        "control_count",
        "event_favorable_return",
        "baseline_mean_favorable_return",
        "favorable_return_lift",
        "role",
        "usable",
        "actual_reversal",
        "transition_improvement",
        "continuation_positive",
        "continuation_outperforms",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(
            f"K20 row artifact is missing columns: {missing}"
        )

    expected_rows = int(summary["classified_row_count"])
    if len(frame) != expected_rows:
        raise ValueError(
            f"K20 row count mismatch: {len(frame)} != {expected_rows}"
        )

    rows: list[FrozenProgressionRoleRow] = []
    seen: set[tuple[str, str, str, int, int]] = set()
    for raw in frame.itertuples(index=False):
        row = FrozenProgressionRoleRow(
            symbol=str(raw.symbol).strip().upper(),
            event_week=str(raw.event_week),
            event_direction=str(raw.event_direction),
            trend_alignment=str(raw.trend_alignment),
            horizon_weeks=int(raw.horizon_weeks),
            control_window_size=int(raw.control_window_size),
            control_count=int(raw.control_count),
            event_favorable_return=_optional_float(
                raw.event_favorable_return
            ),
            baseline_mean_favorable_return=_optional_float(
                raw.baseline_mean_favorable_return
            ),
            favorable_return_lift=_optional_float(
                raw.favorable_return_lift
            ),
            role=str(raw.role),
            usable=_as_bool(raw.usable),
            actual_reversal=_as_bool(raw.actual_reversal),
            transition_improvement=_as_bool(
                raw.transition_improvement
            ),
            continuation_positive=_as_bool(
                raw.continuation_positive
            ),
            continuation_outperforms=_as_bool(
                raw.continuation_outperforms
            ),
        )
        if row.control_window_size not in windows:
            raise ValueError(
                f"unexpected K20 control window: "
                f"{row.control_window_size}"
            )
        key = (
            row.symbol,
            row.event_week,
            row.event_direction,
            row.horizon_weeks,
            row.control_window_size,
        )
        if key in seen:
            raise ValueError(f"duplicate K20 role row: {key}")
        seen.add(key)
        rows.append(row)

    return FrozenProgressionRoleArtifact(
        basket_name=expected_basket_name,
        requested_symbol_count=int(summary["requested_symbol_count"]),
        source_event_count=int(summary["source_event_count"]),
        source_observation_count=int(
            summary["source_observation_count"]
        ),
        source_comparison_row_count=int(
            summary["source_comparison_row_count"]
        ),
        classified_row_count=expected_rows,
        control_windows=windows,
        rows=tuple(rows),
    )


def _same_optional_float(
    values: tuple[float | None, ...],
    *,
    tolerance: float = 1e-12,
) -> bool:
    present = [item for item in values if item is not None]
    if len(present) != len(values):
        return not present
    anchor = present[0]
    return all(abs(item - anchor) <= tolerance for item in present[1:])


def _consensus_group(
    *,
    group: tuple[FrozenProgressionRoleRow, ...],
    control_windows: tuple[int, ...],
) -> ProgressionRoleConsensusRow:
    if not group:
        raise ValueError("consensus group cannot be empty")

    first = group[0]
    windows = tuple(sorted(item.control_window_size for item in group))
    if windows != control_windows:
        raise ValueError(
            f"{first.symbol} {first.event_week} horizon "
            f"{first.horizon_weeks} missing control windows: "
            f"{windows} != {control_windows}"
        )

    invariant_fields = (
        "symbol",
        "event_week",
        "event_direction",
        "trend_alignment",
        "horizon_weeks",
    )
    for item in group[1:]:
        for field in invariant_fields:
            if getattr(item, field) != getattr(first, field):
                raise ValueError(
                    f"window consensus identity mismatch for {field}"
                )

    usable_values = {item.usable for item in group}
    reversal_values = {item.actual_reversal for item in group}
    continuation_values = {
        item.continuation_positive for item in group
    }
    if len(usable_values) != 1:
        raise ValueError("usable state must be stable across windows")
    if len(reversal_values) != 1:
        raise ValueError(
            "actual reversal state must be stable across windows"
        )
    if len(continuation_values) != 1:
        raise ValueError(
            "continuation-positive state must be stable across windows"
        )

    event_returns = tuple(
        item.event_favorable_return for item in group
    )
    if not _same_optional_float(event_returns):
        raise ValueError(
            "event favorable return must be stable across windows"
        )

    usable = first.usable
    majority = len(control_windows) // 2 + 1
    positive_transition = sum(
        item.transition_improvement for item in group
    )
    positive_continuation = sum(
        item.continuation_outperforms for item in group
    )

    if not usable:
        role = CONSENSUS_INCOMPLETE
        robust = False
    elif first.trend_alignment == "opposed":
        if first.actual_reversal:
            role = CONSENSUS_ACTUAL_REVERSAL
            robust = True
        elif positive_transition >= majority:
            role = CONSENSUS_DECELERATION
            robust = positive_transition == len(control_windows)
        elif positive_transition > 0:
            role = CONSENSUS_DECELERATION_UNSTABLE
            robust = False
        else:
            role = CONSENSUS_FAILED_COUNTERTREND
            robust = True
    elif first.trend_alignment == "aligned":
        if not first.continuation_positive:
            role = CONSENSUS_CONTINUATION_FAILED
            robust = True
        elif positive_continuation >= majority:
            role = CONSENSUS_CONTINUATION_OUTPERFORMS
            robust = positive_continuation == len(control_windows)
        elif positive_continuation > 0:
            role = CONSENSUS_CONTINUATION_UNSTABLE
            robust = False
        else:
            role = CONSENSUS_CONTINUATION_WEAKER
            robust = True
    else:
        role = CONSENSUS_NEUTRAL
        robust = True

    return ProgressionRoleConsensusRow(
        symbol=first.symbol,
        event_week=first.event_week,
        event_direction=first.event_direction,
        trend_alignment=first.trend_alignment,
        horizon_weeks=first.horizon_weeks,
        usable=usable,
        event_favorable_return=first.event_favorable_return,
        window_count=len(control_windows),
        majority_threshold=majority,
        positive_transition_windows=positive_transition,
        positive_continuation_windows=positive_continuation,
        consensus_role=role,
        robust_across_windows=robust,
    )


def build_progression_role_consensus_rows(
    artifact: FrozenProgressionRoleArtifact,
) -> tuple[ProgressionRoleConsensusRow, ...]:
    groups: dict[
        tuple[str, str, str, str, int],
        list[FrozenProgressionRoleRow],
    ] = defaultdict(list)
    for row in artifact.rows:
        key = (
            row.symbol,
            row.event_week,
            row.event_direction,
            row.trend_alignment,
            row.horizon_weeks,
        )
        groups[key].append(row)

    rows = tuple(
        _consensus_group(
            group=tuple(
                sorted(
                    items,
                    key=lambda item: item.control_window_size,
                )
            ),
            control_windows=artifact.control_windows,
        )
        for _, items in sorted(groups.items())
    )

    if len(rows) != artifact.source_observation_count:
        raise ValueError(
            "consensus rows must collapse K20 comparisons to the "
            "source observation count: "
            f"{len(rows)} != {artifact.source_observation_count}"
        )
    return rows


def _rate(count: int, total: int) -> float | None:
    return None if total == 0 else count / total


def _cohort_keys(
    row: ProgressionRoleConsensusRow,
) -> tuple[tuple[str, str], ...]:
    return (
        ("all", "all"),
        ("event_direction", row.event_direction),
        ("trend_alignment", row.trend_alignment),
        (
            "direction_trend_alignment",
            f"{row.event_direction}|{row.trend_alignment}",
        ),
    )


def summarize_progression_role_consensus(
    rows: tuple[ProgressionRoleConsensusRow, ...],
) -> tuple[ProgressionRoleConsensusSummary, ...]:
    groups: dict[
        tuple[str, str, int],
        list[ProgressionRoleConsensusRow],
    ] = defaultdict(list)
    for row in rows:
        for dimension, value in _cohort_keys(row):
            groups[(dimension, value, row.horizon_weeks)].append(row)

    output: list[ProgressionRoleConsensusSummary] = []
    for (dimension, value, horizon), group in groups.items():
        usable = [item for item in group if item.usable]
        counts = Counter(item.consensus_role for item in usable)
        symbols = {item.symbol for item in usable}

        transition_total = sum(
            counts[role]
            for role in (
                CONSENSUS_ACTUAL_REVERSAL,
                CONSENSUS_DECELERATION,
                CONSENSUS_DECELERATION_UNSTABLE,
                CONSENSUS_FAILED_COUNTERTREND,
            )
        )
        continuation_total = sum(
            counts[role]
            for role in (
                CONSENSUS_CONTINUATION_OUTPERFORMS,
                CONSENSUS_CONTINUATION_UNSTABLE,
                CONSENSUS_CONTINUATION_WEAKER,
                CONSENSUS_CONTINUATION_FAILED,
            )
        )
        robust_count = sum(item.robust_across_windows for item in usable)

        output.append(
            ProgressionRoleConsensusSummary(
                cohort_dimension=dimension,
                cohort_value=value,
                horizon_weeks=horizon,
                usable_row_count=len(usable),
                symbol_count=len(symbols),
                actual_reversal_count=counts[
                    CONSENSUS_ACTUAL_REVERSAL
                ],
                actual_reversal_rate=_rate(
                    counts[CONSENSUS_ACTUAL_REVERSAL],
                    transition_total,
                ),
                consensus_deceleration_count=counts[
                    CONSENSUS_DECELERATION
                ],
                consensus_deceleration_rate=_rate(
                    counts[CONSENSUS_DECELERATION],
                    transition_total,
                ),
                unstable_deceleration_count=counts[
                    CONSENSUS_DECELERATION_UNSTABLE
                ],
                unstable_deceleration_rate=_rate(
                    counts[CONSENSUS_DECELERATION_UNSTABLE],
                    transition_total,
                ),
                failed_countertrend_count=counts[
                    CONSENSUS_FAILED_COUNTERTREND
                ],
                failed_countertrend_rate=_rate(
                    counts[CONSENSUS_FAILED_COUNTERTREND],
                    transition_total,
                ),
                consensus_continuation_outperform_count=counts[
                    CONSENSUS_CONTINUATION_OUTPERFORMS
                ],
                consensus_continuation_outperform_rate=_rate(
                    counts[CONSENSUS_CONTINUATION_OUTPERFORMS],
                    continuation_total,
                ),
                unstable_continuation_count=counts[
                    CONSENSUS_CONTINUATION_UNSTABLE
                ],
                unstable_continuation_rate=_rate(
                    counts[CONSENSUS_CONTINUATION_UNSTABLE],
                    continuation_total,
                ),
                continuation_weaker_count=counts[
                    CONSENSUS_CONTINUATION_WEAKER
                ],
                continuation_weaker_rate=_rate(
                    counts[CONSENSUS_CONTINUATION_WEAKER],
                    continuation_total,
                ),
                continuation_failed_count=counts[
                    CONSENSUS_CONTINUATION_FAILED
                ],
                continuation_failed_rate=_rate(
                    counts[CONSENSUS_CONTINUATION_FAILED],
                    continuation_total,
                ),
                robust_role_count=robust_count,
                robust_role_rate=_rate(
                    robust_count,
                    len(usable),
                ),
            )
        )

    return tuple(
        sorted(
            output,
            key=lambda item: (
                item.cohort_dimension,
                item.cohort_value,
                item.horizon_weeks,
            ),
        )
    )


def build_progression_role_consensus_audit(
    artifact: FrozenProgressionRoleArtifact,
) -> ProgressionRoleConsensusAudit:
    rows = build_progression_role_consensus_rows(artifact)
    return ProgressionRoleConsensusAudit(
        audit_id=PROGRESSION_ROLE_CONSENSUS_AUDIT_ID,
        basket_name=artifact.basket_name,
        requested_symbol_count=artifact.requested_symbol_count,
        source_event_count=artifact.source_event_count,
        source_observation_count=artifact.source_observation_count,
        source_comparison_row_count=artifact.source_comparison_row_count,
        source_classified_row_count=artifact.classified_row_count,
        consensus_row_count=len(rows),
        control_windows=artifact.control_windows,
        majority_threshold=len(artifact.control_windows) // 2 + 1,
        rows=rows,
        summaries=summarize_progression_role_consensus(rows),
    )


def write_progression_role_consensus_audit(
    audit: ProgressionRoleConsensusAudit,
    output_dir: str | Path,
) -> ProgressionRoleConsensusAuditPaths:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    paths = ProgressionRoleConsensusAuditPaths(
        summary_json=root / "progression_role_consensus_summary.json",
        rows_csv=root / "progression_role_consensus_rows.csv",
        cohorts_csv=root / "progression_role_consensus_cohorts.csv",
    )

    key_summaries = [
        item
        for item in audit.summaries
        if item.cohort_dimension == "direction_trend_alignment"
    ]
    summary = {
        "audit_id": audit.audit_id,
        "basket_name": audit.basket_name,
        "requested_symbol_count": audit.requested_symbol_count,
        "source_event_count": audit.source_event_count,
        "source_observation_count": audit.source_observation_count,
        "source_comparison_row_count": (
            audit.source_comparison_row_count
        ),
        "source_classified_row_count": (
            audit.source_classified_row_count
        ),
        "consensus_row_count": audit.consensus_row_count,
        "control_windows": list(audit.control_windows),
        "majority_threshold": audit.majority_threshold,
        "consensus_definition": (
            "collapse all K20 control-window rows for one event/horizon; "
            "require majority of windows for baseline-dependent role"
        ),
        "direction_trend_consensus_summaries": [
            asdict(item) for item in key_summaries
        ],
        "is_actionable": False,
    }
    paths.summary_json.write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    pd.DataFrame(
        [asdict(item) for item in audit.rows],
    ).to_csv(paths.rows_csv, index=False)
    pd.DataFrame(
        [asdict(item) for item in audit.summaries],
    ).to_csv(paths.cohorts_csv, index=False)
    return paths


__all__ = [
    "EXPECTED_K20_AUDIT_ID",
    "PROGRESSION_ROLE_CONSENSUS_AUDIT_ID",
    "FrozenProgressionRoleArtifact",
    "FrozenProgressionRoleRow",
    "ProgressionRoleConsensusAudit",
    "ProgressionRoleConsensusAuditPaths",
    "ProgressionRoleConsensusRow",
    "ProgressionRoleConsensusSummary",
    "build_progression_role_consensus_audit",
    "build_progression_role_consensus_rows",
    "load_frozen_progression_role_artifacts",
    "summarize_progression_role_consensus",
    "write_progression_role_consensus_audit",
]
