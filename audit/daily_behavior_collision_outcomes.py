"""CSV-only post-analysis for DailyBehavior evidence-identity collisions.

Consumes an already-generated daily sequence study bundle. It does not replay
detectors, weekly authority, or market data and has no production authority.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


DAILY_BEHAVIOR_COLLISION_OUTCOME_AUDIT_ID = (
    "daily-behavior-collision-outcome-stratification-v1"
)


@dataclass(frozen=True, slots=True)
class DailyBehaviorCollisionOutcomePaths:
    summary_json: Path
    direction_summary_csv: Path
    dimension_family_summary_csv: Path
    evidence_variant_breadth_csv: Path
    evidence_variant_outcomes_csv: Path
    within_coarse_outcome_spreads_csv: Path
    within_coarse_pairwise_contrasts_csv: Path

    def as_dict(self) -> dict[str, str]:
        return {
            "summary_json": str(self.summary_json),
            "direction_summary_csv": str(self.direction_summary_csv),
            "dimension_family_summary_csv": str(self.dimension_family_summary_csv),
            "evidence_variant_breadth_csv": str(self.evidence_variant_breadth_csv),
            "evidence_variant_outcomes_csv": str(self.evidence_variant_outcomes_csv),
            "within_coarse_outcome_spreads_csv": str(
                self.within_coarse_outcome_spreads_csv
            ),
            "within_coarse_pairwise_contrasts_csv": str(
                self.within_coarse_pairwise_contrasts_csv
            ),
        }


_REQUIRED_RECORD_COLUMNS = {
    "symbol",
    "weekly_direction",
    "fresh_behavior",
    "signature",
    "evidence_signature",
}
_REQUIRED_OUTCOME_COLUMNS = {
    "symbol",
    "weekly_direction",
    "signature",
    "evidence_signature",
    "horizon_bars",
    "outcome_available",
    "complete",
    "favorable_return",
    "mfe",
    "mae",
}
_REQUIRED_COLLISION_COLUMNS = {
    "weekly_direction",
    "signature",
    "distinct_evidence_signature_count",
    "observation_count",
}


def _require_columns(
    frame: pd.DataFrame,
    required: set[str],
    *,
    label: str,
) -> None:
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{label} missing required columns: {missing}")


def _as_bool(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)
    normalized = series.astype(str).str.strip().str.lower()
    valid = {"true", "false"}
    observed = set(normalized.dropna().unique())
    invalid = sorted(observed - valid)
    if invalid:
        raise ValueError(f"boolean column contains invalid values: {invalid[:5]}")
    return normalized.eq("true")


def _collision_key_frame(collisions: pd.DataFrame) -> pd.DataFrame:
    return collisions.loc[:, ["weekly_direction", "signature"]].drop_duplicates()


def _dimension_family(signature: str) -> str:
    dimensions: set[str] = set()
    for step in str(signature).split(";"):
        if ":" not in step:
            continue
        _, values = step.split(":", 1)
        dimensions.update(item for item in values.split(",") if item)
    return "+".join(sorted(dimensions))


def _read_inputs(
    study_dir: str | Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    root = Path(study_dir)
    records = pd.read_csv(root / "daily_sequence_records.csv")
    outcomes = pd.read_csv(root / "daily_sequence_outcomes.csv")
    collisions = pd.read_csv(root / "daily_sequence_signature_collisions.csv")

    _require_columns(records, _REQUIRED_RECORD_COLUMNS, label="records")
    _require_columns(outcomes, _REQUIRED_OUTCOME_COLUMNS, label="outcomes")
    _require_columns(collisions, _REQUIRED_COLLISION_COLUMNS, label="collisions")

    records = records.copy()
    outcomes = outcomes.copy()
    collisions = collisions.copy()

    records["fresh_behavior"] = _as_bool(records["fresh_behavior"])
    outcomes["outcome_available"] = _as_bool(outcomes["outcome_available"])
    outcomes["complete"] = _as_bool(outcomes["complete"])

    for column in ("favorable_return", "mfe", "mae"):
        outcomes[column] = pd.to_numeric(outcomes[column], errors="coerce")
    outcomes["horizon_bars"] = pd.to_numeric(
        outcomes["horizon_bars"],
        errors="raise",
    ).astype(int)
    collisions["observation_count"] = pd.to_numeric(
        collisions["observation_count"],
        errors="raise",
    ).astype(int)

    return records, outcomes, collisions


def _collision_records(
    records: pd.DataFrame,
    collisions: pd.DataFrame,
) -> pd.DataFrame:
    fresh = records.loc[records["fresh_behavior"]].copy()
    keys = _collision_key_frame(collisions)
    result = fresh.merge(
        keys.assign(is_collision=True),
        how="left",
        on=["weekly_direction", "signature"],
    )
    result["is_collision"] = result["is_collision"].fillna(False).astype(bool)
    return result


def _direction_summary(
    records: pd.DataFrame,
    collisions: pd.DataFrame,
) -> pd.DataFrame:
    collision_records = _collision_records(records, collisions)
    rows: list[dict[str, object]] = []
    for direction, group in collision_records.groupby(
        "weekly_direction",
        sort=True,
    ):
        collided = group.loc[group["is_collision"]]
        rows.append(
            {
                "weekly_direction": direction,
                "fresh_sequence_count": len(group),
                "collision_observation_count": len(collided),
                "collision_rate": (
                    0.0 if len(group) == 0 else len(collided) / len(group)
                ),
                "distinct_coarse_signature_count": group["signature"].nunique(),
                "colliding_coarse_signature_count": collided["signature"].nunique(),
                "distinct_evidence_signature_count": (
                    group["evidence_signature"].nunique()
                ),
                "symbol_count": group["symbol"].nunique(),
                "is_actionable": False,
            }
        )
    return pd.DataFrame(rows)


def _dimension_family_summary(
    records: pd.DataFrame,
    collisions: pd.DataFrame,
) -> pd.DataFrame:
    collision_records = _collision_records(records, collisions)
    collision_records = collision_records.loc[
        collision_records["is_collision"]
    ].copy()
    collision_records["dimension_family"] = collision_records["signature"].map(
        _dimension_family
    )

    rows: list[dict[str, object]] = []
    for (direction, family), group in collision_records.groupby(
        ["weekly_direction", "dimension_family"],
        sort=True,
    ):
        rows.append(
            {
                "weekly_direction": direction,
                "dimension_family": family,
                "collision_observation_count": len(group),
                "coarse_signature_count": group["signature"].nunique(),
                "exact_evidence_signature_count": (
                    group["evidence_signature"].nunique()
                ),
                "symbol_count": group["symbol"].nunique(),
                "is_actionable": False,
            }
        )
    result = pd.DataFrame(rows)
    if not result.empty:
        result = result.sort_values(
            ["collision_observation_count", "weekly_direction"],
            ascending=[False, True],
        ).reset_index(drop=True)
    return result


def _evidence_variant_breadth(
    records: pd.DataFrame,
    collisions: pd.DataFrame,
) -> pd.DataFrame:
    collision_records = _collision_records(records, collisions)
    collision_records = collision_records.loc[
        collision_records["is_collision"]
    ].copy()
    universe_symbol_count = records["symbol"].nunique()

    rows: list[dict[str, object]] = []
    grouped = collision_records.groupby(
        ["weekly_direction", "signature", "evidence_signature"],
        sort=True,
    )
    for (direction, signature, evidence_signature), group in grouped:
        symbol_count = group["symbol"].nunique()
        rows.append(
            {
                "weekly_direction": direction,
                "signature": signature,
                "dimension_family": _dimension_family(signature),
                "evidence_signature": evidence_signature,
                "observation_count": len(group),
                "symbol_count": symbol_count,
                "universe_symbol_share": (
                    0.0
                    if universe_symbol_count == 0
                    else symbol_count / universe_symbol_count
                ),
                "is_actionable": False,
            }
        )

    result = pd.DataFrame(rows)
    if not result.empty:
        result = result.sort_values(
            ["observation_count", "symbol_count"],
            ascending=[False, False],
        ).reset_index(drop=True)
    return result


def _collision_outcomes(
    outcomes: pd.DataFrame,
    collisions: pd.DataFrame,
) -> pd.DataFrame:
    keys = _collision_key_frame(collisions)
    return outcomes.merge(
        keys,
        how="inner",
        on=["weekly_direction", "signature"],
    )


def _variant_outcomes(
    outcomes: pd.DataFrame,
    collisions: pd.DataFrame,
) -> pd.DataFrame:
    collision_outcomes = _collision_outcomes(outcomes, collisions)
    rows: list[dict[str, object]] = []

    grouped = collision_outcomes.groupby(
        [
            "weekly_direction",
            "signature",
            "evidence_signature",
            "horizon_bars",
        ],
        sort=True,
    )
    for (
        direction,
        signature,
        evidence_signature,
        horizon,
    ), group in grouped:
        complete = group.loc[group["complete"]]
        rows.append(
            {
                "weekly_direction": direction,
                "signature": signature,
                "dimension_family": _dimension_family(signature),
                "evidence_signature": evidence_signature,
                "horizon_bars": int(horizon),
                "observation_count": len(group),
                "outcome_available_count": int(group["outcome_available"].sum()),
                "complete_outcome_count": len(complete),
                "symbol_count": group["symbol"].nunique(),
                "mean_favorable_return": complete["favorable_return"].mean(),
                "median_favorable_return": complete["favorable_return"].median(),
                "mean_mfe": complete["mfe"].mean(),
                "mean_mae": complete["mae"].mean(),
                "is_actionable": False,
            }
        )
    return pd.DataFrame(rows)


def _within_coarse_outcome_spreads(
    variant_outcomes: pd.DataFrame,
    *,
    min_complete_per_variant: int,
) -> pd.DataFrame:
    eligible = variant_outcomes.loc[
        variant_outcomes["complete_outcome_count"] >= min_complete_per_variant
    ].copy()
    rows: list[dict[str, object]] = []

    for (direction, signature, horizon), group in eligible.groupby(
        ["weekly_direction", "signature", "horizon_bars"],
        sort=True,
    ):
        if len(group) < 2:
            continue
        rows.append(
            {
                "weekly_direction": direction,
                "signature": signature,
                "dimension_family": _dimension_family(signature),
                "horizon_bars": int(horizon),
                "eligible_evidence_variant_count": len(group),
                "complete_outcome_count": int(
                    group["complete_outcome_count"].sum()
                ),
                "max_variant_symbol_count": int(group["symbol_count"].max()),
                "min_mean_favorable_return": group["mean_favorable_return"].min(),
                "max_mean_favorable_return": group["mean_favorable_return"].max(),
                "mean_favorable_return_spread": (
                    group["mean_favorable_return"].max()
                    - group["mean_favorable_return"].min()
                ),
                "min_mean_mfe": group["mean_mfe"].min(),
                "max_mean_mfe": group["mean_mfe"].max(),
                "mean_mfe_spread": group["mean_mfe"].max() - group["mean_mfe"].min(),
                "min_mean_mae": group["mean_mae"].min(),
                "max_mean_mae": group["mean_mae"].max(),
                "mean_mae_spread": group["mean_mae"].max() - group["mean_mae"].min(),
                "is_actionable": False,
            }
        )

    result = pd.DataFrame(rows)
    if not result.empty:
        result = result.sort_values(
            ["mean_favorable_return_spread", "complete_outcome_count"],
            ascending=[False, False],
        ).reset_index(drop=True)
    return result


def _pairwise_contrasts(
    variant_outcomes: pd.DataFrame,
    *,
    min_complete_per_variant: int,
) -> pd.DataFrame:
    eligible = variant_outcomes.loc[
        variant_outcomes["complete_outcome_count"] >= min_complete_per_variant
    ].copy()
    rows: list[dict[str, object]] = []

    for (direction, signature, horizon), group in eligible.groupby(
        ["weekly_direction", "signature", "horizon_bars"],
        sort=True,
    ):
        ordered = group.sort_values("evidence_signature").reset_index(drop=True)
        if len(ordered) < 2:
            continue

        for left_index in range(len(ordered) - 1):
            left = ordered.iloc[left_index]
            for right_index in range(left_index + 1, len(ordered)):
                right = ordered.iloc[right_index]
                rows.append(
                    {
                        "weekly_direction": direction,
                        "signature": signature,
                        "dimension_family": _dimension_family(signature),
                        "horizon_bars": int(horizon),
                        "evidence_signature_a": left["evidence_signature"],
                        "evidence_signature_b": right["evidence_signature"],
                        "complete_outcome_count_a": int(
                            left["complete_outcome_count"]
                        ),
                        "complete_outcome_count_b": int(
                            right["complete_outcome_count"]
                        ),
                        "symbol_count_a": int(left["symbol_count"]),
                        "symbol_count_b": int(right["symbol_count"]),
                        "delta_mean_favorable_return_a_minus_b": (
                            left["mean_favorable_return"]
                            - right["mean_favorable_return"]
                        ),
                        "delta_mean_mfe_a_minus_b": (
                            left["mean_mfe"] - right["mean_mfe"]
                        ),
                        "delta_mean_mae_a_minus_b": (
                            left["mean_mae"] - right["mean_mae"]
                        ),
                        "is_actionable": False,
                    }
                )
    return pd.DataFrame(rows)


def run_daily_behavior_collision_outcome_analysis(
    *,
    study_dir: str | Path,
    output_dir: str | Path,
    min_complete_per_variant: int = 20,
) -> DailyBehaviorCollisionOutcomePaths:
    if min_complete_per_variant <= 0:
        raise ValueError("min_complete_per_variant must be positive")

    records, outcomes, collisions = _read_inputs(study_dir)
    fresh = records.loc[records["fresh_behavior"]]
    collision_records = _collision_records(records, collisions)
    collided = collision_records.loc[collision_records["is_collision"]]

    reported_collision_observations = int(collisions["observation_count"].sum())
    observed_collision_observations = len(collided)
    if observed_collision_observations != reported_collision_observations:
        raise ValueError(
            "collision observation reconciliation failed: "
            f"records={observed_collision_observations}, "
            f"collision_csv={reported_collision_observations}"
        )

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    paths = DailyBehaviorCollisionOutcomePaths(
        summary_json=root / "daily_behavior_collision_outcome_summary.json",
        direction_summary_csv=root / "daily_behavior_collision_direction_summary.csv",
        dimension_family_summary_csv=(
            root / "daily_behavior_collision_dimension_family_summary.csv"
        ),
        evidence_variant_breadth_csv=(
            root / "daily_behavior_collision_evidence_variant_breadth.csv"
        ),
        evidence_variant_outcomes_csv=(
            root / "daily_behavior_collision_evidence_variant_outcomes.csv"
        ),
        within_coarse_outcome_spreads_csv=(
            root / "daily_behavior_collision_within_coarse_outcome_spreads.csv"
        ),
        within_coarse_pairwise_contrasts_csv=(
            root / "daily_behavior_collision_within_coarse_pairwise_contrasts.csv"
        ),
    )

    direction_summary = _direction_summary(records, collisions)
    dimension_family_summary = _dimension_family_summary(records, collisions)
    breadth = _evidence_variant_breadth(records, collisions)
    variant_outcomes = _variant_outcomes(outcomes, collisions)
    spreads = _within_coarse_outcome_spreads(
        variant_outcomes,
        min_complete_per_variant=min_complete_per_variant,
    )
    contrasts = _pairwise_contrasts(
        variant_outcomes,
        min_complete_per_variant=min_complete_per_variant,
    )

    direction_summary.to_csv(paths.direction_summary_csv, index=False)
    dimension_family_summary.to_csv(paths.dimension_family_summary_csv, index=False)
    breadth.to_csv(paths.evidence_variant_breadth_csv, index=False)
    variant_outcomes.to_csv(paths.evidence_variant_outcomes_csv, index=False)
    spreads.to_csv(paths.within_coarse_outcome_spreads_csv, index=False)
    contrasts.to_csv(paths.within_coarse_pairwise_contrasts_csv, index=False)

    summary = {
        "audit_id": DAILY_BEHAVIOR_COLLISION_OUTCOME_AUDIT_ID,
        "record_count": len(records),
        "fresh_sequence_count": len(fresh),
        "collision_observation_count": observed_collision_observations,
        "collision_rate": (
            0.0 if len(fresh) == 0 else observed_collision_observations / len(fresh)
        ),
        "coarse_signature_collision_count": len(collisions),
        "weekly_direction_count": int(fresh["weekly_direction"].nunique()),
        "symbol_count": int(records["symbol"].nunique()),
        "outcome_observation_count": len(outcomes),
        "dimension_family_row_count": len(dimension_family_summary),
        "evidence_variant_breadth_row_count": len(breadth),
        "evidence_variant_outcome_row_count": len(variant_outcomes),
        "eligible_within_coarse_spread_row_count": len(spreads),
        "eligible_pairwise_contrast_row_count": len(contrasts),
        "min_complete_per_variant": min_complete_per_variant,
        "is_actionable": False,
    }
    paths.summary_json.write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return paths


__all__ = [
    "DAILY_BEHAVIOR_COLLISION_OUTCOME_AUDIT_ID",
    "DailyBehaviorCollisionOutcomePaths",
    "run_daily_behavior_collision_outcome_analysis",
]
