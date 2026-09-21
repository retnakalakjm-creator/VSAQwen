"""Context profiling for ALTERNATE/UP WEAK_RESULT_ONLY.

L12 compares the 2023-2026 ALTERNATE candidate context with earlier ALTERNATE
history using only predeclared production-derived features. It is descriptive,
audit-only, and performs no production behavior changes.
"""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Callable, Iterable, Iterator, Sequence

import numpy as np
import pandas as pd

from audit.daily_event_no_supply_forward_outcomes import COHORT_ALTERNATE
from audit.daily_event_no_supply_matched_environment import (
    l6_equivalent_session_frame,
)
from audit.daily_event_no_supply_temporal_stability import (
    DAILY_NO_SUPPLY_TEMPORAL_STABILITY_AUDIT_ID,
    ERA_2023_2026,
)
from audit.daily_input_reproducibility import (
    DailyAuditInputBundle,
    daily_audit_input_manifest_sha256,
    load_daily_audit_input,
    load_daily_audit_input_bundle,
)
from audit.offline_daily_evidence import _metrics_input, _validate_daily_ohlcv
from engine.columns import (
    COL_CLOSE_POSITION,
    COL_CLOSE_RATIO,
    COL_PRICE_CHANGE_PCT,
    COL_SPREAD_CLASS,
    COL_SPREAD_PERCENTILE,
    COL_SPREAD_RATIO,
    COL_VOLUME,
    COL_VOLUME_CLASS,
    COL_VOLUME_PERCENTILE,
    COL_VOLUME_RATIO,
)
from market_structure.progression import determine_structural_pattern
from market_structure.structure_filter import StructureFilter
from market_structure.swing_engine import SwingEngine
from metrics_engine import MetricsEngine
from models import ClosePosition, SpreadClass, VolumeClass
from trend import TrendAnalyzer


DAILY_NO_SUPPLY_ALTERNATE_CONTEXT_PROFILE_AUDIT_ID = (
    "daily-event-no-supply-alternate-context-profile-v1"
)

GROUP_PRIOR = "ALTERNATE_PRIOR_THROUGH_2022"
GROUP_LATEST = "ALTERNATE_2023_2026"

CONTEXT_CONTINUOUS_FEATURES = (
    "trend_strength",
    "trend_confidence",
    "spread_ratio",
    "spread_percentile",
    "volume_ratio",
    "volume_percentile",
    "close_ratio",
    "price_change_pct",
    "raw_volume_vs_previous_ratio",
    "volume_class_delta",
)

CONTEXT_CATEGORICAL_DIMENSIONS = (
    "trend_state",
    "structural_pattern",
    "close_position",
    "volume_class",
    "previous_volume_class",
    "volume_class_relation",
    "spread_class",
)

CONTEXT_OUTCOME_DIMENSIONS = (
    "trend_state",
    "structural_pattern",
    "close_position",
    "volume_class",
    "volume_class_relation",
)

DEFAULT_CONTEXT_OUTCOME_HORIZONS = (1, 3, 5)


@dataclass(frozen=True, slots=True)
class NoSupplyAlternateContextSourceLineage:
    l11_audit_id: str
    l11_summary_sha256: str
    l11_candidate_targets_sha256: str
    l11_era_outcomes_sha256: str
    l11_consistency_sha256: str
    l8_pair_outcomes_sha256: str
    snapshot_manifest_sha256: str
    snapshot_basket_name: str
    snapshot_period: str
    snapshot_cutoff: str


@dataclass(frozen=True, slots=True)
class NoSupplyAlternateContextSources:
    lineage: NoSupplyAlternateContextSourceLineage
    bundle: DailyAuditInputBundle
    alternate_targets: pd.DataFrame
    pair_outcomes: pd.DataFrame
    prior_target_count: int
    latest_target_count: int


@dataclass(frozen=True, slots=True)
class NoSupplyAlternateCandidateContext:
    symbol: str
    session: str
    bar_index: int
    era: str
    comparison_group: str
    trend_direction: str
    trend_state: str
    trend_strength: float
    trend_confidence: float
    structural_pattern: str
    close_position: str
    volume_class: str
    previous_volume_class: str
    volume_class_relation: str
    spread_class: str
    spread_ratio: float
    spread_percentile: float
    volume_ratio: float
    volume_percentile: float
    close_ratio: float
    price_change_pct: float
    raw_volume_vs_previous_ratio: float
    volume_class_delta: float


