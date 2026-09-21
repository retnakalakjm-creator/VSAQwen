"""Forward-outcome audit for current vs alternate NO_SUPPLY populations.

L7 consumes the canonical L6 event ledger and frozen OHLCV snapshots. It does
not replay detectors and does not change production behavior. Future data is
used only after each already-fixed event identity to measure descriptive
outcomes.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd

from audit.daily_event_no_supply_environment_replay import (
    DAILY_NO_SUPPLY_ENVIRONMENT_REPLAY_AUDIT_ID,
)
from audit.daily_input_reproducibility import (
    DailyAuditInputBundle,
    daily_audit_input_manifest_sha256,
    load_daily_audit_input,
    load_daily_audit_input_bundle,
)
from engine.columns import COL_CLOSE, COL_HIGH, COL_LOW, COL_OPEN
from trading_calendar import NSETradingCalendar


DAILY_NO_SUPPLY_FORWARD_OUTCOME_AUDIT_ID = (
    "daily-event-no-supply-forward-outcomes-v1"
)
DEFAULT_FORWARD_HORIZONS: tuple[int, ...] = (1, 3, 5, 10, 20)
DEFAULT_FORWARD_PRICE_DISCONTINUITY_RATIO = 0.35
COHORT_CURRENT = "CURRENT_BEARISH_ENVIRONMENT"
COHORT_ALTERNATE = "ALTERNATE_BULLISH_ENVIRONMENT"
COHORTS = (COHORT_CURRENT, COHORT_ALTERNATE)


@dataclass(frozen=True, slots=True)
class NoSupplyForwardOutcomeSourceLineage:
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
class NoSupplyForwardOutcomeSources:
    lineage: NoSupplyForwardOutcomeSourceLineage
    bundle: DailyAuditInputBundle
    events: pd.DataFrame
    current_event_count: int
    alternate_event_count: int


@dataclass(frozen=True, slots=True)
class NoSupplyForwardEventOutcome:
    symbol: str
    session: str
    bar_index: int
    cohort: str
    trend_direction: str
    horizon_sessions: int
    horizon_session: str
    event_close: float
    horizon_close: float
    forward_close_return_pct: float
    max_favorable_excursion_pct: float
    max_adverse_excursion_pct: float
    positive_close: bool
    max_single_session_price_move_pct: float
    price_discontinuity_in_event_or_window: bool


@dataclass(frozen=True, slots=True)
class NoSupplyForwardCensoringRow:
    cohort: str
    horizon_sessions: int
    source_event_count: int
    complete_event_count: int
    censored_event_count: int
    censoring_rate: float
    complete_symbol_count: int


@dataclass(frozen=True, slots=True)
class NoSupplyForwardDataQualityRow:
    cohort: str
    horizon_sessions: int
    complete_event_count: int
    clean_event_count: int
    price_discontinuity_event_count: int
    price_discontinuity_rate: float
    clean_symbol_count: int


@dataclass(frozen=True, slots=True)
class NoSupplyForwardCohortSummary:
    cohort: str
    horizon_sessions: int
    event_count: int
    symbol_count: int
    mean_close_return_pct: float
    median_close_return_pct: float
    q25_close_return_pct: float
    q75_close_return_pct: float
    positive_close_count: int
    positive_close_rate: float
    mean_mfe_pct: float
    median_mfe_pct: float
    mean_mae_pct: float
    median_mae_pct: float


@dataclass(frozen=True, slots=True)
class NoSupplyForwardSymbolSummary:
    cohort: str
    horizon_sessions: int
    symbol: str
    event_count: int
    mean_close_return_pct: float
    median_close_return_pct: float
    positive_close_rate: float
    mean_mfe_pct: float
    mean_mae_pct: float


@dataclass(frozen=True, slots=True)
class NoSupplyForwardComparisonRow:
    horizon_sessions: int
    current_event_count: int
    alternate_event_count: int
    current_symbol_count: int
    alternate_symbol_count: int
    current_mean_close_return_pct: float
    alternate_mean_close_return_pct: float
    alternate_minus_current_mean_return_pct: float
    current_median_close_return_pct: float
    alternate_median_close_return_pct: float
    alternate_minus_current_median_return_pct: float
    current_positive_close_rate: float
    alternate_positive_close_rate: float
    alternate_minus_current_positive_rate: float
    current_mean_mfe_pct: float
    alternate_mean_mfe_pct: float
    alternate_minus_current_mean_mfe_pct: float
    current_mean_mae_pct: float
    alternate_mean_mae_pct: float
    alternate_minus_current_mean_mae_pct: float
    current_clean_event_count: int
    alternate_clean_event_count: int
    current_price_discontinuity_event_count: int
    alternate_price_discontinuity_event_count: int
    current_clean_mean_close_return_pct: float
    alternate_clean_mean_close_return_pct: float
    alternate_minus_current_clean_mean_return_pct: float
    current_clean_median_close_return_pct: float
    alternate_clean_median_close_return_pct: float
    alternate_minus_current_clean_median_return_pct: float
    current_clean_positive_close_rate: float
    alternate_clean_positive_close_rate: float
    alternate_minus_current_clean_positive_rate: float
    current_clean_mean_mfe_pct: float
    alternate_clean_mean_mfe_pct: float
    alternate_minus_current_clean_mean_mfe_pct: float
    current_clean_mean_mae_pct: float
    alternate_clean_mean_mae_pct: float
    alternate_minus_current_clean_mean_mae_pct: float
    current_clean_symbol_normalized_mean_return_pct: float
    alternate_clean_symbol_normalized_mean_return_pct: float
    alternate_minus_current_clean_symbol_normalized_return_pct: float
    current_clean_symbol_normalized_positive_rate: float
    alternate_clean_symbol_normalized_positive_rate: float
    alternate_minus_current_clean_symbol_normalized_positive_rate: float
    current_symbol_normalized_mean_return_pct: float
    alternate_symbol_normalized_mean_return_pct: float
    alternate_minus_current_symbol_normalized_return_pct: float
    current_symbol_normalized_positive_rate: float
    alternate_symbol_normalized_positive_rate: float
    alternate_minus_current_symbol_normalized_positive_rate: float


@dataclass(frozen=True, slots=True)
class NoSupplyForwardOutcomeAudit:
    audit_id: str
    source_lineage: NoSupplyForwardOutcomeSourceLineage
    requested_symbol_count: int
    source_event_count: int
    current_source_event_count: int
    alternate_source_event_count: int
    horizon_count: int
    horizons: tuple[int, ...]
    price_discontinuity_ratio: float
    outcome_row_count: int
    censored_event_horizon_count: int
    cohort_summary_rows: tuple[NoSupplyForwardCohortSummary, ...]
    symbol_summary_rows: tuple[NoSupplyForwardSymbolSummary, ...]
    comparison_rows: tuple[NoSupplyForwardComparisonRow, ...]
    censoring_rows: tuple[NoSupplyForwardCensoringRow, ...]
    data_quality_rows: tuple[NoSupplyForwardDataQualityRow, ...]
    event_outcomes: tuple[NoSupplyForwardEventOutcome, ...]

    @property
    def is_actionable(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class NoSupplyForwardOutcomePaths:
    summary_json: Path
    event_outcomes_csv: Path
    cohort_summary_csv: Path
    symbol_summary_csv: Path
    comparison_csv: Path
    censoring_csv: Path
    data_quality_csv: Path

    def as_dict(self) -> dict[str, str]:
        return {
            "summary_json": str(self.summary_json),
            "event_outcomes_csv": str(self.event_outcomes_csv),
            "cohort_summary_csv": str(self.cohort_summary_csv),
            "symbol_summary_csv": str(self.symbol_summary_csv),
            "comparison_csv": str(self.comparison_csv),
            "censoring_csv": str(self.censoring_csv),
            "data_quality_csv": str(self.data_quality_csv),
        }


def _sha256_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _normalize_session(value: object) -> str:
    return pd.Timestamp(value).isoformat()


def _bool_value(value: object) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1"}:
        return True
    if text in {"false", "0"}:
        return False
    raise ValueError(f"cannot parse boolean value {value!r}")


def normalize_forward_horizons(
    horizons: Sequence[int] | Iterable[int],
) -> tuple[int, ...]:
    normalized = tuple(sorted({int(value) for value in horizons}))
    if not normalized:
        raise ValueError("at least one forward horizon is required")
    if any(value < 1 for value in normalized):
        raise ValueError("forward horizons must be positive")
    return normalized


def _validate_l6_summary(summary: dict[str, object]) -> None:
    if (
        summary.get("audit_id")
        != DAILY_NO_SUPPLY_ENVIRONMENT_REPLAY_AUDIT_ID
    ):
        raise ValueError("unexpected L6 audit_id")
    if summary.get("is_actionable") is not False:
        raise ValueError("L7 requires a non-actionable L6 source")

    requested = int(summary.get("requested_symbol_count", -1))
    succeeded = int(summary.get("succeeded_symbol_count", -1))
    failed = int(summary.get("failed_symbol_count", -1))
    if requested < 1 or succeeded != requested or failed != 0:
        raise ValueError("L7 requires a complete zero-failure L6 source")

    if int(summary.get("current_identity_mismatch_count", -1)) != 0:
        raise ValueError("L7 requires exact L6 current identity parity")
    if int(summary.get("current_bar_index_mismatch_count", -1)) != 0:
        raise ValueError("L7 requires exact L6 current bar-index parity")
    if int(summary.get("current_alternate_overlap_count", -1)) != 0:
        raise ValueError("L7 requires disjoint current/alternate populations")

    common = int(summary.get("common_signature_count", -1))
    current = int(summary.get("current_replay_event_count", -1))
    alternate = int(summary.get("alternate_replay_event_count", -1))
    neither = int(summary.get("neither_environment_count", -1))
    if common < 1 or current < 1 or alternate < 1 or neither < 0:
        raise ValueError("L6 population counts are invalid")
    if current + alternate + neither != common:
        raise ValueError("L6 population partition does not reconcile")
    if int(summary.get("current_baseline_event_count", -1)) != current:
        raise ValueError("L6 current replay does not match canonical baseline")


def load_no_supply_forward_outcome_sources(
    *,
    replay_dir: str | Path,
    input_snapshot_dir: str | Path,
    basket_name: str,
) -> NoSupplyForwardOutcomeSources:
    replay_root = Path(replay_dir)
    snapshot_root = Path(input_snapshot_dir)
    summary_path = (
        replay_root / "daily_no_supply_environment_replay_summary.json"
    )
    observations_path = (
        replay_root / "daily_no_supply_environment_observations.csv"
    )
    for path in (summary_path, observations_path):
        if not path.exists():
            raise FileNotFoundError(path)

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    _validate_l6_summary(summary)

    source_lineage = summary.get("source_lineage")
    if not isinstance(source_lineage, dict):
        raise ValueError("L6 source lineage is missing")

    bundle = load_daily_audit_input_bundle(snapshot_root)
    manifest_sha256 = daily_audit_input_manifest_sha256(snapshot_root)
    if bundle.basket_name != basket_name:
        raise ValueError("snapshot basket does not match requested basket")
    if int(summary["requested_symbol_count"]) != bundle.symbol_count:
        raise ValueError("L6 requested symbol count does not match snapshot")
    if (
        str(source_lineage.get("snapshot_audit_id", ""))
        != bundle.audit_id
    ):
        raise ValueError("L6 snapshot audit id does not match snapshot")
    if (
        str(source_lineage.get("snapshot_manifest_sha256", ""))
        != manifest_sha256
    ):
        raise ValueError("L6 snapshot manifest hash does not match snapshot")
    if (
        str(source_lineage.get("snapshot_basket_name", ""))
        != bundle.basket_name
    ):
        raise ValueError("L6 snapshot basket lineage mismatch")
    if str(source_lineage.get("snapshot_period", "")) != bundle.period:
        raise ValueError("L6 snapshot period lineage mismatch")
    if str(source_lineage.get("snapshot_cutoff", "")) != bundle.cutoff:
        raise ValueError("L6 snapshot cutoff lineage mismatch")

    frame = pd.read_csv(observations_path)
    required_columns = {
        "symbol",
        "bar_index",
        "session",
        "trend_direction",
        "current_candidate",
        "alternate_candidate",
    }
    missing = sorted(required_columns - set(frame.columns))
    if missing:
        raise ValueError(f"L6 observations missing columns: {missing}")

    frame = frame.copy()
    frame["symbol"] = frame["symbol"].map(
        lambda value: str(value).strip().upper()
    )
    frame["session"] = frame["session"].map(_normalize_session)
    frame["current_candidate"] = frame["current_candidate"].map(
        _bool_value
    )
    frame["alternate_candidate"] = frame["alternate_candidate"].map(
        _bool_value
    )
    if frame[["symbol", "session"]].duplicated().any():
        raise ValueError("L6 observations contain duplicate identities")
    if len(frame) != int(summary["common_signature_count"]):
        raise ValueError("L6 observation count does not match summary")

    current = frame.loc[frame["current_candidate"]].copy()
    alternate = frame.loc[frame["alternate_candidate"]].copy()
    if len(current) != int(summary["current_replay_event_count"]):
        raise ValueError("L6 current event count does not match ledger")
    if len(alternate) != int(summary["alternate_replay_event_count"]):
        raise ValueError("L6 alternate event count does not match ledger")
    if (
        frame["current_candidate"] & frame["alternate_candidate"]
    ).any():
        raise ValueError("L6 current and alternate events overlap")

    current["cohort"] = COHORT_CURRENT
    alternate["cohort"] = COHORT_ALTERNATE
    events = (
        pd.concat([current, alternate], ignore_index=True)
        .sort_values(["symbol", "bar_index", "session", "cohort"])
        .reset_index(drop=True)
    )

    lineage = NoSupplyForwardOutcomeSourceLineage(
        l6_audit_id=str(summary["audit_id"]),
        l6_summary_sha256=_sha256_file(summary_path),
        l6_observations_sha256=_sha256_file(observations_path),
        snapshot_audit_id=bundle.audit_id,
        snapshot_manifest_sha256=manifest_sha256,
        snapshot_basket_name=bundle.basket_name,
        snapshot_period=bundle.period,
        snapshot_cutoff=bundle.cutoff,
        l5_audit_id=str(source_lineage["l5_audit_id"]),
        l5_summary_sha256=str(source_lineage["l5_summary_sha256"]),
        l5_correction_candidates_sha256=str(
            source_lineage["l5_correction_candidates_sha256"]
        ),
        l3_audit_id=str(source_lineage["l3_audit_id"]),
        l3_summary_sha256=str(source_lineage["l3_summary_sha256"]),
        l3_observations_sha256=str(
            source_lineage["l3_observations_sha256"]
        ),
        l1_summary_sha256=str(source_lineage["l1_summary_sha256"]),
        l1_emissions_sha256=str(source_lineage["l1_emissions_sha256"]),
        l2_summary_sha256=str(source_lineage["l2_summary_sha256"]),
    )
    return NoSupplyForwardOutcomeSources(
        lineage=lineage,
        bundle=bundle,
        events=events,
        current_event_count=len(current),
        alternate_event_count=len(alternate),
    )


def l6_equivalent_session_frame(daily: pd.DataFrame) -> pd.DataFrame:
    """Return the exchange-session sequence used by canonical L6 replay.

    L6 calls completed_daily_only() with the default NSETradingCalendar.
    For the already-frozen historical snapshot used by L7, every retained
    weekday session is complete; the material distinction is that raw snapshot
    rows which the default calendar does not recognize as sessions (for
    example special weekend sessions not configured as extra_sessions) are
    excluded before replay indexing and forward-horizon counting.
    """

    if daily.empty or not isinstance(daily.index, pd.DatetimeIndex):
        raise ValueError("daily data must be non-empty with DatetimeIndex")
    if daily.index.has_duplicates or not daily.index.is_monotonic_increasing:
        raise ValueError("daily sessions must be unique and sorted")

    calendar = NSETradingCalendar()
    mask = [calendar.is_session(session) for session in daily.index]
    filtered = daily.loc[mask].copy()
    if filtered.empty:
        raise ValueError("no L6-equivalent exchange sessions are available")
    return filtered


def _max_single_session_price_move_pct(
    session_daily: pd.DataFrame,
    *,
    start_position: int,
    end_position: int,
) -> float:
    if start_position < 1:
        raise ValueError("price-discontinuity window requires prior session")
    if end_position < start_position:
        raise ValueError("invalid price-discontinuity window")

    window = session_daily.iloc[start_position : end_position + 1]
    previous_close = pd.Series(
        [
            float(session_daily.iloc[start_position - 1][COL_CLOSE]),
            *[
                float(value)
                for value in window[COL_CLOSE].iloc[:-1]
            ],
        ],
        index=window.index,
        dtype=float,
    )
    if (previous_close <= 0.0).any():
        raise ValueError("previous close must be positive")

    maxima: list[float] = []
    for column in (COL_OPEN, COL_HIGH, COL_LOW, COL_CLOSE):
        ratios = (
            (window[column].astype(float) / previous_close - 1.0)
            .abs()
            * 100.0
        )
        maxima.append(float(ratios.max()))
    return max(maxima)


def calculate_symbol_forward_outcomes(
    *,
    symbol: str,
    daily: pd.DataFrame,
    events: pd.DataFrame,
    horizons: Sequence[int] | Iterable[int] = DEFAULT_FORWARD_HORIZONS,
    price_discontinuity_ratio: float = (
        DEFAULT_FORWARD_PRICE_DISCONTINUITY_RATIO
    ),
) -> tuple[
    tuple[NoSupplyForwardEventOutcome, ...],
    tuple[NoSupplyForwardCensoringRow, ...],
]:
    clean_symbol = str(symbol).strip().upper()
    selected_horizons = normalize_forward_horizons(horizons)
    if not 0.0 < price_discontinuity_ratio < 1.0:
        raise ValueError(
            "price_discontinuity_ratio must be between 0 and 1"
        )
    session_daily = l6_equivalent_session_frame(daily)
    for column in (COL_OPEN, COL_HIGH, COL_LOW, COL_CLOSE):
        if column not in session_daily.columns:
            raise ValueError(f"daily data missing required column {column}")

    frame = events.loc[events["symbol"] == clean_symbol].copy()
    session_to_position = {
        _normalize_session(session): index
        for index, session in enumerate(session_daily.index)
    }
    outcomes: list[NoSupplyForwardEventOutcome] = []
    censoring: list[NoSupplyForwardCensoringRow] = []

    for cohort in COHORTS:
        cohort_events = frame.loc[frame["cohort"] == cohort]
        completed_by_horizon = {
            horizon: 0 for horizon in selected_horizons
        }
        completed_symbols = {
            horizon: set() for horizon in selected_horizons
        }

        for event in cohort_events.itertuples(index=False):
            session = _normalize_session(event.session)
            if session not in session_to_position:
                raise ValueError(
                    f"{clean_symbol} event session missing from snapshot: "
                    f"{session}"
                )
            position = session_to_position[session]
            if int(event.bar_index) != position:
                raise ValueError(
                    f"{clean_symbol} L6 bar index drift at {session}: "
                    f"{event.bar_index} != {position}"
                )
            event_close = float(session_daily.iloc[position][COL_CLOSE])
            if event_close <= 0.0:
                raise ValueError("event close must be positive")

            for horizon in selected_horizons:
                end_position = position + horizon
                if end_position >= len(session_daily):
                    continue
                future = session_daily.iloc[position + 1 : end_position + 1]
                if len(future) != horizon:
                    raise RuntimeError("forward horizon slicing drift")

                horizon_session = _normalize_session(
                    session_daily.index[end_position]
                )
                horizon_close = float(
                    session_daily.iloc[end_position][COL_CLOSE]
                )
                forward_return = (
                    horizon_close / event_close - 1.0
                ) * 100.0
                mfe = max(
                    0.0,
                    (
                        float(future[COL_HIGH].max())
                        / event_close
                        - 1.0
                    )
                    * 100.0,
                )
                mae = min(
                    0.0,
                    (
                        float(future[COL_LOW].min())
                        / event_close
                        - 1.0
                    )
                    * 100.0,
                )
                max_price_move_pct = _max_single_session_price_move_pct(
                    session_daily,
                    start_position=position,
                    end_position=end_position,
                )
                price_discontinuity = (
                    max_price_move_pct
                    >= price_discontinuity_ratio * 100.0
                )

                outcomes.append(
                    NoSupplyForwardEventOutcome(
                        symbol=clean_symbol,
                        session=session,
                        bar_index=position,
                        cohort=cohort,
                        trend_direction=str(event.trend_direction),
                        horizon_sessions=horizon,
                        horizon_session=horizon_session,
                        event_close=event_close,
                        horizon_close=horizon_close,
                        forward_close_return_pct=forward_return,
                        max_favorable_excursion_pct=mfe,
                        max_adverse_excursion_pct=mae,
                        positive_close=forward_return > 0.0,
                        max_single_session_price_move_pct=(
                            max_price_move_pct
                        ),
                        price_discontinuity_in_event_or_window=(
                            price_discontinuity
                        ),
                    )
                )
                completed_by_horizon[horizon] += 1
                completed_symbols[horizon].add(clean_symbol)

        source_count = len(cohort_events)
        for horizon in selected_horizons:
            complete = completed_by_horizon[horizon]
            censored = source_count - complete
            censoring.append(
                NoSupplyForwardCensoringRow(
                    cohort=cohort,
                    horizon_sessions=horizon,
                    source_event_count=source_count,
                    complete_event_count=complete,
                    censored_event_count=censored,
                    censoring_rate=(
                        censored / source_count if source_count else 0.0
                    ),
                    complete_symbol_count=len(
                        completed_symbols[horizon]
                    ),
                )
            )

    return tuple(outcomes), tuple(censoring)


def _summary_from_frame(
    cohort: str,
    horizon: int,
    frame: pd.DataFrame,
) -> NoSupplyForwardCohortSummary:
    if frame.empty:
        raise ValueError(
            f"no complete outcomes for {cohort} at horizon {horizon}"
        )
    returns = frame["forward_close_return_pct"]
    mfe = frame["max_favorable_excursion_pct"]
    mae = frame["max_adverse_excursion_pct"]
    positives = int(frame["positive_close"].sum())
    return NoSupplyForwardCohortSummary(
        cohort=cohort,
        horizon_sessions=horizon,
        event_count=len(frame),
        symbol_count=int(frame["symbol"].nunique()),
        mean_close_return_pct=float(returns.mean()),
        median_close_return_pct=float(returns.median()),
        q25_close_return_pct=float(returns.quantile(0.25)),
        q75_close_return_pct=float(returns.quantile(0.75)),
        positive_close_count=positives,
        positive_close_rate=positives / len(frame),
        mean_mfe_pct=float(mfe.mean()),
        median_mfe_pct=float(mfe.median()),
        mean_mae_pct=float(mae.mean()),
        median_mae_pct=float(mae.median()),
    )


def build_forward_outcome_summaries(
    outcomes: tuple[NoSupplyForwardEventOutcome, ...],
    *,
    horizons: Sequence[int] | Iterable[int],
) -> tuple[
    tuple[NoSupplyForwardCohortSummary, ...],
    tuple[NoSupplyForwardSymbolSummary, ...],
    tuple[NoSupplyForwardComparisonRow, ...],
    tuple[NoSupplyForwardDataQualityRow, ...],
]:
    selected_horizons = normalize_forward_horizons(horizons)
    frame = pd.DataFrame([asdict(item) for item in outcomes])
    if frame.empty:
        raise ValueError("forward outcome ledger cannot be empty")

    cohort_rows: list[NoSupplyForwardCohortSummary] = []
    symbol_rows: list[NoSupplyForwardSymbolSummary] = []
    quality_rows: list[NoSupplyForwardDataQualityRow] = []

    for horizon in selected_horizons:
        for cohort in COHORTS:
            selected = frame.loc[
                (frame["horizon_sessions"] == horizon)
                & (frame["cohort"] == cohort)
            ]
            cohort_rows.append(
                _summary_from_frame(cohort, horizon, selected)
            )
            clean = selected.loc[
                ~selected[
                    "price_discontinuity_in_event_or_window"
                ]
            ]
            quality_rows.append(
                NoSupplyForwardDataQualityRow(
                    cohort=cohort,
                    horizon_sessions=horizon,
                    complete_event_count=len(selected),
                    clean_event_count=len(clean),
                    price_discontinuity_event_count=(
                        len(selected) - len(clean)
                    ),
                    price_discontinuity_rate=(
                        (len(selected) - len(clean)) / len(selected)
                        if len(selected)
                        else 0.0
                    ),
                    clean_symbol_count=int(
                        clean["symbol"].nunique()
                    ),
                )
            )
            for symbol, symbol_frame in selected.groupby(
                "symbol",
                sort=True,
            ):
                symbol_rows.append(
                    NoSupplyForwardSymbolSummary(
                        cohort=cohort,
                        horizon_sessions=horizon,
                        symbol=str(symbol),
                        event_count=len(symbol_frame),
                        mean_close_return_pct=float(
                            symbol_frame[
                                "forward_close_return_pct"
                            ].mean()
                        ),
                        median_close_return_pct=float(
                            symbol_frame[
                                "forward_close_return_pct"
                            ].median()
                        ),
                        positive_close_rate=float(
                            symbol_frame["positive_close"].mean()
                        ),
                        mean_mfe_pct=float(
                            symbol_frame[
                                "max_favorable_excursion_pct"
                            ].mean()
                        ),
                        mean_mae_pct=float(
                            symbol_frame[
                                "max_adverse_excursion_pct"
                            ].mean()
                        ),
                    )
                )

    cohort_lookup = {
        (item.horizon_sessions, item.cohort): item
        for item in cohort_rows
    }
    symbol_frame = pd.DataFrame(
        [asdict(item) for item in symbol_rows]
    )
    comparisons: list[NoSupplyForwardComparisonRow] = []
    for horizon in selected_horizons:
        current = cohort_lookup[(horizon, COHORT_CURRENT)]
        alternate = cohort_lookup[(horizon, COHORT_ALTERNATE)]
        current_symbols = symbol_frame.loc[
            (symbol_frame["horizon_sessions"] == horizon)
            & (symbol_frame["cohort"] == COHORT_CURRENT)
        ]
        alternate_symbols = symbol_frame.loc[
            (symbol_frame["horizon_sessions"] == horizon)
            & (symbol_frame["cohort"] == COHORT_ALTERNATE)
        ]
        current_symbol_return = float(
            current_symbols["mean_close_return_pct"].mean()
        )
        alternate_symbol_return = float(
            alternate_symbols["mean_close_return_pct"].mean()
        )
        current_symbol_positive = float(
            current_symbols["positive_close_rate"].mean()
        )
        alternate_symbol_positive = float(
            alternate_symbols["positive_close_rate"].mean()
        )

        current_events = frame.loc[
            (frame["horizon_sessions"] == horizon)
            & (frame["cohort"] == COHORT_CURRENT)
        ]
        alternate_events = frame.loc[
            (frame["horizon_sessions"] == horizon)
            & (frame["cohort"] == COHORT_ALTERNATE)
        ]
        current_clean = current_events.loc[
            ~current_events[
                "price_discontinuity_in_event_or_window"
            ]
        ]
        alternate_clean = alternate_events.loc[
            ~alternate_events[
                "price_discontinuity_in_event_or_window"
            ]
        ]
        if current_clean.empty or alternate_clean.empty:
            raise ValueError(
                f"clean outcome cohort is empty at horizon {horizon}"
            )

        current_clean_symbol = current_clean.groupby(
            "symbol", sort=True
        ).agg(
            mean_return=("forward_close_return_pct", "mean"),
            positive_rate=("positive_close", "mean"),
        )
        alternate_clean_symbol = alternate_clean.groupby(
            "symbol", sort=True
        ).agg(
            mean_return=("forward_close_return_pct", "mean"),
            positive_rate=("positive_close", "mean"),
        )
        if (
            current_clean_symbol.empty
            or alternate_clean_symbol.empty
        ):
            raise ValueError(
                f"clean symbol summary is empty at horizon {horizon}"
            )

        comparisons.append(
            NoSupplyForwardComparisonRow(
                horizon_sessions=horizon,
                current_event_count=current.event_count,
                alternate_event_count=alternate.event_count,
                current_symbol_count=current.symbol_count,
                alternate_symbol_count=alternate.symbol_count,
                current_mean_close_return_pct=(
                    current.mean_close_return_pct
                ),
                alternate_mean_close_return_pct=(
                    alternate.mean_close_return_pct
                ),
                alternate_minus_current_mean_return_pct=(
                    alternate.mean_close_return_pct
                    - current.mean_close_return_pct
                ),
                current_median_close_return_pct=(
                    current.median_close_return_pct
                ),
                alternate_median_close_return_pct=(
                    alternate.median_close_return_pct
                ),
                alternate_minus_current_median_return_pct=(
                    alternate.median_close_return_pct
                    - current.median_close_return_pct
                ),
                current_positive_close_rate=(
                    current.positive_close_rate
                ),
                alternate_positive_close_rate=(
                    alternate.positive_close_rate
                ),
                alternate_minus_current_positive_rate=(
                    alternate.positive_close_rate
                    - current.positive_close_rate
                ),
                current_mean_mfe_pct=current.mean_mfe_pct,
                alternate_mean_mfe_pct=alternate.mean_mfe_pct,
                alternate_minus_current_mean_mfe_pct=(
                    alternate.mean_mfe_pct - current.mean_mfe_pct
                ),
                current_mean_mae_pct=current.mean_mae_pct,
                alternate_mean_mae_pct=alternate.mean_mae_pct,
                alternate_minus_current_mean_mae_pct=(
                    alternate.mean_mae_pct - current.mean_mae_pct
                ),
                current_clean_event_count=len(current_clean),
                alternate_clean_event_count=len(alternate_clean),
                current_price_discontinuity_event_count=(
                    len(current_events) - len(current_clean)
                ),
                alternate_price_discontinuity_event_count=(
                    len(alternate_events) - len(alternate_clean)
                ),
                current_clean_mean_close_return_pct=float(
                    current_clean["forward_close_return_pct"].mean()
                ),
                alternate_clean_mean_close_return_pct=float(
                    alternate_clean["forward_close_return_pct"].mean()
                ),
                alternate_minus_current_clean_mean_return_pct=float(
                    alternate_clean["forward_close_return_pct"].mean()
                    - current_clean["forward_close_return_pct"].mean()
                ),
                current_clean_median_close_return_pct=float(
                    current_clean["forward_close_return_pct"].median()
                ),
                alternate_clean_median_close_return_pct=float(
                    alternate_clean["forward_close_return_pct"].median()
                ),
                alternate_minus_current_clean_median_return_pct=float(
                    alternate_clean["forward_close_return_pct"].median()
                    - current_clean["forward_close_return_pct"].median()
                ),
                current_clean_positive_close_rate=float(
                    current_clean["positive_close"].mean()
                ),
                alternate_clean_positive_close_rate=float(
                    alternate_clean["positive_close"].mean()
                ),
                alternate_minus_current_clean_positive_rate=float(
                    alternate_clean["positive_close"].mean()
                    - current_clean["positive_close"].mean()
                ),
                current_clean_mean_mfe_pct=float(
                    current_clean[
                        "max_favorable_excursion_pct"
                    ].mean()
                ),
                alternate_clean_mean_mfe_pct=float(
                    alternate_clean[
                        "max_favorable_excursion_pct"
                    ].mean()
                ),
                alternate_minus_current_clean_mean_mfe_pct=float(
                    alternate_clean[
                        "max_favorable_excursion_pct"
                    ].mean()
                    - current_clean[
                        "max_favorable_excursion_pct"
                    ].mean()
                ),
                current_clean_mean_mae_pct=float(
                    current_clean[
                        "max_adverse_excursion_pct"
                    ].mean()
                ),
                alternate_clean_mean_mae_pct=float(
                    alternate_clean[
                        "max_adverse_excursion_pct"
                    ].mean()
                ),
                alternate_minus_current_clean_mean_mae_pct=float(
                    alternate_clean[
                        "max_adverse_excursion_pct"
                    ].mean()
                    - current_clean[
                        "max_adverse_excursion_pct"
                    ].mean()
                ),
                current_clean_symbol_normalized_mean_return_pct=float(
                    current_clean_symbol["mean_return"].mean()
                ),
                alternate_clean_symbol_normalized_mean_return_pct=float(
                    alternate_clean_symbol["mean_return"].mean()
                ),
                alternate_minus_current_clean_symbol_normalized_return_pct=float(
                    alternate_clean_symbol["mean_return"].mean()
                    - current_clean_symbol["mean_return"].mean()
                ),
                current_clean_symbol_normalized_positive_rate=float(
                    current_clean_symbol["positive_rate"].mean()
                ),
                alternate_clean_symbol_normalized_positive_rate=float(
                    alternate_clean_symbol["positive_rate"].mean()
                ),
                alternate_minus_current_clean_symbol_normalized_positive_rate=float(
                    alternate_clean_symbol["positive_rate"].mean()
                    - current_clean_symbol["positive_rate"].mean()
                ),
                current_symbol_normalized_mean_return_pct=(
                    current_symbol_return
                ),
                alternate_symbol_normalized_mean_return_pct=(
                    alternate_symbol_return
                ),
                alternate_minus_current_symbol_normalized_return_pct=(
                    alternate_symbol_return - current_symbol_return
                ),
                current_symbol_normalized_positive_rate=(
                    current_symbol_positive
                ),
                alternate_symbol_normalized_positive_rate=(
                    alternate_symbol_positive
                ),
                alternate_minus_current_symbol_normalized_positive_rate=(
                    alternate_symbol_positive - current_symbol_positive
                ),
            )
        )

    return (
        tuple(cohort_rows),
        tuple(symbol_rows),
        tuple(comparisons),
        tuple(quality_rows),
    )


def build_no_supply_forward_outcome_audit(
    *,
    sources: NoSupplyForwardOutcomeSources,
    input_snapshot_dir: str | Path,
    horizons: Sequence[int] | Iterable[int] = DEFAULT_FORWARD_HORIZONS,
    price_discontinuity_ratio: float = (
        DEFAULT_FORWARD_PRICE_DISCONTINUITY_RATIO
    ),
) -> NoSupplyForwardOutcomeAudit:
    selected_horizons = normalize_forward_horizons(horizons)
    if not 0.0 < price_discontinuity_ratio < 1.0:
        raise ValueError(
            "price_discontinuity_ratio must be between 0 and 1"
        )
    events = sources.events
    observations: list[NoSupplyForwardEventOutcome] = []
    censoring_by_key: dict[
        tuple[str, int],
        dict[str, object],
    ] = {}

    basket_symbols = tuple(
        item.symbol for item in sources.bundle.fingerprints
    )
    for symbol in basket_symbols:
        daily = load_daily_audit_input(input_snapshot_dir, symbol)
        symbol_outcomes, symbol_censoring = (
            calculate_symbol_forward_outcomes(
                symbol=symbol,
                daily=daily,
                events=events,
                horizons=selected_horizons,
                price_discontinuity_ratio=price_discontinuity_ratio,
            )
        )
        observations.extend(symbol_outcomes)
        for row in symbol_censoring:
            key = (row.cohort, row.horizon_sessions)
            aggregate = censoring_by_key.setdefault(
                key,
                {
                    "source_event_count": 0,
                    "complete_event_count": 0,
                    "censored_event_count": 0,
                    "symbols": set(),
                },
            )
            aggregate["source_event_count"] = int(
                aggregate["source_event_count"]
            ) + row.source_event_count
            aggregate["complete_event_count"] = int(
                aggregate["complete_event_count"]
            ) + row.complete_event_count
            aggregate["censored_event_count"] = int(
                aggregate["censored_event_count"]
            ) + row.censored_event_count
            if row.complete_event_count:
                symbols = aggregate["symbols"]
                assert isinstance(symbols, set)
                symbols.add(symbol)

    censoring_rows: list[NoSupplyForwardCensoringRow] = []
    expected_source_counts = {
        COHORT_CURRENT: sources.current_event_count,
        COHORT_ALTERNATE: sources.alternate_event_count,
    }
    for horizon in selected_horizons:
        for cohort in COHORTS:
            aggregate = censoring_by_key[(cohort, horizon)]
            source_count = int(aggregate["source_event_count"])
            complete_count = int(aggregate["complete_event_count"])
            censored_count = int(aggregate["censored_event_count"])
            if source_count != expected_source_counts[cohort]:
                raise ValueError(
                    f"{cohort} source count does not reconcile at "
                    f"horizon {horizon}"
                )
            if complete_count + censored_count != source_count:
                raise ValueError(
                    f"{cohort} censoring does not reconcile at "
                    f"horizon {horizon}"
                )
            symbols = aggregate["symbols"]
            assert isinstance(symbols, set)
            censoring_rows.append(
                NoSupplyForwardCensoringRow(
                    cohort=cohort,
                    horizon_sessions=horizon,
                    source_event_count=source_count,
                    complete_event_count=complete_count,
                    censored_event_count=censored_count,
                    censoring_rate=(
                        censored_count / source_count
                        if source_count
                        else 0.0
                    ),
                    complete_symbol_count=len(symbols),
                )
            )

    outcome_tuple = tuple(
        sorted(
            observations,
            key=lambda item: (
                basket_symbols.index(item.symbol),
                item.bar_index,
                item.cohort,
                item.horizon_sessions,
            ),
        )
    )
    cohort_rows, symbol_rows, comparison_rows, quality_rows = (
        build_forward_outcome_summaries(
            outcome_tuple,
            horizons=selected_horizons,
        )
    )

    censored_total = sum(
        item.censored_event_count for item in censoring_rows
    )
    return NoSupplyForwardOutcomeAudit(
        audit_id=DAILY_NO_SUPPLY_FORWARD_OUTCOME_AUDIT_ID,
        source_lineage=sources.lineage,
        requested_symbol_count=sources.bundle.symbol_count,
        source_event_count=(
            sources.current_event_count
            + sources.alternate_event_count
        ),
        current_source_event_count=sources.current_event_count,
        alternate_source_event_count=sources.alternate_event_count,
        horizon_count=len(selected_horizons),
        horizons=selected_horizons,
        price_discontinuity_ratio=price_discontinuity_ratio,
        outcome_row_count=len(outcome_tuple),
        censored_event_horizon_count=censored_total,
        cohort_summary_rows=cohort_rows,
        symbol_summary_rows=symbol_rows,
        comparison_rows=comparison_rows,
        censoring_rows=tuple(censoring_rows),
        data_quality_rows=quality_rows,
        event_outcomes=outcome_tuple,
    )


def write_no_supply_forward_outcome_audit(
    audit: NoSupplyForwardOutcomeAudit,
    output_dir: str | Path,
) -> NoSupplyForwardOutcomePaths:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    paths = NoSupplyForwardOutcomePaths(
        summary_json=root / "daily_no_supply_forward_outcome_summary.json",
        event_outcomes_csv=(
            root / "daily_no_supply_forward_event_outcomes.csv"
        ),
        cohort_summary_csv=(
            root / "daily_no_supply_forward_cohort_summary.csv"
        ),
        symbol_summary_csv=(
            root / "daily_no_supply_forward_symbol_summary.csv"
        ),
        comparison_csv=(
            root / "daily_no_supply_forward_cohort_comparison.csv"
        ),
        censoring_csv=(
            root / "daily_no_supply_forward_censoring_summary.csv"
        ),
        data_quality_csv=(
            root / "daily_no_supply_forward_data_quality_summary.csv"
        ),
    )
    summary = {
        "audit_id": audit.audit_id,
        "requested_symbol_count": audit.requested_symbol_count,
        "source_event_count": audit.source_event_count,
        "current_source_event_count": audit.current_source_event_count,
        "alternate_source_event_count": (
            audit.alternate_source_event_count
        ),
        "horizon_count": audit.horizon_count,
        "horizons": list(audit.horizons),
        "price_discontinuity_ratio": audit.price_discontinuity_ratio,
        "outcome_row_count": audit.outcome_row_count,
        "censored_event_horizon_count": (
            audit.censored_event_horizon_count
        ),
        "cohort_summary_row_count": len(audit.cohort_summary_rows),
        "symbol_summary_row_count": len(audit.symbol_summary_rows),
        "comparison_row_count": len(audit.comparison_rows),
        "censoring_row_count": len(audit.censoring_rows),
        "data_quality_row_count": len(audit.data_quality_rows),
        "source_lineage": asdict(audit.source_lineage),
        "is_actionable": False,
    }
    paths.summary_json.write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    pd.DataFrame(
        [asdict(item) for item in audit.event_outcomes]
    ).to_csv(paths.event_outcomes_csv, index=False)
    pd.DataFrame(
        [asdict(item) for item in audit.cohort_summary_rows]
    ).to_csv(paths.cohort_summary_csv, index=False)
    pd.DataFrame(
        [asdict(item) for item in audit.symbol_summary_rows]
    ).to_csv(paths.symbol_summary_csv, index=False)
    pd.DataFrame(
        [asdict(item) for item in audit.comparison_rows]
    ).to_csv(paths.comparison_csv, index=False)
    pd.DataFrame(
        [asdict(item) for item in audit.censoring_rows]
    ).to_csv(paths.censoring_csv, index=False)
    pd.DataFrame(
        [asdict(item) for item in audit.data_quality_rows]
    ).to_csv(paths.data_quality_csv, index=False)
    return paths


__all__ = [
    "COHORT_ALTERNATE",
    "COHORT_CURRENT",
    "COHORTS",
    "DAILY_NO_SUPPLY_FORWARD_OUTCOME_AUDIT_ID",
    "DEFAULT_FORWARD_HORIZONS",
    "DEFAULT_FORWARD_PRICE_DISCONTINUITY_RATIO",
    "NoSupplyForwardCensoringRow",
    "NoSupplyForwardCohortSummary",
    "NoSupplyForwardDataQualityRow",
    "NoSupplyForwardComparisonRow",
    "NoSupplyForwardEventOutcome",
    "NoSupplyForwardOutcomeAudit",
    "NoSupplyForwardOutcomePaths",
    "NoSupplyForwardOutcomeSourceLineage",
    "NoSupplyForwardOutcomeSources",
    "NoSupplyForwardSymbolSummary",
    "build_forward_outcome_summaries",
    "build_no_supply_forward_outcome_audit",
    "calculate_symbol_forward_outcomes",
    "l6_equivalent_session_frame",
    "load_no_supply_forward_outcome_sources",
    "normalize_forward_horizons",
    "write_no_supply_forward_outcome_audit",
]
