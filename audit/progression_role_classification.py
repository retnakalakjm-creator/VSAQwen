"""Role classification for progression evidence.

This analysis-only audit consumes frozen K19 causal drift rows and classifies
progression events by their relationship to the already-observed trend context.

It does not change production progression semantics.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd


PROGRESSION_ROLE_CLASSIFICATION_AUDIT_ID = (
    "progression-role-classification-v1"
)
EXPECTED_K19_AUDIT_ID = "progression-causal-pre-event-drift-baseline-v1"

ROLE_ACTUAL_REVERSAL = "ACTUAL_REVERSAL"
ROLE_DECELERATION_ONLY = "DECELERATION_WITHOUT_REVERSAL"
ROLE_FAILED_COUNTERTREND = "FAILED_COUNTERTREND_WARNING"
ROLE_CONTINUATION_OUTPERFORMS = "CONTINUATION_OUTPERFORMS_BASELINE"
ROLE_CONTINUATION_WEAKER = "CONTINUATION_WEAKER_THAN_BASELINE"
ROLE_CONTINUATION_FAILED = "CONTINUATION_FAILED"
ROLE_NEUTRAL_CONTEXT = "NEUTRAL_CONTEXT"
ROLE_INCOMPLETE = "INCOMPLETE"


@dataclass(frozen=True, slots=True)
class FrozenCausalDriftRow:
    symbol: str
    event_week: str
    event_direction: str
    trend_alignment: str
    source_event_bar_index: int
    resolved_event_bar_index: int
    horizon_weeks: int
    control_window_size: int
    control_count: int
    event_complete: bool
    event_favorable_return: float | None
    baseline_mean_favorable_return: float | None
    favorable_return_lift: float | None


@dataclass(frozen=True, slots=True)
class FrozenCausalDriftArtifact:
    basket_name: str
    requested_symbol_count: int
    source_event_count: int
    source_observation_count: int
    comparison_row_count: int
    control_windows: tuple[int, ...]
    rows: tuple[FrozenCausalDriftRow, ...]


@dataclass(frozen=True, slots=True)
class ProgressionRoleRow:
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
class ProgressionRoleSummary:
    cohort_dimension: str
    cohort_value: str
    horizon_weeks: int
    control_window_size: int
    usable_row_count: int
    symbol_count: int
    actual_reversal_count: int
    actual_reversal_rate: float | None
    deceleration_only_count: int
    deceleration_only_rate: float | None
    transition_improvement_count: int
    transition_improvement_rate: float | None
    failed_countertrend_count: int
    failed_countertrend_rate: float | None
    continuation_positive_count: int
    continuation_positive_rate: float | None
    continuation_outperform_count: int
    continuation_outperform_rate: float | None
    continuation_weaker_count: int
    continuation_weaker_rate: float | None
    continuation_failed_count: int
    continuation_failed_rate: float | None


@dataclass(frozen=True, slots=True)
class ProgressionRoleAudit:
    audit_id: str
    basket_name: str
    requested_symbol_count: int
    source_event_count: int
    source_observation_count: int
    source_comparison_row_count: int
    classified_row_count: int
    control_windows: tuple[int, ...]
    rows: tuple[ProgressionRoleRow, ...]
    summaries: tuple[ProgressionRoleSummary, ...]

    @property
    def is_actionable(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class ProgressionRoleAuditPaths:
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


def load_frozen_causal_drift_artifacts(
    *,
    input_dir: str | Path,
    expected_basket_name: str,
) -> FrozenCausalDriftArtifact:
    root = Path(input_dir)
    summary_path = root / "progression_causal_drift_summary.json"
    rows_path = root / "progression_causal_drift_rows.csv"
    if not summary_path.exists():
        raise FileNotFoundError(
            f"missing K19 summary artifact: {summary_path}"
        )
    if not rows_path.exists():
        raise FileNotFoundError(
            f"missing K19 row artifact: {rows_path}"
        )

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("audit_id") != EXPECTED_K19_AUDIT_ID:
        raise ValueError("K19 audit_id does not match expected audit")
    if summary.get("basket_name") != expected_basket_name:
        raise ValueError(
            "K19 basket does not match requested basket: "
            f"{summary.get('basket_name')!r} != "
            f"{expected_basket_name!r}"
        )
    if int(summary.get("failed_symbol_count", 0)) != 0:
        raise ValueError("K19 artifact contains failed symbols")

    windows = tuple(
        sorted({int(item) for item in summary["control_windows"]})
    )
    if not windows or any(item <= 0 for item in windows):
        raise ValueError("K19 control windows must be positive")

    frame = pd.read_csv(rows_path)
    required = {
        "symbol",
        "event_week",
        "event_direction",
        "trend_alignment",
        "source_event_bar_index",
        "resolved_event_bar_index",
        "horizon_weeks",
        "control_window_size",
        "control_count",
        "event_complete",
        "event_favorable_return",
        "baseline_mean_favorable_return",
        "favorable_return_lift",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(
            f"K19 row artifact is missing columns: {missing}"
        )

    expected_rows = int(summary["comparison_row_count"])
    if len(frame) != expected_rows:
        raise ValueError(
            f"K19 row count mismatch: {len(frame)} != {expected_rows}"
        )

    rows: list[FrozenCausalDriftRow] = []
    seen: set[tuple[str, str, str, int, int]] = set()
    for raw in frame.itertuples(index=False):
        row = FrozenCausalDriftRow(
            symbol=str(raw.symbol).strip().upper(),
            event_week=str(raw.event_week),
            event_direction=str(raw.event_direction),
            trend_alignment=str(raw.trend_alignment),
            source_event_bar_index=int(raw.source_event_bar_index),
            resolved_event_bar_index=int(raw.resolved_event_bar_index),
            horizon_weeks=int(raw.horizon_weeks),
            control_window_size=int(raw.control_window_size),
            control_count=int(raw.control_count),
            event_complete=_as_bool(raw.event_complete),
            event_favorable_return=_optional_float(
                raw.event_favorable_return
            ),
            baseline_mean_favorable_return=_optional_float(
                raw.baseline_mean_favorable_return
            ),
            favorable_return_lift=_optional_float(
                raw.favorable_return_lift
            ),
        )
        if row.control_window_size not in windows:
            raise ValueError(
                f"unexpected K19 control window: "
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
            raise ValueError(f"duplicate K19 comparison row: {key}")
        seen.add(key)
        rows.append(row)

    return FrozenCausalDriftArtifact(
        basket_name=expected_basket_name,
        requested_symbol_count=int(summary["requested_symbol_count"]),
        source_event_count=int(summary["source_event_count"]),
        source_observation_count=int(
            summary["source_observation_count"]
        ),
        comparison_row_count=expected_rows,
        control_windows=windows,
        rows=tuple(rows),
    )


def classify_progression_role(
    row: FrozenCausalDriftRow,
) -> ProgressionRoleRow:
    usable = (
        row.event_complete
        and row.event_favorable_return is not None
        and row.baseline_mean_favorable_return is not None
        and row.favorable_return_lift is not None
    )

    actual_reversal = False
    transition_improvement = False
    continuation_positive = False
    continuation_outperforms = False

    if not usable:
        role = ROLE_INCOMPLETE
    elif row.trend_alignment == "opposed":
        actual_reversal = row.event_favorable_return > 0.0
        transition_improvement = (
            actual_reversal or row.favorable_return_lift > 0.0
        )
        if actual_reversal:
            role = ROLE_ACTUAL_REVERSAL
        elif row.favorable_return_lift > 0.0:
            role = ROLE_DECELERATION_ONLY
        else:
            role = ROLE_FAILED_COUNTERTREND
    elif row.trend_alignment == "aligned":
        continuation_positive = row.event_favorable_return > 0.0
        continuation_outperforms = (
            continuation_positive
            and row.favorable_return_lift > 0.0
        )
        if continuation_outperforms:
            role = ROLE_CONTINUATION_OUTPERFORMS
        elif continuation_positive:
            role = ROLE_CONTINUATION_WEAKER
        else:
            role = ROLE_CONTINUATION_FAILED
    else:
        role = ROLE_NEUTRAL_CONTEXT

    return ProgressionRoleRow(
        symbol=row.symbol,
        event_week=row.event_week,
        event_direction=row.event_direction,
        trend_alignment=row.trend_alignment,
        horizon_weeks=row.horizon_weeks,
        control_window_size=row.control_window_size,
        control_count=row.control_count,
        event_favorable_return=row.event_favorable_return,
        baseline_mean_favorable_return=(
            row.baseline_mean_favorable_return
        ),
        favorable_return_lift=row.favorable_return_lift,
        role=role,
        usable=usable,
        actual_reversal=actual_reversal,
        transition_improvement=transition_improvement,
        continuation_positive=continuation_positive,
        continuation_outperforms=continuation_outperforms,
    )


def _cohort_keys(
    row: ProgressionRoleRow,
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


def _rate(count: int, total: int) -> float | None:
    return None if total == 0 else count / total


def summarize_progression_roles(
    rows: tuple[ProgressionRoleRow, ...],
) -> tuple[ProgressionRoleSummary, ...]:
    groups: dict[
        tuple[str, str, int, int],
        list[ProgressionRoleRow],
    ] = defaultdict(list)
    for row in rows:
        for dimension, value in _cohort_keys(row):
            groups[
                (
                    dimension,
                    value,
                    row.horizon_weeks,
                    row.control_window_size,
                )
            ].append(row)

    summaries: list[ProgressionRoleSummary] = []
    for (dimension, value, horizon, window), group in groups.items():
        usable = [item for item in group if item.usable]
        counts = Counter(item.role for item in usable)
        symbols = {item.symbol for item in usable}
        actual_reversal = counts[ROLE_ACTUAL_REVERSAL]
        deceleration = counts[ROLE_DECELERATION_ONLY]
        failed_countertrend = counts[ROLE_FAILED_COUNTERTREND]
        continuation_outperforms = counts[
            ROLE_CONTINUATION_OUTPERFORMS
        ]
        continuation_weaker = counts[ROLE_CONTINUATION_WEAKER]
        continuation_failed = counts[ROLE_CONTINUATION_FAILED]
        transition_total = (
            actual_reversal
            + deceleration
            + failed_countertrend
        )
        continuation_total = (
            continuation_outperforms
            + continuation_weaker
            + continuation_failed
        )
        transition_improvement = actual_reversal + deceleration
        continuation_positive = (
            continuation_outperforms + continuation_weaker
        )

        summaries.append(
            ProgressionRoleSummary(
                cohort_dimension=dimension,
                cohort_value=value,
                horizon_weeks=horizon,
                control_window_size=window,
                usable_row_count=len(usable),
                symbol_count=len(symbols),
                actual_reversal_count=actual_reversal,
                actual_reversal_rate=_rate(
                    actual_reversal,
                    transition_total,
                ),
                deceleration_only_count=deceleration,
                deceleration_only_rate=_rate(
                    deceleration,
                    transition_total,
                ),
                transition_improvement_count=transition_improvement,
                transition_improvement_rate=_rate(
                    transition_improvement,
                    transition_total,
                ),
                failed_countertrend_count=failed_countertrend,
                failed_countertrend_rate=_rate(
                    failed_countertrend,
                    transition_total,
                ),
                continuation_positive_count=continuation_positive,
                continuation_positive_rate=_rate(
                    continuation_positive,
                    continuation_total,
                ),
                continuation_outperform_count=(
                    continuation_outperforms
                ),
                continuation_outperform_rate=_rate(
                    continuation_outperforms,
                    continuation_total,
                ),
                continuation_weaker_count=continuation_weaker,
                continuation_weaker_rate=_rate(
                    continuation_weaker,
                    continuation_total,
                ),
                continuation_failed_count=continuation_failed,
                continuation_failed_rate=_rate(
                    continuation_failed,
                    continuation_total,
                ),
            )
        )

    return tuple(
        sorted(
            summaries,
            key=lambda item: (
                item.cohort_dimension,
                item.cohort_value,
                item.horizon_weeks,
                item.control_window_size,
            ),
        )
    )


def build_progression_role_audit(
    artifact: FrozenCausalDriftArtifact,
) -> ProgressionRoleAudit:
    classified = tuple(
        classify_progression_role(row) for row in artifact.rows
    )
    if len(classified) != artifact.comparison_row_count:
        raise ValueError(
            "classified row count must preserve K19 row count"
        )

    return ProgressionRoleAudit(
        audit_id=PROGRESSION_ROLE_CLASSIFICATION_AUDIT_ID,
        basket_name=artifact.basket_name,
        requested_symbol_count=artifact.requested_symbol_count,
        source_event_count=artifact.source_event_count,
        source_observation_count=artifact.source_observation_count,
        source_comparison_row_count=artifact.comparison_row_count,
        classified_row_count=len(classified),
        control_windows=artifact.control_windows,
        rows=classified,
        summaries=summarize_progression_roles(classified),
    )


def write_progression_role_audit(
    audit: ProgressionRoleAudit,
    output_dir: str | Path,
) -> ProgressionRoleAuditPaths:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    paths = ProgressionRoleAuditPaths(
        summary_json=root / "progression_role_summary.json",
        rows_csv=root / "progression_role_rows.csv",
        cohorts_csv=root / "progression_role_cohorts.csv",
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
        "classified_row_count": audit.classified_row_count,
        "control_windows": list(audit.control_windows),
        "role_definitions": {
            ROLE_ACTUAL_REVERSAL: (
                "trend-opposed event; realized return favored event "
                "direction"
            ),
            ROLE_DECELERATION_ONLY: (
                "trend-opposed event; no realized reversal, but event "
                "direction improved versus causal pre-event baseline"
            ),
            ROLE_FAILED_COUNTERTREND: (
                "trend-opposed event; no realized reversal and no "
                "positive causal lift"
            ),
            ROLE_CONTINUATION_OUTPERFORMS: (
                "trend-aligned event; realized continuation was positive "
                "and exceeded causal continuation baseline"
            ),
            ROLE_CONTINUATION_WEAKER: (
                "trend-aligned event; realized continuation was positive "
                "but did not exceed baseline"
            ),
            ROLE_CONTINUATION_FAILED: (
                "trend-aligned event; realized return did not favor "
                "event/trend direction"
            ),
        },
        "direction_trend_role_summaries": [
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
    "EXPECTED_K19_AUDIT_ID",
    "PROGRESSION_ROLE_CLASSIFICATION_AUDIT_ID",
    "FrozenCausalDriftArtifact",
    "FrozenCausalDriftRow",
    "ProgressionRoleAudit",
    "ProgressionRoleAuditPaths",
    "ProgressionRoleRow",
    "ProgressionRoleSummary",
    "ROLE_ACTUAL_REVERSAL",
    "ROLE_CONTINUATION_FAILED",
    "ROLE_CONTINUATION_OUTPERFORMS",
    "ROLE_CONTINUATION_WEAKER",
    "ROLE_DECELERATION_ONLY",
    "ROLE_FAILED_COUNTERTREND",
    "ROLE_INCOMPLETE",
    "ROLE_NEUTRAL_CONTEXT",
    "build_progression_role_audit",
    "classify_progression_role",
    "load_frozen_causal_drift_artifacts",
    "summarize_progression_roles",
    "write_progression_role_audit",
]
