"""Causal replay of the NO_SUPPLY environment predicate alternative.

L6 is audit-only. It reuses the frozen daily snapshots and the existing
Metrics/Swing/Structure/Trend context construction, but evaluates only the
NO_SUPPLY target-bar contract. Production detector behavior is not modified.
"""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Iterator

import pandas as pd

from audit.daily_event_detector_correction_design import (
    DAILY_DETECTOR_CORRECTION_DESIGN_AUDIT_ID,
)
from audit.daily_input_reproducibility import (
    DailyAuditInputBundle,
    daily_audit_input_manifest_sha256,
    load_daily_audit_input_bundle,
)
from audit.offline_daily_evidence import (
    DEFAULT_DAILY_EVIDENCE_MIN_TARGET_INDEX,
    _metrics_input,
    _validate_daily_ohlcv,
)
from daily_completion import completed_daily_only
from engine.columns import COL_CLOSE, COL_OPEN
from evidence.demand import _collect_no_supply
from evidence.engine import EvidenceEngine
from evidence.rules import (
    has_weak_spread,
    is_bearish_bar,
    is_low_volume,
    is_narrow_spread,
    is_weak_close,
    volume_decreasing,
)
from market_structure.structure_filter import StructureFilter
from market_structure.swing_engine import SwingEngine
from metrics_engine import MetricsEngine
from models import EvidenceCode
from trading_calendar import NSETradingCalendar, TradingCalendar
from trend import TrendAnalyzer


DAILY_NO_SUPPLY_ENVIRONMENT_REPLAY_AUDIT_ID = (
    "daily-event-no-supply-environment-replay-v1"
)
NO_SUPPLY_BULLISH_PREDICATE_CANDIDATE_ID = (
    "no-supply-align-predicate-to-bullish-label"
)


@dataclass(frozen=True, slots=True)
class NoSupplyEnvironmentSourceLineage:
    l5_audit_id: str
    l5_summary_sha256: str
    l5_correction_candidates_sha256: str
    l3_audit_id: str
    l3_summary_sha256: str
    l3_observations_sha256: str
    snapshot_audit_id: str
    snapshot_manifest_sha256: str
    snapshot_basket_name: str
    snapshot_period: str
    snapshot_cutoff: str
    l1_summary_sha256: str
    l1_emissions_sha256: str
    l2_summary_sha256: str


@dataclass(frozen=True, slots=True)
class NoSupplyEnvironmentSources:
    lineage: NoSupplyEnvironmentSourceLineage
    bundle: DailyAuditInputBundle
    baseline_current: pd.DataFrame


@dataclass(frozen=True, slots=True)
class NoSupplyEnvironmentObservation:
    symbol: str
    bar_index: int
    session: str
    trend_direction: str
    current_bearish_environment: bool
    alternate_bullish_environment: bool
    current_candidate: bool
    alternate_candidate: bool
    confirmation_count: int
    passed_confirmation_count: int
    passed_confirmations: tuple[str, ...]
    failed_confirmations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class NoSupplySymbolReplaySummary:
    symbol: str
    evaluated_target_count: int
    replayed_bearish_target_count: int
    skipped_non_bearish_target_count: int
    common_signature_count: int
    current_candidate_count: int
    alternate_candidate_count: int
    neither_environment_count: int


@dataclass(frozen=True, slots=True)
class NoSupplyReplayFailure:
    symbol: str
    exception_type: str
    reason: str


@dataclass(frozen=True, slots=True)
class NoSupplyIdentityMismatch:
    side: str
    symbol: str
    session: str
    code: str


@dataclass(frozen=True, slots=True)
class NoSupplyBarIndexDrift:
    symbol: str
    session: str
    baseline_bar_index: int
    replay_bar_index: int
    index_delta: int


