"""Transition-onset audit for trend-opposed progression events.

K23 consumes frozen K22 event-level trajectories and classifies when an opposed
progression event first becomes an actual reversal, whether reversal persists,
and whether non-reversal cases still retain consensus transition support.

Analysis-only. No production semantics are changed.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

from audit.progression_role_consensus import (
    CONSENSUS_ACTUAL_REVERSAL,
    CONSENSUS_DECELERATION,
    CONSENSUS_INCOMPLETE,
)


PROGRESSION_TRANSITION_ONSET_AUDIT_ID = (
    "progression-transition-onset-v1"
)
EXPECTED_K22_AUDIT_ID = "progression-role-horizon-trajectory-v1"
EXPECTED_HORIZONS = (1, 3, 5, 10, 15)

ONSET_IMMEDIATE = "IMMEDIATE_1W"
ONSET_EARLY = "EARLY_3W"
ONSET_MEDIUM = "MEDIUM_5W"
ONSET_LATE = "LATE_10_15W"
ONSET_NO_REVERSAL_TRANSITION = "NO_REVERSAL_TRANSITION_SUPPORT"
ONSET_NO_REVERSAL_NO_SUPPORT = "NO_REVERSAL_NO_SUPPORT"


@dataclass(frozen=True, slots=True)
class FrozenTrajectoryRow:
    symbol: str
    event_week: str
    event_direction: str
    trend_alignment: str
    horizon_count: int
    usable_horizon_count: int
    robust_horizon_count: int
    robust_horizon_rate: float | None
    role_signature: str
    actual_reversal_horizon_count: int
    actual_reversal_horizons: str
    transition_support_horizon_count: int
    majority_actual_reversal: bool
    majority_transition_support: bool


@dataclass(frozen=True, slots=True)
class FrozenTrajectoryArtifact:
    basket_name: str
    requested_symbol_count: int
    source_event_count: int
    source_observation_count: int
    source_consensus_row_count: int
    trajectory_row_count: int
    expected_horizons: tuple[int, ...]
    rows: tuple[FrozenTrajectoryRow, ...]


@dataclass(frozen=True, slots=True)
class ProgressionTransitionOnsetRow:
    symbol: str
    event_week: str
    event_direction: str
    usable_horizon_count: int
    robust_horizon_rate: float | None
    first_reversal_horizon: int | None
    first_transition_support_horizon: int | None
    reversal_horizon_count: int
    transition_support_horizon_count: int
    reversal_horizons: str
    onset_class: str
    reversal_persistent_after_onset: bool
    transition_persistent_after_onset: bool
    reversal_reverted_after_onset: bool
    majority_actual_reversal: bool
    majority_transition_support: bool
    role_signature: str


@dataclass(frozen=True, slots=True)
class ProgressionTransitionOnsetSummary:
    event_direction: str
    event_count: int
    symbol_count: int
    fully_usable_event_count: int
    any_reversal_count: int
    any_reversal_rate: float
    immediate_reversal_count: int
    immediate_reversal_rate: float
    early_reversal_count: int
    early_reversal_rate: float
    medium_reversal_count: int
    medium_reversal_rate: float
    late_reversal_count: int
    late_reversal_rate: float
    no_reversal_transition_count: int
    no_reversal_transition_rate: float
    no_reversal_no_support_count: int
    no_reversal_no_support_rate: float
    reversal_persistent_after_onset_count: int
    reversal_persistent_after_onset_rate_given_reversal: float | None
    transition_persistent_after_onset_count: int
    transition_persistent_after_onset_rate_given_support: float | None
    reversal_reverted_after_onset_count: int
    reversal_reverted_after_onset_rate_given_reversal: float | None
    majority_actual_reversal_count: int
    majority_actual_reversal_rate: float
    majority_transition_support_count: int
    majority_transition_support_rate: float


@dataclass(frozen=True, slots=True)
class ProgressionTransitionOnsetAudit:
    audit_id: str
    basket_name: str
    requested_symbol_count: int
    source_event_count: int
    source_trajectory_row_count: int
    opposed_event_count: int
    rows: tuple[ProgressionTransitionOnsetRow, ...]
    summaries: tuple[ProgressionTransitionOnsetSummary, ...]

    @property
    def is_actionable(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class ProgressionTransitionOnsetPaths:
    summary_json: Path
    rows_csv: Path
    direction_summary_csv: Path

    def as_dict(self) -> dict[str, str]:
        return {
            "summary_json": str(self.summary_json),
            "rows_csv": str(self.rows_csv),
            "direction_summary_csv": str(self.direction_summary_csv),
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


def load_frozen_trajectory_artifacts(
    *,
    input_dir: str | Path,
    expected_basket_name: str,
) -> FrozenTrajectoryArtifact:
    root = Path(input_dir)
    summary_path = root / "progression_role_trajectory_summary.json"
    rows_path = root / "progression_role_trajectories.csv"
    if not summary_path.exists():
        raise FileNotFoundError(
            f"missing K22 summary artifact: {summary_path}"
        )
    if not rows_path.exists():
        raise FileNotFoundError(
            f"missing K22 trajectory artifact: {rows_path}"
        )

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("audit_id") != EXPECTED_K22_AUDIT_ID:
        raise ValueError("K22 audit_id does not match expected audit")
    if summary.get("basket_name") != expected_basket_name:
        raise ValueError(
            "K22 basket does not match requested basket: "
            f"{summary.get('basket_name')!r} != "
            f"{expected_basket_name!r}"
        )

    horizons = tuple(int(item) for item in summary["expected_horizons"])
    if horizons != EXPECTED_HORIZONS:
        raise ValueError(
            f"K22 horizon identity mismatch: "
            f"{horizons} != {EXPECTED_HORIZONS}"
        )

    frame = pd.read_csv(rows_path)
    required = {
        "symbol",
        "event_week",
        "event_direction",
        "trend_alignment",
        "horizon_count",
        "usable_horizon_count",
        "robust_horizon_count",
        "robust_horizon_rate",
        "role_signature",
        "actual_reversal_horizon_count",
        "actual_reversal_horizons",
        "transition_support_horizon_count",
        "majority_actual_reversal",
        "majority_transition_support",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(
            f"K22 trajectory artifact is missing columns: {missing}"
        )

    expected_rows = int(summary["trajectory_row_count"])
    if len(frame) != expected_rows:
        raise ValueError(
            f"K22 row count mismatch: {len(frame)} != {expected_rows}"
        )

    rows: list[FrozenTrajectoryRow] = []
    seen: set[tuple[str, str, str, str]] = set()
    for raw in frame.itertuples(index=False):
        row = FrozenTrajectoryRow(
            symbol=str(raw.symbol).strip().upper(),
            event_week=str(raw.event_week),
            event_direction=str(raw.event_direction),
            trend_alignment=str(raw.trend_alignment),
            horizon_count=int(raw.horizon_count),
            usable_horizon_count=int(raw.usable_horizon_count),
            robust_horizon_count=int(raw.robust_horizon_count),
            robust_horizon_rate=_optional_float(
                raw.robust_horizon_rate
            ),
            role_signature=str(raw.role_signature),
            actual_reversal_horizon_count=int(
                raw.actual_reversal_horizon_count
            ),
            actual_reversal_horizons=(
                ""
                if pd.isna(raw.actual_reversal_horizons)
                else str(raw.actual_reversal_horizons)
            ),
            transition_support_horizon_count=int(
                raw.transition_support_horizon_count
            ),
            majority_actual_reversal=_as_bool(
                raw.majority_actual_reversal
            ),
            majority_transition_support=_as_bool(
                raw.majority_transition_support
            ),
        )
        if row.horizon_count != len(EXPECTED_HORIZONS):
            raise ValueError(
                f"{row.symbol} horizon count mismatch: "
                f"{row.horizon_count}"
            )
        key = (
            row.symbol,
            row.event_week,
            row.event_direction,
            row.trend_alignment,
        )
        if key in seen:
            raise ValueError(f"duplicate K22 trajectory row: {key}")
        seen.add(key)
        rows.append(row)

    return FrozenTrajectoryArtifact(
        basket_name=expected_basket_name,
        requested_symbol_count=int(summary["requested_symbol_count"]),
        source_event_count=int(summary["source_event_count"]),
        source_observation_count=int(
            summary["source_observation_count"]
        ),
        source_consensus_row_count=int(
            summary["source_consensus_row_count"]
        ),
        trajectory_row_count=expected_rows,
        expected_horizons=horizons,
        rows=tuple(rows),
    )


def _parse_role_signature(signature: str) -> dict[int, str]:
    result: dict[int, str] = {}
    for token in signature.split("|"):
        horizon_text, role = token.split(":", 1)
        horizon = int(horizon_text)
        if horizon in result:
            raise ValueError(
                f"duplicate horizon in role signature: {horizon}"
            )
        result[horizon] = role
    if tuple(sorted(result)) != EXPECTED_HORIZONS:
        raise ValueError(
            f"role signature horizon mismatch: "
            f"{tuple(sorted(result))}"
        )
    return result


def _onset_class(
    first_reversal: int | None,
    *,
    majority_transition_support: bool,
) -> str:
    if first_reversal == 1:
        return ONSET_IMMEDIATE
    if first_reversal == 3:
        return ONSET_EARLY
    if first_reversal == 5:
        return ONSET_MEDIUM
    if first_reversal in {10, 15}:
        return ONSET_LATE
    if majority_transition_support:
        return ONSET_NO_REVERSAL_TRANSITION
    return ONSET_NO_REVERSAL_NO_SUPPORT


def _all_later_usable_in(
    *,
    roles: dict[int, str],
    first_horizon: int | None,
    allowed_roles: set[str],
) -> bool:
    if first_horizon is None:
        return False
    later = [
        role
        for horizon, role in sorted(roles.items())
        if horizon >= first_horizon and role != CONSENSUS_INCOMPLETE
    ]
    return bool(later) and all(role in allowed_roles for role in later)


def classify_transition_onset(
    row: FrozenTrajectoryRow,
) -> ProgressionTransitionOnsetRow:
    if row.trend_alignment != "opposed":
        raise ValueError(
            "transition-onset classification requires opposed trend context"
        )

    roles = _parse_role_signature(row.role_signature)
    reversal_horizons = [
        horizon
        for horizon, role in sorted(roles.items())
        if role == CONSENSUS_ACTUAL_REVERSAL
    ]
    transition_horizons = [
        horizon
        for horizon, role in sorted(roles.items())
        if role in {
            CONSENSUS_ACTUAL_REVERSAL,
            CONSENSUS_DECELERATION,
        }
    ]
    if len(reversal_horizons) != row.actual_reversal_horizon_count:
        raise ValueError(
            "K22 reversal count does not match role signature"
        )
    if len(transition_horizons) != row.transition_support_horizon_count:
        raise ValueError(
            "K22 transition-support count does not match role signature"
        )

    first_reversal = (
        None if not reversal_horizons else reversal_horizons[0]
    )
    first_transition = (
        None if not transition_horizons else transition_horizons[0]
    )
    reversal_persistent = _all_later_usable_in(
        roles=roles,
        first_horizon=first_reversal,
        allowed_roles={CONSENSUS_ACTUAL_REVERSAL},
    )
    transition_persistent = _all_later_usable_in(
        roles=roles,
        first_horizon=first_transition,
        allowed_roles={
            CONSENSUS_ACTUAL_REVERSAL,
            CONSENSUS_DECELERATION,
        },
    )

    return ProgressionTransitionOnsetRow(
        symbol=row.symbol,
        event_week=row.event_week,
        event_direction=row.event_direction,
        usable_horizon_count=row.usable_horizon_count,
        robust_horizon_rate=row.robust_horizon_rate,
        first_reversal_horizon=first_reversal,
        first_transition_support_horizon=first_transition,
        reversal_horizon_count=len(reversal_horizons),
        transition_support_horizon_count=len(transition_horizons),
        reversal_horizons=",".join(
            str(item) for item in reversal_horizons
        ),
        onset_class=_onset_class(
            first_reversal,
            majority_transition_support=row.majority_transition_support,
        ),
        reversal_persistent_after_onset=reversal_persistent,
        transition_persistent_after_onset=transition_persistent,
        reversal_reverted_after_onset=(
            first_reversal is not None and not reversal_persistent
        ),
        majority_actual_reversal=row.majority_actual_reversal,
        majority_transition_support=row.majority_transition_support,
        role_signature=row.role_signature,
    )


def _rate(count: int, total: int) -> float:
    return 0.0 if total == 0 else count / total


def _optional_rate(count: int, total: int) -> float | None:
    return None if total == 0 else count / total


def summarize_transition_onsets(
    rows: tuple[ProgressionTransitionOnsetRow, ...],
) -> tuple[ProgressionTransitionOnsetSummary, ...]:
    groups: dict[str, list[ProgressionTransitionOnsetRow]] = defaultdict(list)
    for row in rows:
        groups[row.event_direction].append(row)

    summaries: list[ProgressionTransitionOnsetSummary] = []
    for direction, group in sorted(groups.items()):
        total = len(group)
        classes = Counter(item.onset_class for item in group)
        any_reversal = sum(
            item.first_reversal_horizon is not None for item in group
        )
        any_transition = sum(
            item.first_transition_support_horizon is not None
            for item in group
        )
        reversal_persistent = sum(
            item.reversal_persistent_after_onset for item in group
        )
        transition_persistent = sum(
            item.transition_persistent_after_onset for item in group
        )
        reversal_reverted = sum(
            item.reversal_reverted_after_onset for item in group
        )
        majority_reversal = sum(
            item.majority_actual_reversal for item in group
        )
        majority_transition = sum(
            item.majority_transition_support for item in group
        )

        summaries.append(
            ProgressionTransitionOnsetSummary(
                event_direction=direction,
                event_count=total,
                symbol_count=len({item.symbol for item in group}),
                fully_usable_event_count=sum(
                    item.usable_horizon_count == len(EXPECTED_HORIZONS)
                    for item in group
                ),
                any_reversal_count=any_reversal,
                any_reversal_rate=_rate(any_reversal, total),
                immediate_reversal_count=classes[ONSET_IMMEDIATE],
                immediate_reversal_rate=_rate(
                    classes[ONSET_IMMEDIATE],
                    total,
                ),
                early_reversal_count=classes[ONSET_EARLY],
                early_reversal_rate=_rate(
                    classes[ONSET_EARLY],
                    total,
                ),
                medium_reversal_count=classes[ONSET_MEDIUM],
                medium_reversal_rate=_rate(
                    classes[ONSET_MEDIUM],
                    total,
                ),
                late_reversal_count=classes[ONSET_LATE],
                late_reversal_rate=_rate(
                    classes[ONSET_LATE],
                    total,
                ),
                no_reversal_transition_count=classes[
                    ONSET_NO_REVERSAL_TRANSITION
                ],
                no_reversal_transition_rate=_rate(
                    classes[ONSET_NO_REVERSAL_TRANSITION],
                    total,
                ),
                no_reversal_no_support_count=classes[
                    ONSET_NO_REVERSAL_NO_SUPPORT
                ],
                no_reversal_no_support_rate=_rate(
                    classes[ONSET_NO_REVERSAL_NO_SUPPORT],
                    total,
                ),
                reversal_persistent_after_onset_count=(
                    reversal_persistent
                ),
                reversal_persistent_after_onset_rate_given_reversal=(
                    _optional_rate(reversal_persistent, any_reversal)
                ),
                transition_persistent_after_onset_count=(
                    transition_persistent
                ),
                transition_persistent_after_onset_rate_given_support=(
                    _optional_rate(
                        transition_persistent,
                        any_transition,
                    )
                ),
                reversal_reverted_after_onset_count=reversal_reverted,
                reversal_reverted_after_onset_rate_given_reversal=(
                    _optional_rate(reversal_reverted, any_reversal)
                ),
                majority_actual_reversal_count=majority_reversal,
                majority_actual_reversal_rate=_rate(
                    majority_reversal,
                    total,
                ),
                majority_transition_support_count=majority_transition,
                majority_transition_support_rate=_rate(
                    majority_transition,
                    total,
                ),
            )
        )
    return tuple(summaries)


def build_progression_transition_onset_audit(
    artifact: FrozenTrajectoryArtifact,
) -> ProgressionTransitionOnsetAudit:
    opposed = tuple(
        row for row in artifact.rows if row.trend_alignment == "opposed"
    )
    classified = tuple(
        classify_transition_onset(row) for row in opposed
    )
    return ProgressionTransitionOnsetAudit(
        audit_id=PROGRESSION_TRANSITION_ONSET_AUDIT_ID,
        basket_name=artifact.basket_name,
        requested_symbol_count=artifact.requested_symbol_count,
        source_event_count=artifact.source_event_count,
        source_trajectory_row_count=artifact.trajectory_row_count,
        opposed_event_count=len(classified),
        rows=classified,
        summaries=summarize_transition_onsets(classified),
    )


def write_progression_transition_onset_audit(
    audit: ProgressionTransitionOnsetAudit,
    output_dir: str | Path,
) -> ProgressionTransitionOnsetPaths:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    paths = ProgressionTransitionOnsetPaths(
        summary_json=root / "progression_transition_onset_summary.json",
        rows_csv=root / "progression_transition_onset_rows.csv",
        direction_summary_csv=(
            root / "progression_transition_onset_directions.csv"
        ),
    )

    summary = {
        "audit_id": audit.audit_id,
        "basket_name": audit.basket_name,
        "requested_symbol_count": audit.requested_symbol_count,
        "source_event_count": audit.source_event_count,
        "source_trajectory_row_count": audit.source_trajectory_row_count,
        "opposed_event_count": audit.opposed_event_count,
        "expected_horizons": list(EXPECTED_HORIZONS),
        "onset_definitions": {
            ONSET_IMMEDIATE: "first actual reversal at 1 week",
            ONSET_EARLY: "first actual reversal at 3 weeks",
            ONSET_MEDIUM: "first actual reversal at 5 weeks",
            ONSET_LATE: "first actual reversal at 10 or 15 weeks",
            ONSET_NO_REVERSAL_TRANSITION: (
                "no actual reversal; majority transition support remains"
            ),
            ONSET_NO_REVERSAL_NO_SUPPORT: (
                "no actual reversal and no majority transition support"
            ),
        },
        "direction_summaries": [
            asdict(item) for item in audit.summaries
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
    ).to_csv(paths.direction_summary_csv, index=False)
    return paths


__all__ = [
    "EXPECTED_K22_AUDIT_ID",
    "PROGRESSION_TRANSITION_ONSET_AUDIT_ID",
    "FrozenTrajectoryArtifact",
    "FrozenTrajectoryRow",
    "ProgressionTransitionOnsetAudit",
    "ProgressionTransitionOnsetRow",
    "ProgressionTransitionOnsetSummary",
    "build_progression_transition_onset_audit",
    "classify_transition_onset",
    "load_frozen_trajectory_artifacts",
    "summarize_transition_onsets",
    "write_progression_transition_onset_audit",
]
