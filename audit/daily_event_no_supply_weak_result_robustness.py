"""Robustness and semantic validation for NO_SUPPLY WEAK_RESULT_ONLY.

L10 reuses canonical L9 target classification and canonical L8 matched pair
outcomes. It performs symbol-clustered bootstrap inference and direct source
semantic checks without replaying market structure or production detectors.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from typing import Iterable, Sequence

import numpy as np
import pandas as pd

from audit.daily_event_no_supply_confirmation_strata import (
    DAILY_NO_SUPPLY_CONFIRMATION_STRATA_AUDIT_ID,
    STRATUM_WEAK_RESULT_ONLY,
)
from audit.daily_event_no_supply_forward_outcomes import (
    COHORT_ALTERNATE,
    COHORT_CURRENT,
    DEFAULT_FORWARD_HORIZONS,
    normalize_forward_horizons,
)
from audit.daily_event_no_supply_matched_environment import (
    DAILY_NO_SUPPLY_MATCHED_ENVIRONMENT_AUDIT_ID,
)
from evidence.rules import is_weak_close, volume_decreasing
from models import ClosePosition


DAILY_NO_SUPPLY_WEAK_RESULT_ROBUSTNESS_AUDIT_ID = (
    "daily-event-no-supply-weak-result-robustness-v1"
)
DEFAULT_CLUSTER_BOOTSTRAP_ITERATIONS = 10_000
DEFAULT_CLUSTER_BOOTSTRAP_SEED = 20260921

ESTIMAND_EVENT_WEIGHTED = "EVENT_WEIGHTED"
ESTIMAND_SYMBOL_NORMALIZED = "SYMBOL_NORMALIZED"
BOOTSTRAP_ESTIMANDS = (
    ESTIMAND_EVENT_WEIGHTED,
    ESTIMAND_SYMBOL_NORMALIZED,
)

METRIC_RETURN = "PAIRED_RETURN_DELTA_PCT"
METRIC_POSITIVE_CLOSE = "POSITIVE_CLOSE_RATE_DELTA"
METRIC_MFE = "PAIRED_MFE_DELTA_PCT"
METRIC_MAE = "PAIRED_MAE_DELTA_PCT"
BOOTSTRAP_METRICS = (
    METRIC_RETURN,
    METRIC_POSITIVE_CLOSE,
    METRIC_MFE,
    METRIC_MAE,
)

METRIC_COLUMN = {
    METRIC_RETURN: "paired_return_delta_pct",
    METRIC_POSITIVE_CLOSE: "positive_delta",
    METRIC_MFE: "paired_mfe_delta_pct",
    METRIC_MAE: "paired_mae_delta_pct",
}


@dataclass(frozen=True, slots=True)
class NoSupplyWeakResultSourceLineage:
    l9_audit_id: str
    l9_summary_sha256: str
    l9_targets_sha256: str
    l9_stratum_counts_sha256: str
    l9_stratum_outcomes_sha256: str
    l9_stratum_symbol_outcomes_sha256: str
    l8_audit_id: str
    l8_summary_sha256: str
    l8_pair_outcomes_sha256: str
    l6_observations_sha256: str
    snapshot_manifest_sha256: str


@dataclass(frozen=True, slots=True)
class NoSupplyWeakResultSources:
    lineage: NoSupplyWeakResultSourceLineage
    targets: pd.DataFrame
    pair_outcomes: pd.DataFrame
    current_target_count: int
    alternate_target_count: int


@dataclass(frozen=True, slots=True)
class NoSupplyWeakResultRobustnessRow:
    cohort: str
    horizon_sessions: int
    source_target_count: int
    pair_count: int
    clean_pair_count: int
    symbol_count: int
    clean_symbol_count: int
    event_weighted_return_delta_pct: float
    symbol_normalized_return_delta_pct: float
    event_weighted_positive_close_rate_delta: float
    symbol_normalized_positive_close_rate_delta: float
    event_weighted_mfe_delta_pct: float
    symbol_normalized_mfe_delta_pct: float
    event_weighted_mae_delta_pct: float
    symbol_normalized_mae_delta_pct: float
    positive_return_symbol_count: int
    negative_return_symbol_count: int
    zero_return_symbol_count: int


@dataclass(frozen=True, slots=True)
class NoSupplyWeakResultBootstrapRow:
    cohort: str
    horizon_sessions: int
    metric: str
    estimand: str
    clean_pair_count: int
    symbol_count: int
    observed_value: float
    bootstrap_mean: float
    ci_lower_95: float
    ci_upper_95: float
    bootstrap_fraction_gt_zero: float
    bootstrap_fraction_lt_zero: float
    bootstrap_iterations: int
    bootstrap_seed: int
    ci_excludes_zero: bool


@dataclass(frozen=True, slots=True)
class NoSupplyWeakResultLeaveOneOutRow:
    cohort: str
    horizon_sessions: int
    estimand: str
    full_return_delta_pct: float
    min_leave_one_out_return_delta_pct: float
    min_leave_one_out_symbol: str
    max_leave_one_out_return_delta_pct: float
    max_leave_one_out_symbol: str
    max_absolute_shift_pct: float
    max_absolute_shift_symbol: str
    positive_leave_one_out_count: int
    negative_leave_one_out_count: int
    zero_leave_one_out_count: int
    symbol_count: int


@dataclass(frozen=True, slots=True)
class NoSupplyWeakResultSemanticRow:
    semantic_dimension: str
    input_state: str
    predicate_result: bool
    interpretation: str


@dataclass(frozen=True, slots=True)
class NoSupplyWeakResultRobustnessAudit:
    audit_id: str
    source_lineage: NoSupplyWeakResultSourceLineage
    requested_symbol_count: int
    candidate_target_count: int
    current_candidate_target_count: int
    alternate_candidate_target_count: int
    horizon_count: int
    horizons: tuple[int, ...]
    bootstrap_iterations: int
    bootstrap_seed: int
    robustness_rows: tuple[NoSupplyWeakResultRobustnessRow, ...]
    bootstrap_rows: tuple[NoSupplyWeakResultBootstrapRow, ...]
    leave_one_out_rows: tuple[NoSupplyWeakResultLeaveOneOutRow, ...]
    semantic_rows: tuple[NoSupplyWeakResultSemanticRow, ...]

    @property
    def is_actionable(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class NoSupplyWeakResultRobustnessPaths:
    summary_json: Path
    candidate_targets_csv: Path
    robustness_csv: Path
    bootstrap_csv: Path
    leave_one_out_csv: Path
    semantics_csv: Path

    def as_dict(self) -> dict[str, str]:
        return {
            "summary_json": str(self.summary_json),
            "candidate_targets_csv": str(self.candidate_targets_csv),
            "robustness_csv": str(self.robustness_csv),
            "bootstrap_csv": str(self.bootstrap_csv),
            "leave_one_out_csv": str(self.leave_one_out_csv),
            "semantics_csv": str(self.semantics_csv),
        }


def _sha256_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _normalize_session(value: object) -> str:
    return pd.Timestamp(value).isoformat()


def _parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1"}:
        return True
    if text in {"false", "0"}:
        return False
    raise ValueError(f"cannot parse boolean value {value!r}")


def _validate_l9_summary(summary: dict[str, object]) -> None:
    if (
        summary.get("audit_id")
        != DAILY_NO_SUPPLY_CONFIRMATION_STRATA_AUDIT_ID
    ):
        raise ValueError("unexpected L9 audit_id")
    if summary.get("is_actionable") is not False:
        raise ValueError("L10 requires non-actionable L9 source")
    if int(summary.get("requested_symbol_count", -1)) != 30:
        raise ValueError("L10 requires canonical 30-symbol L9 source")
    if int(summary.get("source_target_count", -1)) != 2509:
        raise ValueError("unexpected L9 source target count")
    if int(summary.get("current_source_target_count", -1)) != 777:
        raise ValueError("unexpected L9 CURRENT source count")
    if int(summary.get("alternate_source_target_count", -1)) != 1732:
        raise ValueError("unexpected L9 ALTERNATE source count")
    if int(summary.get("weak_spread_target_count", -1)) != 2509:
        raise ValueError("L10 requires canonical Weak Spread redundancy")


def load_no_supply_weak_result_sources(
    *,
    confirmation_dir: str | Path,
    matched_dir: str | Path,
) -> NoSupplyWeakResultSources:
    confirmation_root = Path(confirmation_dir)
    matched_root = Path(matched_dir)

    l9_summary_path = (
        confirmation_root / "daily_no_supply_confirmation_strata_summary.json"
    )
    l9_targets_path = (
        confirmation_root / "daily_no_supply_confirmation_targets.csv"
    )
    l9_counts_path = (
        confirmation_root / "daily_no_supply_confirmation_stratum_counts.csv"
    )
    l9_outcomes_path = (
        confirmation_root / "daily_no_supply_confirmation_stratum_outcomes.csv"
    )
    l9_symbol_path = (
        confirmation_root
        / "daily_no_supply_confirmation_stratum_symbol_outcomes.csv"
    )
    l8_summary_path = matched_root / "daily_no_supply_matched_summary.json"
    l8_pair_path = matched_root / "daily_no_supply_matched_pair_outcomes.csv"

    for path in (
        l9_summary_path,
        l9_targets_path,
        l9_counts_path,
        l9_outcomes_path,
        l9_symbol_path,
        l8_summary_path,
        l8_pair_path,
    ):
        if not path.exists():
            raise FileNotFoundError(path)

    l9_summary = json.loads(l9_summary_path.read_text(encoding="utf-8"))
    _validate_l9_summary(l9_summary)
    l9_lineage = l9_summary.get("source_lineage")
    if not isinstance(l9_lineage, dict):
        raise ValueError("L9 source lineage is missing")

    l8_summary_sha256 = _sha256_file(l8_summary_path)
    l8_pair_sha256 = _sha256_file(l8_pair_path)
    if str(l9_lineage.get("l8_summary_sha256", "")) != l8_summary_sha256:
        raise ValueError("L9 points to a different L8 summary")
    if (
        str(l9_lineage.get("l8_pair_outcomes_sha256", ""))
        != l8_pair_sha256
    ):
        raise ValueError("L9 points to a different L8 pair ledger")

    l8_summary = json.loads(l8_summary_path.read_text(encoding="utf-8"))
    if (
        l8_summary.get("audit_id")
        != DAILY_NO_SUPPLY_MATCHED_ENVIRONMENT_AUDIT_ID
    ):
        raise ValueError("unexpected L8 audit_id")
    if l8_summary.get("is_actionable") is not False:
        raise ValueError("L10 requires non-actionable L8 source")
    if int(l8_summary.get("matched_target_count", -1)) != 2509:
        raise ValueError("L10 requires fully matched L8 source")
    if int(l8_summary.get("unmatched_target_count", -1)) != 0:
        raise ValueError("L10 requires zero unmatched L8 targets")

    targets = pd.read_csv(l9_targets_path)
    required_targets = {
        "symbol",
        "session",
        "bar_index",
        "cohort",
        "trend_direction",
        "volume_decreasing",
        "weak_selling_result",
        "stratum",
    }
    missing_targets = sorted(required_targets - set(targets.columns))
    if missing_targets:
        raise ValueError(f"L9 targets missing columns: {missing_targets}")
    targets = targets.copy()
    targets["symbol"] = targets["symbol"].map(
        lambda value: str(value).strip().upper()
    )
    targets["session"] = targets["session"].map(_normalize_session)
    targets["volume_decreasing"] = targets["volume_decreasing"].map(
        _parse_bool
    )
    targets["weak_selling_result"] = targets["weak_selling_result"].map(
        _parse_bool
    )
    if len(targets) != 2509:
        raise ValueError("L9 target ledger count changed")
    if targets[["symbol", "session"]].duplicated().any():
        raise ValueError("L9 target identities are not unique")

    candidate = targets.loc[
        targets["stratum"] == STRATUM_WEAK_RESULT_ONLY
    ].copy()
    if not (
        (~candidate["volume_decreasing"])
        & candidate["weak_selling_result"]
    ).all():
        raise ValueError("WEAK_RESULT_ONLY predicate semantics drifted")

    current_count = int((candidate["cohort"] == COHORT_CURRENT).sum())
    alternate_count = int(
        (candidate["cohort"] == COHORT_ALTERNATE).sum()
    )
    if current_count != 122 or alternate_count != 305:
        raise ValueError(
            "canonical WEAK_RESULT_ONLY population changed: "
            f"{current_count}/{alternate_count}"
        )
    if len(candidate) != 427:
        raise ValueError("canonical WEAK_RESULT_ONLY total must be 427")
    if int(candidate["symbol"].nunique()) != 30:
        raise ValueError("WEAK_RESULT_ONLY must span all 30 symbols")

    pair_outcomes = pd.read_csv(l8_pair_path)
    required_pair = {
        "symbol",
        "cohort",
        "trend_direction",
        "target_session",
        "target_bar_index",
        "horizon_sessions",
        "paired_return_delta_pct",
        "target_positive_close",
        "control_positive_close",
        "paired_mfe_delta_pct",
        "paired_mae_delta_pct",
        "clean_pair",
    }
    missing_pair = sorted(required_pair - set(pair_outcomes.columns))
    if missing_pair:
        raise ValueError(f"L8 pair outcomes missing columns: {missing_pair}")
    pair_outcomes = pair_outcomes.copy()
    pair_outcomes["symbol"] = pair_outcomes["symbol"].map(
        lambda value: str(value).strip().upper()
    )
    pair_outcomes["target_session"] = pair_outcomes[
        "target_session"
    ].map(_normalize_session)
    for column in (
        "target_positive_close",
        "control_positive_close",
        "clean_pair",
    ):
        pair_outcomes[column] = pair_outcomes[column].map(_parse_bool)
    if len(pair_outcomes) != 12539:
        raise ValueError("L8 canonical pair-outcome count changed")

    candidate_ids = set(
        zip(candidate["symbol"], candidate["session"], strict=False)
    )
    pair_candidate = pair_outcomes.loc[
        [
            (symbol, session) in candidate_ids
            for symbol, session in zip(
                pair_outcomes["symbol"],
                pair_outcomes["target_session"],
                strict=False,
            )
        ]
    ].copy()
    if pair_candidate.empty:
        raise ValueError("no L8 outcomes found for WEAK_RESULT_ONLY")

    candidate_map = {
        (row.symbol, row.session): (
            str(row.cohort),
            str(row.trend_direction),
            int(row.bar_index),
        )
        for row in candidate.itertuples(index=False)
    }
    if len(candidate_map) != len(candidate):
        raise ValueError("WEAK_RESULT_ONLY identities are not unique")
    if pair_candidate[
        [
            "symbol",
            "target_session",
            "cohort",
            "horizon_sessions",
        ]
    ].duplicated().any():
        raise ValueError("candidate pair-outcome identities are not unique")
    for row in pair_candidate.itertuples(index=False):
        identity = (row.symbol, row.target_session)
        expected = candidate_map.get(identity)
        if expected is None:
            raise ValueError("candidate pair contains an unknown target")
        cohort, direction, bar_index = expected
        if str(row.cohort) != cohort:
            raise ValueError("candidate pair cohort drift")
        if str(row.trend_direction) != direction:
            raise ValueError("candidate pair trend-direction drift")
        if int(row.target_bar_index) != bar_index:
            raise ValueError("candidate pair bar-index drift")

    pair_candidate["positive_delta"] = (
        pair_candidate["target_positive_close"].astype(float)
        - pair_candidate["control_positive_close"].astype(float)
    )
    pair_target_ids = set(
        zip(
            pair_candidate["symbol"],
            pair_candidate["target_session"],
            strict=False,
        )
    )
    if pair_target_ids != candidate_ids:
        missing = sorted(candidate_ids - pair_target_ids)
        raise ValueError(
            "WEAK_RESULT_ONLY target missing from L8 pair ledger: "
            f"{missing[:5]}"
        )

    lineage = NoSupplyWeakResultSourceLineage(
        l9_audit_id=str(l9_summary["audit_id"]),
        l9_summary_sha256=_sha256_file(l9_summary_path),
        l9_targets_sha256=_sha256_file(l9_targets_path),
        l9_stratum_counts_sha256=_sha256_file(l9_counts_path),
        l9_stratum_outcomes_sha256=_sha256_file(l9_outcomes_path),
        l9_stratum_symbol_outcomes_sha256=_sha256_file(l9_symbol_path),
        l8_audit_id=str(l8_summary["audit_id"]),
        l8_summary_sha256=l8_summary_sha256,
        l8_pair_outcomes_sha256=l8_pair_sha256,
        l6_observations_sha256=str(
            l9_lineage["l6_observations_sha256"]
        ),
        snapshot_manifest_sha256=str(
            l9_lineage["snapshot_manifest_sha256"]
        ),
    )
    return NoSupplyWeakResultSources(
        lineage=lineage,
        targets=candidate.reset_index(drop=True),
        pair_outcomes=pair_candidate.reset_index(drop=True),
        current_target_count=current_count,
        alternate_target_count=alternate_count,
    )


def build_semantic_rows() -> tuple[NoSupplyWeakResultSemanticRow, ...]:
    rows: list[NoSupplyWeakResultSemanticRow] = []
    expected_weak = {
        ClosePosition.ON_LOW,
        ClosePosition.LOWER,
    }
    for position in ClosePosition:
        probe = SimpleNamespace(close_position=position)
        result = bool(is_weak_close(probe))
        if result != (position in expected_weak):
            raise RuntimeError("is_weak_close semantics changed")
        rows.append(
            NoSupplyWeakResultSemanticRow(
                semantic_dimension="WEAK_CLOSE_POSITION",
                input_state=position.name,
                predicate_result=result,
                interpretation=(
                    "passes is_weak_close"
                    if result
                    else "fails is_weak_close"
                ),
            )
        )

    previous = SimpleNamespace(volume=100.0)
    for current_volume, label in (
        (90.0, "CURRENT_LT_PREVIOUS"),
        (100.0, "CURRENT_EQ_PREVIOUS"),
        (110.0, "CURRENT_GT_PREVIOUS"),
    ):
        current = SimpleNamespace(volume=current_volume)
        decreasing = bool(volume_decreasing(current, previous))
        rows.append(
            NoSupplyWeakResultSemanticRow(
                semantic_dimension="VOLUME_RELATION",
                input_state=label,
                predicate_result=not decreasing,
                interpretation=(
                    "passes NOT volume_decreasing"
                    if not decreasing
                    else "fails NOT volume_decreasing"
                ),
            )
        )

    if not all(
        row.predicate_result
        for row in rows
        if row.semantic_dimension == "VOLUME_RELATION"
        and row.input_state in {
            "CURRENT_EQ_PREVIOUS",
            "CURRENT_GT_PREVIOUS",
        }
    ):
        raise RuntimeError("NOT volume_decreasing semantic contract changed")

    return tuple(rows)


def _metric_arrays_by_symbol(
    clean: pd.DataFrame,
    metric: str,
) -> tuple[tuple[str, ...], np.ndarray, np.ndarray, np.ndarray]:
    if metric not in METRIC_COLUMN:
        raise ValueError(f"unknown metric {metric}")
    column = METRIC_COLUMN[metric]
    grouped = clean.groupby("symbol", sort=True)[column]
    symbols = tuple(str(symbol) for symbol in grouped.groups)
    if not symbols:
        raise ValueError("cluster bootstrap requires at least one symbol")

    sums = np.asarray(
        [float(grouped.get_group(symbol).sum()) for symbol in symbols],
        dtype=float,
    )
    counts = np.asarray(
        [len(grouped.get_group(symbol)) for symbol in symbols],
        dtype=float,
    )
    means = sums / counts
    return symbols, sums, counts, means


def _bootstrap_distribution(
    *,
    sums: np.ndarray,
    counts: np.ndarray,
    means: np.ndarray,
    draws: np.ndarray,
    estimand: str,
) -> np.ndarray:
    if estimand == ESTIMAND_EVENT_WEIGHTED:
        sampled_sums = sums[draws].sum(axis=1)
        sampled_counts = counts[draws].sum(axis=1)
        return sampled_sums / sampled_counts
    if estimand == ESTIMAND_SYMBOL_NORMALIZED:
        return means[draws].mean(axis=1)
    raise ValueError(f"unknown estimand {estimand}")


def _observed_value(
    *,
    sums: np.ndarray,
    counts: np.ndarray,
    means: np.ndarray,
    estimand: str,
) -> float:
    if estimand == ESTIMAND_EVENT_WEIGHTED:
        return float(sums.sum() / counts.sum())
    if estimand == ESTIMAND_SYMBOL_NORMALIZED:
        return float(means.mean())
    raise ValueError(f"unknown estimand {estimand}")


def build_bootstrap_rows(
    pair_outcomes: pd.DataFrame,
    *,
    horizons: Sequence[int] | Iterable[int] = DEFAULT_FORWARD_HORIZONS,
    iterations: int = DEFAULT_CLUSTER_BOOTSTRAP_ITERATIONS,
    seed: int = DEFAULT_CLUSTER_BOOTSTRAP_SEED,
) -> tuple[NoSupplyWeakResultBootstrapRow, ...]:
    selected_horizons = normalize_forward_horizons(horizons)
    if iterations < 100:
        raise ValueError("bootstrap iterations must be at least 100")

    rows: list[NoSupplyWeakResultBootstrapRow] = []
    rng = np.random.default_rng(seed)

    for cohort in (COHORT_CURRENT, COHORT_ALTERNATE):
        for horizon in selected_horizons:
            clean = pair_outcomes.loc[
                (pair_outcomes["cohort"] == cohort)
                & (pair_outcomes["horizon_sessions"] == horizon)
                & pair_outcomes["clean_pair"]
            ].copy()
            if clean.empty:
                raise ValueError(
                    f"no clean candidate pairs for {cohort}/{horizon}"
                )
            clean_symbols = tuple(sorted(clean["symbol"].unique()))
            if len(clean_symbols) != 30:
                raise ValueError(
                    f"{cohort}/{horizon} must retain all 30 symbols"
                )
            draws = rng.integers(
                0,
                len(clean_symbols),
                size=(iterations, len(clean_symbols)),
            )

            for metric in BOOTSTRAP_METRICS:
                symbols, sums, counts, means = _metric_arrays_by_symbol(
                    clean,
                    metric,
                )
                if symbols != clean_symbols:
                    raise RuntimeError("symbol ordering drift in bootstrap")
                for estimand in BOOTSTRAP_ESTIMANDS:
                    observed = _observed_value(
                        sums=sums,
                        counts=counts,
                        means=means,
                        estimand=estimand,
                    )
                    distribution = _bootstrap_distribution(
                        sums=sums,
                        counts=counts,
                        means=means,
                        draws=draws,
                        estimand=estimand,
                    )
                    lower, upper = np.quantile(
                        distribution,
                        [0.025, 0.975],
                    )
                    rows.append(
                        NoSupplyWeakResultBootstrapRow(
                            cohort=cohort,
                            horizon_sessions=horizon,
                            metric=metric,
                            estimand=estimand,
                            clean_pair_count=len(clean),
                            symbol_count=len(symbols),
                            observed_value=observed,
                            bootstrap_mean=float(distribution.mean()),
                            ci_lower_95=float(lower),
                            ci_upper_95=float(upper),
                            bootstrap_fraction_gt_zero=float(
                                (distribution > 0.0).mean()
                            ),
                            bootstrap_fraction_lt_zero=float(
                                (distribution < 0.0).mean()
                            ),
                            bootstrap_iterations=iterations,
                            bootstrap_seed=seed,
                            ci_excludes_zero=(
                                float(lower) > 0.0
                                or float(upper) < 0.0
                            ),
                        )
                    )

    return tuple(rows)


def build_robustness_rows(
    pair_outcomes: pd.DataFrame,
    *,
    horizons: Sequence[int] | Iterable[int] = DEFAULT_FORWARD_HORIZONS,
) -> tuple[NoSupplyWeakResultRobustnessRow, ...]:
    selected_horizons = normalize_forward_horizons(horizons)
    rows: list[NoSupplyWeakResultRobustnessRow] = []

    for cohort in (COHORT_CURRENT, COHORT_ALTERNATE):
        source_targets = int(
            pair_outcomes.loc[
                pair_outcomes["cohort"] == cohort,
                ["symbol", "target_session"],
            ]
            .drop_duplicates()
            .shape[0]
        )
        for horizon in selected_horizons:
            selected = pair_outcomes.loc[
                (pair_outcomes["cohort"] == cohort)
                & (pair_outcomes["horizon_sessions"] == horizon)
            ].copy()
            clean = selected.loc[selected["clean_pair"]].copy()
            if clean.empty:
                raise ValueError(
                    f"no clean robustness rows for {cohort}/{horizon}"
                )
            symbol_frame = clean.groupby("symbol", sort=True).agg(
                return_delta=("paired_return_delta_pct", "mean"),
                positive_delta=("positive_delta", "mean"),
                mfe_delta=("paired_mfe_delta_pct", "mean"),
                mae_delta=("paired_mae_delta_pct", "mean"),
            )
            rows.append(
                NoSupplyWeakResultRobustnessRow(
                    cohort=cohort,
                    horizon_sessions=horizon,
                    source_target_count=source_targets,
                    pair_count=len(selected),
                    clean_pair_count=len(clean),
                    symbol_count=int(selected["symbol"].nunique()),
                    clean_symbol_count=int(clean["symbol"].nunique()),
                    event_weighted_return_delta_pct=float(
                        clean["paired_return_delta_pct"].mean()
                    ),
                    symbol_normalized_return_delta_pct=float(
                        symbol_frame["return_delta"].mean()
                    ),
                    event_weighted_positive_close_rate_delta=float(
                        clean["positive_delta"].mean()
                    ),
                    symbol_normalized_positive_close_rate_delta=float(
                        symbol_frame["positive_delta"].mean()
                    ),
                    event_weighted_mfe_delta_pct=float(
                        clean["paired_mfe_delta_pct"].mean()
                    ),
                    symbol_normalized_mfe_delta_pct=float(
                        symbol_frame["mfe_delta"].mean()
                    ),
                    event_weighted_mae_delta_pct=float(
                        clean["paired_mae_delta_pct"].mean()
                    ),
                    symbol_normalized_mae_delta_pct=float(
                        symbol_frame["mae_delta"].mean()
                    ),
                    positive_return_symbol_count=int(
                        (symbol_frame["return_delta"] > 0.0).sum()
                    ),
                    negative_return_symbol_count=int(
                        (symbol_frame["return_delta"] < 0.0).sum()
                    ),
                    zero_return_symbol_count=int(
                        (symbol_frame["return_delta"] == 0.0).sum()
                    ),
                )
            )
    return tuple(rows)


def build_leave_one_out_rows(
    pair_outcomes: pd.DataFrame,
    *,
    horizons: Sequence[int] | Iterable[int] = DEFAULT_FORWARD_HORIZONS,
) -> tuple[NoSupplyWeakResultLeaveOneOutRow, ...]:
    selected_horizons = normalize_forward_horizons(horizons)
    rows: list[NoSupplyWeakResultLeaveOneOutRow] = []

    for cohort in (COHORT_CURRENT, COHORT_ALTERNATE):
        for horizon in selected_horizons:
            clean = pair_outcomes.loc[
                (pair_outcomes["cohort"] == cohort)
                & (pair_outcomes["horizon_sessions"] == horizon)
                & pair_outcomes["clean_pair"]
            ].copy()
            symbols, sums, counts, means = _metric_arrays_by_symbol(
                clean,
                METRIC_RETURN,
            )
            total_sum = sums.sum()
            total_count = counts.sum()

            for estimand in BOOTSTRAP_ESTIMANDS:
                full = _observed_value(
                    sums=sums,
                    counts=counts,
                    means=means,
                    estimand=estimand,
                )
                leave_values: list[float] = []
                for index in range(len(symbols)):
                    if estimand == ESTIMAND_EVENT_WEIGHTED:
                        value = float(
                            (total_sum - sums[index])
                            / (total_count - counts[index])
                        )
                    else:
                        value = float(np.delete(means, index).mean())
                    leave_values.append(value)

                values = np.asarray(leave_values, dtype=float)
                min_index = int(values.argmin())
                max_index = int(values.argmax())
                shifts = np.abs(values - full)
                shift_index = int(shifts.argmax())
                rows.append(
                    NoSupplyWeakResultLeaveOneOutRow(
                        cohort=cohort,
                        horizon_sessions=horizon,
                        estimand=estimand,
                        full_return_delta_pct=full,
                        min_leave_one_out_return_delta_pct=float(
                            values[min_index]
                        ),
                        min_leave_one_out_symbol=symbols[min_index],
                        max_leave_one_out_return_delta_pct=float(
                            values[max_index]
                        ),
                        max_leave_one_out_symbol=symbols[max_index],
                        max_absolute_shift_pct=float(
                            shifts[shift_index]
                        ),
                        max_absolute_shift_symbol=symbols[shift_index],
                        positive_leave_one_out_count=int(
                            (values > 0.0).sum()
                        ),
                        negative_leave_one_out_count=int(
                            (values < 0.0).sum()
                        ),
                        zero_leave_one_out_count=int(
                            (values == 0.0).sum()
                        ),
                        symbol_count=len(symbols),
                    )
                )

    return tuple(rows)


def build_no_supply_weak_result_robustness_audit(
    *,
    sources: NoSupplyWeakResultSources,
    horizons: Sequence[int] | Iterable[int] = DEFAULT_FORWARD_HORIZONS,
    bootstrap_iterations: int = DEFAULT_CLUSTER_BOOTSTRAP_ITERATIONS,
    bootstrap_seed: int = DEFAULT_CLUSTER_BOOTSTRAP_SEED,
) -> NoSupplyWeakResultRobustnessAudit:
    selected_horizons = normalize_forward_horizons(horizons)
    robustness_rows = build_robustness_rows(
        sources.pair_outcomes,
        horizons=selected_horizons,
    )
    bootstrap_rows = build_bootstrap_rows(
        sources.pair_outcomes,
        horizons=selected_horizons,
        iterations=bootstrap_iterations,
        seed=bootstrap_seed,
    )
    leave_one_out_rows = build_leave_one_out_rows(
        sources.pair_outcomes,
        horizons=selected_horizons,
    )
    semantic_rows = build_semantic_rows()

    expected_bootstrap_rows = (
        2
        * len(selected_horizons)
        * len(BOOTSTRAP_METRICS)
        * len(BOOTSTRAP_ESTIMANDS)
    )
    if len(bootstrap_rows) != expected_bootstrap_rows:
        raise RuntimeError("bootstrap row count does not reconcile")
    expected_loo_rows = (
        2 * len(selected_horizons) * len(BOOTSTRAP_ESTIMANDS)
    )
    if len(leave_one_out_rows) != expected_loo_rows:
        raise RuntimeError("leave-one-out row count does not reconcile")

    return NoSupplyWeakResultRobustnessAudit(
        audit_id=DAILY_NO_SUPPLY_WEAK_RESULT_ROBUSTNESS_AUDIT_ID,
        source_lineage=sources.lineage,
        requested_symbol_count=int(sources.targets["symbol"].nunique()),
        candidate_target_count=len(sources.targets),
        current_candidate_target_count=sources.current_target_count,
        alternate_candidate_target_count=sources.alternate_target_count,
        horizon_count=len(selected_horizons),
        horizons=selected_horizons,
        bootstrap_iterations=bootstrap_iterations,
        bootstrap_seed=bootstrap_seed,
        robustness_rows=robustness_rows,
        bootstrap_rows=bootstrap_rows,
        leave_one_out_rows=leave_one_out_rows,
        semantic_rows=semantic_rows,
    )


def write_no_supply_weak_result_robustness_audit(
    audit: NoSupplyWeakResultRobustnessAudit,
    candidate_targets: pd.DataFrame,
    output_dir: str | Path,
) -> NoSupplyWeakResultRobustnessPaths:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    paths = NoSupplyWeakResultRobustnessPaths(
        summary_json=root / "daily_no_supply_weak_result_robustness_summary.json",
        candidate_targets_csv=(
            root / "daily_no_supply_weak_result_candidate_targets.csv"
        ),
        robustness_csv=(
            root / "daily_no_supply_weak_result_robustness.csv"
        ),
        bootstrap_csv=(
            root / "daily_no_supply_weak_result_cluster_bootstrap.csv"
        ),
        leave_one_out_csv=(
            root / "daily_no_supply_weak_result_leave_one_symbol_out.csv"
        ),
        semantics_csv=(
            root / "daily_no_supply_weak_result_semantics.csv"
        ),
    )

    summary = {
        "audit_id": audit.audit_id,
        "requested_symbol_count": audit.requested_symbol_count,
        "candidate_target_count": audit.candidate_target_count,
        "current_candidate_target_count": (
            audit.current_candidate_target_count
        ),
        "alternate_candidate_target_count": (
            audit.alternate_candidate_target_count
        ),
        "horizon_count": audit.horizon_count,
        "horizons": list(audit.horizons),
        "bootstrap_iterations": audit.bootstrap_iterations,
        "bootstrap_seed": audit.bootstrap_seed,
        "robustness_row_count": len(audit.robustness_rows),
        "bootstrap_row_count": len(audit.bootstrap_rows),
        "leave_one_out_row_count": len(audit.leave_one_out_rows),
        "semantic_row_count": len(audit.semantic_rows),
        "candidate_predicate": (
            "is_weak_close(bar) AND "
            "NOT volume_decreasing(bar, previous)"
        ),
        "weak_close_positions": ["ON_LOW", "LOWER"],
        "not_volume_decreasing_relation": (
            "current.volume >= previous.volume"
        ),
        "low_volume_remains_mandatory": True,
        "source_lineage": asdict(audit.source_lineage),
        "is_actionable": False,
    }
    paths.summary_json.write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    candidate_targets.to_csv(paths.candidate_targets_csv, index=False)
    pd.DataFrame(
        [asdict(item) for item in audit.robustness_rows]
    ).to_csv(paths.robustness_csv, index=False)
    pd.DataFrame(
        [asdict(item) for item in audit.bootstrap_rows]
    ).to_csv(paths.bootstrap_csv, index=False)
    pd.DataFrame(
        [asdict(item) for item in audit.leave_one_out_rows]
    ).to_csv(paths.leave_one_out_csv, index=False)
    pd.DataFrame(
        [asdict(item) for item in audit.semantic_rows]
    ).to_csv(paths.semantics_csv, index=False)
    return paths


__all__ = [
    "BOOTSTRAP_ESTIMANDS",
    "BOOTSTRAP_METRICS",
    "DAILY_NO_SUPPLY_WEAK_RESULT_ROBUSTNESS_AUDIT_ID",
    "DEFAULT_CLUSTER_BOOTSTRAP_ITERATIONS",
    "DEFAULT_CLUSTER_BOOTSTRAP_SEED",
    "ESTIMAND_EVENT_WEIGHTED",
    "ESTIMAND_SYMBOL_NORMALIZED",
    "METRIC_MAE",
    "METRIC_MFE",
    "METRIC_POSITIVE_CLOSE",
    "METRIC_RETURN",
    "NoSupplyWeakResultBootstrapRow",
    "NoSupplyWeakResultLeaveOneOutRow",
    "NoSupplyWeakResultRobustnessAudit",
    "NoSupplyWeakResultRobustnessPaths",
    "NoSupplyWeakResultRobustnessRow",
    "NoSupplyWeakResultSemanticRow",
    "NoSupplyWeakResultSourceLineage",
    "NoSupplyWeakResultSources",
    "build_bootstrap_rows",
    "build_leave_one_out_rows",
    "build_no_supply_weak_result_robustness_audit",
    "build_robustness_rows",
    "build_semantic_rows",
    "load_no_supply_weak_result_sources",
    "write_no_supply_weak_result_robustness_audit",
]