@dataclass(frozen=True, slots=True)
class NoSupplyEnvironmentReplayAudit:
    audit_id: str
    source_lineage: NoSupplyEnvironmentSourceLineage
    requested_symbol_count: int
    succeeded_symbol_count: int
    failed_symbol_count: int
    snapshot_worker_count: int
    evaluated_target_count: int
    replayed_bearish_target_count: int
    skipped_non_bearish_target_count: int
    common_signature_count: int
    current_baseline_event_count: int
    current_replay_event_count: int
    alternate_replay_event_count: int
    current_identity_mismatch_count: int
    current_bar_index_mismatch_count: int
    current_alternate_overlap_count: int
    current_only_count: int
    alternate_only_count: int
    neither_environment_count: int
    observations: tuple[NoSupplyEnvironmentObservation, ...]
    symbol_rows: tuple[NoSupplySymbolReplaySummary, ...]
    identity_mismatches: tuple[NoSupplyIdentityMismatch, ...]
    bar_index_drifts: tuple[NoSupplyBarIndexDrift, ...]
    failures: tuple[NoSupplyReplayFailure, ...]

    @property
    def is_actionable(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class NoSupplyEnvironmentReplayPaths:
    summary_json: Path
    observations_csv: Path
    symbol_summary_csv: Path
    identity_mismatch_csv: Path
    index_drift_csv: Path
    failures_csv: Path

    def as_dict(self) -> dict[str, str]:
        return {
            "summary_json": str(self.summary_json),
            "observations_csv": str(self.observations_csv),
            "symbol_summary_csv": str(self.symbol_summary_csv),
            "identity_mismatch_csv": str(self.identity_mismatch_csv),
            "index_drift_csv": str(self.index_drift_csv),
            "failures_csv": str(self.failures_csv),
        }


def _sha256_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _normalize_session(value: object) -> str:
    return pd.Timestamp(value).isoformat()


def _split_names(value: object) -> tuple[str, ...]:
    if value is None or pd.isna(value):
        return ()
    text = str(value).strip()
    if not text:
        return ()
    return tuple(item for item in text.split("|") if item)


def _validate_design_candidate(candidates: pd.DataFrame) -> None:
    required = {
        "candidate_id",
        "code",
        "effect_class",
        "data_sufficiency",
        "requires_replay",
        "projected_event_count",
    }
    missing = sorted(required - set(candidates.columns))
    if missing:
        raise ValueError(
            f"L5 correction candidates missing columns: {missing}"
        )

    selected = candidates.loc[
        candidates["candidate_id"]
        == NO_SUPPLY_BULLISH_PREDICATE_CANDIDATE_ID
    ]
    if len(selected) != 1:
        raise ValueError(
            "L5 must contain exactly one NO_SUPPLY bullish predicate "
            "candidate"
        )
    row = selected.iloc[0]
    if str(row["code"]) != "no_supply":
        raise ValueError("L5 replay candidate must target no_supply")
    if str(row["effect_class"]) != "MANDATORY_PREDICATE_CHANGE":
        raise ValueError("unexpected L5 replay candidate effect_class")
    if str(row["data_sufficiency"]) != "REPLAY_REQUIRED":
        raise ValueError("L5 replay candidate must require replay")
    if str(row["requires_replay"]).lower() not in {"true", "1"}:
        raise ValueError("L5 replay candidate is not marked replay-required")
    if not pd.isna(row["projected_event_count"]):
        raise ValueError(
            "L5 must not project the alternate predicate event count"
        )


def load_no_supply_environment_sources(
    *,
    design_dir: str | Path,
    confirmation_dir: str | Path,
    input_snapshot_dir: str | Path,
    basket_name: str,
) -> NoSupplyEnvironmentSources:
    design_root = Path(design_dir)
    confirmation_root = Path(confirmation_dir)
    snapshot_root = Path(input_snapshot_dir)

    l5_summary_path = (
        design_root / "daily_detector_correction_design_summary.json"
    )
    l5_candidates_path = (
        design_root / "daily_detector_correction_candidates.csv"
    )
    l3_summary_path = (
        confirmation_root
        / "daily_confirmation_counterfactual_summary.json"
    )
    l3_observations_path = (
        confirmation_root / "daily_confirmation_observations.csv"
    )

    for path in (
        l5_summary_path,
        l5_candidates_path,
        l3_summary_path,
        l3_observations_path,
    ):
        if not path.exists():
            raise FileNotFoundError(path)

    l5_summary = json.loads(
        l5_summary_path.read_text(encoding="utf-8")
    )
    if (
        l5_summary.get("audit_id")
        != DAILY_DETECTOR_CORRECTION_DESIGN_AUDIT_ID
    ):
        raise ValueError("unexpected L5 audit_id")
    if l5_summary.get("is_actionable") is not False:
        raise ValueError("L6 requires non-actionable L5 source")

    l5_lineage = l5_summary.get("source_lineage")
    if not isinstance(l5_lineage, dict):
        raise ValueError("L5 source lineage is missing")

    l3_summary_sha256 = _sha256_file(l3_summary_path)
    l3_observations_sha256 = _sha256_file(l3_observations_path)
    if (
        str(l5_lineage.get("l3_summary_sha256", ""))
        != l3_summary_sha256
    ):
        raise ValueError("L5 points to a different L3 summary")
    if (
        str(l5_lineage.get("l3_observations_sha256", ""))
        != l3_observations_sha256
    ):
        raise ValueError("L5 points to a different L3 observation ledger")

    l3_summary = json.loads(
        l3_summary_path.read_text(encoding="utf-8")
    )
    if l3_summary.get("audit_id") != l5_lineage.get("l3_audit_id"):
        raise ValueError("L5/L3 audit id mismatch")
    if int(l3_summary.get("failed_symbol_count", -1)) != 0:
        raise ValueError("L6 requires zero-failure canonical L3")
    if int(l3_summary.get("identity_mismatch_count", -1)) != 0:
        raise ValueError("L6 requires exact L3 identity parity")
    if int(l3_summary.get("bar_index_mismatch_count", -1)) != 0:
        raise ValueError("L6 requires exact L3 bar-index parity")

    l5_candidates = pd.read_csv(l5_candidates_path)
    _validate_design_candidate(l5_candidates)

    observations = pd.read_csv(l3_observations_path)
    required_l3 = {"symbol", "bar_index", "session", "code"}
    missing_l3 = sorted(required_l3 - set(observations.columns))
    if missing_l3:
        raise ValueError(
            f"L3 observations missing columns: {missing_l3}"
        )
    current = (
        observations.loc[
            observations["code"] == "no_supply",
            ["symbol", "bar_index", "session", "code"],
        ]
        .drop_duplicates()
        .copy()
    )
    current["symbol"] = current["symbol"].map(
        lambda value: str(value).strip().upper()
    )
    current["session"] = current["session"].map(_normalize_session)
    current = current.sort_values(
        ["symbol", "bar_index", "session", "code"]
    ).reset_index(drop=True)

    bundle = load_daily_audit_input_bundle(snapshot_root)
    manifest_sha256 = daily_audit_input_manifest_sha256(snapshot_root)
    if bundle.basket_name != basket_name:
        raise ValueError("snapshot basket does not match requested basket")
    if (
        manifest_sha256
        != str(l5_lineage.get("snapshot_manifest_sha256", ""))
    ):
        raise ValueError("snapshot manifest hash does not match L5 lineage")

    l3_lineage = l3_summary.get("source_lineage")
    if not isinstance(l3_lineage, dict):
        raise ValueError("L3 source lineage is missing")
    for key in (
        "l1_summary_sha256",
        "l1_emissions_sha256",
        "l2_summary_sha256",
        "snapshot_manifest_sha256",
    ):
        if str(l5_lineage.get(key, "")) != str(l3_lineage.get(key, "")):
            raise ValueError(f"L5/L3 lineage mismatch for {key}")

    lineage = NoSupplyEnvironmentSourceLineage(
        l5_audit_id=str(l5_summary["audit_id"]),
        l5_summary_sha256=_sha256_file(l5_summary_path),
        l5_correction_candidates_sha256=_sha256_file(
            l5_candidates_path
        ),
        l3_audit_id=str(l3_summary["audit_id"]),
        l3_summary_sha256=l3_summary_sha256,
        l3_observations_sha256=l3_observations_sha256,
        snapshot_audit_id=bundle.audit_id,
        snapshot_manifest_sha256=manifest_sha256,
        snapshot_basket_name=bundle.basket_name,
        snapshot_period=bundle.period,
        snapshot_cutoff=bundle.cutoff,
        l1_summary_sha256=str(l3_lineage["l1_summary_sha256"]),
        l1_emissions_sha256=str(
            l3_lineage["l1_emissions_sha256"]
        ),
        l2_summary_sha256=str(l3_lineage["l2_summary_sha256"]),
    )
    return NoSupplyEnvironmentSources(
        lineage=lineage,
        bundle=bundle,
        baseline_current=current,
    )


def is_raw_bearish_target(row: pd.Series) -> bool:
    """Production-equivalent prefilter for is_bearish_bar()."""

    return float(row[COL_CLOSE]) < float(row[COL_OPEN])


@contextmanager
def _suppress_vsa_info_logs() -> Iterator[None]:
    logger = logging.getLogger("VSA")
    previous_level = logger.level
    logger.setLevel(logging.WARNING)
    try:
        yield
    finally:
        logger.setLevel(previous_level)


def _evaluate_no_supply_target(
    daily_prefix: pd.DataFrame,
) -> NoSupplyEnvironmentObservation | None:
    _validate_daily_ohlcv(daily_prefix)
    metrics = MetricsEngine().calculate(_metrics_input(daily_prefix))

    engine = EvidenceEngine()
    target_index = len(metrics) - 1
    metrics_bar = engine._create_bar_context(
        metrics.iloc[target_index],
        target_index,
    )
    common_signature = (
        is_bearish_bar(metrics_bar)
        and is_low_volume(metrics_bar)
        and is_narrow_spread(metrics_bar)
    )
    if not common_signature:
        return None

    swings = SwingEngine().calculate(metrics)
    structural_swings = StructureFilter().filter(list(swings), metrics)
    trend = TrendAnalyzer().analyze_from_swings(
        metrics,
        swings,
        structural_swings=structural_swings,
    )

    engine._reset(
        metrics=metrics,
        trend=trend,
        structural_swings=tuple(structural_swings),
    )
    ctx = engine._ctx
    if ctx is None:
        raise RuntimeError("EvidenceEngine did not build a context")

    current_bar = ctx.current
    if not (
        is_bearish_bar(current_bar)
        and is_low_volume(current_bar)
        and is_narrow_spread(current_bar)
    ):
        raise RuntimeError(
            "NO_SUPPLY metrics prefilter changed after context build"
        )
    production = tuple(_collect_no_supply(ctx))
    production_current = any(
        item.code == EvidenceCode.NO_SUPPLY
        for item in production
    )
    expected_current = (
        common_signature and ctx.is_bearish_environment()
    )
    if production_current != expected_current:
        raise RuntimeError(
            "direct NO_SUPPLY current predicate does not match production"
        )

    confirmations = (
        ("Weak Spread", has_weak_spread(current_bar)),
        (
            "Volume Decreasing",
            volume_decreasing(current_bar, ctx.previous),
        ),
        ("Weak Selling Result", is_weak_close(current_bar)),
    )
    passed = tuple(name for name, value in confirmations if value)
    failed = tuple(name for name, value in confirmations if not value)
    return NoSupplyEnvironmentObservation(
        symbol="",
        bar_index=current_bar.bar_index,
        session=_normalize_session(current_bar.week_beginning),
        trend_direction=ctx.trend.direction.name,
        current_bearish_environment=ctx.is_bearish_environment(),
        alternate_bullish_environment=ctx.is_bullish_environment(),
        current_candidate=expected_current,
        alternate_candidate=(
            common_signature and ctx.is_bullish_environment()
        ),
        confirmation_count=len(confirmations),
        passed_confirmation_count=len(passed),
        passed_confirmations=passed,
        failed_confirmations=failed,
    )


def replay_symbol_no_supply_environment(
    *,
    symbol: str,
    daily: pd.DataFrame,
    now: str,
    min_target_index: int = DEFAULT_DAILY_EVIDENCE_MIN_TARGET_INDEX,
    calendar: TradingCalendar | None = None,
) -> tuple[
    tuple[NoSupplyEnvironmentObservation, ...],
    NoSupplySymbolReplaySummary,
]:
    clean_symbol = str(symbol).strip().upper()
    if not clean_symbol:
        raise ValueError("symbol cannot be blank")
    if min_target_index < 0:
        raise ValueError("min_target_index cannot be negative")

    _validate_daily_ohlcv(daily)
    exchange_calendar = calendar or NSETradingCalendar()
    completed = completed_daily_only(
        daily,
        now=now,
        calendar=exchange_calendar,
    )
    if completed.empty:
        raise ValueError("no completed daily bars are available")
    _validate_daily_ohlcv(completed)

    observations: list[NoSupplyEnvironmentObservation] = []
    evaluated = max(0, len(completed) - min_target_index)
    replayed = 0

    with _suppress_vsa_info_logs():
        for target_index in range(min_target_index, len(completed)):
            raw_row = completed.iloc[target_index]
            if not is_raw_bearish_target(raw_row):
                continue
            replayed += 1
            prefix = completed.iloc[: target_index + 1].copy()
            observation = _evaluate_no_supply_target(prefix)
            if observation is None:
                continue
            if observation.bar_index != target_index:
                raise ValueError(
                    "NO_SUPPLY replay returned wrong target bar index"
                )
            observations.append(
                NoSupplyEnvironmentObservation(
                    symbol=clean_symbol,
                    bar_index=observation.bar_index,
                    session=observation.session,
                    trend_direction=observation.trend_direction,
                    current_bearish_environment=(
                        observation.current_bearish_environment
                    ),
                    alternate_bullish_environment=(
                        observation.alternate_bullish_environment
                    ),
                    current_candidate=observation.current_candidate,
                    alternate_candidate=observation.alternate_candidate,
                    confirmation_count=observation.confirmation_count,
                    passed_confirmation_count=(
                        observation.passed_confirmation_count
                    ),
                    passed_confirmations=observation.passed_confirmations,
                    failed_confirmations=observation.failed_confirmations,
                )
            )

    current_count = sum(item.current_candidate for item in observations)
    alternate_count = sum(
        item.alternate_candidate for item in observations
    )
    neither_count = sum(
        not item.current_candidate and not item.alternate_candidate
        for item in observations
    )
    summary = NoSupplySymbolReplaySummary(
        symbol=clean_symbol,
        evaluated_target_count=evaluated,
        replayed_bearish_target_count=replayed,
        skipped_non_bearish_target_count=evaluated - replayed,
        common_signature_count=len(observations),
        current_candidate_count=current_count,
        alternate_candidate_count=alternate_count,
        neither_environment_count=neither_count,
    )
    return tuple(observations), summary


def _identity(
    symbol: str,
    session: object,
) -> tuple[str, str]:
    return (
        str(symbol).strip().upper(),
        _normalize_session(session),
    )


def build_no_supply_environment_replay_audit(
    *,
    source_lineage: NoSupplyEnvironmentSourceLineage,
    requested_symbols: tuple[str, ...],
    baseline_current: pd.DataFrame,
    observations: tuple[NoSupplyEnvironmentObservation, ...],
    symbol_rows: tuple[NoSupplySymbolReplaySummary, ...],
    failures: tuple[NoSupplyReplayFailure, ...] = (),
    snapshot_worker_count: int = 1,
) -> NoSupplyEnvironmentReplayAudit:
    symbols = tuple(
        str(symbol).strip().upper()
        for symbol in requested_symbols
    )
    if not symbols or len(set(symbols)) != len(symbols):
        raise ValueError("requested symbols must be non-empty and unique")
    if snapshot_worker_count < 1:
        raise ValueError("snapshot_worker_count must be positive")

    failure_symbols = {item.symbol for item in failures}
    if not failure_symbols <= set(symbols):
        raise ValueError("failure symbols must belong to requested symbols")

    selected_baseline = baseline_current.loc[
        baseline_current["symbol"].isin(symbols)
    ].copy()
    baseline_ids = {
        _identity(row.symbol, row.session)
        for row in selected_baseline.itertuples(index=False)
    }
    current_ids = {
        _identity(item.symbol, item.session)
        for item in observations
        if item.current_candidate
    }
    alternate_ids = {
        _identity(item.symbol, item.session)
        for item in observations
        if item.alternate_candidate
    }

    missing = baseline_ids - current_ids
    extra = current_ids - baseline_ids
    identity_mismatches = tuple(
        [
            NoSupplyIdentityMismatch(
                side="MISSING_FROM_REPLAY",
                symbol=symbol,
                session=session,
                code="no_supply",
            )
            for symbol, session in sorted(missing)
        ]
        + [
            NoSupplyIdentityMismatch(
                side="EXTRA_IN_REPLAY",
                symbol=symbol,
                session=session,
                code="no_supply",
            )
            for symbol, session in sorted(extra)
        ]
    )

    baseline_indexes = {
        _identity(row.symbol, row.session): int(row.bar_index)
        for row in selected_baseline.itertuples(index=False)
    }
    replay_indexes = {
        _identity(item.symbol, item.session): int(item.bar_index)
        for item in observations
        if item.current_candidate
    }
    bar_index_drifts = tuple(
        NoSupplyBarIndexDrift(
            symbol=symbol,
            session=session,
            baseline_bar_index=baseline_indexes[(symbol, session)],
            replay_bar_index=replay_indexes[(symbol, session)],
            index_delta=(
                replay_indexes[(symbol, session)]
                - baseline_indexes[(symbol, session)]
            ),
        )
        for symbol, session in sorted(baseline_ids & current_ids)
        if baseline_indexes[(symbol, session)]
        != replay_indexes[(symbol, session)]
    )

    observation_ids = [
        _identity(item.symbol, item.session)
        for item in observations
    ]
    if len(observation_ids) != len(set(observation_ids)):
        raise ValueError(
            "NO_SUPPLY replay observations contain duplicate identities"
        )
    if any(item.symbol not in symbols for item in observations):
        raise ValueError(
            "NO_SUPPLY replay observations contain unrequested symbols"
        )

    rows_by_symbol = {item.symbol: item for item in symbol_rows}
    if len(rows_by_symbol) != len(symbol_rows):
        raise ValueError("symbol summaries contain duplicate symbols")
    if set(rows_by_symbol) != set(symbols) - failure_symbols:
        raise ValueError(
            "symbol summaries must cover every successful requested symbol"
        )
    for symbol, row in rows_by_symbol.items():
        if (
            row.evaluated_target_count
            != row.replayed_bearish_target_count
            + row.skipped_non_bearish_target_count
        ):
            raise ValueError(
                f"{symbol} evaluated target accounting does not close"
            )
        symbol_observations = tuple(
            item for item in observations if item.symbol == symbol
        )
        current_count = sum(
            item.current_candidate for item in symbol_observations
        )
        alternate_count = sum(
            item.alternate_candidate for item in symbol_observations
        )
        neither_count = sum(
            not item.current_candidate and not item.alternate_candidate
            for item in symbol_observations
        )
        if row.common_signature_count != len(symbol_observations):
            raise ValueError(
                f"{symbol} common signature count does not reconcile"
            )
        if row.current_candidate_count != current_count:
            raise ValueError(
                f"{symbol} current candidate count does not reconcile"
            )
        if row.alternate_candidate_count != alternate_count:
            raise ValueError(
                f"{symbol} alternate candidate count does not reconcile"
            )
        if row.neither_environment_count != neither_count:
            raise ValueError(
                f"{symbol} neither-environment count does not reconcile"
            )

    overlap = current_ids & alternate_ids
    return NoSupplyEnvironmentReplayAudit(
        audit_id=DAILY_NO_SUPPLY_ENVIRONMENT_REPLAY_AUDIT_ID,
        source_lineage=source_lineage,
        requested_symbol_count=len(symbols),
        succeeded_symbol_count=len(symbols) - len(failures),
        failed_symbol_count=len(failures),
        snapshot_worker_count=snapshot_worker_count,
        evaluated_target_count=sum(
            item.evaluated_target_count for item in symbol_rows
        ),
        replayed_bearish_target_count=sum(
            item.replayed_bearish_target_count for item in symbol_rows
        ),
        skipped_non_bearish_target_count=sum(
            item.skipped_non_bearish_target_count for item in symbol_rows
        ),
        common_signature_count=len(observations),
        current_baseline_event_count=len(baseline_ids),
        current_replay_event_count=len(current_ids),
        alternate_replay_event_count=len(alternate_ids),
        current_identity_mismatch_count=len(identity_mismatches),
        current_bar_index_mismatch_count=len(bar_index_drifts),
        current_alternate_overlap_count=len(overlap),
        current_only_count=len(current_ids - alternate_ids),
        alternate_only_count=len(alternate_ids - current_ids),
        neither_environment_count=sum(
            not item.current_candidate and not item.alternate_candidate
            for item in observations
        ),
        observations=tuple(
            sorted(
                observations,
                key=lambda item: (
                    symbols.index(item.symbol),
                    item.bar_index,
                    item.session,
                ),
            )
        ),
        symbol_rows=tuple(
            rows_by_symbol[symbol]
            for symbol in symbols
            if symbol in rows_by_symbol
        ),
        identity_mismatches=identity_mismatches,
        bar_index_drifts=bar_index_drifts,
        failures=tuple(
            sorted(failures, key=lambda item: item.symbol)
        ),
    )


def write_no_supply_environment_replay_audit(
    audit: NoSupplyEnvironmentReplayAudit,
    output_dir: str | Path,
) -> NoSupplyEnvironmentReplayPaths:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    paths = NoSupplyEnvironmentReplayPaths(
        summary_json=root / "daily_no_supply_environment_replay_summary.json",
        observations_csv=root / "daily_no_supply_environment_observations.csv",
        symbol_summary_csv=root / "daily_no_supply_environment_symbols.csv",
        identity_mismatch_csv=(
            root / "daily_no_supply_current_identity_mismatch.csv"
        ),
        index_drift_csv=(
            root / "daily_no_supply_current_index_drift.csv"
        ),
        failures_csv=root / "daily_no_supply_environment_failures.csv",
    )

    summary = {
        "audit_id": audit.audit_id,
        "requested_symbol_count": audit.requested_symbol_count,
        "succeeded_symbol_count": audit.succeeded_symbol_count,
        "failed_symbol_count": audit.failed_symbol_count,
        "snapshot_worker_count": audit.snapshot_worker_count,
        "evaluated_target_count": audit.evaluated_target_count,
        "replayed_bearish_target_count": (
            audit.replayed_bearish_target_count
        ),
        "skipped_non_bearish_target_count": (
            audit.skipped_non_bearish_target_count
        ),
        "common_signature_count": audit.common_signature_count,
        "trend_context_replay_count": audit.common_signature_count,
        "current_baseline_event_count": (
            audit.current_baseline_event_count
        ),
        "current_replay_event_count": audit.current_replay_event_count,
        "alternate_replay_event_count": (
            audit.alternate_replay_event_count
        ),
        "current_identity_mismatch_count": (
            audit.current_identity_mismatch_count
        ),
        "current_bar_index_mismatch_count": (
            audit.current_bar_index_mismatch_count
        ),
        "current_alternate_overlap_count": (
            audit.current_alternate_overlap_count
        ),
        "current_only_count": audit.current_only_count,
        "alternate_only_count": audit.alternate_only_count,
        "neither_environment_count": audit.neither_environment_count,
        "source_lineage": asdict(audit.source_lineage),
        "is_actionable": False,
    }
    paths.summary_json.write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    pd.DataFrame(
        [
            {
                **asdict(item),
                "passed_confirmations": "|".join(
                    item.passed_confirmations
                ),
                "failed_confirmations": "|".join(
                    item.failed_confirmations
                ),
            }
            for item in audit.observations
        ]
    ).to_csv(paths.observations_csv, index=False)
    pd.DataFrame(
        [asdict(item) for item in audit.symbol_rows]
    ).to_csv(paths.symbol_summary_csv, index=False)
    pd.DataFrame(
        [asdict(item) for item in audit.identity_mismatches]
    ).to_csv(paths.identity_mismatch_csv, index=False)
    pd.DataFrame(
        [asdict(item) for item in audit.bar_index_drifts]
    ).to_csv(paths.index_drift_csv, index=False)
    pd.DataFrame(
        [asdict(item) for item in audit.failures]
    ).to_csv(paths.failures_csv, index=False)
    return paths


__all__ = [
    "DAILY_NO_SUPPLY_ENVIRONMENT_REPLAY_AUDIT_ID",
    "NO_SUPPLY_BULLISH_PREDICATE_CANDIDATE_ID",
    "NoSupplyBarIndexDrift",
    "NoSupplyEnvironmentObservation",
    "NoSupplyEnvironmentReplayAudit",
    "NoSupplyEnvironmentReplayPaths",
    "NoSupplyEnvironmentSourceLineage",
    "NoSupplyEnvironmentSources",
    "NoSupplyIdentityMismatch",
    "NoSupplyReplayFailure",
    "NoSupplySymbolReplaySummary",
    "build_no_supply_environment_replay_audit",
    "is_raw_bearish_target",
    "load_no_supply_environment_sources",
    "replay_symbol_no_supply_environment",
    "write_no_supply_environment_replay_audit",
]
