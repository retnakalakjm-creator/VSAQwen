"""Era x VolumeClass-relation interaction audit for ALTERNATE NO_SUPPLY.

L13 reuses the canonical L12 candidate-context ledger and canonical L8 matched
pair outcomes. It asks whether the 2023-2026 ALTERNATE failure is concentrated
in SAME_CLASS targets or is shared by HIGHER_CLASS targets.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd

from audit.daily_event_no_supply_alternate_context_profile import (
    DAILY_NO_SUPPLY_ALTERNATE_CONTEXT_PROFILE_AUDIT_ID,
    GROUP_LATEST,
    GROUP_PRIOR,
)
from audit.daily_event_no_supply_temporal_stability import (
    ERA_2023_2026,
    ERA_ORDER,
)


DAILY_NO_SUPPLY_RELATION_ERA_INTERACTION_AUDIT_ID = (
    "daily-event-no-supply-relation-era-interaction-v1"
)

RELATION_SAME_CLASS = "SAME_CLASS"
RELATION_HIGHER_CLASS = "HIGHER_CLASS"
RELATION_ORDER = (
    RELATION_SAME_CLASS,
    RELATION_HIGHER_CLASS,
)

DEFAULT_INTERACTION_HORIZONS = (1, 3, 5)

ESTIMAND_EVENT_WEIGHTED = "EVENT_WEIGHTED"
ESTIMAND_SYMBOL_NORMALIZED = "SYMBOL_NORMALIZED"
ESTIMANDS = (
    ESTIMAND_EVENT_WEIGHTED,
    ESTIMAND_SYMBOL_NORMALIZED,
)

METRIC_RETURN = "PAIRED_RETURN_DELTA_PCT"
METRIC_MFE = "PAIRED_MFE_DELTA_PCT"
METRICS = (
    METRIC_RETURN,
    METRIC_MFE,
)


@dataclass(frozen=True, slots=True)
class NoSupplyRelationEraSourceLineage:
    l12_audit_id: str
    l12_summary_sha256: str
    l12_contexts_sha256: str
    l12_continuous_shifts_sha256: str
    l12_categorical_shifts_sha256: str
    l12_context_outcomes_sha256: str
    l8_pair_outcomes_sha256: str
    snapshot_manifest_sha256: str


@dataclass(frozen=True, slots=True)
class NoSupplyRelationEraSources:
    lineage: NoSupplyRelationEraSourceLineage
    contexts: pd.DataFrame
    pair_outcomes: pd.DataFrame


@dataclass(frozen=True, slots=True)
class NoSupplyRelationEraCountRow:
    era: str
    volume_class_relation: str
    source_target_count: int
    symbol_count: int
    first_session: str
    last_session: str


@dataclass(frozen=True, slots=True)
class NoSupplyRelationEraOutcomeRow:
    era: str
    volume_class_relation: str
    horizon_sessions: int
    source_target_count: int
    clean_pair_count: int
    symbol_count: int
    event_weighted_return_delta_pct: float
    symbol_normalized_return_delta_pct: float
    event_weighted_mfe_delta_pct: float
    symbol_normalized_mfe_delta_pct: float


@dataclass(frozen=True, slots=True)
class NoSupplyRelationTemporalConsistencyRow:
    volume_class_relation: str
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
class NoSupplyRelationPriorLatestRow:
    volume_class_relation: str
    horizon_sessions: int
    prior_source_target_count: int
    latest_source_target_count: int
    prior_clean_pair_count: int
    latest_clean_pair_count: int
    prior_symbol_count: int
    latest_symbol_count: int
    prior_event_weighted_return_delta_pct: float
    latest_event_weighted_return_delta_pct: float
    latest_minus_prior_event_return_pct: float
    prior_symbol_normalized_return_delta_pct: float
    latest_symbol_normalized_return_delta_pct: float
    latest_minus_prior_symbol_return_pct: float
    prior_event_weighted_mfe_delta_pct: float
    latest_event_weighted_mfe_delta_pct: float
    latest_minus_prior_event_mfe_pct: float
    prior_symbol_normalized_mfe_delta_pct: float
    latest_symbol_normalized_mfe_delta_pct: float
    latest_minus_prior_symbol_mfe_pct: float


@dataclass(frozen=True, slots=True)
class NoSupplyRelationInteractionContrastRow:
    horizon_sessions: int
    metric: str
    estimand: str
    same_class_prior_value: float
    same_class_latest_value: float
    same_class_latest_minus_prior: float
    higher_class_prior_value: float
    higher_class_latest_value: float
    higher_class_latest_minus_prior: float
    same_minus_higher_change: float


@dataclass(frozen=True, slots=True)
class NoSupplyRelationEraInteractionAudit:
    audit_id: str
    source_lineage: NoSupplyRelationEraSourceLineage
    requested_symbol_count: int
    alternate_target_count: int
    same_class_target_count: int
    higher_class_target_count: int
    prior_same_class_target_count: int
    prior_higher_class_target_count: int
    latest_same_class_target_count: int
    latest_higher_class_target_count: int
    era_count: int
    relation_count: int
    horizon_count: int
    horizons: tuple[int, ...]
    count_rows: tuple[NoSupplyRelationEraCountRow, ...]
    outcome_rows: tuple[NoSupplyRelationEraOutcomeRow, ...]
    consistency_rows: tuple[NoSupplyRelationTemporalConsistencyRow, ...]
    prior_latest_rows: tuple[NoSupplyRelationPriorLatestRow, ...]
    interaction_rows: tuple[NoSupplyRelationInteractionContrastRow, ...]

    @property
    def is_actionable(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class NoSupplyRelationEraInteractionPaths:
    summary_json: Path
    era_relation_counts_csv: Path
    era_relation_outcomes_csv: Path
    relation_consistency_csv: Path
    prior_latest_csv: Path
    interaction_contrasts_csv: Path

    def as_dict(self) -> dict[str, str]:
        return {
            "summary_json": str(self.summary_json),
            "era_relation_counts_csv": str(self.era_relation_counts_csv),
            "era_relation_outcomes_csv": str(
                self.era_relation_outcomes_csv
            ),
            "relation_consistency_csv": str(self.relation_consistency_csv),
            "prior_latest_csv": str(self.prior_latest_csv),
            "interaction_contrasts_csv": str(
                self.interaction_contrasts_csv
            ),
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


def _normalize_horizons(
    horizons: Sequence[int] | Iterable[int],
) -> tuple[int, ...]:
    selected = tuple(sorted({int(value) for value in horizons}))
    if not selected or any(value <= 0 for value in selected):
        raise ValueError("interaction horizons must be positive")
    return selected


def _validate_l12_summary(summary: dict[str, object]) -> None:
    if (
        summary.get("audit_id")
        != DAILY_NO_SUPPLY_ALTERNATE_CONTEXT_PROFILE_AUDIT_ID
    ):
        raise ValueError("unexpected L12 audit_id")
    if summary.get("is_actionable") is not False:
        raise ValueError("L13 requires non-actionable L12 source")

    expected = {
        "requested_symbol_count": 30,
        "alternate_target_count": 305,
        "prior_target_count": 263,
        "latest_target_count": 42,
        "context_row_count": 305,
        "continuous_shift_row_count": 10,
        "categorical_shift_row_count": 19,
        "context_outcome_row_count": 45,
    }
    for key, value in expected.items():
        if int(summary.get(key, -1)) != value:
            raise ValueError(f"unexpected canonical L12 {key}")


def load_no_supply_relation_era_sources(
    *,
    context_dir: str | Path,
    matched_dir: str | Path,
) -> NoSupplyRelationEraSources:
    context_root = Path(context_dir)
    matched_root = Path(matched_dir)

    l12_summary_path = (
        context_root / "daily_no_supply_alternate_context_summary.json"
    )
    l12_contexts_path = (
        context_root / "daily_no_supply_alternate_contexts.csv"
    )
    l12_continuous_path = (
        context_root / "daily_no_supply_alternate_continuous_shifts.csv"
    )
    l12_categorical_path = (
        context_root / "daily_no_supply_alternate_categorical_shifts.csv"
    )
    l12_outcomes_path = (
        context_root / "daily_no_supply_alternate_context_outcomes.csv"
    )
    l8_pair_path = matched_root / "daily_no_supply_matched_pair_outcomes.csv"

    for path in (
        l12_summary_path,
        l12_contexts_path,
        l12_continuous_path,
        l12_categorical_path,
        l12_outcomes_path,
        l8_pair_path,
    ):
        if not path.exists():
            raise FileNotFoundError(path)

    summary = json.loads(l12_summary_path.read_text(encoding="utf-8"))
    _validate_l12_summary(summary)
    l12_lineage = summary.get("source_lineage")
    if not isinstance(l12_lineage, dict):
        raise ValueError("L12 source lineage is missing")

    l8_pair_sha256 = _sha256_file(l8_pair_path)
    if (
        str(l12_lineage.get("l8_pair_outcomes_sha256", ""))
        != l8_pair_sha256
    ):
        raise ValueError("L12 points to a different L8 pair ledger")

    contexts = pd.read_csv(l12_contexts_path)
    required_context = {
        "symbol",
        "session",
        "bar_index",
        "era",
        "comparison_group",
        "trend_direction",
        "volume_class",
        "previous_volume_class",
        "volume_class_relation",
        "volume_class_delta",
    }
    missing_context = sorted(required_context - set(contexts.columns))
    if missing_context:
        raise ValueError(f"L12 contexts missing columns: {missing_context}")

    contexts = contexts.copy()
    contexts["symbol"] = contexts["symbol"].map(
        lambda value: str(value).strip().upper()
    )
    contexts["session"] = contexts["session"].map(_normalize_session)

    if len(contexts) != 305:
        raise ValueError("canonical L12 context count changed")
    if contexts[["symbol", "session"]].duplicated().any():
        raise ValueError("L12 context identities are not unique")
    if int(contexts["symbol"].nunique()) != 30:
        raise ValueError("L12 contexts must span 30 symbols")
    if not (contexts["trend_direction"] == "UP").all():
        raise ValueError("L12 contexts contain non-UP direction")

    relations = set(contexts["volume_class_relation"].astype(str))
    if relations != set(RELATION_ORDER):
        raise ValueError(
            "unexpected L12 VolumeClass relation set: "
            f"{sorted(relations)}"
        )
    class_delta = contexts["volume_class_delta"].astype(float)
    if (class_delta < 0.0).any():
        raise ValueError("L12 contexts violate VolumeClass relation semantics")
    same_mask = contexts["volume_class_relation"] == RELATION_SAME_CLASS
    higher_mask = contexts["volume_class_relation"] == RELATION_HIGHER_CLASS
    if not (class_delta.loc[same_mask] == 0.0).all():
        raise ValueError("SAME_CLASS rows must have zero VolumeClass delta")
    if not (class_delta.loc[higher_mask] > 0.0).all():
        raise ValueError("HIGHER_CLASS rows must have positive VolumeClass delta")

    expected_latest = contexts["era"] == ERA_2023_2026
    actual_latest = contexts["comparison_group"] == GROUP_LATEST
    if not (expected_latest == actual_latest).all():
        raise ValueError("L12 era/comparison-group assignment drifted")
    if not (
        contexts.loc[~expected_latest, "comparison_group"] == GROUP_PRIOR
    ).all():
        raise ValueError("pre-2023 L12 rows must use the prior group")

    same_count = int(
        (contexts["volume_class_relation"] == RELATION_SAME_CLASS).sum()
    )
    higher_count = int(
        (contexts["volume_class_relation"] == RELATION_HIGHER_CLASS).sum()
    )
    if (same_count, higher_count) != (201, 104):
        raise ValueError(
            "canonical relation counts changed: "
            f"{same_count}/{higher_count}"
        )

    prior = contexts["comparison_group"] == GROUP_PRIOR
    latest = contexts["comparison_group"] == GROUP_LATEST
    if int(prior.sum()) != 263 or int(latest.sum()) != 42:
        raise ValueError("canonical prior/latest L12 split changed")

    prior_same = int(
        (prior & (contexts["volume_class_relation"] == RELATION_SAME_CLASS))
        .sum()
    )
    prior_higher = int(
        (
            prior
            & (contexts["volume_class_relation"] == RELATION_HIGHER_CLASS)
        ).sum()
    )
    latest_same = int(
        (latest & (contexts["volume_class_relation"] == RELATION_SAME_CLASS))
        .sum()
    )
    latest_higher = int(
        (
            latest
            & (contexts["volume_class_relation"] == RELATION_HIGHER_CLASS)
        ).sum()
    )
    if (prior_same, prior_higher, latest_same, latest_higher) != (
        170,
        93,
        31,
        11,
    ):
        raise ValueError(
            "canonical relation x period counts changed: "
            f"{prior_same}/{prior_higher}/{latest_same}/{latest_higher}"
        )

    pair_outcomes = pd.read_csv(l8_pair_path)
    required_pair = {
        "symbol",
        "cohort",
        "target_session",
        "horizon_sessions",
        "paired_return_delta_pct",
        "paired_mfe_delta_pct",
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
    pair_outcomes["clean_pair"] = pair_outcomes["clean_pair"].map(_parse_bool)

    context_map = {
        (row.symbol, row.session): (
            str(row.era),
            str(row.comparison_group),
            str(row.volume_class_relation),
        )
        for row in contexts.itertuples(index=False)
    }
    context_ids = set(context_map)
    pair_candidate = pair_outcomes.loc[
        [
            (symbol, session) in context_ids
            for symbol, session in zip(
                pair_outcomes["symbol"],
                pair_outcomes["target_session"],
                strict=False,
            )
        ]
    ].copy()

    pair_ids = set(
        zip(
            pair_candidate["symbol"],
            pair_candidate["target_session"],
            strict=False,
        )
    )
    if pair_ids != context_ids:
        raise ValueError("L13 pair coverage does not equal L12 contexts")

    if pair_candidate[
        ["symbol", "target_session", "horizon_sessions"]
    ].duplicated().any():
        raise ValueError("L13 pair identities are not unique")

    pair_candidate["era"] = [
        context_map[(symbol, session)][0]
        for symbol, session in zip(
            pair_candidate["symbol"],
            pair_candidate["target_session"],
            strict=False,
        )
    ]
    pair_candidate["comparison_group"] = [
        context_map[(symbol, session)][1]
        for symbol, session in zip(
            pair_candidate["symbol"],
            pair_candidate["target_session"],
            strict=False,
        )
    ]
    pair_candidate["volume_class_relation"] = [
        context_map[(symbol, session)][2]
        for symbol, session in zip(
            pair_candidate["symbol"],
            pair_candidate["target_session"],
            strict=False,
        )
    ]

    lineage = NoSupplyRelationEraSourceLineage(
        l12_audit_id=str(summary["audit_id"]),
        l12_summary_sha256=_sha256_file(l12_summary_path),
        l12_contexts_sha256=_sha256_file(l12_contexts_path),
        l12_continuous_shifts_sha256=_sha256_file(l12_continuous_path),
        l12_categorical_shifts_sha256=_sha256_file(l12_categorical_path),
        l12_context_outcomes_sha256=_sha256_file(l12_outcomes_path),
        l8_pair_outcomes_sha256=l8_pair_sha256,
        snapshot_manifest_sha256=str(
            l12_lineage["snapshot_manifest_sha256"]
        ),
    )
    return NoSupplyRelationEraSources(
        lineage=lineage,
        contexts=contexts.reset_index(drop=True),
        pair_outcomes=pair_candidate.reset_index(drop=True),
    )


def build_era_relation_count_rows(
    contexts: pd.DataFrame,
) -> tuple[NoSupplyRelationEraCountRow, ...]:
    rows: list[NoSupplyRelationEraCountRow] = []
    for era in ERA_ORDER:
        for relation in RELATION_ORDER:
            selected = contexts.loc[
                (contexts["era"] == era)
                & (contexts["volume_class_relation"] == relation)
            ]
            if selected.empty:
                rows.append(
                    NoSupplyRelationEraCountRow(
                        era=era,
                        volume_class_relation=relation,
                        source_target_count=0,
                        symbol_count=0,
                        first_session="",
                        last_session="",
                    )
                )
                continue
            rows.append(
                NoSupplyRelationEraCountRow(
                    era=era,
                    volume_class_relation=relation,
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
        mfe_delta=("paired_mfe_delta_pct", "mean"),
    )


def _aggregate_group(clean: pd.DataFrame) -> dict[str, float | int]:
    if clean.empty:
        raise ValueError("cannot aggregate an empty clean-pair group")
    symbol_frame = _symbol_means(clean)
    return {
        "clean_pair_count": len(clean),
        "symbol_count": int(clean["symbol"].nunique()),
        "event_return": float(clean["paired_return_delta_pct"].mean()),
        "symbol_return": float(symbol_frame["return_delta"].mean()),
        "event_mfe": float(clean["paired_mfe_delta_pct"].mean()),
        "symbol_mfe": float(symbol_frame["mfe_delta"].mean()),
    }


def build_era_relation_outcome_rows(
    *,
    contexts: pd.DataFrame,
    pair_outcomes: pd.DataFrame,
    horizons: Sequence[int] | Iterable[int] = DEFAULT_INTERACTION_HORIZONS,
) -> tuple[NoSupplyRelationEraOutcomeRow, ...]:
    selected_horizons = _normalize_horizons(horizons)
    rows: list[NoSupplyRelationEraOutcomeRow] = []

    for era in ERA_ORDER:
        for relation in RELATION_ORDER:
            source_target_count = len(
                contexts.loc[
                    (contexts["era"] == era)
                    & (contexts["volume_class_relation"] == relation)
                ]
            )
            if source_target_count == 0:
                continue
            for horizon in selected_horizons:
                clean = pair_outcomes.loc[
                    (pair_outcomes["era"] == era)
                    & (
                        pair_outcomes["volume_class_relation"]
                        == relation
                    )
                    & (pair_outcomes["horizon_sessions"] == horizon)
                    & pair_outcomes["clean_pair"]
                ].copy()
                if clean.empty:
                    continue
                agg = _aggregate_group(clean)
                rows.append(
                    NoSupplyRelationEraOutcomeRow(
                        era=era,
                        volume_class_relation=relation,
                        horizon_sessions=horizon,
                        source_target_count=source_target_count,
                        clean_pair_count=int(agg["clean_pair_count"]),
                        symbol_count=int(agg["symbol_count"]),
                        event_weighted_return_delta_pct=float(
                            agg["event_return"]
                        ),
                        symbol_normalized_return_delta_pct=float(
                            agg["symbol_return"]
                        ),
                        event_weighted_mfe_delta_pct=float(
                            agg["event_mfe"]
                        ),
                        symbol_normalized_mfe_delta_pct=float(
                            agg["symbol_mfe"]
                        ),
                    )
                )
    return tuple(rows)


def _outcome_metric_value(
    row: NoSupplyRelationEraOutcomeRow,
    *,
    metric: str,
    estimand: str,
) -> float:
    mapping = {
        (METRIC_RETURN, ESTIMAND_EVENT_WEIGHTED): (
            "event_weighted_return_delta_pct"
        ),
        (METRIC_RETURN, ESTIMAND_SYMBOL_NORMALIZED): (
            "symbol_normalized_return_delta_pct"
        ),
        (METRIC_MFE, ESTIMAND_EVENT_WEIGHTED): (
            "event_weighted_mfe_delta_pct"
        ),
        (METRIC_MFE, ESTIMAND_SYMBOL_NORMALIZED): (
            "symbol_normalized_mfe_delta_pct"
        ),
    }
    try:
        return float(getattr(row, mapping[(metric, estimand)]))
    except KeyError as exc:
        raise ValueError(
            f"unknown metric/estimand {metric}/{estimand}"
        ) from exc


def build_relation_temporal_consistency_rows(
    outcomes: Sequence[NoSupplyRelationEraOutcomeRow],
    *,
    horizons: Sequence[int] | Iterable[int] = DEFAULT_INTERACTION_HORIZONS,
) -> tuple[NoSupplyRelationTemporalConsistencyRow, ...]:
    selected_horizons = _normalize_horizons(horizons)
    rows: list[NoSupplyRelationTemporalConsistencyRow] = []

    for relation in RELATION_ORDER:
        for horizon in selected_horizons:
            subset = [
                row
                for row in outcomes
                if row.volume_class_relation == relation
                and row.horizon_sessions == horizon
            ]
            if not subset:
                continue
            for metric in METRICS:
                for estimand in ESTIMANDS:
                    values = [
                        (
                            row.era,
                            _outcome_metric_value(
                                row,
                                metric=metric,
                                estimand=estimand,
                            ),
                        )
                        for row in subset
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
                        NoSupplyRelationTemporalConsistencyRow(
                            volume_class_relation=relation,
                            horizon_sessions=horizon,
                            metric=metric,
                            estimand=estimand,
                            available_era_count=len(values),
                            positive_era_count=sum(
                                value > 0.0 for _, value in values
                            ),
                            negative_era_count=sum(
                                value < 0.0 for _, value in values
                            ),
                            zero_era_count=sum(
                                value == 0.0 for _, value in values
                            ),
                            min_era_value=float(min_value),
                            min_era=min_era,
                            max_era_value=float(max_value),
                            max_era=max_era,
                        )
                    )
    return tuple(rows)


def build_prior_latest_rows(
    *,
    contexts: pd.DataFrame,
    pair_outcomes: pd.DataFrame,
    horizons: Sequence[int] | Iterable[int] = DEFAULT_INTERACTION_HORIZONS,
) -> tuple[NoSupplyRelationPriorLatestRow, ...]:
    selected_horizons = _normalize_horizons(horizons)
    rows: list[NoSupplyRelationPriorLatestRow] = []

    for relation in RELATION_ORDER:
        prior_source = contexts.loc[
            (contexts["comparison_group"] == GROUP_PRIOR)
            & (contexts["volume_class_relation"] == relation)
        ]
        latest_source = contexts.loc[
            (contexts["comparison_group"] == GROUP_LATEST)
            & (contexts["volume_class_relation"] == relation)
        ]
        if prior_source.empty or latest_source.empty:
            raise ValueError(
                f"L13 relation lacks prior/latest source rows: {relation}"
            )

        for horizon in selected_horizons:
            prior_clean = pair_outcomes.loc[
                (pair_outcomes["comparison_group"] == GROUP_PRIOR)
                & (
                    pair_outcomes["volume_class_relation"]
                    == relation
                )
                & (pair_outcomes["horizon_sessions"] == horizon)
                & pair_outcomes["clean_pair"]
            ].copy()
            latest_clean = pair_outcomes.loc[
                (pair_outcomes["comparison_group"] == GROUP_LATEST)
                & (
                    pair_outcomes["volume_class_relation"]
                    == relation
                )
                & (pair_outcomes["horizon_sessions"] == horizon)
                & pair_outcomes["clean_pair"]
            ].copy()
            if prior_clean.empty or latest_clean.empty:
                raise ValueError(
                    f"L13 relation lacks prior/latest clean pairs: "
                    f"{relation}/{horizon}"
                )

            prior = _aggregate_group(prior_clean)
            latest = _aggregate_group(latest_clean)

            rows.append(
                NoSupplyRelationPriorLatestRow(
                    volume_class_relation=relation,
                    horizon_sessions=horizon,
                    prior_source_target_count=len(prior_source),
                    latest_source_target_count=len(latest_source),
                    prior_clean_pair_count=int(prior["clean_pair_count"]),
                    latest_clean_pair_count=int(latest["clean_pair_count"]),
                    prior_symbol_count=int(prior["symbol_count"]),
                    latest_symbol_count=int(latest["symbol_count"]),
                    prior_event_weighted_return_delta_pct=float(
                        prior["event_return"]
                    ),
                    latest_event_weighted_return_delta_pct=float(
                        latest["event_return"]
                    ),
                    latest_minus_prior_event_return_pct=float(
                        latest["event_return"] - prior["event_return"]
                    ),
                    prior_symbol_normalized_return_delta_pct=float(
                        prior["symbol_return"]
                    ),
                    latest_symbol_normalized_return_delta_pct=float(
                        latest["symbol_return"]
                    ),
                    latest_minus_prior_symbol_return_pct=float(
                        latest["symbol_return"] - prior["symbol_return"]
                    ),
                    prior_event_weighted_mfe_delta_pct=float(
                        prior["event_mfe"]
                    ),
                    latest_event_weighted_mfe_delta_pct=float(
                        latest["event_mfe"]
                    ),
                    latest_minus_prior_event_mfe_pct=float(
                        latest["event_mfe"] - prior["event_mfe"]
                    ),
                    prior_symbol_normalized_mfe_delta_pct=float(
                        prior["symbol_mfe"]
                    ),
                    latest_symbol_normalized_mfe_delta_pct=float(
                        latest["symbol_mfe"]
                    ),
                    latest_minus_prior_symbol_mfe_pct=float(
                        latest["symbol_mfe"] - prior["symbol_mfe"]
                    ),
                )
            )
    return tuple(rows)


def _prior_latest_value(
    row: NoSupplyRelationPriorLatestRow,
    *,
    metric: str,
    estimand: str,
    period: str,
) -> float:
    mapping = {
        (
            METRIC_RETURN,
            ESTIMAND_EVENT_WEIGHTED,
            "prior",
        ): "prior_event_weighted_return_delta_pct",
        (
            METRIC_RETURN,
            ESTIMAND_EVENT_WEIGHTED,
            "latest",
        ): "latest_event_weighted_return_delta_pct",
        (
            METRIC_RETURN,
            ESTIMAND_SYMBOL_NORMALIZED,
            "prior",
        ): "prior_symbol_normalized_return_delta_pct",
        (
            METRIC_RETURN,
            ESTIMAND_SYMBOL_NORMALIZED,
            "latest",
        ): "latest_symbol_normalized_return_delta_pct",
        (
            METRIC_MFE,
            ESTIMAND_EVENT_WEIGHTED,
            "prior",
        ): "prior_event_weighted_mfe_delta_pct",
        (
            METRIC_MFE,
            ESTIMAND_EVENT_WEIGHTED,
            "latest",
        ): "latest_event_weighted_mfe_delta_pct",
        (
            METRIC_MFE,
            ESTIMAND_SYMBOL_NORMALIZED,
            "prior",
        ): "prior_symbol_normalized_mfe_delta_pct",
        (
            METRIC_MFE,
            ESTIMAND_SYMBOL_NORMALIZED,
            "latest",
        ): "latest_symbol_normalized_mfe_delta_pct",
    }
    try:
        return float(getattr(row, mapping[(metric, estimand, period)]))
    except KeyError as exc:
        raise ValueError(
            f"unknown interaction key {metric}/{estimand}/{period}"
        ) from exc


def build_interaction_contrast_rows(
    prior_latest_rows: Sequence[NoSupplyRelationPriorLatestRow],
    *,
    horizons: Sequence[int] | Iterable[int] = DEFAULT_INTERACTION_HORIZONS,
) -> tuple[NoSupplyRelationInteractionContrastRow, ...]:
    selected_horizons = _normalize_horizons(horizons)
    lookup = {
        (row.volume_class_relation, row.horizon_sessions): row
        for row in prior_latest_rows
    }
    rows: list[NoSupplyRelationInteractionContrastRow] = []

    for horizon in selected_horizons:
        same = lookup[(RELATION_SAME_CLASS, horizon)]
        higher = lookup[(RELATION_HIGHER_CLASS, horizon)]
        for metric in METRICS:
            for estimand in ESTIMANDS:
                same_prior = _prior_latest_value(
                    same,
                    metric=metric,
                    estimand=estimand,
                    period="prior",
                )
                same_latest = _prior_latest_value(
                    same,
                    metric=metric,
                    estimand=estimand,
                    period="latest",
                )
                higher_prior = _prior_latest_value(
                    higher,
                    metric=metric,
                    estimand=estimand,
                    period="prior",
                )
                higher_latest = _prior_latest_value(
                    higher,
                    metric=metric,
                    estimand=estimand,
                    period="latest",
                )
                same_change = same_latest - same_prior
                higher_change = higher_latest - higher_prior
                rows.append(
                    NoSupplyRelationInteractionContrastRow(
                        horizon_sessions=horizon,
                        metric=metric,
                        estimand=estimand,
                        same_class_prior_value=same_prior,
                        same_class_latest_value=same_latest,
                        same_class_latest_minus_prior=same_change,
                        higher_class_prior_value=higher_prior,
                        higher_class_latest_value=higher_latest,
                        higher_class_latest_minus_prior=higher_change,
                        same_minus_higher_change=(
                            same_change - higher_change
                        ),
                    )
                )
    return tuple(rows)


def build_no_supply_relation_era_interaction_audit(
    *,
    sources: NoSupplyRelationEraSources,
    horizons: Sequence[int] | Iterable[int] = DEFAULT_INTERACTION_HORIZONS,
) -> NoSupplyRelationEraInteractionAudit:
    selected_horizons = _normalize_horizons(horizons)
    contexts = sources.contexts

    same_count = int(
        (contexts["volume_class_relation"] == RELATION_SAME_CLASS).sum()
    )
    higher_count = int(
        (contexts["volume_class_relation"] == RELATION_HIGHER_CLASS).sum()
    )
    prior = contexts["comparison_group"] == GROUP_PRIOR
    latest = contexts["comparison_group"] == GROUP_LATEST
    prior_same = int(
        (
            prior
            & (contexts["volume_class_relation"] == RELATION_SAME_CLASS)
        ).sum()
    )
    prior_higher = int(
        (
            prior
            & (contexts["volume_class_relation"] == RELATION_HIGHER_CLASS)
        ).sum()
    )
    latest_same = int(
        (
            latest
            & (contexts["volume_class_relation"] == RELATION_SAME_CLASS)
        ).sum()
    )
    latest_higher = int(
        (
            latest
            & (contexts["volume_class_relation"] == RELATION_HIGHER_CLASS)
        ).sum()
    )

    count_rows = build_era_relation_count_rows(contexts)
    outcome_rows = build_era_relation_outcome_rows(
        contexts=contexts,
        pair_outcomes=sources.pair_outcomes,
        horizons=selected_horizons,
    )
    consistency_rows = build_relation_temporal_consistency_rows(
        outcome_rows,
        horizons=selected_horizons,
    )
    prior_latest_rows = build_prior_latest_rows(
        contexts=contexts,
        pair_outcomes=sources.pair_outcomes,
        horizons=selected_horizons,
    )
    interaction_rows = build_interaction_contrast_rows(
        prior_latest_rows,
        horizons=selected_horizons,
    )

    if len(count_rows) != len(ERA_ORDER) * len(RELATION_ORDER):
        raise RuntimeError("L13 era x relation count rows do not reconcile")
    expected_consistency = (
        len(RELATION_ORDER)
        * len(selected_horizons)
        * len(METRICS)
        * len(ESTIMANDS)
    )
    if len(consistency_rows) != expected_consistency:
        raise RuntimeError("L13 temporal consistency rows do not reconcile")
    expected_prior_latest = len(RELATION_ORDER) * len(selected_horizons)
    if len(prior_latest_rows) != expected_prior_latest:
        raise RuntimeError("L13 prior/latest rows do not reconcile")
    expected_interaction = (
        len(selected_horizons) * len(METRICS) * len(ESTIMANDS)
    )
    if len(interaction_rows) != expected_interaction:
        raise RuntimeError("L13 interaction rows do not reconcile")

    return NoSupplyRelationEraInteractionAudit(
        audit_id=DAILY_NO_SUPPLY_RELATION_ERA_INTERACTION_AUDIT_ID,
        source_lineage=sources.lineage,
        requested_symbol_count=int(contexts["symbol"].nunique()),
        alternate_target_count=len(contexts),
        same_class_target_count=same_count,
        higher_class_target_count=higher_count,
        prior_same_class_target_count=prior_same,
        prior_higher_class_target_count=prior_higher,
        latest_same_class_target_count=latest_same,
        latest_higher_class_target_count=latest_higher,
        era_count=len(ERA_ORDER),
        relation_count=len(RELATION_ORDER),
        horizon_count=len(selected_horizons),
        horizons=selected_horizons,
        count_rows=count_rows,
        outcome_rows=outcome_rows,
        consistency_rows=consistency_rows,
        prior_latest_rows=prior_latest_rows,
        interaction_rows=interaction_rows,
    )


def write_no_supply_relation_era_interaction_audit(
    audit: NoSupplyRelationEraInteractionAudit,
    output_dir: str | Path,
) -> NoSupplyRelationEraInteractionPaths:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    paths = NoSupplyRelationEraInteractionPaths(
        summary_json=root / "daily_no_supply_relation_era_summary.json",
        era_relation_counts_csv=(
            root / "daily_no_supply_relation_era_counts.csv"
        ),
        era_relation_outcomes_csv=(
            root / "daily_no_supply_relation_era_outcomes.csv"
        ),
        relation_consistency_csv=(
            root / "daily_no_supply_relation_temporal_consistency.csv"
        ),
        prior_latest_csv=(
            root / "daily_no_supply_relation_prior_latest.csv"
        ),
        interaction_contrasts_csv=(
            root / "daily_no_supply_relation_interaction_contrasts.csv"
        ),
    )

    summary = {
        "audit_id": audit.audit_id,
        "requested_symbol_count": audit.requested_symbol_count,
        "alternate_target_count": audit.alternate_target_count,
        "same_class_target_count": audit.same_class_target_count,
        "higher_class_target_count": audit.higher_class_target_count,
        "prior_same_class_target_count": (
            audit.prior_same_class_target_count
        ),
        "prior_higher_class_target_count": (
            audit.prior_higher_class_target_count
        ),
        "latest_same_class_target_count": (
            audit.latest_same_class_target_count
        ),
        "latest_higher_class_target_count": (
            audit.latest_higher_class_target_count
        ),
        "era_count": audit.era_count,
        "relation_count": audit.relation_count,
        "horizon_count": audit.horizon_count,
        "horizons": list(audit.horizons),
        "era_relation_count_row_count": len(audit.count_rows),
        "era_relation_outcome_row_count": len(audit.outcome_rows),
        "relation_consistency_row_count": len(audit.consistency_rows),
        "prior_latest_row_count": len(audit.prior_latest_rows),
        "interaction_contrast_row_count": len(audit.interaction_rows),
        "source_lineage": asdict(audit.source_lineage),
        "is_actionable": False,
    }
    paths.summary_json.write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    pd.DataFrame([asdict(item) for item in audit.count_rows]).to_csv(
        paths.era_relation_counts_csv,
        index=False,
    )
    pd.DataFrame([asdict(item) for item in audit.outcome_rows]).to_csv(
        paths.era_relation_outcomes_csv,
        index=False,
    )
    pd.DataFrame(
        [asdict(item) for item in audit.consistency_rows]
    ).to_csv(paths.relation_consistency_csv, index=False)
    pd.DataFrame(
        [asdict(item) for item in audit.prior_latest_rows]
    ).to_csv(paths.prior_latest_csv, index=False)
    pd.DataFrame(
        [asdict(item) for item in audit.interaction_rows]
    ).to_csv(paths.interaction_contrasts_csv, index=False)
    return paths


__all__ = [
    "DAILY_NO_SUPPLY_RELATION_ERA_INTERACTION_AUDIT_ID",
    "DEFAULT_INTERACTION_HORIZONS",
    "ESTIMAND_EVENT_WEIGHTED",
    "ESTIMAND_SYMBOL_NORMALIZED",
    "METRIC_MFE",
    "METRIC_RETURN",
    "RELATION_HIGHER_CLASS",
    "RELATION_ORDER",
    "RELATION_SAME_CLASS",
    "NoSupplyRelationEraCountRow",
    "NoSupplyRelationEraInteractionAudit",
    "NoSupplyRelationEraInteractionPaths",
    "NoSupplyRelationEraOutcomeRow",
    "NoSupplyRelationEraSourceLineage",
    "NoSupplyRelationEraSources",
    "NoSupplyRelationInteractionContrastRow",
    "NoSupplyRelationPriorLatestRow",
    "NoSupplyRelationTemporalConsistencyRow",
    "build_era_relation_count_rows",
    "build_era_relation_outcome_rows",
    "build_interaction_contrast_rows",
    "build_no_supply_relation_era_interaction_audit",
    "build_prior_latest_rows",
    "build_relation_temporal_consistency_rows",
    "load_no_supply_relation_era_sources",
    "write_no_supply_relation_era_interaction_audit",
]
