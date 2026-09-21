"""Matched same-environment outcome audit for NO_SUPPLY.

L8 estimates descriptive incremental lift of the NO_SUPPLY common signature
inside a fixed trend direction. Each L6 target is matched 1:1 to a nearby
same-symbol bearish control bar in the same trend environment that is not an
L6 common-signature bar.

Production behavior is not changed.
"""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Iterable, Iterator, Sequence

import pandas as pd

from audit.daily_event_no_supply_forward_outcomes import (
    COHORT_ALTERNATE,
    COHORT_CURRENT,
    DAILY_NO_SUPPLY_FORWARD_OUTCOME_AUDIT_ID,
    DEFAULT_FORWARD_HORIZONS,
    DEFAULT_FORWARD_PRICE_DISCONTINUITY_RATIO,
    l6_equivalent_session_frame,
    normalize_forward_horizons,
)
from audit.daily_event_no_supply_environment_replay import (
    DAILY_NO_SUPPLY_ENVIRONMENT_REPLAY_AUDIT_ID,
)
from audit.daily_input_reproducibility import (
    DailyAuditInputBundle,
    daily_audit_input_manifest_sha256,
    load_daily_audit_input,
    load_daily_audit_input_bundle,
)
from audit.offline_daily_evidence import (
    DEFAULT_DAILY_EVIDENCE_MIN_TARGET_INDEX,
    _metrics_input,
    _validate_daily_ohlcv,
)
from engine.columns import COL_CLOSE, COL_HIGH, COL_LOW, COL_OPEN
from market_structure.structure_filter import StructureFilter
from market_structure.swing_engine import SwingEngine
from metrics_engine import MetricsEngine
from trend import TrendAnalyzer


DAILY_NO_SUPPLY_MATCHED_ENVIRONMENT_AUDIT_ID = (
    "daily-event-no-supply-matched-environment-outcomes-v1"
)
DEFAULT_MAX_MATCH_DISTANCE_SESSIONS = 60


@dataclass(frozen=True, slots=True)
class NoSupplyMatchedSourceLineage:
    l7_audit_id: str
    l7_summary_sha256: str
    l7_event_outcomes_sha256: str
    l7_comparison_sha256: str
    l7_data_quality_sha256: str
    l6_audit_id: str
    l6_summary_sha256: str
    l6_observations_sha256: str
    snapshot_audit_id: str
    snapshot_manifest_sha256: str
    snapshot_basket_name: str
    snapshot_period: str
    snapshot_cutoff: str
    l5_audit_id: str
    l5_summary_sha256: str
    l5_correction_candidates_sha256: str
    l3_audit_id: str
    l3_summary_sha256: str
    l3_observations_sha256: str
    l1_summary_sha256: str
    l1_emissions_sha256: str
    l2_summary_sha256: str


@dataclass(frozen=True, slots=True)
class NoSupplyMatchedSources:
    lineage: NoSupplyMatchedSourceLineage
    bundle: DailyAuditInputBundle
    targets: pd.DataFrame
    common_signature_sessions: pd.DataFrame
    target_outcomes: pd.DataFrame
    current_target_count: int
    alternate_target_count: int


@dataclass(frozen=True, slots=True)
class NoSupplyMatchedControl:
    symbol: str
    cohort: str
    trend_direction: str
    target_session: str
    target_bar_index: int
    control_session: str
    control_bar_index: int
    distance_sessions: int
    control_trend_direction: str
    candidate_environment_replay_count: int


@dataclass(frozen=True, slots=True)
class NoSupplyUnmatchedTarget:
    symbol: str
    cohort: str
    trend_direction: str
    target_session: str
    target_bar_index: int
    reason: str
    max_match_distance_sessions: int


@dataclass(frozen=True, slots=True)
class NoSupplySymbolMatchSummary:
    symbol: str
    source_target_count: int
    matched_target_count: int
    unmatched_target_count: int
    candidate_environment_replay_count: int
    environment_cache_hit_count: int
    used_control_count: int


@dataclass(frozen=True, slots=True)
class NoSupplyMatchedPairOutcome:
    symbol: str
    cohort: str
    trend_direction: str
    target_session: str
    target_bar_index: int
    control_session: str
    control_bar_index: int
    distance_sessions: int
    horizon_sessions: int
    target_horizon_session: str
    control_horizon_session: str
    target_forward_return_pct: float
    control_forward_return_pct: float
    paired_return_delta_pct: float
    target_positive_close: bool
    control_positive_close: bool
    target_mfe_pct: float
    control_mfe_pct: float
    paired_mfe_delta_pct: float
    target_mae_pct: float
    control_mae_pct: float
    paired_mae_delta_pct: float
    target_price_discontinuity: bool
    control_price_discontinuity: bool
    clean_pair: bool
    control_max_single_session_price_move_pct: float


@dataclass(frozen=True, slots=True)
class NoSupplyMatchedCensoringRow:
    cohort: str
    horizon_sessions: int
    source_target_count: int
    matched_target_count: int
    unmatched_target_count: int
    target_complete_count: int
    target_censored_count: int
    pair_complete_count: int
    control_censored_count: int
    clean_pair_count: int
    discontinuity_pair_count: int


@dataclass(frozen=True, slots=True)
class NoSupplyMatchedOutcomeSummary:
    cohort: str
    horizon_sessions: int
    pair_count: int
    clean_pair_count: int
    symbol_count: int
    clean_symbol_count: int
    mean_target_return_pct: float
    mean_control_return_pct: float
    mean_paired_return_delta_pct: float
    median_paired_return_delta_pct: float
    target_positive_close_rate: float
    control_positive_close_rate: float
    positive_close_rate_delta: float
    mean_target_mfe_pct: float
    mean_control_mfe_pct: float
    mean_paired_mfe_delta_pct: float
    mean_target_mae_pct: float
    mean_control_mae_pct: float
    mean_paired_mae_delta_pct: float
    clean_mean_target_return_pct: float
    clean_mean_control_return_pct: float
    clean_mean_paired_return_delta_pct: float
    clean_median_paired_return_delta_pct: float
    clean_target_positive_close_rate: float
    clean_control_positive_close_rate: float
    clean_positive_close_rate_delta: float
    clean_mean_target_mfe_pct: float
    clean_mean_control_mfe_pct: float
    clean_mean_paired_mfe_delta_pct: float
    clean_mean_target_mae_pct: float
    clean_mean_control_mae_pct: float
    clean_mean_paired_mae_delta_pct: float
    clean_symbol_normalized_return_delta_pct: float
    clean_symbol_normalized_positive_rate_delta: float
    clean_symbol_normalized_mfe_delta_pct: float
    clean_symbol_normalized_mae_delta_pct: float


