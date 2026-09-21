"""Temporal stability audit for NO_SUPPLY WEAK_RESULT_ONLY.

L11 reuses the fixed L10 candidate population and L8 matched pair outcomes.
It partitions target sessions into predetermined calendar eras and evaluates
whether paired behavior is stable across time and after removing each era.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd

from audit.daily_event_no_supply_forward_outcomes import (
    COHORT_ALTERNATE,
    COHORT_CURRENT,
    DEFAULT_FORWARD_HORIZONS,
    normalize_forward_horizons,
)
from audit.daily_event_no_supply_matched_environment import (
    DAILY_NO_SUPPLY_MATCHED_ENVIRONMENT_AUDIT_ID,
)
from audit.daily_event_no_supply_weak_result_robustness import (
    DAILY_NO_SUPPLY_WEAK_RESULT_ROBUSTNESS_AUDIT_ID,
    ESTIMAND_EVENT_WEIGHTED,
    ESTIMAND_SYMBOL_NORMALIZED,
    METRIC_MAE,
    METRIC_MFE,
    METRIC_POSITIVE_CLOSE,
    METRIC_RETURN,
)


DAILY_NO_SUPPLY_TEMPORAL_STABILITY_AUDIT_ID = (
    "daily-event-no-supply-temporal-stability-v1"
)

ERA_EARLY = "EARLY_HISTORY"
ERA_2010_2014 = "2010_2014"
ERA_2015_2019 = "2015_2019"
ERA_2020_2022 = "2020_2022"
ERA_2023_2026 = "2023_2026"
ERA_ORDER = (
    ERA_EARLY,
    ERA_2010_2014,
    ERA_2015_2019,
    ERA_2020_2022,
    ERA_2023_2026,
)

METRICS = (
    METRIC_RETURN,
    METRIC_POSITIVE_CLOSE,
    METRIC_MFE,
    METRIC_MAE,
)
ESTIMANDS = (
    ESTIMAND_EVENT_WEIGHTED,
    ESTIMAND_SYMBOL_NORMALIZED,
)


@dataclass(frozen=True, slots=True)
class NoSupplyTemporalSourceLineage:
    l10_audit_id: str
    l10_summary_sha256: str
    l10_candidate_targets_sha256: str
    l10_robustness_sha256: str
    l10_bootstrap_sha256: str
    l10_leave_one_out_sha256: str
    l10_semantics_sha256: str
    l8_audit_id: str
    l8_summary_sha256: str
    l8_pair_outcomes_sha256: str
    snapshot_manifest_sha256: str


@dataclass(frozen=True, slots=True)
class NoSupplyTemporalSources:
    lineage: NoSupplyTemporalSourceLineage
    targets: pd.DataFrame
    pair_outcomes: pd.DataFrame
    current_target_count: int
    alternate_target_count: int


@dataclass(frozen=True, slots=True)
class NoSupplyTemporalEraDefinition:
    era: str
    start_year: int | None
    end_year: int | None
    interpretation: str


@dataclass(frozen=True, slots=True)
class NoSupplyTemporalEraCountRow:
    era: str
    cohort: str
    source_target_count: int
    symbol_count: int
    first_session: str
    last_session: str


@dataclass(frozen=True, slots=True)
class NoSupplyTemporalEraOutcomeRow:
    era: str
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
class NoSupplyTemporalConsistencyRow:
    cohort: str
    horizon_sessions: int
    metric: str
    estimand: str
    available_era_count: int
    positive_era_count: int
    negative_era_count: int
    zero_era_count: int
    min_era_value: float
    min_era: str
    max_era_value: float
    max_era: str


@dataclass(frozen=True, slots=True)
class NoSupplyTemporalLeaveOneEraOutRow:
    cohort: str
    horizon_sessions: int
    estimand: str
    omitted_era: str
    full_return_delta_pct: float
    leave_one_era_out_return_delta_pct: float
    shift_from_full_pct: float
    remaining_clean_pair_count: int
    remaining_symbol_count: int
    remains_positive: bool


@dataclass(frozen=True, slots=True)
class NoSupplyTemporalStabilityAudit:
    audit_id: str
    source_lineage: NoSupplyTemporalSourceLineage
    requested_symbol_count: int
    candidate_target_count: int
    current_candidate_target_count: int
    alternate_candidate_target_count: int
    era_count: int
    horizon_count: int
    horizons: tuple[int, ...]
    era_definitions: tuple[NoSupplyTemporalEraDefinition, ...]
    era_count_rows: tuple[NoSupplyTemporalEraCountRow, ...]
    era_outcome_rows: tuple[NoSupplyTemporalEraOutcomeRow, ...]
    consistency_rows: tuple[NoSupplyTemporalConsistencyRow, ...]
    leave_one_era_out_rows: tuple[NoSupplyTemporalLeaveOneEraOutRow, ...]

    @property
    def is_actionable(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class NoSupplyTemporalStabilityPaths:
    summary_json: Path
    candidate_targets_csv: Path
    era_definitions_csv: Path
    era_counts_csv: Path
    era_outcomes_csv: Path
    consistency_csv: Path
    leave_one_era_out_csv: Path

    def as_dict(self) -> dict[str, str]:
        return {
            "summary_json": str(self.summary_json),
            "candidate_targets_csv": str(self.candidate_targets_csv),
            "era_definitions_csv": str(self.era_definitions_csv),
            "era_counts_csv": str(self.era_counts_csv),
            "era_outcomes_csv": str(self.era_outcomes_csv),
            "consistency_csv": str(self.consistency_csv),
            "leave_one_era_out_csv": str(self.leave_one_era_out_csv),
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


def era_for_session(value: object) -> str:
    year = pd.Timestamp(value).year
    if year <= 2009:
        return ERA_EARLY
    if year <= 2014:
        return ERA_2010_2014
    if year <= 2019:
        return ERA_2015_2019
    if year <= 2022:
        return ERA_2020_2022
    if year <= 2026:
        return ERA_2023_2026
    raise ValueError(f"session year is outside canonical audit range: {year}")


def canonical_era_definitions() -> tuple[NoSupplyTemporalEraDefinition, ...]:
    return (
        NoSupplyTemporalEraDefinition(
            era=ERA_EARLY,
            start_year=None,
            end_year=2009,
            interpretation="all candidate history through 2009",
        ),
        NoSupplyTemporalEraDefinition(
            era=ERA_2010_2014,
            start_year=2010,
            end_year=2014,
            interpretation="fixed calendar years 2010-2014",
        ),
        NoSupplyTemporalEraDefinition(
            era=ERA_2015_2019,
            start_year=2015,
            end_year=2019,
            interpretation="fixed calendar years 2015-2019",
        ),
        NoSupplyTemporalEraDefinition(
            era=ERA_2020_2022,
            start_year=2020,
            end_year=2022,
            interpretation="fixed calendar years 2020-2022",
        ),
        NoSupplyTemporalEraDefinition(
            era=ERA_2023_2026,
            start_year=2023,
            end_year=2026,
            interpretation="fixed calendar years 2023-2026",
        ),
    )


def _validate_l10_summary(summary: dict[str, object]) -> None:
    if (
        summary.get("audit_id")
        != DAILY_NO_SUPPLY_WEAK_RESULT_ROBUSTNESS_AUDIT_ID
    ):
        raise ValueError("unexpected L10 audit_id")
    if summary.get("is_actionable") is not False:
        raise ValueError("L11 requires non-actionable L10 source")
    expected = {
        "requested_symbol_count": 30,
        "candidate_target_count": 427,
        "current_candidate_target_count": 122,
        "alternate_candidate_target_count": 305,
        "robustness_row_count": 10,
        "bootstrap_row_count": 80,
        "leave_one_out_row_count": 20,
        "semantic_row_count": 8,
    }
    for key, value in expected.items():
        if int(summary.get(key, -1)) != value:
            raise ValueError(f"unexpected canonical L10 {key}")


def load_no_supply_temporal_sources(
    *,
    robustness_dir: str | Path,
    matched_dir: str | Path,
) -> NoSupplyTemporalSources:
    robustness_root = Path(robustness_dir)
    matched_root = Path(matched_dir)

    l10_summary_path = (
        robustness_root / "daily_no_supply_weak_result_robustness_summary.json"
    )
    l10_targets_path = (
        robustness_root / "daily_no_supply_weak_result_candidate_targets.csv"
    )
    l10_robustness_path = (
        robustness_root / "daily_no_supply_weak_result_robustness.csv"
    )
    l10_bootstrap_path = (
        robustness_root / "daily_no_supply_weak_result_cluster_bootstrap.csv"
    )
    l10_loo_path = (
        robustness_root / "daily_no_supply_weak_result_leave_one_symbol_out.csv"
    )
    l10_semantics_path = (
        robustness_root / "daily_no_supply_weak_result_semantics.csv"
    )
    l8_summary_path = matched_root / "daily_no_supply_matched_summary.json"
    l8_pair_path = matched_root / "daily_no_supply_matched_pair_outcomes.csv"

    for path in (
        l10_summary_path,
        l10_targets_path,
        l10_robustness_path,
        l10_bootstrap_path,
        l10_loo_path,
        l10_semantics_path,
        l8_summary_path,
        l8_pair_path,
    ):
        if not path.exists():
            raise FileNotFoundError(path)

    l10_summary = json.loads(l10_summary_path.read_text(encoding="utf-8"))
    _validate_l10_summary(l10_summary)
    l10_lineage = l10_summary.get("source_lineage")
    if not isinstance(l10_lineage, dict):
        raise ValueError("L10 source lineage is missing")

    l8_summary_sha256 = _sha256_file(l8_summary_path)
    l8_pair_sha256 = _sha256_file(l8_pair_path)
    if str(l10_lineage.get("l8_summary_sha256", "")) != l8_summary_sha256:
        raise ValueError("L10 points to a different L8 summary")
    if (
        str(l10_lineage.get("l8_pair_outcomes_sha256", ""))
        != l8_pair_sha256
    ):
        raise ValueError("L10 points to a different L8 pair ledger")

    l8_summary = json.loads(l8_summary_path.read_text(encoding="utf-8"))
    if (
        l8_summary.get("audit_id")
        != DAILY_NO_SUPPLY_MATCHED_ENVIRONMENT_AUDIT_ID
    ):
        raise ValueError("unexpected L8 audit_id")
    if int(l8_summary.get("matched_target_count", -1)) != 2509:
        raise ValueError("L11 requires canonical fully matched L8")

    targets = pd.read_csv(l10_targets_path)
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
        raise ValueError(f"L10 targets missing columns: {missing_targets}")
    targets = targets.copy()
    targets["symbol"] = targets["symbol"].map(
        lambda value: str(value).strip().upper()
    )
    targets["session"] = targets["session"].map(_normalize_session)
    targets["volume_decreasing"] = targets["volume_decreasing"].map(
        _parse_bool
    )
    targets["weak_selling_result"] = targets[
        "weak_selling_result"
    ].map(_parse_bool)
    if not (targets["stratum"] == "WEAK_RESULT_ONLY").all():
        raise ValueError("L10 candidate stratum drifted")
    if not (
        (~targets["volume_decreasing"])
        & targets["weak_selling_result"]
    ).all():
        raise ValueError("L10 candidate predicate semantics drifted")
    targets["era"] = targets["session"].map(era_for_session)
    if len(targets) != 427:
        raise ValueError("canonical L10 candidate count changed")
    if targets[["symbol", "session"]].duplicated().any():
        raise ValueError("L10 candidate identities are not unique")
    if int(targets["symbol"].nunique()) != 30:
        raise ValueError("L10 candidates must span 30 symbols")

    current_count = int((targets["cohort"] == COHORT_CURRENT).sum())
    alternate_count = int((targets["cohort"] == COHORT_ALTERNATE).sum())
    if current_count != 122 or alternate_count != 305:
        raise ValueError("canonical L10 cohort counts changed")

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

    candidate_map = {
        (row.symbol, row.session): (
            str(row.cohort),
            str(row.trend_direction),
            int(row.bar_index),
            str(row.era),
        )
        for row in targets.itertuples(index=False)
    }
    candidate_ids = set(candidate_map)
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
    pair_candidate["era"] = pair_candidate["target_session"].map(
        era_for_session
    )
    pair_candidate["positive_delta"] = (
        pair_candidate["target_positive_close"].astype(float)
        - pair_candidate["control_positive_close"].astype(float)
    )

    if pair_candidate[
        ["symbol", "target_session", "cohort", "horizon_sessions"]
    ].duplicated().any():
        raise ValueError("L11 candidate pair identities are not unique")

    pair_target_ids = set(
        zip(
            pair_candidate["symbol"],
            pair_candidate["target_session"],
            strict=False,
        )
    )
    if pair_target_ids != candidate_ids:
        raise ValueError("L11 candidate coverage does not equal L10 source")

    for row in pair_candidate.itertuples(index=False):
        expected = candidate_map[(row.symbol, row.target_session)]
        cohort, direction, bar_index, era = expected
        if str(row.cohort) != cohort:
            raise ValueError("L11 pair cohort drift")
        if str(row.trend_direction) != direction:
            raise ValueError("L11 pair trend-direction drift")
        if int(row.target_bar_index) != bar_index:
            raise ValueError("L11 pair bar-index drift")
        if str(row.era) != era:
            raise ValueError("L11 era assignment drift")

    lineage = NoSupplyTemporalSourceLineage(
        l10_audit_id=str(l10_summary["audit_id"]),
        l10_summary_sha256=_sha256_file(l10_summary_path),
        l10_candidate_targets_sha256=_sha256_file(l10_targets_path),
        l10_robustness_sha256=_sha256_file(l10_robustness_path),
        l10_bootstrap_sha256=_sha256_file(l10_bootstrap_path),
        l10_leave_one_out_sha256=_sha256_file(l10_loo_path),
        l10_semantics_sha256=_sha256_file(l10_semantics_path),
        l8_audit_id=str(l8_summary["audit_id"]),
        l8_summary_sha256=l8_summary_sha256,
        l8_pair_outcomes_sha256=l8_pair_sha256,
        snapshot_manifest_sha256=str(
            l10_lineage["snapshot_manifest_sha256"]
        ),
    )
    return NoSupplyTemporalSources(
        lineage=lineage,
        targets=targets.reset_index(drop=True),
        pair_outcomes=pair_candidate.reset_index(drop=True),
        current_target_count=current_count,
        alternate_target_count=alternate_count,
    )


def build_era_count_rows(
    targets: pd.DataFrame,
) -> tuple[NoSupplyTemporalEraCountRow, ...]:
    rows: list[NoSupplyTemporalEraCountRow] = []
    for era in ERA_ORDER:
        for cohort in (COHORT_CURRENT, COHORT_ALTERNATE):
            selected = targets.loc[
                (targets["era"] == era)
                & (targets["cohort"] == cohort)
            ]
            if selected.empty:
                rows.append(
                    NoSupplyTemporalEraCountRow(
                        era=era,
                        cohort=cohort,
                        source_target_count=0,
                        symbol_count=0,
                        first_session="",
                        last_session="",
                    )
                )
                continue
            rows.append(
                NoSupplyTemporalEraCountRow(
                    era=era,
                    cohort=cohort,
                    source_target_count=len(selected),
                    symbol_count=int(selected["symbol"].nunique()),
                    first_session=str(selected["session"].min()),
                    last_session=str(selected["session"].max()),
                )
            )
    return tuple(rows)


def _symbol_means(clean: pd.DataFrame) -> pd.DataFrame:
    return clean.groupby("symbol", sort=True).agg(
        return_delta=("paired_return_delta_pct", "mean"),
        positive_delta=("positive_delta", "mean"),
        mfe_delta=("paired_mfe_delta_pct", "mean"),
        mae_delta=("paired_mae_delta_pct", "mean"),
    )


def build_era_outcome_rows(
    *,
    targets: pd.DataFrame,
    pair_outcomes: pd.DataFrame,
    horizons: Sequence[int] | Iterable[int] = DEFAULT_FORWARD_HORIZONS,
) -> tuple[NoSupplyTemporalEraOutcomeRow, ...]:
    selected_horizons = normalize_forward_horizons(horizons)
    rows: list[NoSupplyTemporalEraOutcomeRow] = []

    for era in ERA_ORDER:
        for cohort in (COHORT_CURRENT, COHORT_ALTERNATE):
            target_count = len(
                targets.loc[
                    (targets["era"] == era)
                    & (targets["cohort"] == cohort)
                ]
            )
            if target_count == 0:
                continue
            for horizon in selected_horizons:
                selected = pair_outcomes.loc[
                    (pair_outcomes["era"] == era)
                    & (pair_outcomes["cohort"] == cohort)
                    & (pair_outcomes["horizon_sessions"] == horizon)
                ].copy()
                if selected.empty:
                    continue
                clean = selected.loc[selected["clean_pair"]].copy()
                if clean.empty:
                    continue
                symbol_frame = _symbol_means(clean)
                rows.append(
                    NoSupplyTemporalEraOutcomeRow(
                        era=era,
                        cohort=cohort,
                        horizon_sessions=horizon,
                        source_target_count=target_count,
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


def _era_metric_value(
    row: NoSupplyTemporalEraOutcomeRow,
    *,
    metric: str,
    estimand: str,
) -> float:
    prefix = (
        "event_weighted"
        if estimand == ESTIMAND_EVENT_WEIGHTED
        else "symbol_normalized"
    )
    suffix = {
        METRIC_RETURN: "return_delta_pct",
        METRIC_POSITIVE_CLOSE: "positive_close_rate_delta",
        METRIC_MFE: "mfe_delta_pct",
        METRIC_MAE: "mae_delta_pct",
    }[metric]
    return float(getattr(row, f"{prefix}_{suffix}"))


def build_temporal_consistency_rows(
    era_outcomes: Sequence[NoSupplyTemporalEraOutcomeRow],
    *,
    horizons: Sequence[int] | Iterable[int] = DEFAULT_FORWARD_HORIZONS,
) -> tuple[NoSupplyTemporalConsistencyRow, ...]:
    selected_horizons = normalize_forward_horizons(horizons)
    rows: list[NoSupplyTemporalConsistencyRow] = []

    for cohort in (COHORT_CURRENT, COHORT_ALTERNATE):
        for horizon in selected_horizons:
            subset = [
                item
                for item in era_outcomes
                if item.cohort == cohort
                and item.horizon_sessions == horizon
            ]
            if not subset:
                continue
            for metric in METRICS:
                for estimand in ESTIMANDS:
                    values = [
                        (
                            item.era,
                            _era_metric_value(
                                item,
                                metric=metric,
                                estimand=estimand,
                            ),
                        )
                        for item in subset
                    ]
                    min_era, min_value = min(
                        values,
                        key=lambda item: item[1],
                    )
                    max_era, max_value = max(
                        values,
                        key=lambda item: item[1],
                    )
                    rows.append(
                        NoSupplyTemporalConsistencyRow(
                            cohort=cohort,
                            horizon_sessions=horizon,
                            metric=metric,
                            estimand=estimand,
                            available_era_count=len(values),
                            positive_era_count=sum(
                                value > 0.0
                                for _, value in values
                            ),
                            negative_era_count=sum(
                                value < 0.0
                                for _, value in values
                            ),
                            zero_era_count=sum(
                                value == 0.0
                                for _, value in values
                            ),
                            min_era_value=float(min_value),
                            min_era=min_era,
                            max_era_value=float(max_value),
                            max_era=max_era,
                        )
                    )
    return tuple(rows)


def _return_estimand(
    clean: pd.DataFrame,
    estimand: str,
) -> float:
    if estimand == ESTIMAND_EVENT_WEIGHTED:
        return float(clean["paired_return_delta_pct"].mean())
    if estimand == ESTIMAND_SYMBOL_NORMALIZED:
        return float(
            clean.groupby("symbol")["paired_return_delta_pct"]
            .mean()
            .mean()
        )
    raise ValueError(f"unknown estimand {estimand}")


def build_leave_one_era_out_rows(
    pair_outcomes: pd.DataFrame,
    *,
    horizons: Sequence[int] | Iterable[int] = DEFAULT_FORWARD_HORIZONS,
) -> tuple[NoSupplyTemporalLeaveOneEraOutRow, ...]:
    selected_horizons = normalize_forward_horizons(horizons)
    rows: list[NoSupplyTemporalLeaveOneEraOutRow] = []

    for cohort in (COHORT_CURRENT, COHORT_ALTERNATE):
        for horizon in selected_horizons:
            clean = pair_outcomes.loc[
                (pair_outcomes["cohort"] == cohort)
                & (pair_outcomes["horizon_sessions"] == horizon)
                & pair_outcomes["clean_pair"]
            ].copy()
            if clean.empty:
                raise ValueError(
                    f"no clean pairs for {cohort}/{horizon}"
                )
            for estimand in ESTIMANDS:
                full = _return_estimand(clean, estimand)
                for omitted_era in ERA_ORDER:
                    remaining = clean.loc[
                        clean["era"] != omitted_era
                    ]
                    if remaining.empty:
                        raise ValueError(
                            "leave-one-era-out removed all observations"
                        )
                    value = _return_estimand(remaining, estimand)
                    rows.append(
                        NoSupplyTemporalLeaveOneEraOutRow(
                            cohort=cohort,
                            horizon_sessions=horizon,
                            estimand=estimand,
                            omitted_era=omitted_era,
                            full_return_delta_pct=full,
                            leave_one_era_out_return_delta_pct=value,
                            shift_from_full_pct=value - full,
                            remaining_clean_pair_count=len(remaining),
                            remaining_symbol_count=int(
                                remaining["symbol"].nunique()
                            ),
                            remains_positive=value > 0.0,
                        )
                    )
    return tuple(rows)


def build_no_supply_temporal_stability_audit(
    *,
    sources: NoSupplyTemporalSources,
    horizons: Sequence[int] | Iterable[int] = DEFAULT_FORWARD_HORIZONS,
) -> NoSupplyTemporalStabilityAudit:
    selected_horizons = normalize_forward_horizons(horizons)
    definitions = canonical_era_definitions()
    count_rows = build_era_count_rows(sources.targets)
    outcome_rows = build_era_outcome_rows(
        targets=sources.targets,
        pair_outcomes=sources.pair_outcomes,
        horizons=selected_horizons,
    )
    consistency_rows = build_temporal_consistency_rows(
        outcome_rows,
        horizons=selected_horizons,
    )
    loo_rows = build_leave_one_era_out_rows(
        sources.pair_outcomes,
        horizons=selected_horizons,
    )

    if len(count_rows) != 10:
        raise RuntimeError("L11 era count rows must equal 10")
    expected_consistency = (
        2 * len(selected_horizons) * len(METRICS) * len(ESTIMANDS)
    )
    if len(consistency_rows) != expected_consistency:
        raise RuntimeError("L11 temporal consistency rows do not reconcile")
    expected_loo = (
        2 * len(selected_horizons) * len(ESTIMANDS) * len(ERA_ORDER)
    )
    if len(loo_rows) != expected_loo:
        raise RuntimeError("L11 leave-one-era-out rows do not reconcile")

    return NoSupplyTemporalStabilityAudit(
        audit_id=DAILY_NO_SUPPLY_TEMPORAL_STABILITY_AUDIT_ID,
        source_lineage=sources.lineage,
        requested_symbol_count=int(sources.targets["symbol"].nunique()),
        candidate_target_count=len(sources.targets),
        current_candidate_target_count=sources.current_target_count,
        alternate_candidate_target_count=sources.alternate_target_count,
        era_count=len(ERA_ORDER),
        horizon_count=len(selected_horizons),
        horizons=selected_horizons,
        era_definitions=definitions,
        era_count_rows=count_rows,
        era_outcome_rows=outcome_rows,
        consistency_rows=consistency_rows,
        leave_one_era_out_rows=loo_rows,
    )


def write_no_supply_temporal_stability_audit(
    audit: NoSupplyTemporalStabilityAudit,
    candidate_targets: pd.DataFrame,
    output_dir: str | Path,
) -> NoSupplyTemporalStabilityPaths:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    paths = NoSupplyTemporalStabilityPaths(
        summary_json=root / "daily_no_supply_temporal_stability_summary.json",
        candidate_targets_csv=(
            root / "daily_no_supply_temporal_candidate_targets.csv"
        ),
        era_definitions_csv=(
            root / "daily_no_supply_temporal_era_definitions.csv"
        ),
        era_counts_csv=root / "daily_no_supply_temporal_era_counts.csv",
        era_outcomes_csv=root / "daily_no_supply_temporal_era_outcomes.csv",
        consistency_csv=(
            root / "daily_no_supply_temporal_consistency.csv"
        ),
        leave_one_era_out_csv=(
            root / "daily_no_supply_temporal_leave_one_era_out.csv"
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
        "era_count": audit.era_count,
        "eras": list(ERA_ORDER),
        "horizon_count": audit.horizon_count,
        "horizons": list(audit.horizons),
        "era_count_row_count": len(audit.era_count_rows),
        "era_outcome_row_count": len(audit.era_outcome_rows),
        "consistency_row_count": len(audit.consistency_rows),
        "leave_one_era_out_row_count": len(
            audit.leave_one_era_out_rows
        ),
        "source_lineage": asdict(audit.source_lineage),
        "is_actionable": False,
    }
    paths.summary_json.write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    candidate_targets.to_csv(paths.candidate_targets_csv, index=False)
    pd.DataFrame(
        [asdict(item) for item in audit.era_definitions]
    ).to_csv(paths.era_definitions_csv, index=False)
    pd.DataFrame(
        [asdict(item) for item in audit.era_count_rows]
    ).to_csv(paths.era_counts_csv, index=False)
    pd.DataFrame(
        [asdict(item) for item in audit.era_outcome_rows]
    ).to_csv(paths.era_outcomes_csv, index=False)
    pd.DataFrame(
        [asdict(item) for item in audit.consistency_rows]
    ).to_csv(paths.consistency_csv, index=False)
    pd.DataFrame(
        [asdict(item) for item in audit.leave_one_era_out_rows]
    ).to_csv(paths.leave_one_era_out_csv, index=False)
    return paths


__all__ = [
    "DAILY_NO_SUPPLY_TEMPORAL_STABILITY_AUDIT_ID",
    "ERA_ORDER",
    "NoSupplyTemporalConsistencyRow",
    "NoSupplyTemporalEraCountRow",
    "NoSupplyTemporalEraDefinition",
    "NoSupplyTemporalEraOutcomeRow",
    "NoSupplyTemporalLeaveOneEraOutRow",
    "NoSupplyTemporalSourceLineage",
    "NoSupplyTemporalSources",
    "NoSupplyTemporalStabilityAudit",
    "NoSupplyTemporalStabilityPaths",
    "build_era_count_rows",
    "build_era_outcome_rows",
    "build_leave_one_era_out_rows",
    "build_no_supply_temporal_stability_audit",
    "build_temporal_consistency_rows",
    "canonical_era_definitions",
    "era_for_session",
    "load_no_supply_temporal_sources",
    "write_no_supply_temporal_stability_audit",
]