@dataclass(frozen=True, slots=True)
class NoSupplyAlternateContinuousShiftRow:
    feature: str
    prior_count: int
    latest_count: int
    prior_mean: float
    latest_mean: float
    mean_delta: float
    prior_median: float
    latest_median: float
    median_delta: float
    pooled_standard_deviation: float
    standardized_mean_difference: float


@dataclass(frozen=True, slots=True)
class NoSupplyAlternateCategoricalShiftRow:
    dimension: str
    level: str
    prior_count: int
    prior_rate: float
    latest_count: int
    latest_rate: float
    latest_minus_prior_rate_pp: float


@dataclass(frozen=True, slots=True)
class NoSupplyAlternateContextOutcomeRow:
    dimension: str
    level: str
    horizon_sessions: int
    source_target_count: int
    clean_pair_count: int
    symbol_count: int
    event_weighted_return_delta_pct: float
    symbol_normalized_return_delta_pct: float
    event_weighted_mfe_delta_pct: float
    symbol_normalized_mfe_delta_pct: float


@dataclass(frozen=True, slots=True)
class NoSupplyAlternateContextProfileAudit:
    audit_id: str
    source_lineage: NoSupplyAlternateContextSourceLineage
    requested_symbol_count: int
    alternate_target_count: int
    prior_target_count: int
    latest_target_count: int
    context_row_count: int
    continuous_shift_rows: tuple[NoSupplyAlternateContinuousShiftRow, ...]
    categorical_shift_rows: tuple[NoSupplyAlternateCategoricalShiftRow, ...]
    context_outcome_rows: tuple[NoSupplyAlternateContextOutcomeRow, ...]

    @property
    def is_actionable(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class NoSupplyAlternateContextProfilePaths:
    summary_json: Path
    contexts_csv: Path
    continuous_shifts_csv: Path
    categorical_shifts_csv: Path
    context_outcomes_csv: Path

    def as_dict(self) -> dict[str, str]:
        return {
            "summary_json": str(self.summary_json),
            "contexts_csv": str(self.contexts_csv),
            "continuous_shifts_csv": str(self.continuous_shifts_csv),
            "categorical_shifts_csv": str(self.categorical_shifts_csv),
            "context_outcomes_csv": str(self.context_outcomes_csv),
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


@contextmanager
def _suppress_vsa_info_logs() -> Iterator[None]:
    logger = logging.getLogger("VSA")
    previous = logger.level
    logger.setLevel(logging.WARNING)
    try:
        yield
    finally:
        logger.setLevel(previous)


def _validate_l11_summary(summary: dict[str, object]) -> None:
    if (
        summary.get("audit_id")
        != DAILY_NO_SUPPLY_TEMPORAL_STABILITY_AUDIT_ID
    ):
        raise ValueError("unexpected L11 audit_id")
    if summary.get("is_actionable") is not False:
        raise ValueError("L12 requires non-actionable L11 source")
    expected = {
        "requested_symbol_count": 30,
        "candidate_target_count": 427,
        "current_candidate_target_count": 122,
        "alternate_candidate_target_count": 305,
        "era_count": 5,
        "era_count_row_count": 10,
        "era_outcome_row_count": 50,
        "consistency_row_count": 80,
        "leave_one_era_out_row_count": 100,
    }
    for key, value in expected.items():
        if int(summary.get(key, -1)) != value:
            raise ValueError(f"unexpected canonical L11 {key}")


def load_no_supply_alternate_context_sources(
    *,
    temporal_dir: str | Path,
    matched_dir: str | Path,
    input_snapshot_dir: str | Path,
    basket_name: str,
) -> NoSupplyAlternateContextSources:
    temporal_root = Path(temporal_dir)
    matched_root = Path(matched_dir)
    snapshot_root = Path(input_snapshot_dir)

    l11_summary_path = (
        temporal_root / "daily_no_supply_temporal_stability_summary.json"
    )
    l11_targets_path = (
        temporal_root / "daily_no_supply_temporal_candidate_targets.csv"
    )
    l11_era_outcomes_path = (
        temporal_root / "daily_no_supply_temporal_era_outcomes.csv"
    )
    l11_consistency_path = (
        temporal_root / "daily_no_supply_temporal_consistency.csv"
    )
    l8_pair_path = matched_root / "daily_no_supply_matched_pair_outcomes.csv"

    for path in (
        l11_summary_path,
        l11_targets_path,
        l11_era_outcomes_path,
        l11_consistency_path,
        l8_pair_path,
    ):
        if not path.exists():
            raise FileNotFoundError(path)

    l11_summary = json.loads(l11_summary_path.read_text(encoding="utf-8"))
    _validate_l11_summary(l11_summary)
    l11_lineage = l11_summary.get("source_lineage")
    if not isinstance(l11_lineage, dict):
        raise ValueError("L11 source lineage is missing")

    if (
        str(l11_lineage.get("l8_pair_outcomes_sha256", ""))
        != _sha256_file(l8_pair_path)
    ):
        raise ValueError("L11 points to a different L8 pair ledger")

    bundle = load_daily_audit_input_bundle(snapshot_root)
    manifest_sha256 = daily_audit_input_manifest_sha256(snapshot_root)
    if bundle.basket_name != basket_name:
        raise ValueError("snapshot basket does not match requested basket")
    if (
        str(l11_lineage.get("snapshot_manifest_sha256", ""))
        != manifest_sha256
    ):
        raise ValueError("snapshot manifest hash does not match L11 lineage")

    targets = pd.read_csv(l11_targets_path)
    required_targets = {
        "symbol",
        "session",
        "bar_index",
        "cohort",
        "trend_direction",
        "volume_decreasing",
        "weak_selling_result",
        "stratum",
        "era",
    }
    missing_targets = sorted(required_targets - set(targets.columns))
    if missing_targets:
        raise ValueError(f"L11 targets missing columns: {missing_targets}")
    targets = targets.copy()
    targets["symbol"] = targets["symbol"].map(
        lambda value: str(value).strip().upper()
    )
    targets["session"] = targets["session"].map(_normalize_session)
    targets["volume_decreasing"] = targets["volume_decreasing"].map(_parse_bool)
    targets["weak_selling_result"] = targets[
        "weak_selling_result"
    ].map(_parse_bool)
    if len(targets) != 427:
        raise ValueError("canonical L11 target count changed")
    if targets[["symbol", "session"]].duplicated().any():
        raise ValueError("L11 target identities are not unique")
    if not (targets["stratum"] == "WEAK_RESULT_ONLY").all():
        raise ValueError("L11 candidate stratum changed")
    if not (
        (~targets["volume_decreasing"])
        & targets["weak_selling_result"]
    ).all():
        raise ValueError("L11 candidate predicate semantics changed")

    alternate = targets.loc[
        targets["cohort"] == COHORT_ALTERNATE
    ].copy()
    if len(alternate) != 305:
        raise ValueError("canonical ALTERNATE candidate count changed")
    if int(alternate["symbol"].nunique()) != 30:
        raise ValueError("canonical ALTERNATE candidates must span 30 symbols")
    latest_count = int((alternate["era"] == ERA_2023_2026).sum())
    prior_count = len(alternate) - latest_count
    if latest_count != 42 or prior_count != 263:
        raise ValueError(
            "canonical ALTERNATE era split changed: "
            f"prior={prior_count}, latest={latest_count}"
        )
    alternate["comparison_group"] = np.where(
        alternate["era"] == ERA_2023_2026,
        GROUP_LATEST,
        GROUP_PRIOR,
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

    target_ids = set(
        zip(alternate["symbol"], alternate["session"], strict=False)
    )
    pair_candidate = pair_outcomes.loc[
        [
            (symbol, session) in target_ids
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
    if pair_ids != target_ids:
        raise ValueError("L12 pair coverage does not equal ALTERNATE targets")

    lineage = NoSupplyAlternateContextSourceLineage(
        l11_audit_id=str(l11_summary["audit_id"]),
        l11_summary_sha256=_sha256_file(l11_summary_path),
        l11_candidate_targets_sha256=_sha256_file(l11_targets_path),
        l11_era_outcomes_sha256=_sha256_file(l11_era_outcomes_path),
        l11_consistency_sha256=_sha256_file(l11_consistency_path),
        l8_pair_outcomes_sha256=_sha256_file(l8_pair_path),
        snapshot_manifest_sha256=manifest_sha256,
        snapshot_basket_name=bundle.basket_name,
        snapshot_period=bundle.period,
        snapshot_cutoff=bundle.cutoff,
    )
    return NoSupplyAlternateContextSources(
        lineage=lineage,
        bundle=bundle,
        alternate_targets=alternate.reset_index(drop=True),
        pair_outcomes=pair_candidate.reset_index(drop=True),
        prior_target_count=prior_count,
        latest_target_count=latest_count,
    )


def extract_candidate_context(
    *,
    symbol: str,
    daily: pd.DataFrame,
    session: str,
    expected_bar_index: int,
    era: str,
    comparison_group: str,
) -> NoSupplyAlternateCandidateContext:
    _validate_daily_ohlcv(daily)
    session_daily = l6_equivalent_session_frame(daily)
    normalized_session = _normalize_session(session)
    positions = {
        _normalize_session(value): index
        for index, value in enumerate(session_daily.index)
    }
    if normalized_session not in positions:
        raise ValueError(
            f"{symbol} target session missing from snapshot: "
            f"{normalized_session}"
        )
    position = positions[normalized_session]
    if position != int(expected_bar_index):
        raise ValueError(
            f"{symbol} L12 bar-index drift at {normalized_session}: "
            f"{expected_bar_index} != {position}"
        )
    if position < 1:
        raise ValueError("candidate context requires a previous session")

    prefix = session_daily.iloc[: position + 1].copy()
    metrics = MetricsEngine().calculate(_metrics_input(prefix))
    swings = SwingEngine().calculate(metrics)
    structural = StructureFilter().filter(list(swings), metrics)
    trend = TrendAnalyzer().analyze_from_swings(
        metrics,
        swings,
        structural_swings=structural,
    )
    current = metrics.iloc[-1]
    previous = metrics.iloc[-2]
    previous_volume = float(previous[COL_VOLUME])
    if previous_volume <= 0.0:
        raise ValueError("previous volume must be positive")

    pattern = determine_structural_pattern(trend.structure.swings)
    if trend.structure.direction.name != "UP":
        raise ValueError(
            f"{symbol} ALTERNATE target lost UP direction at "
            f"{normalized_session}: {trend.structure.direction.name}"
        )

    current_volume_class = VolumeClass(int(current[COL_VOLUME_CLASS]))
    previous_volume_class = VolumeClass(int(previous[COL_VOLUME_CLASS]))
    if current_volume_class < previous_volume_class:
        raise ValueError(
            f"{symbol} WEAK_RESULT_ONLY lost NOT volume_decreasing "
            f"VolumeClass semantics at {normalized_session}: "
            f"{current_volume_class.name} < {previous_volume_class.name}"
        )
    volume_class_relation = (
        "SAME_CLASS"
        if current_volume_class == previous_volume_class
        else "HIGHER_CLASS"
    )

    return NoSupplyAlternateCandidateContext(
        symbol=str(symbol).strip().upper(),
        session=normalized_session,
        bar_index=position,
        era=str(era),
        comparison_group=str(comparison_group),
        trend_direction=trend.structure.direction.name,
        trend_state=trend.structure.state.name,
        trend_strength=float(trend.structure.strength),
        trend_confidence=float(trend.structure.confidence),
        structural_pattern=pattern.name,
        close_position=ClosePosition(
            int(current[COL_CLOSE_POSITION])
        ).name,
        volume_class=current_volume_class.name,
        previous_volume_class=previous_volume_class.name,
        volume_class_relation=volume_class_relation,
        spread_class=SpreadClass(int(current[COL_SPREAD_CLASS])).name,
        spread_ratio=float(current[COL_SPREAD_RATIO]),
        spread_percentile=float(current[COL_SPREAD_PERCENTILE]),
        volume_ratio=float(current[COL_VOLUME_RATIO]),
        volume_percentile=float(current[COL_VOLUME_PERCENTILE]),
        close_ratio=float(current[COL_CLOSE_RATIO]),
        price_change_pct=float(current[COL_PRICE_CHANGE_PCT]),
        raw_volume_vs_previous_ratio=(
            float(current[COL_VOLUME]) / previous_volume
        ),
        volume_class_delta=float(
            int(current_volume_class) - int(previous_volume_class)
        ),
    )


def build_candidate_contexts(
    *,
    sources: NoSupplyAlternateContextSources,
    input_snapshot_dir: str | Path,
    progress_writer: Callable[[str], None] | None = None,
) -> tuple[NoSupplyAlternateCandidateContext, ...]:
    rows: list[NoSupplyAlternateCandidateContext] = []
    targets = sources.alternate_targets.sort_values(
        ["symbol", "bar_index"]
    )
    symbols = tuple(sorted(targets["symbol"].unique()))

    with _suppress_vsa_info_logs():
        for symbol_index, symbol in enumerate(symbols, start=1):
            daily = load_daily_audit_input(input_snapshot_dir, symbol)
            symbol_targets = targets.loc[targets["symbol"] == symbol]
            for target in symbol_targets.itertuples(index=False):
                rows.append(
                    extract_candidate_context(
                        symbol=symbol,
                        daily=daily,
                        session=target.session,
                        expected_bar_index=int(target.bar_index),
                        era=str(target.era),
                        comparison_group=str(target.comparison_group),
                    )
                )
            if progress_writer is not None:
                progress_writer(
                    "[daily-no-supply-l12] "
                    f"{symbol_index}/{len(symbols)} {symbol}: "
                    f"{len(symbol_targets)} contexts"
                )

    if len(rows) != 305:
        raise RuntimeError("L12 context count does not reconcile")
    identities = {(item.symbol, item.session) for item in rows}
    if len(identities) != len(rows):
        raise RuntimeError("L12 context identities are not unique")
    return tuple(rows)


def _pooled_standard_deviation(
    prior: np.ndarray,
    latest: np.ndarray,
) -> float:
    if len(prior) < 2 or len(latest) < 2:
        return 0.0
    numerator = (
        (len(prior) - 1) * float(np.var(prior, ddof=1))
        + (len(latest) - 1) * float(np.var(latest, ddof=1))
    )
    denominator = len(prior) + len(latest) - 2
    if denominator <= 0:
        return 0.0
    return float(np.sqrt(max(0.0, numerator / denominator)))


def build_continuous_shift_rows(
    contexts: pd.DataFrame,
) -> tuple[NoSupplyAlternateContinuousShiftRow, ...]:
    rows: list[NoSupplyAlternateContinuousShiftRow] = []
    prior_frame = contexts.loc[
        contexts["comparison_group"] == GROUP_PRIOR
    ]
    latest_frame = contexts.loc[
        contexts["comparison_group"] == GROUP_LATEST
    ]
    if len(prior_frame) != 263 or len(latest_frame) != 42:
        raise ValueError("L12 comparison groups do not reconcile")

    for feature in CONTEXT_CONTINUOUS_FEATURES:
        prior = prior_frame[feature].astype(float).to_numpy()
        latest = latest_frame[feature].astype(float).to_numpy()
        pooled = _pooled_standard_deviation(prior, latest)
        mean_delta = float(latest.mean() - prior.mean())
        smd = 0.0 if pooled == 0.0 else mean_delta / pooled
        rows.append(
            NoSupplyAlternateContinuousShiftRow(
                feature=feature,
                prior_count=len(prior),
                latest_count=len(latest),
                prior_mean=float(prior.mean()),
                latest_mean=float(latest.mean()),
                mean_delta=mean_delta,
                prior_median=float(np.median(prior)),
                latest_median=float(np.median(latest)),
                median_delta=float(
                    np.median(latest) - np.median(prior)
                ),
                pooled_standard_deviation=pooled,
                standardized_mean_difference=float(smd),
            )
        )
    return tuple(rows)


def build_categorical_shift_rows(
    contexts: pd.DataFrame,
) -> tuple[NoSupplyAlternateCategoricalShiftRow, ...]:
    rows: list[NoSupplyAlternateCategoricalShiftRow] = []
    prior_frame = contexts.loc[
        contexts["comparison_group"] == GROUP_PRIOR
    ]
    latest_frame = contexts.loc[
        contexts["comparison_group"] == GROUP_LATEST
    ]

    for dimension in CONTEXT_CATEGORICAL_DIMENSIONS:
        levels = sorted(
            set(prior_frame[dimension].astype(str))
            | set(latest_frame[dimension].astype(str))
        )
        for level in levels:
            prior_count = int((prior_frame[dimension] == level).sum())
            latest_count = int((latest_frame[dimension] == level).sum())
            prior_rate = prior_count / len(prior_frame)
            latest_rate = latest_count / len(latest_frame)
            rows.append(
                NoSupplyAlternateCategoricalShiftRow(
                    dimension=dimension,
                    level=level,
                    prior_count=prior_count,
                    prior_rate=prior_rate,
                    latest_count=latest_count,
                    latest_rate=latest_rate,
                    latest_minus_prior_rate_pp=(
                        (latest_rate - prior_rate) * 100.0
                    ),
                )
            )
    return tuple(rows)


def build_context_outcome_rows(
    *,
    contexts: pd.DataFrame,
    pair_outcomes: pd.DataFrame,
    horizons: Sequence[int] | Iterable[int] = (
        DEFAULT_CONTEXT_OUTCOME_HORIZONS
    ),
) -> tuple[NoSupplyAlternateContextOutcomeRow, ...]:
    selected_horizons = tuple(sorted({int(value) for value in horizons}))
    if not selected_horizons or any(value <= 0 for value in selected_horizons):
        raise ValueError("context outcome horizons must be positive")

    context_map = {
        (row.symbol, row.session): row
        for row in contexts.itertuples(index=False)
    }
    if len(context_map) != len(contexts):
        raise ValueError("context identities are not unique")

    pairs = pair_outcomes.copy()
    for dimension in CONTEXT_OUTCOME_DIMENSIONS:
        pairs[dimension] = [
            getattr(context_map[(symbol, session)], dimension)
            for symbol, session in zip(
                pairs["symbol"],
                pairs["target_session"],
                strict=False,
            )
        ]

    rows: list[NoSupplyAlternateContextOutcomeRow] = []
    for dimension in CONTEXT_OUTCOME_DIMENSIONS:
        for level in sorted(pairs[dimension].astype(str).unique()):
            target_ids = {
                (row.symbol, row.session)
                for row in contexts.loc[
                    contexts[dimension] == level
                ].itertuples(index=False)
            }
            source_target_count = len(target_ids)
            for horizon in selected_horizons:
                selected = pairs.loc[
                    (pairs[dimension] == level)
                    & (pairs["horizon_sessions"] == horizon)
                    & pairs["clean_pair"]
                ].copy()
                if selected.empty:
                    continue
                symbol_frame = selected.groupby("symbol", sort=True).agg(
                    return_delta=("paired_return_delta_pct", "mean"),
                    mfe_delta=("paired_mfe_delta_pct", "mean"),
                )
                rows.append(
                    NoSupplyAlternateContextOutcomeRow(
                        dimension=dimension,
                        level=str(level),
                        horizon_sessions=horizon,
                        source_target_count=source_target_count,
                        clean_pair_count=len(selected),
                        symbol_count=int(selected["symbol"].nunique()),
                        event_weighted_return_delta_pct=float(
                            selected["paired_return_delta_pct"].mean()
                        ),
                        symbol_normalized_return_delta_pct=float(
                            symbol_frame["return_delta"].mean()
                        ),
                        event_weighted_mfe_delta_pct=float(
                            selected["paired_mfe_delta_pct"].mean()
                        ),
                        symbol_normalized_mfe_delta_pct=float(
                            symbol_frame["mfe_delta"].mean()
                        ),
                    )
                )
    return tuple(rows)


def build_no_supply_alternate_context_profile_audit(
    *,
    sources: NoSupplyAlternateContextSources,
    contexts: Sequence[NoSupplyAlternateCandidateContext],
) -> NoSupplyAlternateContextProfileAudit:
    frame = pd.DataFrame([asdict(item) for item in contexts])
    if len(frame) != 305:
        raise ValueError("L12 requires exactly 305 context rows")
    if int((frame["comparison_group"] == GROUP_PRIOR).sum()) != 263:
        raise ValueError("L12 prior context count changed")
    if int((frame["comparison_group"] == GROUP_LATEST).sum()) != 42:
        raise ValueError("L12 latest context count changed")

    continuous = build_continuous_shift_rows(frame)
    categorical = build_categorical_shift_rows(frame)
    outcomes = build_context_outcome_rows(
        contexts=frame,
        pair_outcomes=sources.pair_outcomes,
    )

    return NoSupplyAlternateContextProfileAudit(
        audit_id=DAILY_NO_SUPPLY_ALTERNATE_CONTEXT_PROFILE_AUDIT_ID,
        source_lineage=sources.lineage,
        requested_symbol_count=int(frame["symbol"].nunique()),
        alternate_target_count=len(frame),
        prior_target_count=sources.prior_target_count,
        latest_target_count=sources.latest_target_count,
        context_row_count=len(frame),
        continuous_shift_rows=continuous,
        categorical_shift_rows=categorical,
        context_outcome_rows=outcomes,
    )


def write_no_supply_alternate_context_profile_audit(
    audit: NoSupplyAlternateContextProfileAudit,
    contexts: Sequence[NoSupplyAlternateCandidateContext],
    output_dir: str | Path,
) -> NoSupplyAlternateContextProfilePaths:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    paths = NoSupplyAlternateContextProfilePaths(
        summary_json=root / "daily_no_supply_alternate_context_summary.json",
        contexts_csv=root / "daily_no_supply_alternate_contexts.csv",
        continuous_shifts_csv=(
            root / "daily_no_supply_alternate_continuous_shifts.csv"
        ),
        categorical_shifts_csv=(
            root / "daily_no_supply_alternate_categorical_shifts.csv"
        ),
        context_outcomes_csv=(
            root / "daily_no_supply_alternate_context_outcomes.csv"
        ),
    )
    summary = {
        "audit_id": audit.audit_id,
        "requested_symbol_count": audit.requested_symbol_count,
        "alternate_target_count": audit.alternate_target_count,
        "prior_target_count": audit.prior_target_count,
        "latest_target_count": audit.latest_target_count,
        "context_row_count": audit.context_row_count,
        "continuous_shift_row_count": len(audit.continuous_shift_rows),
        "categorical_shift_row_count": len(audit.categorical_shift_rows),
        "context_outcome_row_count": len(audit.context_outcome_rows),
        "continuous_features": list(CONTEXT_CONTINUOUS_FEATURES),
        "categorical_dimensions": list(
            CONTEXT_CATEGORICAL_DIMENSIONS
        ),
        "outcome_dimensions": list(CONTEXT_OUTCOME_DIMENSIONS),
        "outcome_horizons": list(DEFAULT_CONTEXT_OUTCOME_HORIZONS),
        "source_lineage": asdict(audit.source_lineage),
        "is_actionable": False,
    }
    paths.summary_json.write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    pd.DataFrame([asdict(item) for item in contexts]).to_csv(
        paths.contexts_csv,
        index=False,
    )
    pd.DataFrame(
        [asdict(item) for item in audit.continuous_shift_rows]
    ).to_csv(paths.continuous_shifts_csv, index=False)
    pd.DataFrame(
        [asdict(item) for item in audit.categorical_shift_rows]
    ).to_csv(paths.categorical_shifts_csv, index=False)
    pd.DataFrame(
        [asdict(item) for item in audit.context_outcome_rows]
    ).to_csv(paths.context_outcomes_csv, index=False)
    return paths


__all__ = [
    "CONTEXT_CATEGORICAL_DIMENSIONS",
    "CONTEXT_CONTINUOUS_FEATURES",
    "CONTEXT_OUTCOME_DIMENSIONS",
    "DAILY_NO_SUPPLY_ALTERNATE_CONTEXT_PROFILE_AUDIT_ID",
    "DEFAULT_CONTEXT_OUTCOME_HORIZONS",
    "GROUP_LATEST",
    "GROUP_PRIOR",
    "NoSupplyAlternateCandidateContext",
    "NoSupplyAlternateCategoricalShiftRow",
    "NoSupplyAlternateContextOutcomeRow",
    "NoSupplyAlternateContextProfileAudit",
    "NoSupplyAlternateContextProfilePaths",
    "NoSupplyAlternateContextSourceLineage",
    "NoSupplyAlternateContextSources",
    "NoSupplyAlternateContinuousShiftRow",
    "build_candidate_contexts",
    "build_categorical_shift_rows",
    "build_context_outcome_rows",
    "build_continuous_shift_rows",
    "build_no_supply_alternate_context_profile_audit",
    "extract_candidate_context",
    "load_no_supply_alternate_context_sources",
    "write_no_supply_alternate_context_profile_audit",
]
