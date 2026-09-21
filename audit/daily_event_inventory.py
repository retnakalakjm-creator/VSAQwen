"""Inventory and point-in-time audit for existing daily Evidence events.

L1 is descriptive only. It freezes the current EvidenceCode vocabulary, registry
coverage, active EvidenceEngine collector reachability, daily-behavior mappings,
and point-in-time emissions produced by the existing K5 daily prefix replay.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from audit.offline_daily_evidence import OfflineDailyEvidenceArchive
from daily_behavior import daily_behavior_dimensions_for_code
from evidence.evidence_registry import EVIDENCE_LIBRARY
from evidence.profiles import EVIDENCE_REGISTRY
from models import EvidenceCode, EvidenceDirection
from weekly_setup import WeeklySetupDirection


DAILY_EVENT_INVENTORY_AUDIT_ID = "daily-event-inventory-point-in-time-v1"


DIRECT_ACTIVE_DIRECTIONS: dict[EvidenceCode, EvidenceDirection] = {
    EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING: EvidenceDirection.BULLISH,
    EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING: EvidenceDirection.BEARISH,
}


ACTIVE_DAILY_COLLECTOR_SOURCES: dict[
    EvidenceCode,
    tuple[str, ...],
] = {
    EvidenceCode.BUYING_CLIMAX: ("evidence.supply.collect_supply",),
    EvidenceCode.SUPPLY_COMING_IN: ("evidence.supply.collect_supply",),
    EvidenceCode.INCREASING_SUPPLY: ("evidence.supply.collect_supply",),
    EvidenceCode.HIDDEN_SUPPLY: ("evidence.supply.collect_supply",),
    EvidenceCode.SUPPLY_DRYING_UP: ("evidence.supply.collect_supply",),
    EvidenceCode.UPTHRUST: ("evidence.supply.collect_supply",),
    EvidenceCode.NO_DEMAND: ("evidence.supply.collect_supply",),
    EvidenceCode.STOPPING_VOLUME: ("evidence.demand.collect_demand",),
    EvidenceCode.SELLING_CLIMAX: ("evidence.demand.collect_demand",),
    EvidenceCode.INCREASING_DEMAND: ("evidence.demand.collect_demand",),
    EvidenceCode.DEMAND_COMING_IN: (
        "evidence.demand.collect_demand",
        "evidence.demand_coming_in.collect_demand_coming_in",
    ),
    EvidenceCode.TEST: ("evidence.demand.collect_demand",),
    EvidenceCode.SHAKEOUT: ("evidence.demand.collect_demand",),
    EvidenceCode.NO_SUPPLY: ("evidence.demand.collect_demand",),
    EvidenceCode.ABSORPTION: (
        "evidence.demand.collect_demand",
        "evidence.effort.collect_effort",
    ),
    EvidenceCode.EFFORT_GT_RESULT: ("evidence.effort.collect_effort",),
    EvidenceCode.RESULT_GT_EFFORT: ("evidence.effort.collect_effort",),
    EvidenceCode.SPRING: ("evidence.spring.collect_spring",),
    EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING: (
        "background.structural_progression.collect_structural_progression",
    ),
    EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING: (
        "background.structural_progression.collect_structural_progression",
    ),
}


@dataclass(frozen=True, slots=True)
class DailyEventAuditFailure:
    symbol: str
    exception_type: str
    reason: str


@dataclass(frozen=True, slots=True)
class DailyEventEmission:
    symbol: str
    bar_index: int
    session: str
    code: str
    category: str
    direction: str
    strength: float
    weight: float
    quality: float
    test_index: int | None
    recovery_index: int | None
    occurrence_on_bar_code: int


@dataclass(frozen=True, slots=True)
class DailyEventDuplicateEmission:
    symbol: str
    bar_index: int
    session: str
    code: str
    emission_count: int
    extra_emission_count: int


@dataclass(frozen=True, slots=True)
class DailyEventInventoryRow:
    code: str
    enum_defined: bool
    profile_registered: bool
    legacy_registry_registered: bool
    active_collector: bool
    collector_sources: tuple[str, ...]
    bullish_behavior_dimensions: tuple[str, ...]
    bearish_behavior_dimensions: tuple[str, ...]
    declared_direction: str | None
    bullish_behavior_direction_compatible: bool | None
    bearish_behavior_direction_compatible: bool | None
    emitted_directions: tuple[str, ...]
    emitted_count: int
    emitted_symbol_count: int
    emitted_session_count: int
    duplicate_group_count: int
    duplicate_extra_emission_count: int
    first_session: str | None
    last_session: str | None
    inventory_status: str


@dataclass(frozen=True, slots=True)
class DailyEventInventoryInputProvenance:
    source: str
    snapshot_audit_id: str | None = None
    snapshot_manifest_sha256: str | None = None
    snapshot_basket_name: str | None = None
    snapshot_period: str | None = None
    snapshot_cutoff: str | None = None


@dataclass(frozen=True, slots=True)
class DailyEventInventoryAudit:
    audit_id: str
    requested_symbol_count: int
    succeeded_symbol_count: int
    failed_symbol_count: int
    evaluated_bar_count: int
    defined_code_count: int
    profile_registered_code_count: int
    legacy_registry_code_count: int
    active_collector_code_count: int
    behavior_mapped_code_count: int
    emitted_code_count: int
    evidence_emission_count: int
    event_bar_count: int
    duplicate_group_count: int
    duplicate_extra_emission_count: int
    active_not_observed_code_count: int
    behavior_mapped_inactive_code_count: int
    behavior_direction_mismatch_count: int
    inventory_rows: tuple[DailyEventInventoryRow, ...]
    emissions: tuple[DailyEventEmission, ...]
    duplicates: tuple[DailyEventDuplicateEmission, ...]
    failures: tuple[DailyEventAuditFailure, ...]
    input_provenance: DailyEventInventoryInputProvenance | None = None

    @property
    def is_actionable(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class DailyEventInventoryAuditPaths:
    summary_json: Path
    inventory_csv: Path
    emissions_csv: Path
    duplicates_csv: Path
    failures_csv: Path

    def as_dict(self) -> dict[str, str]:
        return {
            "summary_json": str(self.summary_json),
            "inventory_csv": str(self.inventory_csv),
            "emissions_csv": str(self.emissions_csv),
            "duplicates_csv": str(self.duplicates_csv),
            "failures_csv": str(self.failures_csv),
        }


def _code_value(code: object) -> str:
    value = getattr(code, "value", None)
    if isinstance(value, str):
        return value
    return str(code)


def _enum_code_by_value() -> dict[str, EvidenceCode]:
    return {item.value: item for item in EvidenceCode}


def _behavior_dimensions(
    code: EvidenceCode,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    bullish: list[str] = []
    bearish: list[str] = []
    for weekly_direction, dimension in daily_behavior_dimensions_for_code(code):
        if weekly_direction is WeeklySetupDirection.BULLISH:
            bullish.append(dimension.value)
        else:
            bearish.append(dimension.value)
    return tuple(bullish), tuple(bearish)


def _declared_direction(
    code: EvidenceCode,
) -> EvidenceDirection | None:
    profile = EVIDENCE_REGISTRY.get(code)
    if profile is not None:
        return profile.direction
    legacy = EVIDENCE_LIBRARY.get(code)
    if legacy is not None:
        return legacy.direction
    return DIRECT_ACTIVE_DIRECTIONS.get(code)


def _direction_compatible(
    *,
    declared: EvidenceDirection | None,
    weekly_direction: WeeklySetupDirection,
    behavior_mapped: bool,
) -> bool | None:
    if not behavior_mapped or declared is None:
        return None
    expected = (
        EvidenceDirection.BULLISH
        if weekly_direction is WeeklySetupDirection.BULLISH
        else EvidenceDirection.BEARISH
    )
    return declared == expected


def _inventory_status(
    *,
    emitted_count: int,
    active_collector: bool,
    behavior_mapped: bool,
    registered: bool,
) -> str:
    if emitted_count > 0:
        return "EMITTED_POINT_IN_TIME"
    if active_collector:
        return "ACTIVE_NOT_OBSERVED"
    if behavior_mapped:
        return "BEHAVIOR_MAPPED_BUT_INACTIVE"
    if registered:
        return "REGISTERED_BUT_INACTIVE"
    return "DEFINED_BUT_INACTIVE"


def _flatten_emissions(
    archives: Iterable[OfflineDailyEvidenceArchive],
) -> tuple[DailyEventEmission, ...]:
    rows: list[DailyEventEmission] = []
    for archive in archives:
        for observation in archive.observations:
            occurrence: Counter[str] = Counter()
            for item in observation.evidence:
                code = _code_value(item.code)
                occurrence[code] += 1
                rows.append(
                    DailyEventEmission(
                        symbol=archive.symbol,
                        bar_index=observation.bar_index,
                        session=observation.session,
                        code=code,
                        category=getattr(item.category, "name", str(item.category)),
                        direction=getattr(
                            item.direction,
                            "name",
                            str(item.direction),
                        ),
                        strength=float(item.strength),
                        weight=float(item.weight),
                        quality=float(item.quality),
                        test_index=item.test_index,
                        recovery_index=item.recovery_index,
                        occurrence_on_bar_code=occurrence[code],
                    )
                )
    return tuple(rows)


def _duplicate_rows(
    emissions: tuple[DailyEventEmission, ...],
) -> tuple[DailyEventDuplicateEmission, ...]:
    grouped: dict[tuple[str, int, str, str], int] = defaultdict(int)
    for item in emissions:
        grouped[(item.symbol, item.bar_index, item.session, item.code)] += 1

    return tuple(
        DailyEventDuplicateEmission(
            symbol=symbol,
            bar_index=bar_index,
            session=session,
            code=code,
            emission_count=count,
            extra_emission_count=count - 1,
        )
        for (symbol, bar_index, session, code), count in sorted(grouped.items())
        if count > 1
    )


def build_daily_event_inventory_audit(
    *,
    requested_symbols: tuple[str, ...],
    archives: tuple[OfflineDailyEvidenceArchive, ...],
    failures: tuple[DailyEventAuditFailure, ...] = (),
    input_provenance: DailyEventInventoryInputProvenance | None = None,
) -> DailyEventInventoryAudit:
    clean_requested = tuple(str(symbol).strip().upper() for symbol in requested_symbols)
    if len(set(clean_requested)) != len(clean_requested):
        raise ValueError("requested symbols must be unique")

    archive_symbols = [archive.symbol for archive in archives]
    failure_symbols = [failure.symbol for failure in failures]
    if len(set(archive_symbols)) != len(archive_symbols):
        raise ValueError("successful archive symbols must be unique")
    if len(set(failure_symbols)) != len(failure_symbols):
        raise ValueError("failure symbols must be unique")
    if set(archive_symbols) & set(failure_symbols):
        raise ValueError("a symbol cannot be both successful and failed")
    if set(archive_symbols) | set(failure_symbols) != set(clean_requested):
        raise ValueError(
            "successful plus failed symbols must equal requested symbols"
        )

    emissions = _flatten_emissions(archives)
    duplicates = _duplicate_rows(emissions)
    enum_by_value = _enum_code_by_value()
    emitted_values = sorted({item.code for item in emissions})
    inventory_values = sorted(set(enum_by_value) | set(emitted_values))

    code_emissions: dict[str, list[DailyEventEmission]] = defaultdict(list)
    code_duplicates: dict[str, list[DailyEventDuplicateEmission]] = defaultdict(list)
    for item in emissions:
        code_emissions[item.code].append(item)
    for item in duplicates:
        code_duplicates[item.code].append(item)

    inventory_rows: list[DailyEventInventoryRow] = []
    behavior_mapped_count = 0
    active_not_observed_count = 0
    behavior_mapped_inactive_count = 0
    behavior_direction_mismatch_count = 0

    for value in inventory_values:
        enum_code = enum_by_value.get(value)
        profile_registered = (
            enum_code in EVIDENCE_REGISTRY if enum_code is not None else False
        )
        legacy_registered = (
            enum_code in EVIDENCE_LIBRARY if enum_code is not None else False
        )
        collector_sources = (
            ACTIVE_DAILY_COLLECTOR_SOURCES.get(enum_code, ())
            if enum_code is not None
            else ()
        )
        bullish_dimensions: tuple[str, ...] = ()
        bearish_dimensions: tuple[str, ...] = ()
        if enum_code is not None:
            bullish_dimensions, bearish_dimensions = _behavior_dimensions(enum_code)
        behavior_mapped = bool(bullish_dimensions or bearish_dimensions)
        if behavior_mapped:
            behavior_mapped_count += 1

        declared = (
            _declared_direction(enum_code)
            if enum_code is not None
            else None
        )
        bullish_compatible = _direction_compatible(
            declared=declared,
            weekly_direction=WeeklySetupDirection.BULLISH,
            behavior_mapped=bool(bullish_dimensions),
        )
        bearish_compatible = _direction_compatible(
            declared=declared,
            weekly_direction=WeeklySetupDirection.BEARISH,
            behavior_mapped=bool(bearish_dimensions),
        )
        behavior_direction_mismatch_count += sum(
            value is False
            for value in (bullish_compatible, bearish_compatible)
        )

        emitted = code_emissions.get(value, [])
        duplicate_items = code_duplicates.get(value, [])
        active_collector = bool(collector_sources)
        registered = profile_registered or legacy_registered
        status = _inventory_status(
            emitted_count=len(emitted),
            active_collector=active_collector,
            behavior_mapped=behavior_mapped,
            registered=registered,
        )
        if status == "ACTIVE_NOT_OBSERVED":
            active_not_observed_count += 1
        if status == "BEHAVIOR_MAPPED_BUT_INACTIVE":
            behavior_mapped_inactive_count += 1

        sessions = sorted({item.session for item in emitted})
        inventory_rows.append(
            DailyEventInventoryRow(
                code=value,
                enum_defined=enum_code is not None,
                profile_registered=profile_registered,
                legacy_registry_registered=legacy_registered,
                active_collector=active_collector,
                collector_sources=collector_sources,
                bullish_behavior_dimensions=bullish_dimensions,
                bearish_behavior_dimensions=bearish_dimensions,
                declared_direction=(
                    declared.name if declared is not None else None
                ),
                bullish_behavior_direction_compatible=bullish_compatible,
                bearish_behavior_direction_compatible=bearish_compatible,
                emitted_directions=tuple(
                    sorted({item.direction for item in emitted})
                ),
                emitted_count=len(emitted),
                emitted_symbol_count=len({item.symbol for item in emitted}),
                emitted_session_count=len(sessions),
                duplicate_group_count=len(duplicate_items),
                duplicate_extra_emission_count=sum(
                    item.extra_emission_count for item in duplicate_items
                ),
                first_session=sessions[0] if sessions else None,
                last_session=sessions[-1] if sessions else None,
                inventory_status=status,
            )
        )

    evaluated_bar_count = sum(archive.evaluated_bar_count for archive in archives)
    event_bar_count = len(
        {(item.symbol, item.bar_index, item.session) for item in emissions}
    )
    return DailyEventInventoryAudit(
        audit_id=DAILY_EVENT_INVENTORY_AUDIT_ID,
        requested_symbol_count=len(clean_requested),
        succeeded_symbol_count=len(archives),
        failed_symbol_count=len(failures),
        evaluated_bar_count=evaluated_bar_count,
        defined_code_count=len(EvidenceCode),
        profile_registered_code_count=len(EVIDENCE_REGISTRY),
        legacy_registry_code_count=len(EVIDENCE_LIBRARY),
        active_collector_code_count=len(ACTIVE_DAILY_COLLECTOR_SOURCES),
        behavior_mapped_code_count=behavior_mapped_count,
        emitted_code_count=len(emitted_values),
        evidence_emission_count=len(emissions),
        event_bar_count=event_bar_count,
        duplicate_group_count=len(duplicates),
        duplicate_extra_emission_count=sum(
            item.extra_emission_count for item in duplicates
        ),
        active_not_observed_code_count=active_not_observed_count,
        behavior_mapped_inactive_code_count=behavior_mapped_inactive_count,
        behavior_direction_mismatch_count=behavior_direction_mismatch_count,
        inventory_rows=tuple(inventory_rows),
        emissions=emissions,
        duplicates=duplicates,
        failures=tuple(sorted(failures, key=lambda item: item.symbol)),
        input_provenance=input_provenance,
    )


def write_daily_event_inventory_audit(
    audit: DailyEventInventoryAudit,
    output_dir: str | Path,
) -> DailyEventInventoryAuditPaths:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    paths = DailyEventInventoryAuditPaths(
        summary_json=root / "daily_event_inventory_summary.json",
        inventory_csv=root / "daily_event_inventory.csv",
        emissions_csv=root / "daily_event_emissions.csv",
        duplicates_csv=root / "daily_event_duplicates.csv",
        failures_csv=root / "daily_event_failures.csv",
    )

    summary = {
        "audit_id": audit.audit_id,
        "requested_symbol_count": audit.requested_symbol_count,
        "succeeded_symbol_count": audit.succeeded_symbol_count,
        "failed_symbol_count": audit.failed_symbol_count,
        "evaluated_bar_count": audit.evaluated_bar_count,
        "defined_code_count": audit.defined_code_count,
        "profile_registered_code_count": audit.profile_registered_code_count,
        "legacy_registry_code_count": audit.legacy_registry_code_count,
        "active_collector_code_count": audit.active_collector_code_count,
        "behavior_mapped_code_count": audit.behavior_mapped_code_count,
        "emitted_code_count": audit.emitted_code_count,
        "evidence_emission_count": audit.evidence_emission_count,
        "event_bar_count": audit.event_bar_count,
        "duplicate_group_count": audit.duplicate_group_count,
        "duplicate_extra_emission_count": (
            audit.duplicate_extra_emission_count
        ),
        "active_not_observed_code_count": (
            audit.active_not_observed_code_count
        ),
        "behavior_mapped_inactive_code_count": (
            audit.behavior_mapped_inactive_code_count
        ),
        "behavior_direction_mismatch_count": (
            audit.behavior_direction_mismatch_count
        ),
        "input_provenance": (
            None
            if audit.input_provenance is None
            else asdict(audit.input_provenance)
        ),
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
                "collector_sources": "|".join(item.collector_sources),
                "bullish_behavior_dimensions": "|".join(
                    item.bullish_behavior_dimensions
                ),
                "bearish_behavior_dimensions": "|".join(
                    item.bearish_behavior_dimensions
                ),
                "emitted_directions": "|".join(item.emitted_directions),
            }
            for item in audit.inventory_rows
        ]
    ).to_csv(paths.inventory_csv, index=False)

    pd.DataFrame(
        [asdict(item) for item in audit.emissions],
        columns=(
            "symbol",
            "bar_index",
            "session",
            "code",
            "category",
            "direction",
            "strength",
            "weight",
            "quality",
            "test_index",
            "recovery_index",
            "occurrence_on_bar_code",
        ),
    ).to_csv(paths.emissions_csv, index=False)
    pd.DataFrame(
        [asdict(item) for item in audit.duplicates],
        columns=(
            "symbol",
            "bar_index",
            "session",
            "code",
            "emission_count",
            "extra_emission_count",
        ),
    ).to_csv(paths.duplicates_csv, index=False)
    pd.DataFrame(
        [asdict(item) for item in audit.failures],
        columns=("symbol", "exception_type", "reason"),
    ).to_csv(paths.failures_csv, index=False)
    return paths


__all__ = [
    "ACTIVE_DAILY_COLLECTOR_SOURCES",
    "DAILY_EVENT_INVENTORY_AUDIT_ID",
    "DIRECT_ACTIVE_DIRECTIONS",
    "DailyEventAuditFailure",
    "DailyEventDuplicateEmission",
    "DailyEventEmission",
    "DailyEventInventoryAudit",
    "DailyEventInventoryAuditPaths",
    "DailyEventInventoryInputProvenance",
    "DailyEventInventoryRow",
    "build_daily_event_inventory_audit",
    "write_daily_event_inventory_audit",
]
