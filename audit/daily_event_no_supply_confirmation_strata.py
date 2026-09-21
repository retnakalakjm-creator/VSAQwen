"""Confirmation-stratified matched outcomes for NO_SUPPLY.

L9 reuses canonical L8 matched pair outcomes and canonical L6 confirmation
observations. It performs no market-data, detector, or trend replay.
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
from audit.daily_event_no_supply_environment_replay import (
    DAILY_NO_SUPPLY_ENVIRONMENT_REPLAY_AUDIT_ID,
)
from audit.daily_event_no_supply_matched_environment import (
    DAILY_NO_SUPPLY_MATCHED_ENVIRONMENT_AUDIT_ID,
)


DAILY_NO_SUPPLY_CONFIRMATION_STRATA_AUDIT_ID = (
    "daily-event-no-supply-confirmation-strata-v1"
)

STRATUM_NEITHER = "NEITHER"
STRATUM_VOLUME_ONLY = "VOLUME_ONLY"
STRATUM_WEAK_RESULT_ONLY = "WEAK_RESULT_ONLY"
STRATUM_BOTH = "BOTH"
CONFIRMATION_STRATA = (
    STRATUM_NEITHER,
    STRATUM_VOLUME_ONLY,
    STRATUM_WEAK_RESULT_ONLY,
    STRATUM_BOTH,
)

GATE_VOLUME_DECREASING = "VOLUME_DECREASING"
GATE_WEAK_SELLING_RESULT = "WEAK_SELLING_RESULT"
GATE_BOTH = "BOTH"
CONFIRMATION_GATES = (
    GATE_VOLUME_DECREASING,
    GATE_WEAK_SELLING_RESULT,
    GATE_BOTH,
)

WEAK_SPREAD_NAME = "Weak Spread"
VOLUME_DECREASING_NAME = "Volume Decreasing"
WEAK_SELLING_RESULT_NAME = "Weak Selling Result"


@dataclass(frozen=True, slots=True)
class NoSupplyConfirmationSourceLineage:
    l8_audit_id: str
    l8_summary_sha256: str
    l8_controls_sha256: str
    l8_pair_outcomes_sha256: str
    l8_censoring_sha256: str
    l8_outcome_summary_sha256: str
    l6_audit_id: str
    l6_summary_sha256: str
    l6_observations_sha256: str
    snapshot_manifest_sha256: str
    l7_summary_sha256: str
    l7_event_outcomes_sha256: str


@dataclass(frozen=True, slots=True)
class NoSupplyConfirmationSources:
    lineage: NoSupplyConfirmationSourceLineage
    targets: pd.DataFrame
    pair_outcomes: pd.DataFrame
    current_target_count: int
    alternate_target_count: int


@dataclass(frozen=True, slots=True)
class NoSupplyConfirmationTarget:
    symbol: str
    session: str
    bar_index: int
    cohort: str
    trend_direction: str
    volume_decreasing: bool
    weak_selling_result: bool
    stratum: str


@dataclass(frozen=True, slots=True)
class NoSupplyConfirmationCountRow:
    dimension: str
    segment: str
    cohort: str
    target_count: int
    symbol_count: int
    target_rate_within_cohort: float


@dataclass(frozen=True, slots=True)
class NoSupplyConfirmationOutcomeRow:
    dimension: str
    segment: str
    cohort: str
    horizon_sessions: int
    source_target_count: int
    pair_count: int
    clean_pair_count: int
    symbol_count: int
    clean_symbol_count: int
    mean_paired_return_delta_pct: float
    median_paired_return_delta_pct: float
    positive_close_rate_delta: float
    mean_paired_mfe_delta_pct: float
    mean_paired_mae_delta_pct: float
    clean_mean_paired_return_delta_pct: float
    clean_median_paired_return_delta_pct: float
    clean_positive_close_rate_delta: float
    clean_mean_paired_mfe_delta_pct: float
    clean_mean_paired_mae_delta_pct: float
    clean_symbol_normalized_return_delta_pct: float
    clean_positive_return_symbol_count: int
    clean_negative_return_symbol_count: int
    clean_zero_return_symbol_count: int
    clean_symbol_normalized_positive_rate_delta: float
    clean_symbol_normalized_mfe_delta_pct: float
    clean_symbol_normalized_mae_delta_pct: float


@dataclass(frozen=True, slots=True)
class NoSupplyConfirmationSymbolOutcomeRow:
    dimension: str
    segment: str
    cohort: str
    horizon_sessions: int
    symbol: str
    clean_pair_count: int
    mean_paired_return_delta_pct: float
    positive_close_rate_delta: float
    mean_paired_mfe_delta_pct: float
    mean_paired_mae_delta_pct: float


@dataclass(frozen=True, slots=True)
class NoSupplyConfirmationStrataAudit:
    audit_id: str
    source_lineage: NoSupplyConfirmationSourceLineage
    requested_symbol_count: int
    source_target_count: int
    current_source_target_count: int
    alternate_source_target_count: int
    weak_spread_target_count: int
    meaningful_confirmation_target_count: int
    horizon_count: int
    horizons: tuple[int, ...]
    stratum_count_rows: tuple[NoSupplyConfirmationCountRow, ...]
    gate_count_rows: tuple[NoSupplyConfirmationCountRow, ...]
    stratum_outcome_rows: tuple[NoSupplyConfirmationOutcomeRow, ...]
    gate_outcome_rows: tuple[NoSupplyConfirmationOutcomeRow, ...]
    stratum_symbol_rows: tuple[NoSupplyConfirmationSymbolOutcomeRow, ...]
    gate_symbol_rows: tuple[NoSupplyConfirmationSymbolOutcomeRow, ...]

    @property
    def is_actionable(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class NoSupplyConfirmationStrataPaths:
    summary_json: Path
    targets_csv: Path
    stratum_counts_csv: Path
    gate_counts_csv: Path
    stratum_outcomes_csv: Path
    gate_outcomes_csv: Path
    stratum_symbol_outcomes_csv: Path
    gate_symbol_outcomes_csv: Path

    def as_dict(self) -> dict[str, str]:
        return {
            "summary_json": str(self.summary_json),
            "targets_csv": str(self.targets_csv),
            "stratum_counts_csv": str(self.stratum_counts_csv),
            "gate_counts_csv": str(self.gate_counts_csv),
            "stratum_outcomes_csv": str(self.stratum_outcomes_csv),
            "gate_outcomes_csv": str(self.gate_outcomes_csv),
            "stratum_symbol_outcomes_csv": str(
                self.stratum_symbol_outcomes_csv
            ),
            "gate_symbol_outcomes_csv": str(
                self.gate_symbol_outcomes_csv
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


def _split_names(value: object) -> tuple[str, ...]:
    if value is None or pd.isna(value):
        return ()
    text = str(value).strip()
    if not text:
        return ()
    return tuple(item for item in text.split("|") if item)


def confirmation_stratum(
    *,
    volume_decreasing: bool,
    weak_selling_result: bool,
) -> str:
    if volume_decreasing and weak_selling_result:
        return STRATUM_BOTH
    if volume_decreasing:
        return STRATUM_VOLUME_ONLY
    if weak_selling_result:
        return STRATUM_WEAK_RESULT_ONLY
    return STRATUM_NEITHER


def _gate_passes(
    *,
    gate: str,
    volume_decreasing: bool,
    weak_selling_result: bool,
) -> bool:
    if gate == GATE_VOLUME_DECREASING:
        return volume_decreasing
    if gate == GATE_WEAK_SELLING_RESULT:
        return weak_selling_result
    if gate == GATE_BOTH:
        return volume_decreasing and weak_selling_result
    raise ValueError(f"unknown confirmation gate {gate!r}")


def _validate_l8_summary(summary: dict[str, object]) -> None:
    if (
        summary.get("audit_id")
        != DAILY_NO_SUPPLY_MATCHED_ENVIRONMENT_AUDIT_ID
    ):
        raise ValueError("unexpected L8 audit_id")
    if summary.get("is_actionable") is not False:
        raise ValueError("L9 requires non-actionable L8 source")
    if int(summary.get("requested_symbol_count", -1)) != 30:
        raise ValueError("L9 requires canonical 30-symbol L8 source")
    if int(summary.get("source_target_count", -1)) != 2509:
        raise ValueError("unexpected L8 source target count")
    if int(summary.get("current_source_target_count", -1)) != 777:
        raise ValueError("unexpected L8 CURRENT target count")
    if int(summary.get("alternate_source_target_count", -1)) != 1732:
        raise ValueError("unexpected L8 ALTERNATE target count")
    if int(summary.get("matched_target_count", -1)) != 2509:
        raise ValueError("L9 requires fully matched canonical L8 source")
    if int(summary.get("unmatched_target_count", -1)) != 0:
        raise ValueError("L9 requires zero unmatched L8 targets")
    if float(summary.get("match_rate", -1.0)) != 1.0:
        raise ValueError("L9 requires 100% L8 match rate")
    if int(summary.get("pair_outcome_row_count", -1)) != 12539:
        raise ValueError("unexpected canonical L8 pair-outcome row count")


def load_no_supply_confirmation_sources(
    *,
    matched_dir: str | Path,
    replay_dir: str | Path,
) -> NoSupplyConfirmationSources:
    matched_root = Path(matched_dir)
    replay_root = Path(replay_dir)

    l8_summary_path = matched_root / "daily_no_supply_matched_summary.json"
    l8_controls_path = matched_root / "daily_no_supply_matched_controls.csv"
    l8_pair_path = matched_root / "daily_no_supply_matched_pair_outcomes.csv"
    l8_censor_path = matched_root / "daily_no_supply_matched_censoring.csv"
    l8_outcome_path = (
        matched_root / "daily_no_supply_matched_outcome_summary.csv"
    )
    l6_summary_path = (
        replay_root / "daily_no_supply_environment_replay_summary.json"
    )
    l6_observations_path = (
        replay_root / "daily_no_supply_environment_observations.csv"
    )

    for path in (
        l8_summary_path,
        l8_controls_path,
        l8_pair_path,
        l8_censor_path,
        l8_outcome_path,
        l6_summary_path,
        l6_observations_path,
    ):
        if not path.exists():
            raise FileNotFoundError(path)

    l8_summary = json.loads(l8_summary_path.read_text(encoding="utf-8"))
    _validate_l8_summary(l8_summary)
    l8_lineage = l8_summary.get("source_lineage")
    if not isinstance(l8_lineage, dict):
        raise ValueError("L8 source lineage is missing")

    l6_summary_sha256 = _sha256_file(l6_summary_path)
    l6_observations_sha256 = _sha256_file(l6_observations_path)
    if str(l8_lineage.get("l6_summary_sha256", "")) != l6_summary_sha256:
        raise ValueError("L8 points to a different L6 summary")
    if (
        str(l8_lineage.get("l6_observations_sha256", ""))
        != l6_observations_sha256
    ):
        raise ValueError("L8 points to a different L6 observation ledger")

    l6_summary = json.loads(l6_summary_path.read_text(encoding="utf-8"))
    if (
        l6_summary.get("audit_id")
        != DAILY_NO_SUPPLY_ENVIRONMENT_REPLAY_AUDIT_ID
    ):
        raise ValueError("unexpected L6 audit_id")
    if l6_summary.get("is_actionable") is not False:
        raise ValueError("L9 requires non-actionable L6 source")
    if int(l6_summary.get("common_signature_count", -1)) != 3584:
        raise ValueError("unexpected canonical L6 common-signature count")

    controls = pd.read_csv(l8_controls_path)
    required_controls = {
        "symbol",
        "cohort",
        "trend_direction",
        "target_session",
        "target_bar_index",
        "control_session",
        "control_bar_index",
    }
    missing_controls = sorted(required_controls - set(controls.columns))
    if missing_controls:
        raise ValueError(
            f"L8 controls missing columns: {missing_controls}"
        )
    controls = controls.copy()
    controls["symbol"] = controls["symbol"].map(
        lambda value: str(value).strip().upper()
    )
    controls["target_session"] = controls["target_session"].map(
        _normalize_session
    )
    controls["control_session"] = controls["control_session"].map(
        _normalize_session
    )
    if len(controls) != 2509:
        raise ValueError("L8 controls must contain exactly 2,509 rows")
    if controls[["symbol", "target_session"]].duplicated().any():
        raise ValueError("L8 target identities are not unique")
    if controls[["symbol", "control_session"]].duplicated().any():
        raise ValueError("L8 control identities are not unique")

    observations = pd.read_csv(l6_observations_path)
    required_observations = {
        "symbol",
        "bar_index",
        "session",
        "trend_direction",
        "current_candidate",
        "alternate_candidate",
        "confirmation_count",
        "passed_confirmation_count",
        "passed_confirmations",
        "failed_confirmations",
    }
    missing_observations = sorted(
        required_observations - set(observations.columns)
    )
    if missing_observations:
        raise ValueError(
            "L6 observations missing columns: "
            f"{missing_observations}"
        )
    observations = observations.copy()
    observations["symbol"] = observations["symbol"].map(
        lambda value: str(value).strip().upper()
    )
    observations["session"] = observations["session"].map(
        _normalize_session
    )
    observations["current_candidate"] = observations[
        "current_candidate"
    ].map(_parse_bool)
    observations["alternate_candidate"] = observations[
        "alternate_candidate"
    ].map(_parse_bool)
    observations["passed_names"] = observations[
        "passed_confirmations"
    ].map(_split_names)
    observations["failed_names"] = observations[
        "failed_confirmations"
    ].map(_split_names)

    observation_map = {
        (row.symbol, row.session): row
        for row in observations.itertuples(index=False)
    }
    if len(observation_map) != len(observations):
        raise ValueError("L6 observation identities are not unique")

    target_rows: list[dict[str, object]] = []
    for row in controls.itertuples(index=False):
        identity = (row.symbol, row.target_session)
        source = observation_map.get(identity)
        if source is None:
            raise ValueError(
                f"L8 target missing from L6 confirmations: {identity}"
            )
        expected_current = row.cohort == COHORT_CURRENT
        expected_alternate = row.cohort == COHORT_ALTERNATE
        if bool(source.current_candidate) != expected_current:
            raise ValueError("L8/L6 CURRENT target identity drift")
        if bool(source.alternate_candidate) != expected_alternate:
            raise ValueError("L8/L6 ALTERNATE target identity drift")
        if int(source.bar_index) != int(row.target_bar_index):
            raise ValueError("L8/L6 target bar-index drift")
        if str(source.trend_direction) != str(row.trend_direction):
            raise ValueError("L8/L6 target trend-direction drift")
        if int(source.confirmation_count) != 3:
            raise ValueError("NO_SUPPLY must expose exactly 3 confirmations")

        passed = set(source.passed_names)
        failed = set(source.failed_names)
        all_names = passed | failed
        expected_names = {
            WEAK_SPREAD_NAME,
            VOLUME_DECREASING_NAME,
            WEAK_SELLING_RESULT_NAME,
        }
        if all_names != expected_names:
            raise ValueError("NO_SUPPLY confirmation names changed")
        if passed & failed:
            raise ValueError("confirmation cannot both pass and fail")
        if int(source.passed_confirmation_count) != len(passed):
            raise ValueError("passed confirmation count does not reconcile")
        if WEAK_SPREAD_NAME not in passed:
            raise ValueError(
                "Weak Spread is not universally implied by Narrow Spread"
            )

        volume = VOLUME_DECREASING_NAME in passed
        weak_result = WEAK_SELLING_RESULT_NAME in passed
        target_rows.append(
            {
                "symbol": row.symbol,
                "session": row.target_session,
                "bar_index": int(row.target_bar_index),
                "cohort": str(row.cohort),
                "trend_direction": str(row.trend_direction),
                "volume_decreasing": volume,
                "weak_selling_result": weak_result,
                "stratum": confirmation_stratum(
                    volume_decreasing=volume,
                    weak_selling_result=weak_result,
                ),
            }
        )

    targets = pd.DataFrame(target_rows)
    if len(targets) != 2509:
        raise RuntimeError("L9 target ledger does not reconcile")
    current_count = int((targets["cohort"] == COHORT_CURRENT).sum())
    alternate_count = int((targets["cohort"] == COHORT_ALTERNATE).sum())
    if current_count != 777 or alternate_count != 1732:
        raise ValueError("L9 cohort counts do not match canonical L8")

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
        raise ValueError("L8 pair outcome row count changed")
    if pair_outcomes[
        [
            "symbol",
            "target_session",
            "cohort",
            "horizon_sessions",
        ]
    ].duplicated().any():
        raise ValueError("L8 pair-outcome identities are not unique")

    valid_target_ids = set(
        zip(targets["symbol"], targets["session"], strict=False)
    )
    pair_ids = set(
        zip(
            pair_outcomes["symbol"],
            pair_outcomes["target_session"],
            strict=False,
        )
    )
    if not pair_ids <= valid_target_ids:
        raise ValueError("L8 pair outcomes contain an unknown target")

    lineage = NoSupplyConfirmationSourceLineage(
        l8_audit_id=str(l8_summary["audit_id"]),
        l8_summary_sha256=_sha256_file(l8_summary_path),
        l8_controls_sha256=_sha256_file(l8_controls_path),
        l8_pair_outcomes_sha256=_sha256_file(l8_pair_path),
        l8_censoring_sha256=_sha256_file(l8_censor_path),
        l8_outcome_summary_sha256=_sha256_file(l8_outcome_path),
        l6_audit_id=str(l6_summary["audit_id"]),
        l6_summary_sha256=l6_summary_sha256,
        l6_observations_sha256=l6_observations_sha256,
        snapshot_manifest_sha256=str(
            l8_lineage["snapshot_manifest_sha256"]
        ),
        l7_summary_sha256=str(l8_lineage["l7_summary_sha256"]),
        l7_event_outcomes_sha256=str(
            l8_lineage["l7_event_outcomes_sha256"]
        ),
    )
    return NoSupplyConfirmationSources(
        lineage=lineage,
        targets=targets,
        pair_outcomes=pair_outcomes,
        current_target_count=current_count,
        alternate_target_count=alternate_count,
    )


def _segment_mask(
    targets: pd.DataFrame,
    *,
    dimension: str,
    segment: str,
) -> pd.Series:
    if dimension == "STRATUM":
        return targets["stratum"] == segment
    if dimension == "GATE":
        if segment == GATE_VOLUME_DECREASING:
            return targets["volume_decreasing"]
        if segment == GATE_WEAK_SELLING_RESULT:
            return targets["weak_selling_result"]
        if segment == GATE_BOTH:
            return (
                targets["volume_decreasing"]
                & targets["weak_selling_result"]
            )
    raise ValueError(f"unknown segment {dimension}/{segment}")


def build_confirmation_count_rows(
    targets: pd.DataFrame,
    *,
    dimension: str,
    segments: Sequence[str] | Iterable[str],
) -> tuple[NoSupplyConfirmationCountRow, ...]:
    rows: list[NoSupplyConfirmationCountRow] = []
    for cohort in (COHORT_CURRENT, COHORT_ALTERNATE):
        cohort_targets = targets.loc[targets["cohort"] == cohort]
        cohort_count = len(cohort_targets)
        if cohort_count < 1:
            raise ValueError(f"empty cohort {cohort}")
        for segment in segments:
            mask = _segment_mask(
                cohort_targets,
                dimension=dimension,
                segment=segment,
            )
            selected = cohort_targets.loc[mask]
            rows.append(
                NoSupplyConfirmationCountRow(
                    dimension=dimension,
                    segment=segment,
                    cohort=cohort,
                    target_count=len(selected),
                    symbol_count=int(selected["symbol"].nunique()),
                    target_rate_within_cohort=(
                        len(selected) / cohort_count
                    ),
                )
            )
    return tuple(rows)


def _aggregate_outcome_segment(
    *,
    dimension: str,
    segment: str,
    cohort: str,
    horizon: int,
    target_subset: pd.DataFrame,
    pair_outcomes: pd.DataFrame,
) -> tuple[
    NoSupplyConfirmationOutcomeRow | None,
    tuple[NoSupplyConfirmationSymbolOutcomeRow, ...],
]:
    target_ids = set(
        zip(
            target_subset["symbol"],
            target_subset["session"],
            strict=False,
        )
    )
    selected = pair_outcomes.loc[
        (pair_outcomes["cohort"] == cohort)
        & (pair_outcomes["horizon_sessions"] == horizon)
    ].copy()
    if target_ids:
        selected = selected.loc[
            [
                (symbol, session) in target_ids
                for symbol, session in zip(
                    selected["symbol"],
                    selected["target_session"],
                    strict=False,
                )
            ]
        ]
    else:
        selected = selected.iloc[0:0]

    source_target_count = len(target_subset)
    if source_target_count == 0:
        return None, ()
    if selected.empty:
        return None, ()

    selected["positive_delta"] = (
        selected["target_positive_close"].astype(float)
        - selected["control_positive_close"].astype(float)
    )
    clean = selected.loc[selected["clean_pair"]].copy()
    if clean.empty:
        return None, ()

    symbol_frame = clean.groupby("symbol", sort=True).agg(
        return_delta=("paired_return_delta_pct", "mean"),
        positive_delta=("positive_delta", "mean"),
        mfe_delta=("paired_mfe_delta_pct", "mean"),
        mae_delta=("paired_mae_delta_pct", "mean"),
        clean_pair_count=("paired_return_delta_pct", "size"),
    )

    symbol_rows = tuple(
        NoSupplyConfirmationSymbolOutcomeRow(
            dimension=dimension,
            segment=segment,
            cohort=cohort,
            horizon_sessions=horizon,
            symbol=str(symbol),
            clean_pair_count=int(row["clean_pair_count"]),
            mean_paired_return_delta_pct=float(row["return_delta"]),
            positive_close_rate_delta=float(row["positive_delta"]),
            mean_paired_mfe_delta_pct=float(row["mfe_delta"]),
            mean_paired_mae_delta_pct=float(row["mae_delta"]),
        )
        for symbol, row in symbol_frame.iterrows()
    )

    row = NoSupplyConfirmationOutcomeRow(
        dimension=dimension,
        segment=segment,
        cohort=cohort,
        horizon_sessions=horizon,
        source_target_count=source_target_count,
        pair_count=len(selected),
        clean_pair_count=len(clean),
        symbol_count=int(selected["symbol"].nunique()),
        clean_symbol_count=int(clean["symbol"].nunique()),
        mean_paired_return_delta_pct=float(
            selected["paired_return_delta_pct"].mean()
        ),
        median_paired_return_delta_pct=float(
            selected["paired_return_delta_pct"].median()
        ),
        positive_close_rate_delta=float(
            selected["positive_delta"].mean()
        ),
        mean_paired_mfe_delta_pct=float(
            selected["paired_mfe_delta_pct"].mean()
        ),
        mean_paired_mae_delta_pct=float(
            selected["paired_mae_delta_pct"].mean()
        ),
        clean_mean_paired_return_delta_pct=float(
            clean["paired_return_delta_pct"].mean()
        ),
        clean_median_paired_return_delta_pct=float(
            clean["paired_return_delta_pct"].median()
        ),
        clean_positive_close_rate_delta=float(
            clean["positive_delta"].mean()
        ),
        clean_mean_paired_mfe_delta_pct=float(
            clean["paired_mfe_delta_pct"].mean()
        ),
        clean_mean_paired_mae_delta_pct=float(
            clean["paired_mae_delta_pct"].mean()
        ),
        clean_symbol_normalized_return_delta_pct=float(
            symbol_frame["return_delta"].mean()
        ),
        clean_positive_return_symbol_count=int(
            (symbol_frame["return_delta"] > 0.0).sum()
        ),
        clean_negative_return_symbol_count=int(
            (symbol_frame["return_delta"] < 0.0).sum()
        ),
        clean_zero_return_symbol_count=int(
            (symbol_frame["return_delta"] == 0.0).sum()
        ),
        clean_symbol_normalized_positive_rate_delta=float(
            symbol_frame["positive_delta"].mean()
        ),
        clean_symbol_normalized_mfe_delta_pct=float(
            symbol_frame["mfe_delta"].mean()
        ),
        clean_symbol_normalized_mae_delta_pct=float(
            symbol_frame["mae_delta"].mean()
        ),
    )
    return row, symbol_rows


def build_confirmation_outcome_rows(
    *,
    targets: pd.DataFrame,
    pair_outcomes: pd.DataFrame,
    dimension: str,
    segments: Sequence[str] | Iterable[str],
    horizons: Sequence[int] | Iterable[int] = DEFAULT_FORWARD_HORIZONS,
) -> tuple[
    tuple[NoSupplyConfirmationOutcomeRow, ...],
    tuple[NoSupplyConfirmationSymbolOutcomeRow, ...],
]:
    selected_horizons = normalize_forward_horizons(horizons)
    outcome_rows: list[NoSupplyConfirmationOutcomeRow] = []
    symbol_rows: list[NoSupplyConfirmationSymbolOutcomeRow] = []

    for cohort in (COHORT_CURRENT, COHORT_ALTERNATE):
        cohort_targets = targets.loc[targets["cohort"] == cohort]
        for segment in segments:
            mask = _segment_mask(
                cohort_targets,
                dimension=dimension,
                segment=segment,
            )
            target_subset = cohort_targets.loc[mask]
            for horizon in selected_horizons:
                row, symbols = _aggregate_outcome_segment(
                    dimension=dimension,
                    segment=segment,
                    cohort=cohort,
                    horizon=horizon,
                    target_subset=target_subset,
                    pair_outcomes=pair_outcomes,
                )
                if row is not None:
                    outcome_rows.append(row)
                    symbol_rows.extend(symbols)

    return tuple(outcome_rows), tuple(symbol_rows)


def build_no_supply_confirmation_strata_audit(
    *,
    sources: NoSupplyConfirmationSources,
    horizons: Sequence[int] | Iterable[int] = DEFAULT_FORWARD_HORIZONS,
) -> NoSupplyConfirmationStrataAudit:
    selected_horizons = normalize_forward_horizons(horizons)
    targets = sources.targets
    source_count = len(targets)
    if source_count != 2509:
        raise ValueError("L9 requires 2,509 canonical targets")
    if (
        sources.current_target_count
        + sources.alternate_target_count
        != source_count
    ):
        raise ValueError("L9 cohort counts do not reconcile")

    stratum_counts = build_confirmation_count_rows(
        targets,
        dimension="STRATUM",
        segments=CONFIRMATION_STRATA,
    )
    gate_counts = build_confirmation_count_rows(
        targets,
        dimension="GATE",
        segments=CONFIRMATION_GATES,
    )
    for cohort in (COHORT_CURRENT, COHORT_ALTERNATE):
        cohort_rows = [
            item
            for item in stratum_counts
            if item.cohort == cohort
        ]
        expected = int((targets["cohort"] == cohort).sum())
        if sum(item.target_count for item in cohort_rows) != expected:
            raise ValueError(
                f"{cohort} confirmation strata do not partition targets"
            )

    stratum_outcomes, stratum_symbols = build_confirmation_outcome_rows(
        targets=targets,
        pair_outcomes=sources.pair_outcomes,
        dimension="STRATUM",
        segments=CONFIRMATION_STRATA,
        horizons=selected_horizons,
    )
    gate_outcomes, gate_symbols = build_confirmation_outcome_rows(
        targets=targets,
        pair_outcomes=sources.pair_outcomes,
        dimension="GATE",
        segments=CONFIRMATION_GATES,
        horizons=selected_horizons,
    )

    weak_spread_count = source_count
    meaningful_count = int(
        (
            targets["volume_decreasing"]
            | targets["weak_selling_result"]
        ).sum()
    )
    return NoSupplyConfirmationStrataAudit(
        audit_id=DAILY_NO_SUPPLY_CONFIRMATION_STRATA_AUDIT_ID,
        source_lineage=sources.lineage,
        requested_symbol_count=int(targets["symbol"].nunique()),
        source_target_count=source_count,
        current_source_target_count=sources.current_target_count,
        alternate_source_target_count=sources.alternate_target_count,
        weak_spread_target_count=weak_spread_count,
        meaningful_confirmation_target_count=meaningful_count,
        horizon_count=len(selected_horizons),
        horizons=selected_horizons,
        stratum_count_rows=stratum_counts,
        gate_count_rows=gate_counts,
        stratum_outcome_rows=stratum_outcomes,
        gate_outcome_rows=gate_outcomes,
        stratum_symbol_rows=stratum_symbols,
        gate_symbol_rows=gate_symbols,
    )


def write_no_supply_confirmation_strata_audit(
    audit: NoSupplyConfirmationStrataAudit,
    targets: pd.DataFrame,
    output_dir: str | Path,
) -> NoSupplyConfirmationStrataPaths:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    paths = NoSupplyConfirmationStrataPaths(
        summary_json=root / "daily_no_supply_confirmation_strata_summary.json",
        targets_csv=root / "daily_no_supply_confirmation_targets.csv",
        stratum_counts_csv=(
            root / "daily_no_supply_confirmation_stratum_counts.csv"
        ),
        gate_counts_csv=(
            root / "daily_no_supply_confirmation_gate_counts.csv"
        ),
        stratum_outcomes_csv=(
            root / "daily_no_supply_confirmation_stratum_outcomes.csv"
        ),
        gate_outcomes_csv=(
            root / "daily_no_supply_confirmation_gate_outcomes.csv"
        ),
        stratum_symbol_outcomes_csv=(
            root
            / "daily_no_supply_confirmation_stratum_symbol_outcomes.csv"
        ),
        gate_symbol_outcomes_csv=(
            root
            / "daily_no_supply_confirmation_gate_symbol_outcomes.csv"
        ),
    )

    summary = {
        "audit_id": audit.audit_id,
        "requested_symbol_count": audit.requested_symbol_count,
        "source_target_count": audit.source_target_count,
        "current_source_target_count": audit.current_source_target_count,
        "alternate_source_target_count": (
            audit.alternate_source_target_count
        ),
        "weak_spread_target_count": audit.weak_spread_target_count,
        "meaningful_confirmation_target_count": (
            audit.meaningful_confirmation_target_count
        ),
        "horizon_count": audit.horizon_count,
        "horizons": list(audit.horizons),
        "stratum_count_row_count": len(audit.stratum_count_rows),
        "gate_count_row_count": len(audit.gate_count_rows),
        "stratum_outcome_row_count": len(audit.stratum_outcome_rows),
        "gate_outcome_row_count": len(audit.gate_outcome_rows),
        "stratum_symbol_row_count": len(audit.stratum_symbol_rows),
        "gate_symbol_row_count": len(audit.gate_symbol_rows),
        "source_lineage": asdict(audit.source_lineage),
        "is_actionable": False,
    }
    paths.summary_json.write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    targets.to_csv(paths.targets_csv, index=False)
    pd.DataFrame(
        [asdict(item) for item in audit.stratum_count_rows]
    ).to_csv(paths.stratum_counts_csv, index=False)
    pd.DataFrame(
        [asdict(item) for item in audit.gate_count_rows]
    ).to_csv(paths.gate_counts_csv, index=False)
    pd.DataFrame(
        [asdict(item) for item in audit.stratum_outcome_rows]
    ).to_csv(paths.stratum_outcomes_csv, index=False)
    pd.DataFrame(
        [asdict(item) for item in audit.gate_outcome_rows]
    ).to_csv(paths.gate_outcomes_csv, index=False)
    pd.DataFrame(
        [asdict(item) for item in audit.stratum_symbol_rows]
    ).to_csv(paths.stratum_symbol_outcomes_csv, index=False)
    pd.DataFrame(
        [asdict(item) for item in audit.gate_symbol_rows]
    ).to_csv(paths.gate_symbol_outcomes_csv, index=False)
    return paths


__all__ = [
    "CONFIRMATION_GATES",
    "CONFIRMATION_STRATA",
    "DAILY_NO_SUPPLY_CONFIRMATION_STRATA_AUDIT_ID",
    "GATE_BOTH",
    "GATE_VOLUME_DECREASING",
    "GATE_WEAK_SELLING_RESULT",
    "NoSupplyConfirmationCountRow",
    "NoSupplyConfirmationOutcomeRow",
    "NoSupplyConfirmationSourceLineage",
    "NoSupplyConfirmationSources",
    "NoSupplyConfirmationStrataAudit",
    "NoSupplyConfirmationStrataPaths",
    "NoSupplyConfirmationSymbolOutcomeRow",
    "NoSupplyConfirmationTarget",
    "STRATUM_BOTH",
    "STRATUM_NEITHER",
    "STRATUM_VOLUME_ONLY",
    "STRATUM_WEAK_RESULT_ONLY",
    "build_confirmation_count_rows",
    "build_confirmation_outcome_rows",
    "build_no_supply_confirmation_strata_audit",
    "confirmation_stratum",
    "load_no_supply_confirmation_sources",
    "write_no_supply_confirmation_strata_audit",
]
