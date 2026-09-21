from __future__ import annotations

import inspect
import json

import pandas as pd

from audit.daily_event_inventory import (
    ACTIVE_DAILY_COLLECTOR_SOURCES,
    DAILY_EVENT_INVENTORY_AUDIT_ID,
    DailyEventInventoryInputProvenance,
    build_daily_event_inventory_audit,
    write_daily_event_inventory_audit,
)
from audit.offline_daily_evidence import (
    DailyEvidenceBarObservation,
    DailyEvidenceSourceFingerprint,
    OfflineDailyEvidenceArchive,
)
from daily_behavior import (
    DailyBehaviorDimension,
    daily_behavior_dimensions_for_code,
)
from evidence.demand import collect_demand
from evidence.effort import collect_effort
from evidence.engine import EvidenceEngine
from models import (
    Evidence,
    EvidenceCategory,
    EvidenceCode,
    EvidenceDirection,
)
from weekly_setup import WeeklySetupDirection


def _evidence(
    code: EvidenceCode,
    *,
    bar_index: int,
    session: str,
) -> Evidence:
    direction = {
        EvidenceCode.NO_SUPPLY: EvidenceDirection.BULLISH,
        EvidenceCode.ABSORPTION: EvidenceDirection.BULLISH,
    }[code]
    category = {
        EvidenceCode.NO_SUPPLY: EvidenceCategory.DEMAND,
        EvidenceCode.ABSORPTION: EvidenceCategory.ABSORPTION,
    }[code]
    return Evidence(
        code=code,
        category=category,
        direction=direction,
        strength=0.8,
        weight=0.0,
        observation=code.value,
        description=code.value,
        bar_index=bar_index,
        week_beginning=session,
    )


def _archive() -> OfflineDailyEvidenceArchive:
    sessions = pd.date_range("2026-01-01", periods=3, freq="D")
    daily = pd.DataFrame(
        {
            "open": [100.0, 101.0, 102.0],
            "high": [102.0, 103.0, 104.0],
            "low": [99.0, 100.0, 101.0],
            "close": [101.0, 102.0, 103.0],
            "volume": [1000.0, 1100.0, 1200.0],
        },
        index=sessions,
    )
    session = sessions[2].isoformat()
    return OfflineDailyEvidenceArchive(
        symbol="AAA.NS",
        producer_id="fixture",
        completed_daily=daily,
        source_fingerprint=DailyEvidenceSourceFingerprint(
            symbol="AAA.NS",
            row_count=3,
            first_session=sessions[0].isoformat(),
            last_session=sessions[-1].isoformat(),
            sha256="sha256:fixture",
        ),
        min_target_index=2,
        observations=(
            DailyEvidenceBarObservation(
                bar_index=2,
                session=session,
                evidence=(
                    _evidence(
                        EvidenceCode.ABSORPTION,
                        bar_index=2,
                        session=session,
                    ),
                    _evidence(
                        EvidenceCode.ABSORPTION,
                        bar_index=2,
                        session=session,
                    ),
                    _evidence(
                        EvidenceCode.NO_SUPPLY,
                        bar_index=2,
                        session=session,
                    ),
                ),
            ),
        ),
    )


def test_active_collector_manifest_matches_engine_entrypoints() -> None:
    engine_source = inspect.getsource(EvidenceEngine.collect)
    for call in (
        "self._collect_supply()",
        "self._collect_demand()",
        "self._collect_spring()",
        "self._collect_effort()",
        "self._collect_structural_progression()",
    ):
        assert call in engine_source

    demand_source = inspect.getsource(collect_demand)
    effort_source = inspect.getsource(collect_effort)
    assert "collect_absorption(ctx)" in demand_source
    assert "collect_absorption(ctx)" in effort_source


def test_public_daily_behavior_mapping_exposes_existing_code_usage() -> None:
    mappings = daily_behavior_dimensions_for_code(EvidenceCode.NO_SUPPLY)
    assert (
        WeeklySetupDirection.BULLISH,
        DailyBehaviorDimension.OPPOSING_PRESSURE_RECEDING,
    ) in mappings
    assert not any(
        direction is WeeklySetupDirection.BEARISH
        for direction, _ in mappings
    )