@dataclass(frozen=True, slots=True)
class NoSupplyMatchedSymbolOutcomeSummary:
    cohort: str
    horizon_sessions: int
    symbol: str
    clean_pair_count: int
    mean_paired_return_delta_pct: float
    positive_close_rate_delta: float
    mean_paired_mfe_delta_pct: float
    mean_paired_mae_delta_pct: float


@dataclass(frozen=True, slots=True)
class NoSupplyMatchedEnvironmentAudit:
    audit_id: str
    source_lineage: NoSupplyMatchedSourceLineage
    requested_symbol_count: int
    source_target_count: int
    current_source_target_count: int
    alternate_source_target_count: int
    common_signature_count: int
    max_match_distance_sessions: int
    min_target_index: int
    horizon_count: int
    horizons: tuple[int, ...]
    price_discontinuity_ratio: float
    matched_target_count: int
    unmatched_target_count: int
    match_rate: float
    pair_outcome_row_count: int
    controls: tuple[NoSupplyMatchedControl, ...]
    unmatched_targets: tuple[NoSupplyUnmatchedTarget, ...]
    symbol_match_rows: tuple[NoSupplySymbolMatchSummary, ...]
    pair_outcomes: tuple[NoSupplyMatchedPairOutcome, ...]
    censoring_rows: tuple[NoSupplyMatchedCensoringRow, ...]
    outcome_summary_rows: tuple[NoSupplyMatchedOutcomeSummary, ...]
    symbol_outcome_rows: tuple[NoSupplyMatchedSymbolOutcomeSummary, ...]

    @property
    def is_actionable(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class NoSupplyMatchedEnvironmentPaths:
    summary_json: Path
    controls_csv: Path
    unmatched_csv: Path
    symbol_match_csv: Path
    pair_outcomes_csv: Path
    censoring_csv: Path
    outcome_summary_csv: Path
    symbol_outcome_csv: Path

    def as_dict(self) -> dict[str, str]:
        return {
            "summary_json": str(self.summary_json),
            "controls_csv": str(self.controls_csv),
            "unmatched_csv": str(self.unmatched_csv),
            "symbol_match_csv": str(self.symbol_match_csv),
            "pair_outcomes_csv": str(self.pair_outcomes_csv),
            "censoring_csv": str(self.censoring_csv),
            "outcome_summary_csv": str(self.outcome_summary_csv),
            "symbol_outcome_csv": str(self.symbol_outcome_csv),
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
    raise ValueError(f"cannot parse boolean {value!r}")


def _validate_l7_summary(summary: dict[str, object]) -> None:
    if summary.get("audit_id") != DAILY_NO_SUPPLY_FORWARD_OUTCOME_AUDIT_ID:
        raise ValueError("unexpected L7 audit_id")
    if summary.get("is_actionable") is not False:
        raise ValueError("L8 requires non-actionable L7 source")
    if int(summary.get("requested_symbol_count", -1)) != 30:
        raise ValueError("L8 requires canonical 30-symbol L7 source")
    if int(summary.get("source_event_count", -1)) != 2509:
        raise ValueError("unexpected canonical L7 source event count")
    if int(summary.get("current_source_event_count", -1)) != 777:
        raise ValueError("unexpected canonical current L7 count")
    if int(summary.get("alternate_source_event_count", -1)) != 1732:
        raise ValueError("unexpected canonical alternate L7 count")
    if float(summary.get("price_discontinuity_ratio", -1.0)) != (
        DEFAULT_FORWARD_PRICE_DISCONTINUITY_RATIO
    ):
        raise ValueError("unexpected L7 discontinuity ratio")


def load_no_supply_matched_sources(
    *,
    forward_dir: str | Path,
    replay_dir: str | Path,
    input_snapshot_dir: str | Path,
    basket_name: str,
) -> NoSupplyMatchedSources:
    forward_root = Path(forward_dir)
    replay_root = Path(replay_dir)
    snapshot_root = Path(input_snapshot_dir)

    l7_summary_path = (
        forward_root / "daily_no_supply_forward_outcome_summary.json"
    )
    l7_outcomes_path = (
        forward_root / "daily_no_supply_forward_event_outcomes.csv"
    )
    l7_comparison_path = (
        forward_root / "daily_no_supply_forward_cohort_comparison.csv"
    )
    l7_quality_path = (
        forward_root / "daily_no_supply_forward_data_quality_summary.csv"
    )
    l6_summary_path = (
        replay_root / "daily_no_supply_environment_replay_summary.json"
    )
    l6_observations_path = (
        replay_root / "daily_no_supply_environment_observations.csv"
    )
    for path in (
        l7_summary_path,
        l7_outcomes_path,
        l7_comparison_path,
        l7_quality_path,
        l6_summary_path,
        l6_observations_path,
    ):
        if not path.exists():
            raise FileNotFoundError(path)

    l7_summary = json.loads(l7_summary_path.read_text(encoding="utf-8"))
    _validate_l7_summary(l7_summary)
    l7_lineage = l7_summary.get("source_lineage")
    if not isinstance(l7_lineage, dict):
        raise ValueError("L7 source lineage is missing")

    l6_summary_sha256 = _sha256_file(l6_summary_path)
    l6_observations_sha256 = _sha256_file(l6_observations_path)
    if str(l7_lineage.get("l6_summary_sha256", "")) != l6_summary_sha256:
        raise ValueError("L7 points to a different L6 summary")
    if (
        str(l7_lineage.get("l6_observations_sha256", ""))
        != l6_observations_sha256
    ):
        raise ValueError("L7 points to a different L6 observation ledger")

    l6_summary = json.loads(l6_summary_path.read_text(encoding="utf-8"))
    if (
        l6_summary.get("audit_id")
        != DAILY_NO_SUPPLY_ENVIRONMENT_REPLAY_AUDIT_ID
    ):
        raise ValueError("unexpected L6 audit_id")
    if l6_summary.get("is_actionable") is not False:
        raise ValueError("L8 requires non-actionable L6 source")
    if int(l6_summary.get("failed_symbol_count", -1)) != 0:
        raise ValueError("L8 requires zero-failure L6")
    if int(l6_summary.get("current_identity_mismatch_count", -1)) != 0:
        raise ValueError("L8 requires exact L6 identity parity")
    if int(l6_summary.get("current_bar_index_mismatch_count", -1)) != 0:
        raise ValueError("L8 requires exact L6 bar-index parity")

    bundle = load_daily_audit_input_bundle(snapshot_root)
    manifest_sha256 = daily_audit_input_manifest_sha256(snapshot_root)
    if bundle.basket_name != basket_name:
        raise ValueError("snapshot basket does not match requested basket")
    if bundle.symbol_count != int(l7_summary["requested_symbol_count"]):
        raise ValueError("snapshot symbol count does not match L7")
    if str(l7_lineage.get("snapshot_manifest_sha256", "")) != manifest_sha256:
        raise ValueError("snapshot manifest hash does not match L7 lineage")

    observations = pd.read_csv(l6_observations_path)
    required_l6 = {
        "symbol",
        "bar_index",
        "session",
        "trend_direction",
        "current_candidate",
        "alternate_candidate",
    }
    missing = sorted(required_l6 - set(observations.columns))
    if missing:
        raise ValueError(f"L6 observations missing columns: {missing}")
    observations = observations.copy()
    observations["symbol"] = observations["symbol"].map(
        lambda value: str(value).strip().upper()
    )
    observations["session"] = observations["session"].map(_normalize_session)
    observations["current_candidate"] = observations["current_candidate"].map(
        _parse_bool
    )
    observations["alternate_candidate"] = observations[
        "alternate_candidate"
    ].map(_parse_bool)
    if observations[["symbol", "session"]].duplicated().any():
        raise ValueError("L6 common-signature identities are not unique")
    if len(observations) != int(l6_summary["common_signature_count"]):
        raise ValueError("L6 common-signature count does not reconcile")

    current = observations.loc[observations["current_candidate"]].copy()
    alternate = observations.loc[observations["alternate_candidate"]].copy()
    if len(current) != 777 or len(alternate) != 1732:
        raise ValueError("L6 target populations do not match canonical counts")
    if not (current["trend_direction"] == "DOWN").all():
        raise ValueError("current L8 targets must be DOWN environment")
    if not (alternate["trend_direction"] == "UP").all():
        raise ValueError("alternate L8 targets must be UP environment")
    current["cohort"] = COHORT_CURRENT
    alternate["cohort"] = COHORT_ALTERNATE
    targets = (
        pd.concat([current, alternate], ignore_index=True)
        .loc[
            :,
            ["symbol", "bar_index", "session", "trend_direction", "cohort"],
        ]
        .sort_values(["symbol", "bar_index", "cohort"])
        .reset_index(drop=True)
    )

    target_outcomes = pd.read_csv(l7_outcomes_path)
    required_l7 = {
        "symbol",
        "session",
        "bar_index",
        "cohort",
        "horizon_sessions",
        "horizon_session",
        "forward_close_return_pct",
        "max_favorable_excursion_pct",
        "max_adverse_excursion_pct",
        "positive_close",
        "price_discontinuity_in_event_or_window",
    }
    missing_l7 = sorted(required_l7 - set(target_outcomes.columns))
    if missing_l7:
        raise ValueError(f"L7 outcomes missing columns: {missing_l7}")
    target_outcomes = target_outcomes.copy()
    target_outcomes["symbol"] = target_outcomes["symbol"].map(
        lambda value: str(value).strip().upper()
    )
    target_outcomes["session"] = target_outcomes["session"].map(
        _normalize_session
    )
    target_outcomes["horizon_session"] = target_outcomes[
        "horizon_session"
    ].map(_normalize_session)
    target_outcomes["positive_close"] = target_outcomes[
        "positive_close"
    ].map(_parse_bool)
    target_outcomes["price_discontinuity_in_event_or_window"] = (
        target_outcomes["price_discontinuity_in_event_or_window"].map(
            _parse_bool
        )
    )
    if target_outcomes[
        ["symbol", "session", "cohort", "horizon_sessions"]
    ].duplicated().any():
        raise ValueError("L7 outcome identities are not unique")

    lineage = NoSupplyMatchedSourceLineage(
        l7_audit_id=str(l7_summary["audit_id"]),
        l7_summary_sha256=_sha256_file(l7_summary_path),
        l7_event_outcomes_sha256=_sha256_file(l7_outcomes_path),
        l7_comparison_sha256=_sha256_file(l7_comparison_path),
        l7_data_quality_sha256=_sha256_file(l7_quality_path),
        l6_audit_id=str(l6_summary["audit_id"]),
        l6_summary_sha256=l6_summary_sha256,
        l6_observations_sha256=l6_observations_sha256,
        snapshot_audit_id=bundle.audit_id,
        snapshot_manifest_sha256=manifest_sha256,
        snapshot_basket_name=bundle.basket_name,
        snapshot_period=bundle.period,
        snapshot_cutoff=bundle.cutoff,
        l5_audit_id=str(l7_lineage["l5_audit_id"]),
        l5_summary_sha256=str(l7_lineage["l5_summary_sha256"]),
        l5_correction_candidates_sha256=str(
            l7_lineage["l5_correction_candidates_sha256"]
        ),
        l3_audit_id=str(l7_lineage["l3_audit_id"]),
        l3_summary_sha256=str(l7_lineage["l3_summary_sha256"]),
        l3_observations_sha256=str(l7_lineage["l3_observations_sha256"]),
        l1_summary_sha256=str(l7_lineage["l1_summary_sha256"]),
        l1_emissions_sha256=str(l7_lineage["l1_emissions_sha256"]),
        l2_summary_sha256=str(l7_lineage["l2_summary_sha256"]),
    )
    return NoSupplyMatchedSources(
        lineage=lineage,
        bundle=bundle,
        targets=targets,
        common_signature_sessions=observations[
            ["symbol", "session", "bar_index"]
        ].copy(),
        target_outcomes=target_outcomes,
        current_target_count=len(current),
        alternate_target_count=len(alternate),
    )


def subset_no_supply_matched_sources(
    sources: NoSupplyMatchedSources,
    symbols: Sequence[str] | Iterable[str],
) -> NoSupplyMatchedSources:
    selected = tuple(
        str(symbol).strip().upper()
        for symbol in symbols
        if str(symbol).strip()
    )
    if not selected or len(selected) != len(set(selected)):
        raise ValueError("selected symbols must be non-empty and unique")
    available = set(sources.targets["symbol"])
    missing = sorted(set(selected) - available)
    if missing:
        raise ValueError(f"selected symbols are absent from L8 targets: {missing}")

    targets = sources.targets.loc[
        sources.targets["symbol"].isin(selected)
    ].copy()
    common = sources.common_signature_sessions.loc[
        sources.common_signature_sessions["symbol"].isin(selected)
    ].copy()
    outcomes = sources.target_outcomes.loc[
        sources.target_outcomes["symbol"].isin(selected)
    ].copy()
    return NoSupplyMatchedSources(
        lineage=sources.lineage,
        bundle=sources.bundle,
        targets=targets,
        common_signature_sessions=common,
        target_outcomes=outcomes,
        current_target_count=int(
            (targets["cohort"] == COHORT_CURRENT).sum()
        ),
        alternate_target_count=int(
            (targets["cohort"] == COHORT_ALTERNATE).sum()
        ),
    )


@contextmanager
def _suppress_vsa_info_logs() -> Iterator[None]:
    logger = logging.getLogger("VSA")
    previous = logger.level
    logger.setLevel(logging.WARNING)
    try:
        yield
    finally:
        logger.setLevel(previous)


def replay_environment_direction(
    daily_prefix: pd.DataFrame,
) -> str:
    """Return exact L6 trend-environment direction for one target prefix."""

    _validate_daily_ohlcv(daily_prefix)
    metrics = MetricsEngine().calculate(_metrics_input(daily_prefix))
    swings = SwingEngine().calculate(metrics)
    structural = StructureFilter().filter(list(swings), metrics)
    trend = TrendAnalyzer().analyze_from_swings(
        metrics,
        swings,
        structural_swings=structural,
    )
    return trend.structure.direction.name


def _raw_bearish(row: pd.Series) -> bool:
    return float(row[COL_CLOSE]) < float(row[COL_OPEN])


def match_symbol_controls(
    *,
    symbol: str,
    daily: pd.DataFrame,
    targets: pd.DataFrame,
    common_signature_sessions: pd.DataFrame,
    max_match_distance_sessions: int = DEFAULT_MAX_MATCH_DISTANCE_SESSIONS,
    min_target_index: int = DEFAULT_DAILY_EVIDENCE_MIN_TARGET_INDEX,
) -> tuple[
    tuple[NoSupplyMatchedControl, ...],
    tuple[NoSupplyUnmatchedTarget, ...],
    NoSupplySymbolMatchSummary,
]:
    clean_symbol = str(symbol).strip().upper()
    if max_match_distance_sessions < 1:
        raise ValueError("max_match_distance_sessions must be positive")
    if min_target_index < 0:
        raise ValueError("min_target_index cannot be negative")

    session_daily = l6_equivalent_session_frame(daily)
    symbol_targets = (
        targets.loc[targets["symbol"] == clean_symbol]
        .sort_values(["bar_index", "cohort"])
        .reset_index(drop=True)
    )
    common = common_signature_sessions.loc[
        common_signature_sessions["symbol"] == clean_symbol
    ]
    common_sessions = {
        _normalize_session(value) for value in common["session"].tolist()
    }
    session_to_position = {
        _normalize_session(session): index
        for index, session in enumerate(session_daily.index)
    }

    used_controls: set[int] = set()
    environment_cache: dict[int, str] = {}
    replay_count = 0
    cache_hits = 0
    controls: list[NoSupplyMatchedControl] = []
    unmatched: list[NoSupplyUnmatchedTarget] = []

    def direction_at(position: int) -> str:
        nonlocal replay_count, cache_hits
        if position in environment_cache:
            cache_hits += 1
            return environment_cache[position]
        prefix = session_daily.iloc[: position + 1].copy()
        direction = replay_environment_direction(prefix)
        environment_cache[position] = direction
        replay_count += 1
        return direction

    with _suppress_vsa_info_logs():
        for target in symbol_targets.itertuples(index=False):
            target_session = _normalize_session(target.session)
            if target_session not in session_to_position:
                raise ValueError(
                    f"{clean_symbol} target session missing from snapshot: "
                    f"{target_session}"
                )
            target_position = session_to_position[target_session]
            if int(target.bar_index) != target_position:
                raise ValueError(
                    f"{clean_symbol} target index drift at {target_session}: "
                    f"{target.bar_index} != {target_position}"
                )

            expected_direction = str(target.trend_direction)
            replay_count_before_target = replay_count
            selected: tuple[int, int, str] | None = None
            for distance in range(1, max_match_distance_sessions + 1):
                for candidate_position in (
                    target_position - distance,
                    target_position + distance,
                ):
                    if candidate_position < min_target_index:
                        continue
                    if candidate_position >= len(session_daily):
                        continue
                    if candidate_position in used_controls:
                        continue
                    candidate_session = _normalize_session(
                        session_daily.index[candidate_position]
                    )
                    if candidate_session in common_sessions:
                        continue
                    if not _raw_bearish(
                        session_daily.iloc[candidate_position]
                    ):
                        continue
                    direction = direction_at(candidate_position)
                    if direction != expected_direction:
                        continue
                    selected = (
                        candidate_position,
                        distance,
                        direction,
                    )
                    break
                if selected is not None:
                    break

            if selected is None:
                unmatched.append(
                    NoSupplyUnmatchedTarget(
                        symbol=clean_symbol,
                        cohort=str(target.cohort),
                        trend_direction=expected_direction,
                        target_session=target_session,
                        target_bar_index=target_position,
                        reason="NO_SAME_ENVIRONMENT_CONTROL_WITHIN_DISTANCE",
                        max_match_distance_sessions=(
                            max_match_distance_sessions
                        ),
                    )
                )
                continue

            control_position, distance, direction = selected
            used_controls.add(control_position)
            controls.append(
                NoSupplyMatchedControl(
                    symbol=clean_symbol,
                    cohort=str(target.cohort),
                    trend_direction=expected_direction,
                    target_session=target_session,
                    target_bar_index=target_position,
                    control_session=_normalize_session(
                        session_daily.index[control_position]
                    ),
                    control_bar_index=control_position,
                    distance_sessions=distance,
                    control_trend_direction=direction,
                    candidate_environment_replay_count=(
                        replay_count - replay_count_before_target
                    ),
                )
            )

    summary = NoSupplySymbolMatchSummary(
        symbol=clean_symbol,
        source_target_count=len(symbol_targets),
        matched_target_count=len(controls),
        unmatched_target_count=len(unmatched),
        candidate_environment_replay_count=replay_count,
        environment_cache_hit_count=cache_hits,
        used_control_count=len(used_controls),
    )
    return tuple(controls), tuple(unmatched), summary


def _max_single_session_price_move_pct(
    session_daily: pd.DataFrame,
    *,
    start_position: int,
    end_position: int,
) -> float:
    if start_position < 1:
        raise ValueError("control outcome requires prior session")
    window = session_daily.iloc[start_position : end_position + 1]
    previous_close = pd.Series(
        [
            float(session_daily.iloc[start_position - 1][COL_CLOSE]),
            *[float(value) for value in window[COL_CLOSE].iloc[:-1]],
        ],
        index=window.index,
        dtype=float,
    )
    maxima: list[float] = []
    for column in (COL_OPEN, COL_HIGH, COL_LOW, COL_CLOSE):
        move = (
            (window[column].astype(float) / previous_close - 1.0)
            .abs()
            * 100.0
        )
        maxima.append(float(move.max()))
    return max(maxima)


def _control_outcome(
    session_daily: pd.DataFrame,
    *,
    position: int,
    horizon: int,
    price_discontinuity_ratio: float,
) -> dict[str, object] | None:
    end_position = position + horizon
    if end_position >= len(session_daily):
        return None
    event_close = float(session_daily.iloc[position][COL_CLOSE])
    if event_close <= 0.0:
        raise ValueError("control event close must be positive")
    future = session_daily.iloc[position + 1 : end_position + 1]
    horizon_close = float(session_daily.iloc[end_position][COL_CLOSE])
    forward_return = (horizon_close / event_close - 1.0) * 100.0
    mfe = max(
        0.0,
        (float(future[COL_HIGH].max()) / event_close - 1.0) * 100.0,
    )
    mae = min(
        0.0,
        (float(future[COL_LOW].min()) / event_close - 1.0) * 100.0,
    )
    max_move = _max_single_session_price_move_pct(
        session_daily,
        start_position=position,
        end_position=end_position,
    )
    return {
        "horizon_session": _normalize_session(
            session_daily.index[end_position]
        ),
        "forward_return_pct": forward_return,
        "positive_close": forward_return > 0.0,
        "mfe_pct": mfe,
        "mae_pct": mae,
        "max_move_pct": max_move,
        "discontinuity": (
            max_move >= price_discontinuity_ratio * 100.0
        ),
    }


def build_matched_pair_outcomes(
    *,
    controls: Sequence[NoSupplyMatchedControl],
    sources: NoSupplyMatchedSources,
    input_snapshot_dir: str | Path,
    horizons: Sequence[int] | Iterable[int] = DEFAULT_FORWARD_HORIZONS,
    price_discontinuity_ratio: float = (
        DEFAULT_FORWARD_PRICE_DISCONTINUITY_RATIO
    ),
) -> tuple[
    tuple[NoSupplyMatchedPairOutcome, ...],
    tuple[NoSupplyMatchedCensoringRow, ...],
]:
    selected_horizons = normalize_forward_horizons(horizons)
    if not 0.0 < price_discontinuity_ratio < 1.0:
        raise ValueError("price_discontinuity_ratio must be between 0 and 1")

    by_symbol: dict[str, list[NoSupplyMatchedControl]] = {}
    for control in controls:
        by_symbol.setdefault(control.symbol, []).append(control)

    outcome_rows: list[NoSupplyMatchedPairOutcome] = []
    counters: dict[tuple[str, int], dict[str, int]] = {
        (cohort, horizon): {
            "source": int(
                (
                    sources.targets["cohort"] == cohort
                ).sum()
            ),
            "matched": sum(
                item.cohort == cohort for item in controls
            ),
            "target_complete": 0,
            "pair_complete": 0,
            "control_censored": 0,
            "clean": 0,
            "discontinuity": 0,
        }
        for cohort in (COHORT_CURRENT, COHORT_ALTERNATE)
        for horizon in selected_horizons
    }

    for symbol, symbol_controls in by_symbol.items():
        daily = load_daily_audit_input(input_snapshot_dir, symbol)
        session_daily = l6_equivalent_session_frame(daily)
        target_outcomes = sources.target_outcomes.loc[
            sources.target_outcomes["symbol"] == symbol
        ]

        for control in symbol_controls:
            control_position = control.control_bar_index
            for horizon in selected_horizons:
                key = (control.cohort, horizon)
                target_rows = target_outcomes.loc[
                    (
                        target_outcomes["session"]
                        == control.target_session
                    )
                    & (
                        target_outcomes["cohort"]
                        == control.cohort
                    )
                    & (
                        target_outcomes["horizon_sessions"]
                        == horizon
                    )
                ]
                if target_rows.empty:
                    continue
                if len(target_rows) != 1:
                    raise ValueError("target outcome identity is not unique")
                counters[key]["target_complete"] += 1

                control_outcome = _control_outcome(
                    session_daily,
                    position=control_position,
                    horizon=horizon,
                    price_discontinuity_ratio=price_discontinuity_ratio,
                )
                if control_outcome is None:
                    counters[key]["control_censored"] += 1
                    continue

                target = target_rows.iloc[0]
                target_discontinuity = _parse_bool(
                    target[
                        "price_discontinuity_in_event_or_window"
                    ]
                )
                control_discontinuity = bool(
                    control_outcome["discontinuity"]
                )
                clean_pair = (
                    not target_discontinuity
                    and not control_discontinuity
                )
                counters[key]["pair_complete"] += 1
                if clean_pair:
                    counters[key]["clean"] += 1
                else:
                    counters[key]["discontinuity"] += 1

                target_return = float(
                    target["forward_close_return_pct"]
                )
                control_return = float(
                    control_outcome["forward_return_pct"]
                )
                target_mfe = float(
                    target["max_favorable_excursion_pct"]
                )
                control_mfe = float(control_outcome["mfe_pct"])
                target_mae = float(
                    target["max_adverse_excursion_pct"]
                )
                control_mae = float(control_outcome["mae_pct"])
                outcome_rows.append(
                    NoSupplyMatchedPairOutcome(
                        symbol=symbol,
                        cohort=control.cohort,
                        trend_direction=control.trend_direction,
                        target_session=control.target_session,
                        target_bar_index=control.target_bar_index,
                        control_session=control.control_session,
                        control_bar_index=control.control_bar_index,
                        distance_sessions=control.distance_sessions,
                        horizon_sessions=horizon,
                        target_horizon_session=_normalize_session(
                            target["horizon_session"]
                        ),
                        control_horizon_session=str(
                            control_outcome["horizon_session"]
                        ),
                        target_forward_return_pct=target_return,
                        control_forward_return_pct=control_return,
                        paired_return_delta_pct=(
                            target_return - control_return
                        ),
                        target_positive_close=_parse_bool(
                            target["positive_close"]
                        ),
                        control_positive_close=bool(
                            control_outcome["positive_close"]
                        ),
                        target_mfe_pct=target_mfe,
                        control_mfe_pct=control_mfe,
                        paired_mfe_delta_pct=(
                            target_mfe - control_mfe
                        ),
                        target_mae_pct=target_mae,
                        control_mae_pct=control_mae,
                        paired_mae_delta_pct=(
                            target_mae - control_mae
                        ),
                        target_price_discontinuity=(
                            target_discontinuity
                        ),
                        control_price_discontinuity=(
                            control_discontinuity
                        ),
                        clean_pair=clean_pair,
                        control_max_single_session_price_move_pct=float(
                            control_outcome["max_move_pct"]
                        ),
                    )
                )

    censoring_rows: list[NoSupplyMatchedCensoringRow] = []
    matched_by_cohort = {
        cohort: sum(item.cohort == cohort for item in controls)
        for cohort in (COHORT_CURRENT, COHORT_ALTERNATE)
    }
    for horizon in selected_horizons:
        for cohort in (COHORT_CURRENT, COHORT_ALTERNATE):
            item = counters[(cohort, horizon)]
            matched = matched_by_cohort[cohort]
            if item["matched"] != matched:
                raise RuntimeError("matched counter drift")
            target_censored = matched - item["target_complete"]
            censoring_rows.append(
                NoSupplyMatchedCensoringRow(
                    cohort=cohort,
                    horizon_sessions=horizon,
                    source_target_count=item["source"],
                    matched_target_count=matched,
                    unmatched_target_count=(
                        item["source"] - matched
                    ),
                    target_complete_count=item["target_complete"],
                    target_censored_count=target_censored,
                    pair_complete_count=item["pair_complete"],
                    control_censored_count=item["control_censored"],
                    clean_pair_count=item["clean"],
                    discontinuity_pair_count=item["discontinuity"],
                )
            )

    return (
        tuple(
            sorted(
                outcome_rows,
                key=lambda item: (
                    item.cohort,
                    item.symbol,
                    item.target_bar_index,
                    item.horizon_sessions,
                ),
            )
        ),
        tuple(censoring_rows),
    )


def build_matched_outcome_summaries(
    pair_outcomes: Sequence[NoSupplyMatchedPairOutcome],
    *,
    horizons: Sequence[int] | Iterable[int],
) -> tuple[
    tuple[NoSupplyMatchedOutcomeSummary, ...],
    tuple[NoSupplyMatchedSymbolOutcomeSummary, ...],
]:
    selected_horizons = normalize_forward_horizons(horizons)
    frame = pd.DataFrame([asdict(item) for item in pair_outcomes])
    if frame.empty:
        raise ValueError("matched pair outcome ledger cannot be empty")

    summary_rows: list[NoSupplyMatchedOutcomeSummary] = []
    symbol_rows: list[NoSupplyMatchedSymbolOutcomeSummary] = []

    for horizon in selected_horizons:
        for cohort in (COHORT_CURRENT, COHORT_ALTERNATE):
            selected = frame.loc[
                (frame["cohort"] == cohort)
                & (frame["horizon_sessions"] == horizon)
            ]
            if selected.empty:
                raise ValueError(
                    f"no matched outcomes for {cohort} horizon {horizon}"
                )
            clean = selected.loc[selected["clean_pair"]]
            if clean.empty:
                raise ValueError(
                    f"no clean matched outcomes for {cohort} horizon {horizon}"
                )

            symbol_clean = clean.groupby("symbol", sort=True).agg(
                return_delta=("paired_return_delta_pct", "mean"),
                target_positive=("target_positive_close", "mean"),
                control_positive=("control_positive_close", "mean"),
                mfe_delta=("paired_mfe_delta_pct", "mean"),
                mae_delta=("paired_mae_delta_pct", "mean"),
            )
            for symbol, row in symbol_clean.iterrows():
                symbol_rows.append(
                    NoSupplyMatchedSymbolOutcomeSummary(
                        cohort=cohort,
                        horizon_sessions=horizon,
                        symbol=str(symbol),
                        clean_pair_count=int(
                            (
                                clean["symbol"] == symbol
                            ).sum()
                        ),
                        mean_paired_return_delta_pct=float(
                            row["return_delta"]
                        ),
                        positive_close_rate_delta=float(
                            row["target_positive"]
                            - row["control_positive"]
                        ),
                        mean_paired_mfe_delta_pct=float(
                            row["mfe_delta"]
                        ),
                        mean_paired_mae_delta_pct=float(
                            row["mae_delta"]
                        ),
                    )
                )

            summary_rows.append(
                NoSupplyMatchedOutcomeSummary(
                    cohort=cohort,
                    horizon_sessions=horizon,
                    pair_count=len(selected),
                    clean_pair_count=len(clean),
                    symbol_count=int(selected["symbol"].nunique()),
                    clean_symbol_count=int(clean["symbol"].nunique()),
                    mean_target_return_pct=float(
                        selected["target_forward_return_pct"].mean()
                    ),
                    mean_control_return_pct=float(
                        selected["control_forward_return_pct"].mean()
                    ),
                    mean_paired_return_delta_pct=float(
                        selected["paired_return_delta_pct"].mean()
                    ),
                    median_paired_return_delta_pct=float(
                        selected["paired_return_delta_pct"].median()
                    ),
                    target_positive_close_rate=float(
                        selected["target_positive_close"].mean()
                    ),
                    control_positive_close_rate=float(
                        selected["control_positive_close"].mean()
                    ),
                    positive_close_rate_delta=float(
                        selected["target_positive_close"].mean()
                        - selected["control_positive_close"].mean()
                    ),
                    mean_target_mfe_pct=float(
                        selected["target_mfe_pct"].mean()
                    ),
                    mean_control_mfe_pct=float(
                        selected["control_mfe_pct"].mean()
                    ),
                    mean_paired_mfe_delta_pct=float(
                        selected["paired_mfe_delta_pct"].mean()
                    ),
                    mean_target_mae_pct=float(
                        selected["target_mae_pct"].mean()
                    ),
                    mean_control_mae_pct=float(
                        selected["control_mae_pct"].mean()
                    ),
                    mean_paired_mae_delta_pct=float(
                        selected["paired_mae_delta_pct"].mean()
                    ),
                    clean_mean_target_return_pct=float(
                        clean["target_forward_return_pct"].mean()
                    ),
                    clean_mean_control_return_pct=float(
                        clean["control_forward_return_pct"].mean()
                    ),
                    clean_mean_paired_return_delta_pct=float(
                        clean["paired_return_delta_pct"].mean()
                    ),
                    clean_median_paired_return_delta_pct=float(
                        clean["paired_return_delta_pct"].median()
                    ),
                    clean_target_positive_close_rate=float(
                        clean["target_positive_close"].mean()
                    ),
                    clean_control_positive_close_rate=float(
                        clean["control_positive_close"].mean()
                    ),
                    clean_positive_close_rate_delta=float(
                        clean["target_positive_close"].mean()
                        - clean["control_positive_close"].mean()
                    ),
                    clean_mean_target_mfe_pct=float(
                        clean["target_mfe_pct"].mean()
                    ),
                    clean_mean_control_mfe_pct=float(
                        clean["control_mfe_pct"].mean()
                    ),
                    clean_mean_paired_mfe_delta_pct=float(
                        clean["paired_mfe_delta_pct"].mean()
                    ),
                    clean_mean_target_mae_pct=float(
                        clean["target_mae_pct"].mean()
                    ),
                    clean_mean_control_mae_pct=float(
                        clean["control_mae_pct"].mean()
                    ),
                    clean_mean_paired_mae_delta_pct=float(
                        clean["paired_mae_delta_pct"].mean()
                    ),
                    clean_symbol_normalized_return_delta_pct=float(
                        symbol_clean["return_delta"].mean()
                    ),
                    clean_symbol_normalized_positive_rate_delta=float(
                        (
                            symbol_clean["target_positive"]
                            - symbol_clean["control_positive"]
                        ).mean()
                    ),
                    clean_symbol_normalized_mfe_delta_pct=float(
                        symbol_clean["mfe_delta"].mean()
                    ),
                    clean_symbol_normalized_mae_delta_pct=float(
                        symbol_clean["mae_delta"].mean()
                    ),
                )
            )

    return tuple(summary_rows), tuple(symbol_rows)


def build_no_supply_matched_environment_audit(
    *,
    sources: NoSupplyMatchedSources,
    controls: Sequence[NoSupplyMatchedControl],
    unmatched_targets: Sequence[NoSupplyUnmatchedTarget],
    symbol_match_rows: Sequence[NoSupplySymbolMatchSummary],
    input_snapshot_dir: str | Path,
    max_match_distance_sessions: int,
    min_target_index: int = DEFAULT_DAILY_EVIDENCE_MIN_TARGET_INDEX,
    horizons: Sequence[int] | Iterable[int] = DEFAULT_FORWARD_HORIZONS,
    price_discontinuity_ratio: float = (
        DEFAULT_FORWARD_PRICE_DISCONTINUITY_RATIO
    ),
) -> NoSupplyMatchedEnvironmentAudit:
    selected_horizons = normalize_forward_horizons(horizons)
    source_target_count = len(sources.targets)
    if (
        sources.current_target_count
        + sources.alternate_target_count
        != source_target_count
    ):
        raise ValueError("L8 target cohort counts do not reconcile")
    if len(controls) + len(unmatched_targets) != source_target_count:
        raise ValueError("matched + unmatched targets do not reconcile")

    source_target_map = {
        (
            str(row.symbol),
            _normalize_session(row.session),
        ): (
            str(row.cohort),
            str(row.trend_direction),
            int(row.bar_index),
        )
        for row in sources.targets.itertuples(index=False)
    }
    if len(source_target_map) != source_target_count:
        raise ValueError("L8 source target identities are not unique")

    common_ids = {
        (
            str(row.symbol),
            _normalize_session(row.session),
        )
        for row in sources.common_signature_sessions.itertuples(
            index=False
        )
    }
    identities = {
        (item.symbol, item.target_session) for item in controls
    }
    if len(identities) != len(controls):
        raise ValueError("a target was matched more than once")
    unmatched_ids = {
        (item.symbol, item.target_session)
        for item in unmatched_targets
    }
    if len(unmatched_ids) != len(unmatched_targets):
        raise ValueError("an unmatched target was duplicated")
    if identities & unmatched_ids:
        raise ValueError("a target is both matched and unmatched")
    if identities | unmatched_ids != set(source_target_map):
        raise ValueError("matched target coverage does not equal L8 source")

    control_ids = {
        (item.symbol, item.control_session) for item in controls
    }
    if len(control_ids) != len(controls):
        raise ValueError("a control was reused")
    if control_ids & common_ids:
        raise ValueError("a matched control is an L6 common-signature bar")

    for item in controls:
        key = (item.symbol, item.target_session)
        expected_cohort, expected_direction, expected_index = (
            source_target_map[key]
        )
        if item.cohort != expected_cohort:
            raise ValueError("matched control cohort drift")
        if item.trend_direction != expected_direction:
            raise ValueError("matched target trend direction drift")
        if item.control_trend_direction != expected_direction:
            raise ValueError("control environment does not match target")
        if item.target_bar_index != expected_index:
            raise ValueError("matched target bar index drift")
        if not 1 <= item.distance_sessions <= max_match_distance_sessions:
            raise ValueError("matched control distance is outside contract")

    expected_symbols = set(sources.targets["symbol"])
    rows_by_symbol = {item.symbol: item for item in symbol_match_rows}
    if len(rows_by_symbol) != len(symbol_match_rows):
        raise ValueError("symbol match summaries contain duplicates")
    if set(rows_by_symbol) != expected_symbols:
        raise ValueError("symbol match summaries do not cover source symbols")
    for symbol, row in rows_by_symbol.items():
        source_count = int(
            (sources.targets["symbol"] == symbol).sum()
        )
        matched_count = sum(
            item.symbol == symbol for item in controls
        )
        unmatched_count = sum(
            item.symbol == symbol for item in unmatched_targets
        )
        if row.source_target_count != source_count:
            raise ValueError(f"{symbol} source target count drift")
        if row.matched_target_count != matched_count:
            raise ValueError(f"{symbol} matched target count drift")
        if row.unmatched_target_count != unmatched_count:
            raise ValueError(f"{symbol} unmatched target count drift")
        if matched_count + unmatched_count != source_count:
            raise ValueError(f"{symbol} target accounting does not close")

    pair_outcomes, censoring_rows = build_matched_pair_outcomes(
        controls=controls,
        sources=sources,
        input_snapshot_dir=input_snapshot_dir,
        horizons=selected_horizons,
        price_discontinuity_ratio=price_discontinuity_ratio,
    )
    outcome_summary_rows, symbol_outcome_rows = (
        build_matched_outcome_summaries(
            pair_outcomes,
            horizons=selected_horizons,
        )
    )

    return NoSupplyMatchedEnvironmentAudit(
        audit_id=DAILY_NO_SUPPLY_MATCHED_ENVIRONMENT_AUDIT_ID,
        source_lineage=sources.lineage,
        requested_symbol_count=int(sources.targets["symbol"].nunique()),
        source_target_count=source_target_count,
        current_source_target_count=sources.current_target_count,
        alternate_source_target_count=sources.alternate_target_count,
        common_signature_count=len(sources.common_signature_sessions),
        max_match_distance_sessions=max_match_distance_sessions,
        min_target_index=min_target_index,
        horizon_count=len(selected_horizons),
        horizons=selected_horizons,
        price_discontinuity_ratio=price_discontinuity_ratio,
        matched_target_count=len(controls),
        unmatched_target_count=len(unmatched_targets),
        match_rate=len(controls) / source_target_count,
        pair_outcome_row_count=len(pair_outcomes),
        controls=tuple(controls),
        unmatched_targets=tuple(unmatched_targets),
        symbol_match_rows=tuple(symbol_match_rows),
        pair_outcomes=pair_outcomes,
        censoring_rows=censoring_rows,
        outcome_summary_rows=outcome_summary_rows,
        symbol_outcome_rows=symbol_outcome_rows,
    )


def write_no_supply_matched_environment_audit(
    audit: NoSupplyMatchedEnvironmentAudit,
    output_dir: str | Path,
) -> NoSupplyMatchedEnvironmentPaths:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    paths = NoSupplyMatchedEnvironmentPaths(
        summary_json=root / "daily_no_supply_matched_summary.json",
        controls_csv=root / "daily_no_supply_matched_controls.csv",
        unmatched_csv=root / "daily_no_supply_matched_unmatched.csv",
        symbol_match_csv=root / "daily_no_supply_matched_symbols.csv",
        pair_outcomes_csv=root / "daily_no_supply_matched_pair_outcomes.csv",
        censoring_csv=root / "daily_no_supply_matched_censoring.csv",
        outcome_summary_csv=(
            root / "daily_no_supply_matched_outcome_summary.csv"
        ),
        symbol_outcome_csv=(
            root / "daily_no_supply_matched_symbol_outcomes.csv"
        ),
    )
    summary = {
        "audit_id": audit.audit_id,
        "requested_symbol_count": audit.requested_symbol_count,
        "source_target_count": audit.source_target_count,
        "current_source_target_count": audit.current_source_target_count,
        "alternate_source_target_count": audit.alternate_source_target_count,
        "common_signature_count": audit.common_signature_count,
        "max_match_distance_sessions": audit.max_match_distance_sessions,
        "min_target_index": audit.min_target_index,
        "horizon_count": audit.horizon_count,
        "horizons": list(audit.horizons),
        "price_discontinuity_ratio": audit.price_discontinuity_ratio,
        "matched_target_count": audit.matched_target_count,
        "unmatched_target_count": audit.unmatched_target_count,
        "match_rate": audit.match_rate,
        "pair_outcome_row_count": audit.pair_outcome_row_count,
        "censoring_row_count": len(audit.censoring_rows),
        "outcome_summary_row_count": len(audit.outcome_summary_rows),
        "symbol_outcome_row_count": len(audit.symbol_outcome_rows),
        "source_lineage": asdict(audit.source_lineage),
        "is_actionable": False,
    }
    paths.summary_json.write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    pd.DataFrame([asdict(item) for item in audit.controls]).to_csv(
        paths.controls_csv,
        index=False,
    )
    pd.DataFrame(
        [asdict(item) for item in audit.unmatched_targets]
    ).to_csv(paths.unmatched_csv, index=False)
    pd.DataFrame(
        [asdict(item) for item in audit.symbol_match_rows]
    ).to_csv(paths.symbol_match_csv, index=False)
    pd.DataFrame(
        [asdict(item) for item in audit.pair_outcomes]
    ).to_csv(paths.pair_outcomes_csv, index=False)
    pd.DataFrame(
        [asdict(item) for item in audit.censoring_rows]
    ).to_csv(paths.censoring_csv, index=False)
    pd.DataFrame(
        [asdict(item) for item in audit.outcome_summary_rows]
    ).to_csv(paths.outcome_summary_csv, index=False)
    pd.DataFrame(
        [asdict(item) for item in audit.symbol_outcome_rows]
    ).to_csv(paths.symbol_outcome_csv, index=False)
    return paths


__all__ = [
    "DAILY_NO_SUPPLY_MATCHED_ENVIRONMENT_AUDIT_ID",
    "DEFAULT_MAX_MATCH_DISTANCE_SESSIONS",
    "NoSupplyMatchedControl",
    "NoSupplyMatchedCensoringRow",
    "NoSupplyMatchedEnvironmentAudit",
    "NoSupplyMatchedEnvironmentPaths",
    "NoSupplyMatchedOutcomeSummary",
    "NoSupplyMatchedPairOutcome",
    "NoSupplyMatchedSourceLineage",
    "NoSupplyMatchedSources",
    "NoSupplyMatchedSymbolOutcomeSummary",
    "NoSupplySymbolMatchSummary",
    "NoSupplyUnmatchedTarget",
    "build_matched_outcome_summaries",
    "build_matched_pair_outcomes",
    "build_no_supply_matched_environment_audit",
    "load_no_supply_matched_sources",
    "match_symbol_controls",
    "replay_environment_direction",
    "subset_no_supply_matched_sources",
    "write_no_supply_matched_environment_audit",
]
