"""Event-level horizon trajectory audit for progression roles.

K22 consumes frozen K21 consensus rows and collapses the five forward horizons
into one descriptive trajectory per progression event. It preserves the exact
1/3/5/10/15-week role path instead of treating horizon rows as independent
events.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean

import pandas as pd

from audit.progression_role_consensus import (
    CONSENSUS_ACTUAL_REVERSAL,
    CONSENSUS_CONTINUATION_FAILED,
    CONSENSUS_CONTINUATION_OUTPERFORMS,
    CONSENSUS_CONTINUATION_UNSTABLE,
    CONSENSUS_CONTINUATION_WEAKER,
    CONSENSUS_DECELERATION,
    CONSENSUS_DECELERATION_UNSTABLE,
    CONSENSUS_FAILED_COUNTERTREND,
    CONSENSUS_INCOMPLETE,
    CONSENSUS_NEUTRAL,
)


PROGRESSION_ROLE_HORIZON_TRAJECTORY_AUDIT_ID = (
    "progression-role-horizon-trajectory-v1"
)
EXPECTED_K21_AUDIT_ID = "progression-role-window-consensus-v1"
EXPECTED_HORIZONS = (1, 3, 5, 10, 15)


@dataclass(frozen=True, slots=True)
class FrozenConsensusRow:
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
class FrozenConsensusArtifact:
    basket_name: str
    requested_symbol_count: int
    source_event_count: int
    source_observation_count: int
    source_comparison_row_count: int
    source_classified_row_count: int
    consensus_row_count: int
    control_windows: tuple[int, ...]
    majority_threshold: int
    rows: tuple[FrozenConsensusRow, ...]


@dataclass(frozen=True, slots=True)
class ProgressionRoleTrajectoryRow:
    symbol: str
    event_week: str
    event_direction: str
    trend_alignment: str
    horizon_count: int
    usable_horizon_count: int
    robust_horizon_count: int
    robust_horizon_rate: float | None
    all_usable_horizons_robust: bool
    role_signature: str
    actual_reversal_horizon_count: int
    actual_reversal_horizons: str
    consensus_deceleration_horizon_count: int
    unstable_deceleration_horizon_count: int
    failed_countertrend_horizon_count: int
    continuation_outperform_horizon_count: int
    unstable_continuation_horizon_count: int
    continuation_weaker_horizon_count: int
    continuation_failed_horizon_count: int
    neutral_horizon_count: int
    incomplete_horizon_count: int
    transition_support_horizon_count: int
    continuation_support_horizon_count: int
    majority_actual_reversal: bool
    majority_transition_support: bool
    majority_continuation_outperform: bool
    majority_continuation_failure: bool


@dataclass(frozen=True, slots=True)
class ProgressionRoleTrajectorySummary:
    cohort_dimension: str
    cohort_value: str
    event_count: int
    symbol_count: int
    fully_usable_event_count: int
    mean_usable_horizon_count: float | None
    mean_robust_horizon_rate: float | None
    all_usable_horizons_robust_count: int
    all_usable_horizons_robust_rate: float | None
    any_actual_reversal_event_count: int
    any_actual_reversal_event_rate: float | None
    majority_actual_reversal_event_count: int
    majority_actual_reversal_event_rate: float | None
    majority_transition_support_event_count: int
    majority_transition_support_event_rate: float | None
    majority_continuation_outperform_event_count: int
    majority_continuation_outperform_event_rate: float | None
    majority_continuation_failure_event_count: int
    majority_continuation_failure_event_rate: float | None


@dataclass(frozen=True, slots=True)
class ProgressionRoleTrajectorySignature:
    event_direction: str
    trend_alignment: str
    role_signature: str
    event_count: int
    symbol_count: int
    event_rate_within_context: float


@dataclass(frozen=True, slots=True)
class ProgressionRoleTrajectoryAudit:
    audit_id: str
    basket_name: str
    requested_symbol_count: int
    source_event_count: int
    source_observation_count: int
    source_consensus_row_count: int
    trajectory_row_count: int
    expected_horizons: tuple[int, ...]
    rows: tuple[ProgressionRoleTrajectoryRow, ...]
    summaries: tuple[ProgressionRoleTrajectorySummary, ...]
    signatures: tuple[ProgressionRoleTrajectorySignature, ...]

    @property
    def is_actionable(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class ProgressionRoleTrajectoryAuditPaths:
    summary_json: Path
    trajectories_csv: Path
    cohorts_csv: Path
    signatures_csv: Path

    def as_dict(self) -> dict[str, str]:
        return {
            "summary_json": str(self.summary_json),
            "trajectories_csv": str(self.trajectories_csv),
            "cohorts_csv": str(self.cohorts_csv),
            "signatures_csv": str(self.signatures_csv),
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


def load_frozen_role_consensus_artifacts(
    *,
    input_dir: str | Path,
    expected_basket_name: str,
) -> FrozenConsensusArtifact:
    root = Path(input_dir)
    summary_path = root / "progression_role_consensus_summary.json"
    rows_path = root / "progression_role_consensus_rows.csv"
    if not summary_path.exists():
        raise FileNotFoundError(
            f"missing K21 summary artifact: {summary_path}"
        )
    if not rows_path.exists():
        raise FileNotFoundError(
            f"missing K21 row artifact: {rows_path}"
        )

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("audit_id") != EXPECTED_K21_AUDIT_ID:
        raise ValueError("K21 audit_id does not match expected audit")
    if summary.get("basket_name") != expected_basket_name:
        raise ValueError(
            "K21 basket does not match requested basket: "
            f"{summary.get('basket_name')!r} != "
            f"{expected_basket_name!r}"
        )

    frame = pd.read_csv(rows_path)
    required = {
        "symbol",
        "event_week",
        "event_direction",
        "trend_alignment",
        "horizon_weeks",
        "usable",
        "event_favorable_return",
        "window_count",
        "majority_threshold",
        "positive_transition_windows",
        "positive_continuation_windows",
        "consensus_role",
        "robust_across_windows",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(
            f"K21 row artifact is missing columns: {missing}"
        )

    expected_rows = int(summary["consensus_row_count"])
    if len(frame) != expected_rows:
        raise ValueError(
            f"K21 row count mismatch: {len(frame)} != {expected_rows}"
        )

    windows = tuple(
        sorted({int(item) for item in summary["control_windows"]})
    )
    majority_threshold = int(summary["majority_threshold"])

    rows: list[FrozenConsensusRow] = []
    seen: set[tuple[str, str, str, str, int]] = set()
    for raw in frame.itertuples(index=False):
        row = FrozenConsensusRow(
            symbol=str(raw.symbol).strip().upper(),
            event_week=str(raw.event_week),
            event_direction=str(raw.event_direction),
            trend_alignment=str(raw.trend_alignment),
            horizon_weeks=int(raw.horizon_weeks),
            usable=_as_bool(raw.usable),
            event_favorable_return=_optional_float(
                raw.event_favorable_return
            ),
            window_count=int(raw.window_count),
            majority_threshold=int(raw.majority_threshold),
            positive_transition_windows=int(
                raw.positive_transition_windows
            ),
            positive_continuation_windows=int(
                raw.positive_continuation_windows
            ),
            consensus_role=str(raw.consensus_role),
            robust_across_windows=_as_bool(
                raw.robust_across_windows
            ),
        )
        if row.horizon_weeks not in EXPECTED_HORIZONS:
            raise ValueError(
                f"unexpected K21 horizon: {row.horizon_weeks}"
            )
        if row.window_count != len(windows):
            raise ValueError(
                "K21 row window_count does not match summary windows"
            )
        if row.majority_threshold != majority_threshold:
            raise ValueError(
                "K21 row majority threshold does not match summary"
            )
        key = (
            row.symbol,
            row.event_week,
            row.event_direction,
            row.trend_alignment,
            row.horizon_weeks,
        )
        if key in seen:
            raise ValueError(f"duplicate K21 consensus row: {key}")
        seen.add(key)
        rows.append(row)

    return FrozenConsensusArtifact(
        basket_name=expected_basket_name,
        requested_symbol_count=int(summary["requested_symbol_count"]),
        source_event_count=int(summary["source_event_count"]),
        source_observation_count=int(
            summary["source_observation_count"]
        ),
        source_comparison_row_count=int(
            summary["source_comparison_row_count"]
        ),
        source_classified_row_count=int(
            summary["source_classified_row_count"]
        ),
        consensus_row_count=expected_rows,
        control_windows=windows,
        majority_threshold=majority_threshold,
        rows=tuple(rows),
    )


def _count_role(
    rows: tuple[FrozenConsensusRow, ...],
    role: str,
) -> int:
    return sum(item.consensus_role == role for item in rows)


def _trajectory_group(
    rows: tuple[FrozenConsensusRow, ...],
) -> ProgressionRoleTrajectoryRow:
    if not rows:
        raise ValueError("trajectory group cannot be empty")
    ordered = tuple(sorted(rows, key=lambda item: item.horizon_weeks))
    first = ordered[0]

    horizons = tuple(item.horizon_weeks for item in ordered)
    if horizons != EXPECTED_HORIZONS:
        raise ValueError(
            f"{first.symbol} {first.event_week} horizon identity mismatch: "
            f"{horizons} != {EXPECTED_HORIZONS}"
        )

    identity_fields = (
        "symbol",
        "event_week",
        "event_direction",
        "trend_alignment",
    )
    for item in ordered[1:]:
        for field in identity_fields:
            if getattr(item, field) != getattr(first, field):
                raise ValueError(
                    f"trajectory identity mismatch for {field}"
                )

    usable = tuple(item for item in ordered if item.usable)
    usable_count = len(usable)
    robust_count = sum(item.robust_across_windows for item in usable)
    robust_rate = (
        None if usable_count == 0 else robust_count / usable_count
    )

    role_signature = "|".join(
        f"{item.horizon_weeks}:{item.consensus_role}"
        for item in ordered
    )
    reversal_horizons = tuple(
        item.horizon_weeks
        for item in usable
        if item.consensus_role == CONSENSUS_ACTUAL_REVERSAL
    )

    actual_reversal = len(reversal_horizons)
    consensus_deceleration = _count_role(
        usable,
        CONSENSUS_DECELERATION,
    )
    unstable_deceleration = _count_role(
        usable,
        CONSENSUS_DECELERATION_UNSTABLE,
    )
    failed_countertrend = _count_role(
        usable,
        CONSENSUS_FAILED_COUNTERTREND,
    )
    continuation_outperform = _count_role(
        usable,
        CONSENSUS_CONTINUATION_OUTPERFORMS,
    )
    unstable_continuation = _count_role(
        usable,
        CONSENSUS_CONTINUATION_UNSTABLE,
    )
    continuation_weaker = _count_role(
        usable,
        CONSENSUS_CONTINUATION_WEAKER,
    )
    continuation_failed = _count_role(
        usable,
        CONSENSUS_CONTINUATION_FAILED,
    )
    neutral = _count_role(usable, CONSENSUS_NEUTRAL)
    incomplete = _count_role(ordered, CONSENSUS_INCOMPLETE)

    transition_support = actual_reversal + consensus_deceleration
    continuation_support = continuation_outperform
    majority_threshold = len(EXPECTED_HORIZONS) // 2 + 1

    return ProgressionRoleTrajectoryRow(
        symbol=first.symbol,
        event_week=first.event_week,
        event_direction=first.event_direction,
        trend_alignment=first.trend_alignment,
        horizon_count=len(ordered),
        usable_horizon_count=usable_count,
        robust_horizon_count=robust_count,
        robust_horizon_rate=robust_rate,
        all_usable_horizons_robust=(
            usable_count > 0 and robust_count == usable_count
        ),
        role_signature=role_signature,
        actual_reversal_horizon_count=actual_reversal,
        actual_reversal_horizons=",".join(
            str(item) for item in reversal_horizons
        ),
        consensus_deceleration_horizon_count=(
            consensus_deceleration
        ),
        unstable_deceleration_horizon_count=unstable_deceleration,
        failed_countertrend_horizon_count=failed_countertrend,
        continuation_outperform_horizon_count=(
            continuation_outperform
        ),
        unstable_continuation_horizon_count=unstable_continuation,
        continuation_weaker_horizon_count=continuation_weaker,
        continuation_failed_horizon_count=continuation_failed,
        neutral_horizon_count=neutral,
        incomplete_horizon_count=incomplete,
        transition_support_horizon_count=transition_support,
        continuation_support_horizon_count=continuation_support,
        majority_actual_reversal=(
            usable_count > 0
            and actual_reversal >= majority_threshold
        ),
        majority_transition_support=(
            usable_count > 0
            and transition_support >= majority_threshold
        ),
        majority_continuation_outperform=(
            usable_count > 0
            and continuation_support >= majority_threshold
        ),
        majority_continuation_failure=(
            usable_count > 0
            and continuation_failed >= majority_threshold
        ),
    )


def build_progression_role_trajectories(
    artifact: FrozenConsensusArtifact,
) -> tuple[ProgressionRoleTrajectoryRow, ...]:
    groups: dict[
        tuple[str, str, str, str],
        list[FrozenConsensusRow],
    ] = defaultdict(list)
    for row in artifact.rows:
        key = (
            row.symbol,
            row.event_week,
            row.event_direction,
            row.trend_alignment,
        )
        groups[key].append(row)

    output = tuple(
        _trajectory_group(tuple(items))
        for _, items in sorted(groups.items())
    )
    if len(output) != artifact.source_event_count:
        raise ValueError(
            "trajectory row count must equal source event count: "
            f"{len(output)} != {artifact.source_event_count}"
        )
    return output


def _rate(count: int, total: int) -> float | None:
    return None if total == 0 else count / total


def _cohort_keys(
    row: ProgressionRoleTrajectoryRow,
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


def summarize_progression_role_trajectories(
    rows: tuple[ProgressionRoleTrajectoryRow, ...],
) -> tuple[ProgressionRoleTrajectorySummary, ...]:
    groups: dict[
        tuple[str, str],
        list[ProgressionRoleTrajectoryRow],
    ] = defaultdict(list)
    for row in rows:
        for key in _cohort_keys(row):
            groups[key].append(row)

    output: list[ProgressionRoleTrajectorySummary] = []
    for (dimension, value), group in groups.items():
        event_count = len(group)
        fully_usable = sum(
            item.usable_horizon_count == len(EXPECTED_HORIZONS)
            for item in group
        )
        usable_counts = [
            item.usable_horizon_count for item in group
        ]
        robust_rates = [
            item.robust_horizon_rate
            for item in group
            if item.robust_horizon_rate is not None
        ]
        all_robust = sum(
            item.all_usable_horizons_robust for item in group
        )
        any_reversal = sum(
            item.actual_reversal_horizon_count > 0 for item in group
        )
        majority_reversal = sum(
            item.majority_actual_reversal for item in group
        )
        majority_transition = sum(
            item.majority_transition_support for item in group
        )
        majority_continuation = sum(
            item.majority_continuation_outperform for item in group
        )
        majority_failure = sum(
            item.majority_continuation_failure for item in group
        )

        output.append(
            ProgressionRoleTrajectorySummary(
                cohort_dimension=dimension,
                cohort_value=value,
                event_count=event_count,
                symbol_count=len({item.symbol for item in group}),
                fully_usable_event_count=fully_usable,
                mean_usable_horizon_count=(
                    None
                    if not usable_counts
                    else mean(usable_counts)
                ),
                mean_robust_horizon_rate=(
                    None
                    if not robust_rates
                    else mean(robust_rates)
                ),
                all_usable_horizons_robust_count=all_robust,
                all_usable_horizons_robust_rate=_rate(
                    all_robust,
                    event_count,
                ),
                any_actual_reversal_event_count=any_reversal,
                any_actual_reversal_event_rate=_rate(
                    any_reversal,
                    event_count,
                ),
                majority_actual_reversal_event_count=(
                    majority_reversal
                ),
                majority_actual_reversal_event_rate=_rate(
                    majority_reversal,
                    event_count,
                ),
                majority_transition_support_event_count=(
                    majority_transition
                ),
                majority_transition_support_event_rate=_rate(
                    majority_transition,
                    event_count,
                ),
                majority_continuation_outperform_event_count=(
                    majority_continuation
                ),
                majority_continuation_outperform_event_rate=_rate(
                    majority_continuation,
                    event_count,
                ),
                majority_continuation_failure_event_count=(
                    majority_failure
                ),
                majority_continuation_failure_event_rate=_rate(
                    majority_failure,
                    event_count,
                ),
            )
        )

    return tuple(
        sorted(
            output,
            key=lambda item: (
                item.cohort_dimension,
                item.cohort_value,
            ),
        )
    )


def summarize_trajectory_signatures(
    rows: tuple[ProgressionRoleTrajectoryRow, ...],
) -> tuple[ProgressionRoleTrajectorySignature, ...]:
    context_totals = Counter(
        (item.event_direction, item.trend_alignment)
        for item in rows
    )
    groups: dict[
        tuple[str, str, str],
        list[ProgressionRoleTrajectoryRow],
    ] = defaultdict(list)
    for row in rows:
        groups[
            (
                row.event_direction,
                row.trend_alignment,
                row.role_signature,
            )
        ].append(row)

    output: list[ProgressionRoleTrajectorySignature] = []
    for (direction, alignment, signature), group in groups.items():
        total = context_totals[(direction, alignment)]
        output.append(
            ProgressionRoleTrajectorySignature(
                event_direction=direction,
                trend_alignment=alignment,
                role_signature=signature,
                event_count=len(group),
                symbol_count=len({item.symbol for item in group}),
                event_rate_within_context=len(group) / total,
            )
        )

    return tuple(
        sorted(
            output,
            key=lambda item: (
                item.event_direction,
                item.trend_alignment,
                -item.event_count,
                item.role_signature,
            ),
        )
    )


def build_progression_role_trajectory_audit(
    artifact: FrozenConsensusArtifact,
) -> ProgressionRoleTrajectoryAudit:
    rows = build_progression_role_trajectories(artifact)
    return ProgressionRoleTrajectoryAudit(
        audit_id=PROGRESSION_ROLE_HORIZON_TRAJECTORY_AUDIT_ID,
        basket_name=artifact.basket_name,
        requested_symbol_count=artifact.requested_symbol_count,
        source_event_count=artifact.source_event_count,
        source_observation_count=artifact.source_observation_count,
        source_consensus_row_count=artifact.consensus_row_count,
        trajectory_row_count=len(rows),
        expected_horizons=EXPECTED_HORIZONS,
        rows=rows,
        summaries=summarize_progression_role_trajectories(rows),
        signatures=summarize_trajectory_signatures(rows),
    )


def write_progression_role_trajectory_audit(
    audit: ProgressionRoleTrajectoryAudit,
    output_dir: str | Path,
) -> ProgressionRoleTrajectoryAuditPaths:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    paths = ProgressionRoleTrajectoryAuditPaths(
        summary_json=root / "progression_role_trajectory_summary.json",
        trajectories_csv=root / "progression_role_trajectories.csv",
        cohorts_csv=root / "progression_role_trajectory_cohorts.csv",
        signatures_csv=root / "progression_role_trajectory_signatures.csv",
    )

    context_summaries = [
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
        "source_consensus_row_count": audit.source_consensus_row_count,
        "trajectory_row_count": audit.trajectory_row_count,
        "expected_horizons": list(audit.expected_horizons),
        "trajectory_definition": (
            "one row per progression event; preserve exact K21 role "
            "sequence across 1/3/5/10/15-week horizons"
        ),
        "direction_trend_trajectory_summaries": [
            asdict(item) for item in context_summaries
        ],
        "is_actionable": False,
    }
    paths.summary_json.write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    pd.DataFrame(
        [asdict(item) for item in audit.rows],
    ).to_csv(paths.trajectories_csv, index=False)
    pd.DataFrame(
        [asdict(item) for item in audit.summaries],
    ).to_csv(paths.cohorts_csv, index=False)
    pd.DataFrame(
        [asdict(item) for item in audit.signatures],
    ).to_csv(paths.signatures_csv, index=False)
    return paths


__all__ = [
    "EXPECTED_HORIZONS",
    "EXPECTED_K21_AUDIT_ID",
    "PROGRESSION_ROLE_HORIZON_TRAJECTORY_AUDIT_ID",
    "FrozenConsensusArtifact",
    "FrozenConsensusRow",
    "ProgressionRoleTrajectoryAudit",
    "ProgressionRoleTrajectoryAuditPaths",
    "ProgressionRoleTrajectoryRow",
    "ProgressionRoleTrajectorySignature",
    "ProgressionRoleTrajectorySummary",
    "build_progression_role_trajectories",
    "build_progression_role_trajectory_audit",
    "load_frozen_role_consensus_artifacts",
    "summarize_progression_role_trajectories",
    "summarize_trajectory_signatures",
    "write_progression_role_trajectory_audit",
]