def test_inventory_freezes_defined_registered_and_active_boundaries() -> None:
    audit = build_daily_event_inventory_audit(
        requested_symbols=("AAA.NS",),
        archives=(_archive(),),
    )
    rows = {item.code: item for item in audit.inventory_rows}

    assert audit.audit_id == DAILY_EVENT_INVENTORY_AUDIT_ID
    assert audit.defined_code_count == len(EvidenceCode) == 37
    assert audit.profile_registered_code_count == 21
    assert audit.legacy_registry_code_count == 10
    assert audit.active_collector_code_count == len(
        ACTIVE_DAILY_COLLECTOR_SOURCES
    ) == 20
    assert audit.behavior_mapped_code_count == 29

    assert rows[EvidenceCode.NO_SUPPLY.value].active_collector is True
    assert rows[EvidenceCode.DEMAND_DRYING_UP.value].active_collector is False
    assert rows[EvidenceCode.STRONG_UPTREND.value].active_collector is False
    assert (
        rows[EvidenceCode.HIDDEN_DEMAND.value].inventory_status
        == "BEHAVIOR_MAPPED_BUT_INACTIVE"
    )
    result_gt_effort = rows[EvidenceCode.RESULT_GT_EFFORT.value]
    assert result_gt_effort.declared_direction == "NEUTRAL"
    assert result_gt_effort.bullish_behavior_direction_compatible is False
    assert result_gt_effort.bearish_behavior_direction_compatible is False
    absorption = rows[EvidenceCode.ABSORPTION.value]
    assert absorption.bullish_behavior_direction_compatible is True
    assert absorption.bearish_behavior_direction_compatible is False
    assert audit.behavior_direction_mismatch_count == 3


def test_inventory_detects_same_bar_duplicate_emissions() -> None:
    audit = build_daily_event_inventory_audit(
        requested_symbols=("AAA.NS",),
        archives=(_archive(),),
    )
    rows = {item.code: item for item in audit.inventory_rows}
    absorption = rows[EvidenceCode.ABSORPTION.value]

    assert audit.evidence_emission_count == 3
    assert audit.event_bar_count == 1
    assert audit.duplicate_group_count == 1
    assert audit.duplicate_extra_emission_count == 1
    assert absorption.emitted_count == 2
    assert absorption.duplicate_group_count == 1
    assert absorption.duplicate_extra_emission_count == 1
    assert len(ACTIVE_DAILY_COLLECTOR_SOURCES[EvidenceCode.ABSORPTION]) == 2


def test_inventory_remains_non_actionable_and_writes_ledgers(tmp_path) -> None:
    audit = build_daily_event_inventory_audit(
        requested_symbols=("AAA.NS",),
        archives=(_archive(),),
    )
    paths = write_daily_event_inventory_audit(audit, tmp_path)

    assert audit.is_actionable is False
    assert paths.summary_json.exists()
    assert paths.inventory_csv.exists()
    assert paths.emissions_csv.exists()
    assert paths.duplicates_csv.exists()
    assert paths.failures_csv.exists()

    inventory = pd.read_csv(paths.inventory_csv)
    duplicates = pd.read_csv(paths.duplicates_csv)
    assert EvidenceCode.ABSORPTION.value in set(inventory["code"])
    assert duplicates.iloc[0]["emission_count"] == 2

def test_inventory_summary_records_frozen_input_provenance(
    tmp_path,
) -> None:
    provenance = DailyEventInventoryInputProvenance(
        source="FROZEN_DAILY_INPUT_SNAPSHOT",
        snapshot_audit_id="daily-audit-input-snapshot-v1",
        snapshot_manifest_sha256="a" * 64,
        snapshot_basket_name="test-basket",
        snapshot_period="max",
        snapshot_cutoff="2026-09-18T00:00:00",
    )
    audit = build_daily_event_inventory_audit(
        requested_symbols=("AAA.NS",),
        archives=(_archive(),),
        input_provenance=provenance,
    )

    paths = write_daily_event_inventory_audit(audit, tmp_path)
    summary = json.loads(
        paths.summary_json.read_text(encoding="utf-8")
    )

    assert audit.input_provenance == provenance
    assert summary["input_provenance"] == {
        "source": "FROZEN_DAILY_INPUT_SNAPSHOT",
        "snapshot_audit_id": "daily-audit-input-snapshot-v1",
        "snapshot_manifest_sha256": "a" * 64,
        "snapshot_basket_name": "test-basket",
        "snapshot_period": "max",
        "snapshot_cutoff": "2026-09-18T00:00:00",
    }

