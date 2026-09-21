"""Final robustness and behavior-sequence validation for BC / UPTHRUST.

L18 consumes the canonical L17 semantic replay only. The detector definitions
are frozen before this stage:

* BC_EXHAUSTION_CANDIDATE:
  canonical BUYING_CLIMAX effort core with non-strong high-price acceptance.
* UT_STRUCTURAL_REJECTION_CANDIDATE:
  probe above latest causally confirmed structural swing high and close back at
  or below that structural high.

The audit performs no market replay, no forward-return study, no threshold
search, and no production mutation.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from statistics import median
from typing import Sequence

import pandas as pd

from audit.daily_event_bc_upthrust_semantic_replay import (
    BC_ACCEPTANCE_STRONG,
    DAILY_BC_UPTHRUST_SEMANTIC_REPLAY_AUDIT_ID,
)
from daily_behavior import (
    DailyBehaviorDimension,
    daily_behavior_dimensions_for_code,
)
from models import EvidenceCode
from weekly_setup import WeeklySetupDirection


DAILY_BC_UPTHRUST_FINAL_VALIDATION_AUDIT_ID = (
    "daily-event-bc-upthrust-final-validation-v1"
)

BC_CANDIDATE = "BC_EXHAUSTION_CANDIDATE"
UT_CANDIDATE = "UT_STRUCTURAL_REJECTION_CANDIDATE"
CANDIDATE_ORDER = (BC_CANDIDATE, UT_CANDIDATE)

PARTITION_BC_ONLY = "BC_ONLY"
PARTITION_UT_ONLY = "UT_ONLY"
PARTITION_BOTH = "BOTH"
PARTITION_ORDER = (
    PARTITION_BC_ONLY,
    PARTITION_UT_ONLY,
    PARTITION_BOTH,
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

DEFAULT_SEQUENCE_LOOKBACK_BARS = 5
MAX_SEQUENCE_OFFSET = DEFAULT_SEQUENCE_LOOKBACK_BARS - 1

TRANSITION_BC_TO_UT = "BC_TO_UT"
TRANSITION_UT_TO_BC = "UT_TO_BC"
TRANSITION_ORDER = (
    TRANSITION_BC_TO_UT,
    TRANSITION_UT_TO_BC,
)


@dataclass(frozen=True, slots=True)
class BcUpthrustFinalValidationLineage:
    l17_audit_id: str
    l17_summary_sha256: str
    l17_observations_sha256: str
    l17_symbols_sha256: str
    snapshot_manifest_sha256: str


@dataclass(frozen=True, slots=True)
class BcUpthrustFinalSources:
    lineage: BcUpthrustFinalValidationLineage
    observations: pd.DataFrame
    symbols: pd.DataFrame


@dataclass(frozen=True, slots=True)
class CandidateSymbolRow:
    symbol: str
    evaluated_target_count: int
    bc_candidate_count: int
    bc_candidate_rate: float
    ut_candidate_count: int
    ut_candidate_rate: float
    same_bar_overlap_count: int


@dataclass(frozen=True, slots=True)
class CandidateSymbolSummaryRow:
    candidate: str
    event_count: int
    symbol_count: int
    min_symbol_count: int
    median_symbol_count: float
    max_symbol_count: int
    min_symbol_rate: float
    median_symbol_rate: float
    max_symbol_rate: float
    max_symbol_share_of_candidate: float


@dataclass(frozen=True, slots=True)
class CandidateEraRow:
    candidate: str
    era: str
    event_count: int
    candidate_share: float
    symbol_count: int


@dataclass(frozen=True, slots=True)
class CandidatePartitionRow:
    partition: str
    event_count: int
    symbol_count: int


@dataclass(frozen=True, slots=True)
class CandidateTransitionRow:
    transition: str
    lookback_bars: int
    max_positive_offset: int
    source_event_count: int
    source_with_target_count: int
    source_with_target_rate: float
    ordered_pair_count: int
    symbol_count: int
    median_positive_offset: float | None


@dataclass(frozen=True, slots=True)
class CandidateTransitionOffsetRow:
    transition: str
    positive_offset: int
    ordered_pair_count: int
    symbol_count: int


@dataclass(frozen=True, slots=True)
class CandidateTransitionEraRow:
    transition: str
    era: str
    source_event_count: int
    source_with_target_count: int
    source_with_target_rate: float
    ordered_pair_count: int
    symbol_count: int


@dataclass(frozen=True, slots=True)
class CandidateBehaviorMappingRow:
    evidence_code: str
    weekly_direction: str
    dimension: str


@dataclass(frozen=True, slots=True)
class BcUpthrustFinalValidationAudit:
    audit_id: str
    source_lineage: BcUpthrustFinalValidationLineage
    requested_symbol_count: int
    evaluated_target_count: int
    bc_candidate_count: int
    ut_candidate_count: int
    same_bar_overlap_count: int
    bc_only_count: int
    ut_only_count: int
    candidate_union_count: int
    era_count: int
    sequence_lookback_bars: int
    current_behavior_mapping_collapsed: bool
    symbol_rows: tuple[CandidateSymbolRow, ...]
    symbol_summary_rows: tuple[CandidateSymbolSummaryRow, ...]
    era_rows: tuple[CandidateEraRow, ...]
    partition_rows: tuple[CandidatePartitionRow, ...]
    transition_rows: tuple[CandidateTransitionRow, ...]
    transition_offset_rows: tuple[CandidateTransitionOffsetRow, ...]
    transition_era_rows: tuple[CandidateTransitionEraRow, ...]
    behavior_mapping_rows: tuple[CandidateBehaviorMappingRow, ...]

    @property
    def is_actionable(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class BcUpthrustFinalValidationPaths:
    summary_json: Path
    symbol_rows_csv: Path
    symbol_summary_csv: Path
    era_rows_csv: Path
    partitions_csv: Path
    transitions_csv: Path
    transition_offsets_csv: Path
    transition_eras_csv: Path
    behavior_mapping_csv: Path

    def as_dict(self) -> dict[str, str]:
        return {
            key: str(value)
            for key, value in asdict(self).items()
        }


def _sha256_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1"}:
        return True
    if text in {"false", "0"}:
        return False
    raise ValueError(f"cannot parse boolean value {value!r}")


def _normalize_session(value: object) -> str:
    return pd.Timestamp(value).isoformat()


def _era_for_session(value: object) -> str:
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
    raise ValueError(f"session year outside frozen era contract: {year}")


def load_bc_upthrust_final_sources(
    input_dir: str | Path,
) -> BcUpthrustFinalSources:
    root = Path(input_dir)
    summary_path = root / "daily_bc_upthrust_semantic_summary.json"
    observations_path = root / "daily_bc_upthrust_semantic_observations.csv"
    symbols_path = root / "daily_bc_upthrust_semantic_symbols.csv"

    for path in (summary_path, observations_path, symbols_path):
        if not path.exists():
            raise FileNotFoundError(path)

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if (
        str(summary.get("audit_id"))
        != DAILY_BC_UPTHRUST_SEMANTIC_REPLAY_AUDIT_ID
    ):
        raise ValueError("unexpected L17 audit_id")
    if summary.get("is_actionable") is not False:
        raise ValueError("L18 requires non-actionable L17 source")

    expected = {
        "requested_symbol_count": 30,
        "succeeded_symbol_count": 30,
        "failed_symbol_count": 0,
        "evaluated_target_count": 198382,
        "baseline_bc_event_count": 4497,
        "replay_bc_event_count": 4497,
        "bc_identity_mismatch_count": 0,
        "bc_effort_core_count": 4497,
        "ut_structural_rejection_count": 10526,
        "failure_row_count": 0,
    }
    for key, value in expected.items():
        if int(summary.get(key, -1)) != value:
            raise ValueError(
                f"unexpected canonical L17 {key}: "
                f"{summary.get(key)!r}"
            )

    lineage = summary.get("source_lineage")
    if not isinstance(lineage, dict):
        raise ValueError("L17 source_lineage is missing")

    observations = pd.read_csv(observations_path)
    required_observation = {
        "symbol",
        "bar_index",
        "session",
        "bc_effort_core",
        "bc_acceptance",
        "ut_structural_rejection",
    }
    missing = sorted(required_observation - set(observations.columns))
    if missing:
        raise ValueError(
            f"L17 observations missing columns: {missing}"
        )

    observations = observations.copy()
    observations["symbol"] = observations["symbol"].map(
        lambda value: str(value).strip().upper()
    )
    observations["bar_index"] = observations["bar_index"].astype(int)
    observations["session"] = observations["session"].map(
        _normalize_session
    )
    observations["bc_effort_core"] = observations[
        "bc_effort_core"
    ].map(_parse_bool)
    observations["ut_structural_rejection"] = observations[
        "ut_structural_rejection"
    ].map(_parse_bool)
    observations["era"] = observations["session"].map(_era_for_session)

    if observations[
        ["symbol", "bar_index", "session"]
    ].duplicated().any():
        raise ValueError("L17 observation identities are not unique")

    observations["bc_candidate"] = (
        observations["bc_effort_core"]
        & (
            observations["bc_acceptance"].astype(str)
            != BC_ACCEPTANCE_STRONG
        )
    )
    observations["ut_candidate"] = observations[
        "ut_structural_rejection"
    ]

    bc_count = int(observations["bc_candidate"].sum())
    ut_count = int(observations["ut_candidate"].sum())
    overlap = int(
        (
            observations["bc_candidate"]
            & observations["ut_candidate"]
        ).sum()
    )
    if (bc_count, ut_count, overlap) != (887, 10526, 129):
        raise ValueError(
            "frozen L18 candidate identities changed: "
            f"{bc_count}/{ut_count}/{overlap}"
        )

    symbols = pd.read_csv(symbols_path)
    required_symbols = {
        "symbol",
        "evaluated_target_count",
    }
    missing_symbols = sorted(required_symbols - set(symbols.columns))
    if missing_symbols:
        raise ValueError(
            f"L17 symbols missing columns: {missing_symbols}"
        )
    symbols = symbols.copy()
    symbols["symbol"] = symbols["symbol"].map(
        lambda value: str(value).strip().upper()
    )
    symbols["evaluated_target_count"] = symbols[
        "evaluated_target_count"
    ].astype(int)
    if len(symbols) != 30 or symbols["symbol"].nunique() != 30:
        raise ValueError("canonical L17 symbol ledger changed")

    snapshot_manifest = str(
        lineage.get("snapshot_manifest_sha256", "")
    )
    if not snapshot_manifest:
        raise ValueError("L17 snapshot manifest hash is missing")

    return BcUpthrustFinalSources(
        lineage=BcUpthrustFinalValidationLineage(
            l17_audit_id=str(summary["audit_id"]),
            l17_summary_sha256=_sha256_file(summary_path),
            l17_observations_sha256=_sha256_file(observations_path),
            l17_symbols_sha256=_sha256_file(symbols_path),
            snapshot_manifest_sha256=snapshot_manifest,
        ),
        observations=observations.reset_index(drop=True),
        symbols=symbols.reset_index(drop=True),
    )


def build_symbol_rows(
    sources: BcUpthrustFinalSources,
) -> tuple[CandidateSymbolRow, ...]:
    rows: list[CandidateSymbolRow] = []
    for symbol_row in sources.symbols.itertuples(index=False):
        symbol = str(symbol_row.symbol)
        evaluated = int(symbol_row.evaluated_target_count)
        selected = sources.observations.loc[
            sources.observations["symbol"] == symbol
        ]
        bc_count = int(selected["bc_candidate"].sum())
        ut_count = int(selected["ut_candidate"].sum())
        overlap = int(
            (
                selected["bc_candidate"]
                & selected["ut_candidate"]
            ).sum()
        )
        rows.append(
            CandidateSymbolRow(
                symbol=symbol,
                evaluated_target_count=evaluated,
                bc_candidate_count=bc_count,
                bc_candidate_rate=(
                    bc_count / evaluated if evaluated else 0.0
                ),
                ut_candidate_count=ut_count,
                ut_candidate_rate=(
                    ut_count / evaluated if evaluated else 0.0
                ),
                same_bar_overlap_count=overlap,
            )
        )
    return tuple(rows)


def _summary_for_candidate(
    symbol_rows: Sequence[CandidateSymbolRow],
    *,
    candidate: str,
) -> CandidateSymbolSummaryRow:
    if candidate == BC_CANDIDATE:
        counts = [row.bc_candidate_count for row in symbol_rows]
        rates = [row.bc_candidate_rate for row in symbol_rows]
    elif candidate == UT_CANDIDATE:
        counts = [row.ut_candidate_count for row in symbol_rows]
        rates = [row.ut_candidate_rate for row in symbol_rows]
    else:
        raise ValueError(f"unsupported candidate: {candidate}")

    total = sum(counts)
    return CandidateSymbolSummaryRow(
        candidate=candidate,
        event_count=total,
        symbol_count=sum(count > 0 for count in counts),
        min_symbol_count=min(counts),
        median_symbol_count=float(median(counts)),
        max_symbol_count=max(counts),
        min_symbol_rate=min(rates),
        median_symbol_rate=float(median(rates)),
        max_symbol_rate=max(rates),
        max_symbol_share_of_candidate=(
            max(counts) / total if total else 0.0
        ),
    )


def build_symbol_summary_rows(
    symbol_rows: Sequence[CandidateSymbolRow],
) -> tuple[CandidateSymbolSummaryRow, ...]:
    return tuple(
        _summary_for_candidate(symbol_rows, candidate=candidate)
        for candidate in CANDIDATE_ORDER
    )


def build_era_rows(
    observations: pd.DataFrame,
) -> tuple[CandidateEraRow, ...]:
    rows: list[CandidateEraRow] = []
    definitions = (
        (BC_CANDIDATE, "bc_candidate"),
        (UT_CANDIDATE, "ut_candidate"),
    )
    for candidate, column in definitions:
        total = int(observations[column].sum())
        for era in ERA_ORDER:
            selected = observations.loc[
                (observations["era"] == era)
                & observations[column]
            ]
            rows.append(
                CandidateEraRow(
                    candidate=candidate,
                    era=era,
                    event_count=len(selected),
                    candidate_share=(
                        len(selected) / total if total else 0.0
                    ),
                    symbol_count=int(selected["symbol"].nunique()),
                )
            )
    return tuple(rows)


def build_partition_rows(
    observations: pd.DataFrame,
) -> tuple[CandidatePartitionRow, ...]:
    bc = observations["bc_candidate"]
    ut = observations["ut_candidate"]
    masks = {
        PARTITION_BC_ONLY: bc & ~ut,
        PARTITION_UT_ONLY: ut & ~bc,
        PARTITION_BOTH: bc & ut,
    }
    return tuple(
        CandidatePartitionRow(
            partition=partition,
            event_count=int(mask.sum()),
            symbol_count=int(
                observations.loc[mask, "symbol"].nunique()
            ),
        )
        for partition, mask in (
            (name, masks[name]) for name in PARTITION_ORDER
        )
    )


def _candidate_indices(
    frame: pd.DataFrame,
    column: str,
) -> tuple[int, ...]:
    return tuple(
        sorted(
            int(value)
            for value in frame.loc[frame[column], "bar_index"]
        )
    )


def _transition_definition(
    transition: str,
) -> tuple[str, str]:
    if transition == TRANSITION_BC_TO_UT:
        return "bc_candidate", "ut_candidate"
    if transition == TRANSITION_UT_TO_BC:
        return "ut_candidate", "bc_candidate"
    raise ValueError(f"unsupported transition: {transition}")


def _transition_records(
    observations: pd.DataFrame,
    *,
    transition: str,
    max_positive_offset: int,
) -> tuple[
    list[tuple[str, str, int, int]],
    list[tuple[str, str, int]],
]:
    source_column, target_column = _transition_definition(transition)
    pairs: list[tuple[str, str, int, int]] = []
    sources_with_target: list[tuple[str, str, int]] = []

    for symbol, frame in observations.groupby("symbol", sort=True):
        frame = frame.sort_values("bar_index")
        target_indices = set(_candidate_indices(frame, target_column))
        source = frame.loc[frame[source_column]]
        for row in source.itertuples(index=False):
            source_index = int(row.bar_index)
            found_offsets = tuple(
                offset
                for offset in range(1, max_positive_offset + 1)
                if source_index + offset in target_indices
            )
            if not found_offsets:
                continue
            sources_with_target.append(
                (str(symbol), str(row.era), source_index)
            )
            pairs.extend(
                (
                    str(symbol),
                    str(row.era),
                    source_index,
                    offset,
                )
                for offset in found_offsets
            )
    return pairs, sources_with_target


def build_transition_rows(
    observations: pd.DataFrame,
    *,
    lookback_bars: int = DEFAULT_SEQUENCE_LOOKBACK_BARS,
) -> tuple[
    tuple[CandidateTransitionRow, ...],
    tuple[CandidateTransitionOffsetRow, ...],
    tuple[CandidateTransitionEraRow, ...],
]:
    if lookback_bars < 2:
        raise ValueError("sequence lookback must be at least 2")
    max_offset = lookback_bars - 1

    summary_rows: list[CandidateTransitionRow] = []
    offset_rows: list[CandidateTransitionOffsetRow] = []
    era_rows: list[CandidateTransitionEraRow] = []

    for transition in TRANSITION_ORDER:
        source_column, _ = _transition_definition(transition)
        source = observations.loc[observations[source_column]]
        pairs, sources_with_target = _transition_records(
            observations,
            transition=transition,
            max_positive_offset=max_offset,
        )
        source_ids = {
            (str(row.symbol), int(row.bar_index))
            for row in source.itertuples(index=False)
        }
        source_with_ids = {
            (symbol, bar_index)
            for symbol, _, bar_index in sources_with_target
        }
        offsets = [item[3] for item in pairs]
        summary_rows.append(
            CandidateTransitionRow(
                transition=transition,
                lookback_bars=lookback_bars,
                max_positive_offset=max_offset,
                source_event_count=len(source_ids),
                source_with_target_count=len(source_with_ids),
                source_with_target_rate=(
                    len(source_with_ids) / len(source_ids)
                    if source_ids
                    else 0.0
                ),
                ordered_pair_count=len(pairs),
                symbol_count=len(
                    {item[0] for item in pairs}
                ),
                median_positive_offset=(
                    float(median(offsets)) if offsets else None
                ),
            )
        )

        for offset in range(1, max_offset + 1):
            selected = [item for item in pairs if item[3] == offset]
            offset_rows.append(
                CandidateTransitionOffsetRow(
                    transition=transition,
                    positive_offset=offset,
                    ordered_pair_count=len(selected),
                    symbol_count=len(
                        {item[0] for item in selected}
                    ),
                )
            )

        for era in ERA_ORDER:
            source_era = source.loc[source["era"] == era]
            source_era_ids = {
                (str(row.symbol), int(row.bar_index))
                for row in source_era.itertuples(index=False)
            }
            source_with_era = {
                (symbol, bar_index)
                for symbol, item_era, bar_index
                in sources_with_target
                if item_era == era
            }
            pair_era = [
                item for item in pairs if item[1] == era
            ]
            era_rows.append(
                CandidateTransitionEraRow(
                    transition=transition,
                    era=era,
                    source_event_count=len(source_era_ids),
                    source_with_target_count=len(source_with_era),
                    source_with_target_rate=(
                        len(source_with_era) / len(source_era_ids)
                        if source_era_ids
                        else 0.0
                    ),
                    ordered_pair_count=len(pair_era),
                    symbol_count=len(
                        {item[0] for item in pair_era}
                    ),
                )
            )

    return (
        tuple(summary_rows),
        tuple(offset_rows),
        tuple(era_rows),
    )


def build_behavior_mapping_rows(
) -> tuple[CandidateBehaviorMappingRow, ...]:
    rows: list[CandidateBehaviorMappingRow] = []
    for code in (
        EvidenceCode.BUYING_CLIMAX,
        EvidenceCode.UPTHRUST,
    ):
        mappings = daily_behavior_dimensions_for_code(code)
        for weekly_direction, dimension in mappings:
            rows.append(
                CandidateBehaviorMappingRow(
                    evidence_code=code.value,
                    weekly_direction=weekly_direction.value,
                    dimension=dimension.value,
                )
            )

    expected = {
        (
            EvidenceCode.BUYING_CLIMAX.value,
            WeeklySetupDirection.BEARISH.value,
            DailyBehaviorDimension.REJECTION_OF_OPPOSING_MOVE.value,
        ),
        (
            EvidenceCode.UPTHRUST.value,
            WeeklySetupDirection.BEARISH.value,
            DailyBehaviorDimension.REJECTION_OF_OPPOSING_MOVE.value,
        ),
    }
    observed = {
        (
            row.evidence_code,
            row.weekly_direction,
            row.dimension,
        )
        for row in rows
    }
    if observed != expected:
        raise ValueError(
            "current BC/UPTHRUST behavior mapping changed"
        )
    return tuple(rows)


def build_bc_upthrust_final_validation_audit(
    sources: BcUpthrustFinalSources,
    *,
    sequence_lookback_bars: int = DEFAULT_SEQUENCE_LOOKBACK_BARS,
) -> BcUpthrustFinalValidationAudit:
    symbol_rows = build_symbol_rows(sources)
    symbol_summary_rows = build_symbol_summary_rows(symbol_rows)
    era_rows = build_era_rows(sources.observations)
    partition_rows = build_partition_rows(sources.observations)
    (
        transition_rows,
        transition_offset_rows,
        transition_era_rows,
    ) = build_transition_rows(
        sources.observations,
        lookback_bars=sequence_lookback_bars,
    )
    behavior_mapping_rows = build_behavior_mapping_rows()

    bc_count = int(sources.observations["bc_candidate"].sum())
    ut_count = int(sources.observations["ut_candidate"].sum())
    overlap = int(
        (
            sources.observations["bc_candidate"]
            & sources.observations["ut_candidate"]
        ).sum()
    )
    union = int(
        (
            sources.observations["bc_candidate"]
            | sources.observations["ut_candidate"]
        ).sum()
    )

    partition_lookup = {
        row.partition: row.event_count for row in partition_rows
    }
    if (
        partition_lookup[PARTITION_BC_ONLY]
        + partition_lookup[PARTITION_BOTH]
        != bc_count
    ):
        raise RuntimeError("BC partition does not reconcile")
    if (
        partition_lookup[PARTITION_UT_ONLY]
        + partition_lookup[PARTITION_BOTH]
        != ut_count
    ):
        raise RuntimeError("UT partition does not reconcile")

    return BcUpthrustFinalValidationAudit(
        audit_id=DAILY_BC_UPTHRUST_FINAL_VALIDATION_AUDIT_ID,
        source_lineage=sources.lineage,
        requested_symbol_count=len(symbol_rows),
        evaluated_target_count=int(
            sources.symbols["evaluated_target_count"].sum()
        ),
        bc_candidate_count=bc_count,
        ut_candidate_count=ut_count,
        same_bar_overlap_count=overlap,
        bc_only_count=partition_lookup[PARTITION_BC_ONLY],
        ut_only_count=partition_lookup[PARTITION_UT_ONLY],
        candidate_union_count=union,
        era_count=len(ERA_ORDER),
        sequence_lookback_bars=sequence_lookback_bars,
        current_behavior_mapping_collapsed=True,
        symbol_rows=symbol_rows,
        symbol_summary_rows=symbol_summary_rows,
        era_rows=era_rows,
        partition_rows=partition_rows,
        transition_rows=transition_rows,
        transition_offset_rows=transition_offset_rows,
        transition_era_rows=transition_era_rows,
        behavior_mapping_rows=behavior_mapping_rows,
    )


def write_bc_upthrust_final_validation_audit(
    audit: BcUpthrustFinalValidationAudit,
    output_dir: str | Path,
) -> BcUpthrustFinalValidationPaths:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    paths = BcUpthrustFinalValidationPaths(
        summary_json=root / "daily_bc_upthrust_final_summary.json",
        symbol_rows_csv=root / "daily_bc_upthrust_final_symbols.csv",
        symbol_summary_csv=(
            root / "daily_bc_upthrust_final_symbol_summary.csv"
        ),
        era_rows_csv=root / "daily_bc_upthrust_final_eras.csv",
        partitions_csv=root / "daily_bc_upthrust_final_partitions.csv",
        transitions_csv=root / "daily_bc_upthrust_final_transitions.csv",
        transition_offsets_csv=(
            root / "daily_bc_upthrust_final_transition_offsets.csv"
        ),
        transition_eras_csv=(
            root / "daily_bc_upthrust_final_transition_eras.csv"
        ),
        behavior_mapping_csv=(
            root / "daily_bc_upthrust_final_behavior_mapping.csv"
        ),
    )

    summary = {
        "audit_id": audit.audit_id,
        "requested_symbol_count": audit.requested_symbol_count,
        "evaluated_target_count": audit.evaluated_target_count,
        "bc_candidate_count": audit.bc_candidate_count,
        "ut_candidate_count": audit.ut_candidate_count,
        "same_bar_overlap_count": audit.same_bar_overlap_count,
        "bc_only_count": audit.bc_only_count,
        "ut_only_count": audit.ut_only_count,
        "candidate_union_count": audit.candidate_union_count,
        "era_count": audit.era_count,
        "sequence_lookback_bars": audit.sequence_lookback_bars,
        "current_behavior_mapping_collapsed": (
            audit.current_behavior_mapping_collapsed
        ),
        "symbol_row_count": len(audit.symbol_rows),
        "symbol_summary_row_count": len(audit.symbol_summary_rows),
        "era_row_count": len(audit.era_rows),
        "partition_row_count": len(audit.partition_rows),
        "transition_row_count": len(audit.transition_rows),
        "transition_offset_row_count": len(
            audit.transition_offset_rows
        ),
        "transition_era_row_count": len(
            audit.transition_era_rows
        ),
        "behavior_mapping_row_count": len(
            audit.behavior_mapping_rows
        ),
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

    _write(audit.symbol_rows, paths.symbol_rows_csv)
    _write(audit.symbol_summary_rows, paths.symbol_summary_csv)
    _write(audit.era_rows, paths.era_rows_csv)
    _write(audit.partition_rows, paths.partitions_csv)
    _write(audit.transition_rows, paths.transitions_csv)
    _write(audit.transition_offset_rows, paths.transition_offsets_csv)
    _write(audit.transition_era_rows, paths.transition_eras_csv)
    _write(audit.behavior_mapping_rows, paths.behavior_mapping_csv)
    return paths


__all__ = [
    "BC_CANDIDATE",
    "DAILY_BC_UPTHRUST_FINAL_VALIDATION_AUDIT_ID",
    "DEFAULT_SEQUENCE_LOOKBACK_BARS",
    "ERA_ORDER",
    "TRANSITION_BC_TO_UT",
    "TRANSITION_UT_TO_BC",
    "UT_CANDIDATE",
    "BcUpthrustFinalSources",
    "BcUpthrustFinalValidationAudit",
    "BcUpthrustFinalValidationLineage",
    "BcUpthrustFinalValidationPaths",
    "CandidateBehaviorMappingRow",
    "CandidateEraRow",
    "CandidatePartitionRow",
    "CandidateSymbolRow",
    "CandidateSymbolSummaryRow",
    "CandidateTransitionEraRow",
    "CandidateTransitionOffsetRow",
    "CandidateTransitionRow",
    "build_bc_upthrust_final_validation_audit",
    "build_behavior_mapping_rows",
    "build_era_rows",
    "build_partition_rows",
    "build_symbol_rows",
    "build_symbol_summary_rows",
    "build_transition_rows",
    "load_bc_upthrust_final_sources",
    "write_bc_upthrust_final_validation_audit",
]
