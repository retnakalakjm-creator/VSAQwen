"""Causal semantic replay for BUYING_CLIMAX vs UPTHRUST.

L17 is deliberately bounded by the L16 semantic design. It replays three
predeclared populations only:

* BUYING_CLIMAX current effort/background core, partitioned by existing
  close-position acceptance geometry.
* UPTHRUST local previous-high rejection.
* UPTHRUST latest causally confirmed structural-high rejection.

The replay uses frozen daily snapshots, performs no outcome analysis, tunes no
thresholds, and changes no production behavior.
"""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Iterator, Sequence

import pandas as pd

from audit.daily_event_confirmation_semantics import (
    load_canonical_l3_observations,
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
from daily_completion import completed_daily_only
from evidence.engine import EvidenceEngine
from evidence.rules import (
    is_above_average_spread,
    is_bullish_bar,
    is_very_high_volume,
)
from market_structure.structure_filter import StructureFilter
from market_structure.swing_engine import SwingEngine
from metrics_engine import MetricsEngine
from models import (
    BarContext,
    ClosePosition,
    Direction,
    EvidenceCode,
    SpreadClass,
    StructuralSwing,
    SwingType,
    VolumeClass,
)
from trading_calendar import NSETradingCalendar, TradingCalendar


DAILY_BC_UPTHRUST_SEMANTIC_REPLAY_AUDIT_ID = (
    "daily-event-bc-upthrust-semantic-replay-v1"
)

BC_CODE = EvidenceCode.BUYING_CLIMAX.value

POPULATION_BC_CORE = "BC_EFFORT_CORE"
POPULATION_UT_LOCAL = "UT_LOCAL_PREVIOUS_HIGH_REJECTION"
POPULATION_UT_STRUCTURAL = "UT_STRUCTURAL_HIGH_REJECTION"
POPULATION_ORDER = (
    POPULATION_BC_CORE,
    POPULATION_UT_LOCAL,
    POPULATION_UT_STRUCTURAL,
)

BC_ACCEPTANCE_STRONG = "STRONG_HIGH_ACCEPTANCE"
BC_ACCEPTANCE_MIDDLE = "MIDDLE_ACCEPTANCE"
BC_ACCEPTANCE_WEAK = "WEAK_LOWER_ACCEPTANCE"
BC_ACCEPTANCE_ORDER = (
    BC_ACCEPTANCE_STRONG,
    BC_ACCEPTANCE_MIDDLE,
    BC_ACCEPTANCE_WEAK,
)

DESCRIPTOR_DIMENSIONS = (
    "direction",
    "volume_class",
    "spread_class",
    "close_position",
)


@dataclass(frozen=True, slots=True)
class BcUpthrustSemanticReplayLineage:
    l3_audit_id: str
    l3_summary_sha256: str
    l3_observations_sha256: str
    l1_summary_sha256: str
    l1_emissions_sha256: str
    l2_summary_sha256: str
    snapshot_audit_id: str
    snapshot_manifest_sha256: str
    snapshot_basket_name: str
    snapshot_period: str
    snapshot_cutoff: str


@dataclass(frozen=True, slots=True)
class BcUpthrustSemanticSources:
    lineage: BcUpthrustSemanticReplayLineage
    bundle: DailyAuditInputBundle
    baseline_bc: pd.DataFrame


@dataclass(frozen=True, slots=True)
class BcUpthrustSemanticObservation:
    symbol: str
    bar_index: int
    session: str
    bc_effort_core: bool
    bc_acceptance: str
    ut_local_rejection: bool
    ut_structural_rejection: bool
    direction: str
    volume_class: str
    spread_class: str
    close_position: str
    close_ratio: float
    upper_shadow_ratio: float
    volume_ratio: float
    spread_ratio: float
    previous_high: float
    structural_high_reference: float | None
    structural_high_pivot_index: int | None
    structural_high_confirmation_index: int | None


@dataclass(frozen=True, slots=True)
class BcUpthrustSemanticSymbolRow:
    symbol: str
    evaluated_target_count: int
    structural_reference_available_count: int
    bc_effort_core_count: int
    ut_local_rejection_count: int
    ut_structural_rejection_count: int
    union_candidate_count: int


@dataclass(frozen=True, slots=True)
class BcUpthrustSemanticFailure:
    symbol: str
    exception_type: str
    reason: str


@dataclass(frozen=True, slots=True)
class BcUpthrustPopulationRow:
    population: str
    event_count: int
    event_share_of_evaluated: float
    symbol_count: int
    bullish_bar_rate: float
    very_high_volume_rate: float
    above_average_spread_rate: float
    weak_close_rate: float
    mean_close_ratio: float
    mean_upper_shadow_ratio: float


@dataclass(frozen=True, slots=True)
class BcAcceptanceRow:
    acceptance: str
    event_count: int
    share_of_bc_core: float
    symbol_count: int


@dataclass(frozen=True, slots=True)
class BcUpthrustDescriptorRow:
    population: str
    dimension: str
    level: str
    event_count: int
    event_share: float
    symbol_count: int


@dataclass(frozen=True, slots=True)
class BcUpthrustPairwiseRow:
    population_a: str
    population_b: str
    population_a_count: int
    population_b_count: int
    overlap_count: int
    union_count: int
    jaccard: float
    relationship: str


@dataclass(frozen=True, slots=True)
class BcParityMismatch:
    side: str
    symbol: str
    bar_index: int
    session: str


@dataclass(frozen=True, slots=True)
class BcUpthrustSemanticReplayAudit:
    audit_id: str
    source_lineage: BcUpthrustSemanticReplayLineage
    requested_symbol_count: int
    succeeded_symbol_count: int
    failed_symbol_count: int
    evaluated_target_count: int
    structural_reference_available_count: int
    baseline_bc_event_count: int
    replay_bc_event_count: int
    bc_identity_mismatch_count: int
    bc_effort_core_count: int
    ut_local_rejection_count: int
    ut_structural_rejection_count: int
    union_candidate_count: int
    population_rows: tuple[BcUpthrustPopulationRow, ...]
    acceptance_rows: tuple[BcAcceptanceRow, ...]
    descriptor_rows: tuple[BcUpthrustDescriptorRow, ...]
    pairwise_rows: tuple[BcUpthrustPairwiseRow, ...]
    symbol_rows: tuple[BcUpthrustSemanticSymbolRow, ...]
    observations: tuple[BcUpthrustSemanticObservation, ...]
    bc_parity_mismatches: tuple[BcParityMismatch, ...]
    failures: tuple[BcUpthrustSemanticFailure, ...]

    @property
    def is_actionable(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class BcUpthrustSemanticReplayPaths:
    summary_json: Path
    populations_csv: Path
    bc_acceptance_csv: Path
    descriptors_csv: Path
    pairwise_csv: Path
    symbols_csv: Path
    observations_csv: Path
    bc_parity_mismatch_csv: Path
    failures_csv: Path

    def as_dict(self) -> dict[str, str]:
        return {
            "summary_json": str(self.summary_json),
            "populations_csv": str(self.populations_csv),
            "bc_acceptance_csv": str(self.bc_acceptance_csv),
            "descriptors_csv": str(self.descriptors_csv),
            "pairwise_csv": str(self.pairwise_csv),
            "symbols_csv": str(self.symbols_csv),
            "observations_csv": str(self.observations_csv),
            "bc_parity_mismatch_csv": str(self.bc_parity_mismatch_csv),
            "failures_csv": str(self.failures_csv),
        }


def _normalize_session(value: object) -> str:
    return pd.Timestamp(value).isoformat()


def load_bc_upthrust_semantic_sources(
    *,
    confirmation_dir: str | Path,
    input_snapshot_dir: str | Path,
    basket_name: str,
) -> BcUpthrustSemanticSources:
    _, observations, l3_lineage = load_canonical_l3_observations(
        confirmation_dir
    )
    snapshot_root = Path(input_snapshot_dir)
    bundle = load_daily_audit_input_bundle(snapshot_root)
    manifest_sha256 = daily_audit_input_manifest_sha256(snapshot_root)

    if bundle.basket_name != basket_name:
        raise ValueError("snapshot basket does not match requested basket")
    if bundle.symbol_count != 30:
        raise ValueError("L17 canonical replay requires 30 symbols")
    if manifest_sha256 != l3_lineage.snapshot_manifest_sha256:
        raise ValueError("snapshot manifest differs from canonical L3")
    if bundle.period != "max":
        raise ValueError("L17 requires the frozen full-history snapshot")

    baseline = observations.loc[
        observations["code"] == BC_CODE,
        ["symbol", "bar_index", "session"],
    ].copy()
    baseline["symbol"] = baseline["symbol"].map(
        lambda value: str(value).strip().upper()
    )
    baseline["session"] = baseline["session"].map(_normalize_session)
    baseline = baseline.drop_duplicates().sort_values(
        ["symbol", "bar_index", "session"]
    ).reset_index(drop=True)
    if len(baseline) != 4497:
        raise ValueError(
            "canonical BUYING_CLIMAX baseline count changed: "
            f"{len(baseline)}"
        )
    if int(baseline["symbol"].nunique()) != 30:
        raise ValueError("canonical BUYING_CLIMAX must span 30 symbols")

    lineage = BcUpthrustSemanticReplayLineage(
        l3_audit_id=l3_lineage.l3_audit_id,
        l3_summary_sha256=l3_lineage.l3_summary_sha256,
        l3_observations_sha256=l3_lineage.l3_observations_sha256,
        l1_summary_sha256=l3_lineage.l1_summary_sha256,
        l1_emissions_sha256=l3_lineage.l1_emissions_sha256,
        l2_summary_sha256=l3_lineage.l2_summary_sha256,
        snapshot_audit_id=bundle.audit_id,
        snapshot_manifest_sha256=manifest_sha256,
        snapshot_basket_name=bundle.basket_name,
        snapshot_period=bundle.period,
        snapshot_cutoff=bundle.cutoff,
    )
    return BcUpthrustSemanticSources(
        lineage=lineage,
        bundle=bundle,
        baseline_bc=baseline,
    )


def classify_bc_acceptance(bar: BarContext) -> str:
    if bar.close_position in (ClosePosition.UPPER, ClosePosition.ON_HIGH):
        return BC_ACCEPTANCE_STRONG
    if bar.close_position == ClosePosition.MIDDLE:
        return BC_ACCEPTANCE_MIDDLE
    if bar.close_position in (ClosePosition.LOWER, ClosePosition.ON_LOW):
        return BC_ACCEPTANCE_WEAK
    raise ValueError(f"unsupported close position: {bar.close_position!r}")


def rejects_reference_high(
    bar: BarContext,
    reference_high: float,
) -> bool:
    if reference_high <= 0.0:
        raise ValueError("reference_high must be positive")
    return (
        float(bar.high) > float(reference_high)
        and float(bar.close_price) <= float(reference_high)
    )


def _latest_structural_high(
    structural_swings: Sequence[StructuralSwing],
    *,
    target_index: int,
) -> StructuralSwing | None:
    highs = [
        item
        for item in structural_swings
        if item.swing.type is SwingType.HIGH
        and item.swing.confirmation_index <= target_index
        and item.swing.bar_index < target_index
    ]
    if not highs:
        return None
    return max(
        highs,
        key=lambda item: (
            item.swing.confirmation_index,
            item.swing.bar_index,
        ),
    )


def _upper_shadow_ratio(bar: BarContext) -> float:
    spread = float(bar.high) - float(bar.low)
    if spread <= 0.0:
        return 0.0
    return float(bar.upper_shadow) / spread


@contextmanager
def _suppress_vsa_info_logs() -> Iterator[None]:
    logger = logging.getLogger("VSA")
    previous = logger.level
    logger.setLevel(logging.WARNING)
    try:
        yield
    finally:
        logger.setLevel(previous)


def replay_symbol_bc_upthrust_semantics(
    *,
    symbol: str,
    daily: pd.DataFrame,
    baseline_bc: pd.DataFrame,
    now: str,
    min_target_index: int = DEFAULT_DAILY_EVIDENCE_MIN_TARGET_INDEX,
    calendar: TradingCalendar | None = None,
    progress_writer: Callable[[str], None] | None = None,
    progress_every: int = 2000,
) -> tuple[
    tuple[BcUpthrustSemanticObservation, ...],
    BcUpthrustSemanticSymbolRow,
]:
    """Replay L17 populations with one metrics/structure pass per symbol.

    BUYING_CLIMAX identity comes from the canonical L3 production ledger and is
    verified against the frozen snapshot's exact bar index/session. UPTHRUST
    local geometry is evaluated bar by bar from causal OHLC. Structural-high
    geometry uses the full batch of structural swings only as a cache; a swing
    is eligible at a target bar only when its confirmation_index is already
    reached. StructureFilter explicitly guarantees that a confirmed swing's
    professional evaluation depends only on that swing and earlier history.
    """

    clean_symbol = str(symbol).strip().upper()
    if not clean_symbol:
        raise ValueError("symbol cannot be blank")
    if min_target_index < 1:
        raise ValueError("min_target_index must be at least 1")
    if progress_every <= 0:
        raise ValueError("progress_every must be positive")

    _validate_daily_ohlcv(daily)
    completed = completed_daily_only(
        daily,
        now=now,
        calendar=calendar or NSETradingCalendar(),
    )
    if completed.empty:
        raise ValueError("no completed daily bars are available")
    _validate_daily_ohlcv(completed)

    if min_target_index >= len(completed):
        return (), BcUpthrustSemanticSymbolRow(
            symbol=clean_symbol,
            evaluated_target_count=0,
            structural_reference_available_count=0,
            bc_effort_core_count=0,
            ut_local_rejection_count=0,
            ut_structural_rejection_count=0,
            union_candidate_count=0,
        )

    if progress_writer is not None:
        progress_writer(
            f"[daily-bc-ut-l17] {clean_symbol}: building metrics"
        )
    metrics = MetricsEngine().calculate(_metrics_input(completed))
    engine = EvidenceEngine()
    bars = tuple(
        engine._create_bar_context(metrics.iloc[index], index)
        for index in range(len(metrics))
    )

    # One causal-stable batch per symbol. StructuralSwing evaluations are stable
    # after confirmation by StructureFilter contract; eligibility below still
    # requires confirmation_index <= target_index.
    if progress_writer is not None:
        progress_writer(
            f"[daily-bc-ut-l17] {clean_symbol}: building swings"
        )
    swings = SwingEngine().calculate(metrics)
    if progress_writer is not None:
        progress_writer(
            f"[daily-bc-ut-l17] {clean_symbol}: filtering structure"
        )
    structural = StructureFilter().filter(list(swings), metrics)
    if progress_writer is not None:
        progress_writer(
            f"[daily-bc-ut-l17] {clean_symbol}: scanning semantic geometry"
        )
    structural_highs = sorted(
        (
            item
            for item in structural
            if item.swing.type is SwingType.HIGH
        ),
        key=lambda item: (
            item.swing.confirmation_index,
            item.swing.bar_index,
        ),
    )

    symbol_baseline = baseline_bc.loc[
        baseline_bc["symbol"] == clean_symbol
    ].copy()
    baseline_by_index: dict[int, str] = {}
    for row in symbol_baseline.itertuples(index=False):
        bar_index = int(row.bar_index)
        if bar_index < 0 or bar_index >= len(completed):
            raise ValueError(
                f"baseline BC bar index outside snapshot: {bar_index}"
            )
        session = _normalize_session(completed.index[bar_index])
        expected_session = _normalize_session(row.session)
        if session != expected_session:
            raise ValueError(
                "baseline BC session/index drift: "
                f"{bar_index} {session} != {expected_session}"
            )
        baseline_by_index[bar_index] = expected_session

        # Campaign qualification is inherited from the canonical production
        # ledger; the remaining mandatory bar predicates are revalidated here.
        bar = bars[bar_index]
        if not (
            is_bullish_bar(bar)
            and is_very_high_volume(bar)
            and is_above_average_spread(bar)
        ):
            raise ValueError(
                "baseline BC no longer satisfies production bar core at "
                f"{clean_symbol} {expected_session}"
            )

    observations: list[BcUpthrustSemanticObservation] = []
    structural_reference_available = 0
    local_count = 0
    structural_count = 0

    high_cursor = 0
    confirmed_highs: list[StructuralSwing] = []

    with _suppress_vsa_info_logs():
        for target_index in range(min_target_index, len(metrics)):
            while (
                high_cursor < len(structural_highs)
                and structural_highs[
                    high_cursor
                ].swing.confirmation_index <= target_index
            ):
                confirmed_highs.append(structural_highs[high_cursor])
                high_cursor += 1

            current = bars[target_index]
            previous = bars[target_index - 1]
            bc_core = target_index in baseline_by_index

            local_rejection = rejects_reference_high(
                current,
                float(previous.high),
            )

            structural_high = next(
                (
                    item
                    for item in reversed(confirmed_highs)
                    if item.swing.bar_index < target_index
                ),
                None,
            )
            if structural_high is not None:
                structural_reference_available += 1
                structural_rejection = rejects_reference_high(
                    current,
                    float(structural_high.swing.price),
                )
                structural_price: float | None = float(
                    structural_high.swing.price
                )
                structural_pivot: int | None = int(
                    structural_high.swing.bar_index
                )
                structural_confirmation: int | None = int(
                    structural_high.swing.confirmation_index
                )
            else:
                structural_rejection = False
                structural_price = None
                structural_pivot = None
                structural_confirmation = None

            if local_rejection:
                local_count += 1
            if structural_rejection:
                structural_count += 1

            if bc_core or local_rejection or structural_rejection:
                observations.append(
                    BcUpthrustSemanticObservation(
                        symbol=clean_symbol,
                        bar_index=target_index,
                        session=_normalize_session(
                            completed.index[target_index]
                        ),
                        bc_effort_core=bc_core,
                        bc_acceptance=(
                            classify_bc_acceptance(current)
                            if bc_core
                            else ""
                        ),
                        ut_local_rejection=local_rejection,
                        ut_structural_rejection=structural_rejection,
                        direction=current.direction.name,
                        volume_class=current.volume.name,
                        spread_class=current.spread.name,
                        close_position=current.close_position.name,
                        close_ratio=float(current.close_ratio),
                        upper_shadow_ratio=_upper_shadow_ratio(current),
                        volume_ratio=float(current.volume_ratio),
                        spread_ratio=float(current.spread_ratio),
                        previous_high=float(previous.high),
                        structural_high_reference=structural_price,
                        structural_high_pivot_index=structural_pivot,
                        structural_high_confirmation_index=(
                            structural_confirmation
                        ),
                    )
                )

            if (
                progress_writer is not None
                and (target_index - min_target_index + 1) % progress_every == 0
            ):
                progress_writer(
                    "[daily-bc-ut-l17] "
                    f"{clean_symbol}: processed "
                    f"{target_index - min_target_index + 1}/"
                    f"{len(metrics) - min_target_index} bars"
                )

    return tuple(observations), BcUpthrustSemanticSymbolRow(
        symbol=clean_symbol,
        evaluated_target_count=len(metrics) - min_target_index,
        structural_reference_available_count=structural_reference_available,
        bc_effort_core_count=len(baseline_by_index),
        ut_local_rejection_count=local_count,
        ut_structural_rejection_count=structural_count,
        union_candidate_count=len(observations),
    )

def _identity(
    symbol: object,
    bar_index: object,
    session: object,
) -> tuple[str, int, str]:
    return (
        str(symbol).strip().upper(),
        int(bar_index),
        _normalize_session(session),
    )


def _population_ids(
    observations: Sequence[BcUpthrustSemanticObservation],
    population: str,
) -> set[tuple[str, str]]:
    if population == POPULATION_BC_CORE:
        predicate = lambda item: item.bc_effort_core
    elif population == POPULATION_UT_LOCAL:
        predicate = lambda item: item.ut_local_rejection
    elif population == POPULATION_UT_STRUCTURAL:
        predicate = lambda item: item.ut_structural_rejection
    else:
        raise ValueError(f"unsupported population: {population}")
    return {
        (item.symbol, item.session)
        for item in observations
        if predicate(item)
    }


def _relationship(
    a: set[tuple[str, str]],
    b: set[tuple[str, str]],
) -> str:
    if a == b:
        return "IDENTICAL_FIRING_SET"
    if not (a & b):
        return "DISJOINT"
    if a < b:
        return "A_STRICT_SUBSET_OF_B"
    if b < a:
        return "B_STRICT_SUBSET_OF_A"
    return "PARTIAL_OVERLAP"


def build_pairwise_rows(
    observations: Sequence[BcUpthrustSemanticObservation],
) -> tuple[BcUpthrustPairwiseRow, ...]:
    ids = {
        population: _population_ids(observations, population)
        for population in POPULATION_ORDER
    }
    pairs = (
        (POPULATION_BC_CORE, POPULATION_UT_LOCAL),
        (POPULATION_BC_CORE, POPULATION_UT_STRUCTURAL),
        (POPULATION_UT_LOCAL, POPULATION_UT_STRUCTURAL),
    )
    rows: list[BcUpthrustPairwiseRow] = []
    for population_a, population_b in pairs:
        a = ids[population_a]
        b = ids[population_b]
        overlap = a & b
        union = a | b
        rows.append(
            BcUpthrustPairwiseRow(
                population_a=population_a,
                population_b=population_b,
                population_a_count=len(a),
                population_b_count=len(b),
                overlap_count=len(overlap),
                union_count=len(union),
                jaccard=len(overlap) / len(union) if union else 0.0,
                relationship=_relationship(a, b),
            )
        )
    return tuple(rows)


def _population_frame(
    frame: pd.DataFrame,
    population: str,
) -> pd.DataFrame:
    column = {
        POPULATION_BC_CORE: "bc_effort_core",
        POPULATION_UT_LOCAL: "ut_local_rejection",
        POPULATION_UT_STRUCTURAL: "ut_structural_rejection",
    }[population]
    return frame.loc[frame[column]].copy()


def build_population_rows(
    observations: Sequence[BcUpthrustSemanticObservation],
    *,
    evaluated_target_count: int,
) -> tuple[BcUpthrustPopulationRow, ...]:
    frame = pd.DataFrame([asdict(item) for item in observations])
    if frame.empty:
        return ()
    rows: list[BcUpthrustPopulationRow] = []
    for population in POPULATION_ORDER:
        selected = _population_frame(frame, population)
        if selected.empty:
            rows.append(
                BcUpthrustPopulationRow(
                    population=population,
                    event_count=0,
                    event_share_of_evaluated=0.0,
                    symbol_count=0,
                    bullish_bar_rate=0.0,
                    very_high_volume_rate=0.0,
                    above_average_spread_rate=0.0,
                    weak_close_rate=0.0,
                    mean_close_ratio=0.0,
                    mean_upper_shadow_ratio=0.0,
                )
            )
            continue
        rows.append(
            BcUpthrustPopulationRow(
                population=population,
                event_count=len(selected),
                event_share_of_evaluated=(
                    len(selected) / evaluated_target_count
                    if evaluated_target_count
                    else 0.0
                ),
                symbol_count=int(selected["symbol"].nunique()),
                bullish_bar_rate=float(
                    (selected["direction"] == Direction.UP.name).mean()
                ),
                very_high_volume_rate=float(
                    selected["volume_class"].isin(
                        (
                            VolumeClass.VERY_HIGH.name,
                            VolumeClass.ULTRA_HIGH.name,
                        )
                    ).mean()
                ),
                above_average_spread_rate=float(
                    selected["spread_class"].isin(
                        (
                            SpreadClass.ABOVE_AVERAGE.name,
                            SpreadClass.WIDE.name,
                            SpreadClass.VERY_WIDE.name,
                        )
                    ).mean()
                ),
                weak_close_rate=float(
                    selected["close_position"].isin(
                        (
                            ClosePosition.LOWER.name,
                            ClosePosition.ON_LOW.name,
                        )
                    ).mean()
                ),
                mean_close_ratio=float(selected["close_ratio"].mean()),
                mean_upper_shadow_ratio=float(
                    selected["upper_shadow_ratio"].mean()
                ),
            )
        )
    return tuple(rows)


def build_acceptance_rows(
    observations: Sequence[BcUpthrustSemanticObservation],
) -> tuple[BcAcceptanceRow, ...]:
    frame = pd.DataFrame([asdict(item) for item in observations])
    if frame.empty:
        return ()
    bc = frame.loc[frame["bc_effort_core"]]
    total = len(bc)
    rows: list[BcAcceptanceRow] = []
    for acceptance in BC_ACCEPTANCE_ORDER:
        selected = bc.loc[bc["bc_acceptance"] == acceptance]
        rows.append(
            BcAcceptanceRow(
                acceptance=acceptance,
                event_count=len(selected),
                share_of_bc_core=len(selected) / total if total else 0.0,
                symbol_count=int(selected["symbol"].nunique()),
            )
        )
    return tuple(rows)


def build_descriptor_rows(
    observations: Sequence[BcUpthrustSemanticObservation],
) -> tuple[BcUpthrustDescriptorRow, ...]:
    frame = pd.DataFrame([asdict(item) for item in observations])
    if frame.empty:
        return ()
    rows: list[BcUpthrustDescriptorRow] = []
    for population in POPULATION_ORDER:
        selected = _population_frame(frame, population)
        if selected.empty:
            continue
        for dimension in DESCRIPTOR_DIMENSIONS:
            values = selected[dimension].map(
                lambda value: str(value)
            )
            for level in sorted(values.unique()):
                mask = values == level
                rows.append(
                    BcUpthrustDescriptorRow(
                        population=population,
                        dimension=dimension,
                        level=level,
                        event_count=int(mask.sum()),
                        event_share=float(mask.mean()),
                        symbol_count=int(
                            selected.loc[mask, "symbol"].nunique()
                        ),
                    )
                )
    return tuple(rows)


def build_bc_upthrust_semantic_replay_audit(
    *,
    sources: BcUpthrustSemanticSources,
    requested_symbols: Sequence[str],
    observations: Sequence[BcUpthrustSemanticObservation],
    symbol_rows: Sequence[BcUpthrustSemanticSymbolRow],
    failures: Sequence[BcUpthrustSemanticFailure] = (),
) -> BcUpthrustSemanticReplayAudit:
    clean_symbols = tuple(
        str(symbol).strip().upper() for symbol in requested_symbols
    )
    if not clean_symbols or len(set(clean_symbols)) != len(clean_symbols):
        raise ValueError("requested symbols must be unique and non-empty")

    selected_symbol_set = set(clean_symbols)
    baseline_ids = {
        _identity(row.symbol, row.bar_index, row.session)
        for row in sources.baseline_bc.itertuples(index=False)
        if str(row.symbol).strip().upper() in selected_symbol_set
    }
    replay_ids = {
        _identity(item.symbol, item.bar_index, item.session)
        for item in observations
        if item.bc_effort_core
    }
    missing = baseline_ids - replay_ids
    extra = replay_ids - baseline_ids
    parity_rows = tuple(
        [
            BcParityMismatch(
                side="BASELINE_ONLY",
                symbol=symbol,
                bar_index=bar_index,
                session=session,
            )
            for symbol, bar_index, session in sorted(missing)
        ]
        + [
            BcParityMismatch(
                side="REPLAY_ONLY",
                symbol=symbol,
                bar_index=bar_index,
                session=session,
            )
            for symbol, bar_index, session in sorted(extra)
        ]
    )

    evaluated = sum(row.evaluated_target_count for row in symbol_rows)
    structural_available = sum(
        row.structural_reference_available_count for row in symbol_rows
    )

    bc_ids = _population_ids(observations, POPULATION_BC_CORE)
    local_ids = _population_ids(observations, POPULATION_UT_LOCAL)
    structural_ids = _population_ids(
        observations,
        POPULATION_UT_STRUCTURAL,
    )
    union_ids = bc_ids | local_ids | structural_ids

    return BcUpthrustSemanticReplayAudit(
        audit_id=DAILY_BC_UPTHRUST_SEMANTIC_REPLAY_AUDIT_ID,
        source_lineage=sources.lineage,
        requested_symbol_count=len(clean_symbols),
        succeeded_symbol_count=len(symbol_rows),
        failed_symbol_count=len(failures),
        evaluated_target_count=evaluated,
        structural_reference_available_count=structural_available,
        baseline_bc_event_count=len(baseline_ids),
        replay_bc_event_count=len(bc_ids),
        bc_identity_mismatch_count=len(parity_rows),
        bc_effort_core_count=len(bc_ids),
        ut_local_rejection_count=len(local_ids),
        ut_structural_rejection_count=len(structural_ids),
        union_candidate_count=len(union_ids),
        population_rows=build_population_rows(
            observations,
            evaluated_target_count=evaluated,
        ),
        acceptance_rows=build_acceptance_rows(observations),
        descriptor_rows=build_descriptor_rows(observations),
        pairwise_rows=build_pairwise_rows(observations),
        symbol_rows=tuple(symbol_rows),
        observations=tuple(observations),
        bc_parity_mismatches=parity_rows,
        failures=tuple(failures),
    )


def write_bc_upthrust_semantic_replay_audit(
    audit: BcUpthrustSemanticReplayAudit,
    output_dir: str | Path,
) -> BcUpthrustSemanticReplayPaths:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    paths = BcUpthrustSemanticReplayPaths(
        summary_json=root / "daily_bc_upthrust_semantic_summary.json",
        populations_csv=root / "daily_bc_upthrust_semantic_populations.csv",
        bc_acceptance_csv=root / "daily_bc_acceptance_geometry.csv",
        descriptors_csv=(
            root / "daily_bc_upthrust_semantic_descriptors.csv"
        ),
        pairwise_csv=root / "daily_bc_upthrust_semantic_pairwise.csv",
        symbols_csv=root / "daily_bc_upthrust_semantic_symbols.csv",
        observations_csv=root / "daily_bc_upthrust_semantic_observations.csv",
        bc_parity_mismatch_csv=root / "daily_bc_semantic_parity_mismatches.csv",
        failures_csv=root / "daily_bc_upthrust_semantic_failures.csv",
    )

    summary = {
        "audit_id": audit.audit_id,
        "requested_symbol_count": audit.requested_symbol_count,
        "succeeded_symbol_count": audit.succeeded_symbol_count,
        "failed_symbol_count": audit.failed_symbol_count,
        "evaluated_target_count": audit.evaluated_target_count,
        "structural_reference_available_count": (
            audit.structural_reference_available_count
        ),
        "baseline_bc_event_count": audit.baseline_bc_event_count,
        "replay_bc_event_count": audit.replay_bc_event_count,
        "bc_identity_mismatch_count": audit.bc_identity_mismatch_count,
        "bc_effort_core_count": audit.bc_effort_core_count,
        "ut_local_rejection_count": audit.ut_local_rejection_count,
        "ut_structural_rejection_count": (
            audit.ut_structural_rejection_count
        ),
        "union_candidate_count": audit.union_candidate_count,
        "population_row_count": len(audit.population_rows),
        "bc_acceptance_row_count": len(audit.acceptance_rows),
        "descriptor_row_count": len(audit.descriptor_rows),
        "pairwise_row_count": len(audit.pairwise_rows),
        "symbol_row_count": len(audit.symbol_rows),
        "observation_row_count": len(audit.observations),
        "bc_parity_mismatch_row_count": len(
            audit.bc_parity_mismatches
        ),
        "failure_row_count": len(audit.failures),
        "source_lineage": asdict(audit.source_lineage),
        "is_actionable": False,
    }
    paths.summary_json.write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    def _write(rows: Sequence[object], path: Path) -> None:
        pd.DataFrame([asdict(row) for row in rows]).to_csv(
            path,
            index=False,
        )

    _write(audit.population_rows, paths.populations_csv)
    _write(audit.acceptance_rows, paths.bc_acceptance_csv)
    _write(audit.descriptor_rows, paths.descriptors_csv)
    _write(audit.pairwise_rows, paths.pairwise_csv)
    _write(audit.symbol_rows, paths.symbols_csv)
    _write(audit.observations, paths.observations_csv)
    _write(audit.bc_parity_mismatches, paths.bc_parity_mismatch_csv)
    _write(audit.failures, paths.failures_csv)
    return paths


def run_bc_upthrust_semantic_replay(
    *,
    sources: BcUpthrustSemanticSources,
    input_snapshot_dir: str | Path,
    now: str,
    symbols: Sequence[str] | None = None,
    min_target_index: int = DEFAULT_DAILY_EVIDENCE_MIN_TARGET_INDEX,
    progress_writer: Callable[[str], None] | None = None,
) -> BcUpthrustSemanticReplayAudit:
    selected = tuple(
        str(symbol).strip().upper()
        for symbol in (
            symbols
            if symbols is not None
            else tuple(
                item.symbol for item in sources.bundle.fingerprints
            )
        )
    )
    if not selected or len(set(selected)) != len(selected):
        raise ValueError("selected symbols must be unique and non-empty")

    observations: list[BcUpthrustSemanticObservation] = []
    symbol_rows: list[BcUpthrustSemanticSymbolRow] = []
    failures: list[BcUpthrustSemanticFailure] = []

    for index, symbol in enumerate(selected, start=1):
        try:
            daily = load_daily_audit_input(input_snapshot_dir, symbol)
            symbol_observations, symbol_row = (
                replay_symbol_bc_upthrust_semantics(
                    symbol=symbol,
                    daily=daily,
                    baseline_bc=sources.baseline_bc,
                    now=now,
                    min_target_index=min_target_index,
                    progress_writer=progress_writer,
                )
            )
            observations.extend(symbol_observations)
            symbol_rows.append(symbol_row)
            if progress_writer is not None:
                progress_writer(
                    "[daily-bc-ut-l17] "
                    f"{index}/{len(selected)} {symbol}: "
                    f"BC={symbol_row.bc_effort_core_count}, "
                    f"UT-local={symbol_row.ut_local_rejection_count}, "
                    f"UT-struct={symbol_row.ut_structural_rejection_count}"
                )
        except Exception as exc:
            failures.append(
                BcUpthrustSemanticFailure(
                    symbol=symbol,
                    exception_type=type(exc).__name__,
                    reason=str(exc),
                )
            )
            if progress_writer is not None:
                progress_writer(
                    "[daily-bc-ut-l17] "
                    f"{index}/{len(selected)} {symbol}: FAILED "
                    f"{type(exc).__name__}: {exc}"
                )

    return build_bc_upthrust_semantic_replay_audit(
        sources=sources,
        requested_symbols=selected,
        observations=tuple(observations),
        symbol_rows=tuple(symbol_rows),
        failures=tuple(failures),
    )


__all__ = [
    "BC_ACCEPTANCE_MIDDLE",
    "BC_ACCEPTANCE_STRONG",
    "BC_ACCEPTANCE_WEAK",
    "DAILY_BC_UPTHRUST_SEMANTIC_REPLAY_AUDIT_ID",
    "POPULATION_BC_CORE",
    "POPULATION_UT_LOCAL",
    "POPULATION_UT_STRUCTURAL",
    "BcAcceptanceRow",
    "BcParityMismatch",
    "BcUpthrustDescriptorRow",
    "BcUpthrustPairwiseRow",
    "BcUpthrustPopulationRow",
    "BcUpthrustSemanticFailure",
    "BcUpthrustSemanticObservation",
    "BcUpthrustSemanticReplayAudit",
    "BcUpthrustSemanticReplayLineage",
    "BcUpthrustSemanticReplayPaths",
    "BcUpthrustSemanticSources",
    "BcUpthrustSemanticSymbolRow",
    "build_acceptance_rows",
    "build_bc_upthrust_semantic_replay_audit",
    "build_descriptor_rows",
    "build_pairwise_rows",
    "build_population_rows",
    "classify_bc_acceptance",
    "load_bc_upthrust_semantic_sources",
    "rejects_reference_high",
    "replay_symbol_bc_upthrust_semantics",
    "run_bc_upthrust_semantic_replay",
    "write_bc_upthrust_semantic_replay_audit",
]
