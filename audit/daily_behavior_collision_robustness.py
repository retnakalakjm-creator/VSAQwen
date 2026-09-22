"""Robustness checks for broad DailyBehavior evidence-identity contrasts.

This audit consumes existing CSV artifacts only. It never replays detectors,
weekly authority, market data, scoring, or actionability.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


DAILY_BEHAVIOR_COLLISION_ROBUSTNESS_AUDIT_ID = (
    "daily-behavior-collision-robustness-v1"
)


@dataclass(frozen=True, slots=True)
class DailyBehaviorCollisionRobustnessPaths:
    summary_json: Path
    broad_pairs_csv: Path
    horizon_robustness_csv: Path
    pair_summary_csv: Path

    def as_dict(self) -> dict[str, str]:
        return {
            "summary_json": str(self.summary_json),
            "broad_pairs_csv": str(self.broad_pairs_csv),
            "horizon_robustness_csv": str(self.horizon_robustness_csv),
            "pair_summary_csv": str(self.pair_summary_csv),
        }


_REQUIRED_PAIRWISE_COLUMNS = {
    "weekly_direction",
    "signature",
    "dimension_family",
    "horizon_bars",
    "evidence_signature_a",
    "evidence_signature_b",
    "complete_outcome_count_a",
    "complete_outcome_count_b",
    "symbol_count_a",
    "symbol_count_b",
    "delta_mean_favorable_return_a_minus_b",
}
_REQUIRED_OUTCOME_COLUMNS = {
    "symbol",
    "signal_bar_index",
    "weekly_direction",
    "signature",
    "evidence_signature",
    "horizon_bars",
    "complete",
    "favorable_return",
    "mfe",
    "mae",
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


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _as_bool(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)
    normalized = series.astype(str).str.strip().str.lower()
    invalid = sorted(set(normalized.unique()) - {"true", "false"})
    if invalid:
        raise ValueError(f"boolean column contains invalid values: {invalid[:5]}")
    return normalized.eq("true")


def _sign(value: float) -> int:
    if not math.isfinite(value):
        return 0
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def _same_nonzero_sign(values: list[float]) -> bool:
    signs = {_sign(float(value)) for value in values}
    return len(signs) == 1 and 0 not in signs


def _read_pairwise(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    _require_columns(frame, _REQUIRED_PAIRWISE_COLUMNS, label="pairwise contrasts")

    frame = frame.copy()
    integer_columns = (
        "horizon_bars",
        "complete_outcome_count_a",
        "complete_outcome_count_b",
        "symbol_count_a",
        "symbol_count_b",
    )
    for column in integer_columns:
        frame[column] = pd.to_numeric(frame[column], errors="raise").astype(int)
    frame["delta_mean_favorable_return_a_minus_b"] = pd.to_numeric(
        frame["delta_mean_favorable_return_a_minus_b"],
        errors="raise",
    )
    return frame


def _read_outcomes(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    _require_columns(frame, _REQUIRED_OUTCOME_COLUMNS, label="raw outcomes")

    frame = frame.copy()
    frame["complete"] = _as_bool(frame["complete"])
    frame["signal_bar_index"] = pd.to_numeric(
        frame["signal_bar_index"],
        errors="raise",
    ).astype(int)
    frame["horizon_bars"] = pd.to_numeric(
        frame["horizon_bars"],
        errors="raise",
    ).astype(int)
    for column in ("favorable_return", "mfe", "mae"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def _broad_pairs(
    pairwise: pd.DataFrame,
    *,
    horizons: tuple[int, ...],
    min_complete_per_variant: int,
    min_symbols_per_variant: int,
) -> pd.DataFrame:
    eligible = pairwise.loc[
        (pairwise["complete_outcome_count_a"] >= min_complete_per_variant)
        & (pairwise["complete_outcome_count_b"] >= min_complete_per_variant)
        & (pairwise["symbol_count_a"] >= min_symbols_per_variant)
        & (pairwise["symbol_count_b"] >= min_symbols_per_variant)
        & (pairwise["horizon_bars"].isin(horizons))
    ].copy()

    pair_keys = [
        "weekly_direction",
        "signature",
        "dimension_family",
        "evidence_signature_a",
        "evidence_signature_b",
    ]
    rows: list[dict[str, object]] = []
    required_horizons = set(horizons)

    for key, group in eligible.groupby(pair_keys, sort=True):
        observed_horizons = set(group["horizon_bars"].astype(int))
        if observed_horizons != required_horizons:
            continue
        deltas = [
            float(item)
            for item in group.sort_values("horizon_bars")[
                "delta_mean_favorable_return_a_minus_b"
            ]
        ]
        rows.append(
            {
                **dict(zip(pair_keys, key, strict=True)),
                "horizon_count": len(horizons),
                "min_complete_outcome_count_a": int(
                    group["complete_outcome_count_a"].min()
                ),
                "min_complete_outcome_count_b": int(
                    group["complete_outcome_count_b"].min()
                ),
                "min_symbol_count_a": int(group["symbol_count_a"].min()),
                "min_symbol_count_b": int(group["symbol_count_b"].min()),
                "pooled_sign_stable_across_horizons": _same_nonzero_sign(deltas),
                "is_actionable": False,
            }
        )

    return pd.DataFrame(rows)


def _variant_rows(
    outcomes: pd.DataFrame,
    *,
    direction: str,
    signature: str,
    evidence_signature: str,
    horizon: int,
) -> pd.DataFrame:
    return outcomes.loc[
        outcomes["complete"]
        & (outcomes["weekly_direction"] == direction)
        & (outcomes["signature"] == signature)
        & (outcomes["evidence_signature"] == evidence_signature)
        & (outcomes["horizon_bars"] == horizon)
    ].copy()


def _metric_delta(
    left: pd.DataFrame,
    right: pd.DataFrame,
    metric: str,
) -> float:
    return float(left[metric].mean() - right[metric].mean())


def _symbol_balanced(
    left: pd.DataFrame,
    right: pd.DataFrame,
    metric: str,
) -> tuple[int, float, float]:
    left_means = left.groupby("symbol", sort=True)[metric].mean()
    right_means = right.groupby("symbol", sort=True)[metric].mean()
    paired = pd.concat(
        [left_means.rename("a"), right_means.rename("b")],
        axis=1,
        join="inner",
    ).dropna()
    if paired.empty:
        return 0, math.nan, math.nan

    deltas = paired["a"] - paired["b"]
    return len(paired), float(deltas.mean()), float(deltas.median())


def _leave_one_symbol_out(
    left: pd.DataFrame,
    right: pd.DataFrame,
    metric: str,
    pooled_delta: float,
) -> tuple[int, float, float, float, bool]:
    symbols = sorted(set(left["symbol"]) | set(right["symbol"]))
    deltas: list[float] = []

    for symbol in symbols:
        left_drop = left.loc[left["symbol"] != symbol]
        right_drop = right.loc[right["symbol"] != symbol]
        if left_drop.empty or right_drop.empty:
            continue
        delta = _metric_delta(left_drop, right_drop, metric)
        if math.isfinite(delta):
            deltas.append(delta)

    if not deltas:
        return 0, math.nan, math.nan, math.nan, False

    pooled_sign = _sign(pooled_delta)
    same_sign_count = sum(_sign(delta) == pooled_sign for delta in deltas)
    same_sign_fraction = (
        0.0 if pooled_sign == 0 else same_sign_count / len(deltas)
    )
    return (
        len(deltas),
        min(deltas),
        max(deltas),
        same_sign_fraction,
        pooled_sign != 0 and same_sign_count == len(deltas),
    )


def _nearest_time_matches(
    left: pd.DataFrame,
    right: pd.DataFrame,
    *,
    max_gap_bars: int,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []

    common_symbols = sorted(set(left["symbol"]) & set(right["symbol"]))
    for symbol in common_symbols:
        left_symbol = left.loc[left["symbol"] == symbol].sort_values(
            "signal_bar_index"
        )
        right_symbol = right.loc[right["symbol"] == symbol].sort_values(
            "signal_bar_index"
        )
        if left_symbol.empty or right_symbol.empty:
            continue

        candidates: list[tuple[int, int, int]] = []
        right_indices = right_symbol["signal_bar_index"].tolist()
        for left_position, left_index in enumerate(
            left_symbol["signal_bar_index"].tolist()
        ):
            for right_position, right_index in enumerate(right_indices):
                gap = abs(int(left_index) - int(right_index))
                if gap <= max_gap_bars:
                    candidates.append((gap, left_position, right_position))

        used_left: set[int] = set()
        used_right: set[int] = set()
        for gap, left_position, right_position in sorted(candidates):
            if left_position in used_left or right_position in used_right:
                continue
            used_left.add(left_position)
            used_right.add(right_position)

            left_row = left_symbol.iloc[left_position]
            right_row = right_symbol.iloc[right_position]
            rows.append(
                {
                    "symbol": symbol,
                    "gap_bars": gap,
                    "favorable_return_delta": (
                        float(left_row["favorable_return"])
                        - float(right_row["favorable_return"])
                    ),
                    "mfe_delta": (
                        float(left_row["mfe"]) - float(right_row["mfe"])
                    ),
                    "mae_delta": (
                        float(left_row["mae"]) - float(right_row["mae"])
                    ),
                }
            )

    return pd.DataFrame(rows)


def _horizon_robustness(
    pairwise: pd.DataFrame,
    outcomes: pd.DataFrame,
    broad_pairs: pd.DataFrame,
    *,
    horizons: tuple[int, ...],
    max_time_gap_bars: int,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []

    for pair in broad_pairs.itertuples(index=False):
        for horizon in horizons:
            left = _variant_rows(
                outcomes,
                direction=pair.weekly_direction,
                signature=pair.signature,
                evidence_signature=pair.evidence_signature_a,
                horizon=horizon,
            )
            right = _variant_rows(
                outcomes,
                direction=pair.weekly_direction,
                signature=pair.signature,
                evidence_signature=pair.evidence_signature_b,
                horizon=horizon,
            )
            if left.empty or right.empty:
                raise ValueError(
                    "broad pair missing complete raw outcomes: "
                    f"{pair.weekly_direction} / {pair.signature} / "
                    f"{pair.evidence_signature_a} / "
                    f"{pair.evidence_signature_b} / h={horizon}"
                )

            pairwise_row = pairwise.loc[
                (pairwise["weekly_direction"] == pair.weekly_direction)
                & (pairwise["signature"] == pair.signature)
                & (
                    pairwise["evidence_signature_a"]
                    == pair.evidence_signature_a
                )
                & (
                    pairwise["evidence_signature_b"]
                    == pair.evidence_signature_b
                )
                & (pairwise["horizon_bars"] == horizon)
            ]
            if len(pairwise_row) != 1:
                raise ValueError("expected exactly one #366 pairwise contrast row")

            pooled_favorable = _metric_delta(
                left,
                right,
                "favorable_return",
            )
            expected = float(
                pairwise_row.iloc[0][
                    "delta_mean_favorable_return_a_minus_b"
                ]
            )
            if not math.isclose(
                pooled_favorable,
                expected,
                rel_tol=1e-9,
                abs_tol=1e-12,
            ):
                raise ValueError(
                    "raw outcome / #366 pooled contrast mismatch: "
                    f"expected={expected}, observed={pooled_favorable}"
                )

            paired_symbols, balanced_favorable, balanced_favorable_median = (
                _symbol_balanced(left, right, "favorable_return")
            )
            _, balanced_mfe, _ = _symbol_balanced(left, right, "mfe")
            _, balanced_mae, _ = _symbol_balanced(left, right, "mae")

            (
                loo_count,
                loo_min,
                loo_max,
                loo_same_sign_fraction,
                loo_all_same_sign,
            ) = _leave_one_symbol_out(
                left,
                right,
                "favorable_return",
                pooled_favorable,
            )

            matches = _nearest_time_matches(
                left,
                right,
                max_gap_bars=max_time_gap_bars,
            )
            if matches.empty:
                matched_pair_count = 0
                matched_symbol_count = 0
                mean_gap = math.nan
                matched_favorable = math.nan
                matched_favorable_median = math.nan
                matched_mfe = math.nan
                matched_mae = math.nan
            else:
                matched_pair_count = len(matches)
                matched_symbol_count = int(matches["symbol"].nunique())
                mean_gap = float(matches["gap_bars"].mean())
                matched_favorable = float(
                    matches["favorable_return_delta"].mean()
                )
                matched_favorable_median = float(
                    matches["favorable_return_delta"].median()
                )
                matched_mfe = float(matches["mfe_delta"].mean())
                matched_mae = float(matches["mae_delta"].mean())

            rows.append(
                {
                    "weekly_direction": pair.weekly_direction,
                    "signature": pair.signature,
                    "dimension_family": pair.dimension_family,
                    "evidence_signature_a": pair.evidence_signature_a,
                    "evidence_signature_b": pair.evidence_signature_b,
                    "horizon_bars": horizon,
                    "complete_outcome_count_a": len(left),
                    "complete_outcome_count_b": len(right),
                    "symbol_count_a": left["symbol"].nunique(),
                    "symbol_count_b": right["symbol"].nunique(),
                    "pooled_delta_mean_favorable_return_a_minus_b": (
                        pooled_favorable
                    ),
                    "pooled_delta_mean_mfe_a_minus_b": _metric_delta(
                        left,
                        right,
                        "mfe",
                    ),
                    "pooled_delta_mean_mae_a_minus_b": _metric_delta(
                        left,
                        right,
                        "mae",
                    ),
                    "paired_symbol_count": paired_symbols,
                    "symbol_balanced_delta_mean_favorable_return_a_minus_b": (
                        balanced_favorable
                    ),
                    "symbol_balanced_delta_median_favorable_return_a_minus_b": (
                        balanced_favorable_median
                    ),
                    "symbol_balanced_delta_mean_mfe_a_minus_b": balanced_mfe,
                    "symbol_balanced_delta_mean_mae_a_minus_b": balanced_mae,
                    "loo_iteration_count": loo_count,
                    "loo_min_delta_mean_favorable_return_a_minus_b": loo_min,
                    "loo_max_delta_mean_favorable_return_a_minus_b": loo_max,
                    "loo_same_sign_as_pooled_fraction": loo_same_sign_fraction,
                    "loo_all_same_sign_as_pooled": loo_all_same_sign,
                    "matched_pair_count": matched_pair_count,
                    "matched_symbol_count": matched_symbol_count,
                    "matched_mean_gap_bars": mean_gap,
                    "matched_delta_mean_favorable_return_a_minus_b": (
                        matched_favorable
                    ),
                    "matched_delta_median_favorable_return_a_minus_b": (
                        matched_favorable_median
                    ),
                    "matched_delta_mean_mfe_a_minus_b": matched_mfe,
                    "matched_delta_mean_mae_a_minus_b": matched_mae,
                    "is_actionable": False,
                }
            )

    return pd.DataFrame(rows)


def _pair_summary(
    horizon_rows: pd.DataFrame,
    *,
    horizons: tuple[int, ...],
) -> pd.DataFrame:
    pair_keys = [
        "weekly_direction",
        "signature",
        "dimension_family",
        "evidence_signature_a",
        "evidence_signature_b",
    ]
    rows: list[dict[str, object]] = []

    for key, group in horizon_rows.groupby(pair_keys, sort=True):
        group = group.sort_values("horizon_bars")
        if tuple(group["horizon_bars"].astype(int)) != horizons:
            raise ValueError("robustness pair is missing a required horizon")

        pooled = group[
            "pooled_delta_mean_favorable_return_a_minus_b"
        ].astype(float).tolist()
        balanced = group[
            "symbol_balanced_delta_mean_favorable_return_a_minus_b"
        ].astype(float).tolist()
        matched = group[
            "matched_delta_mean_favorable_return_a_minus_b"
        ].astype(float).tolist()

        pooled_stable = _same_nonzero_sign(pooled)
        balanced_stable = _same_nonzero_sign(balanced)
        matched_stable = _same_nonzero_sign(matched)
        loo_stable = bool(group["loo_all_same_sign_as_pooled"].all())

        method_signs_same_each_horizon = True
        for pooled_value, balanced_value, matched_value in zip(
            pooled,
            balanced,
            matched,
            strict=True,
        ):
            signs = {
                _sign(pooled_value),
                _sign(balanced_value),
                _sign(matched_value),
            }
            if len(signs) != 1 or 0 in signs:
                method_signs_same_each_horizon = False
                break

        rows.append(
            {
                **dict(zip(pair_keys, key, strict=True)),
                "horizon_count": len(group),
                "pooled_sign_stable_across_horizons": pooled_stable,
                "symbol_balanced_sign_stable_across_horizons": balanced_stable,
                "matched_sign_stable_across_horizons": matched_stable,
                "loo_all_same_sign_as_pooled_all_horizons": loo_stable,
                "all_methods_same_sign_each_horizon": (
                    method_signs_same_each_horizon
                ),
                "all_methods_sign_stable_across_horizons": (
                    pooled_stable
                    and balanced_stable
                    and matched_stable
                    and loo_stable
                    and method_signs_same_each_horizon
                ),
                "min_complete_outcome_count_a": int(
                    group["complete_outcome_count_a"].min()
                ),
                "min_complete_outcome_count_b": int(
                    group["complete_outcome_count_b"].min()
                ),
                "min_paired_symbol_count": int(
                    group["paired_symbol_count"].min()
                ),
                "min_matched_pair_count": int(
                    group["matched_pair_count"].min()
                ),
                "min_matched_symbol_count": int(
                    group["matched_symbol_count"].min()
                ),
                "max_matched_mean_gap_bars": float(
                    group["matched_mean_gap_bars"].max()
                ),
                "is_actionable": False,
            }
        )

    return pd.DataFrame(rows)


def run_daily_behavior_collision_robustness(
    *,
    raw_outcomes_csv: str | Path,
    pairwise_contrasts_csv: str | Path,
    output_dir: str | Path,
    horizons: tuple[int, ...] = (1, 3, 5, 10, 15),
    min_complete_per_variant: int = 100,
    min_symbols_per_variant: int = 20,
    max_time_gap_bars: int = 20,
) -> DailyBehaviorCollisionRobustnessPaths:
    if not horizons or any(item <= 0 for item in horizons):
        raise ValueError("horizons must contain positive bar counts")
    if tuple(sorted(set(horizons))) != horizons:
        raise ValueError("horizons must be unique and sorted")
    if min_complete_per_variant <= 0:
        raise ValueError("min_complete_per_variant must be positive")
    if min_symbols_per_variant <= 0:
        raise ValueError("min_symbols_per_variant must be positive")
    if max_time_gap_bars < 0:
        raise ValueError("max_time_gap_bars cannot be negative")

    outcomes_path = Path(raw_outcomes_csv)
    pairwise_path = Path(pairwise_contrasts_csv)
    outcomes = _read_outcomes(outcomes_path)
    pairwise = _read_pairwise(pairwise_path)

    broad_pairs = _broad_pairs(
        pairwise,
        horizons=horizons,
        min_complete_per_variant=min_complete_per_variant,
        min_symbols_per_variant=min_symbols_per_variant,
    )
    if broad_pairs.empty:
        raise ValueError("no broad evidence-variant pairs satisfy thresholds")

    horizon_rows = _horizon_robustness(
        pairwise,
        outcomes,
        broad_pairs,
        horizons=horizons,
        max_time_gap_bars=max_time_gap_bars,
    )
    pair_summary = _pair_summary(horizon_rows, horizons=horizons)

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    paths = DailyBehaviorCollisionRobustnessPaths(
        summary_json=root / "daily_behavior_collision_robustness_summary.json",
        broad_pairs_csv=root / "daily_behavior_collision_broad_pairs.csv",
        horizon_robustness_csv=(
            root / "daily_behavior_collision_horizon_robustness.csv"
        ),
        pair_summary_csv=root / "daily_behavior_collision_pair_summary.csv",
    )

    broad_pairs.to_csv(paths.broad_pairs_csv, index=False)
    horizon_rows.to_csv(paths.horizon_robustness_csv, index=False)
    pair_summary.to_csv(paths.pair_summary_csv, index=False)

    summary = {
        "audit_id": DAILY_BEHAVIOR_COLLISION_ROBUSTNESS_AUDIT_ID,
        "raw_outcomes_csv": str(outcomes_path),
        "raw_outcomes_sha256": _file_sha256(outcomes_path),
        "raw_outcome_row_count": len(outcomes),
        "pairwise_contrasts_csv": str(pairwise_path),
        "pairwise_contrasts_sha256": _file_sha256(pairwise_path),
        "pairwise_contrast_row_count": len(pairwise),
        "horizons_bars": list(horizons),
        "min_complete_per_variant": min_complete_per_variant,
        "min_symbols_per_variant": min_symbols_per_variant,
        "max_time_gap_bars": max_time_gap_bars,
        "broad_pair_count": len(broad_pairs),
        "pooled_sign_stable_pair_count": int(
            broad_pairs["pooled_sign_stable_across_horizons"].sum()
        ),
        "horizon_robustness_row_count": len(horizon_rows),
        "all_methods_sign_stable_pair_count": int(
            pair_summary["all_methods_sign_stable_across_horizons"].sum()
        ),
        "pair_summary_row_count": len(pair_summary),
        "is_actionable": False,
    }
    paths.summary_json.write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return paths


__all__ = [
    "DAILY_BEHAVIOR_COLLISION_ROBUSTNESS_AUDIT_ID",
    "DailyBehaviorCollisionRobustnessPaths",
    "run_daily_behavior_collision_robustness",
]
