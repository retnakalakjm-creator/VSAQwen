from __future__ import annotations

import json

import pandas as pd

from audit.daily_event_cofiring import (
    DAILY_EVENT_COFIRING_AUDIT_ID,
    FrozenDailyEventLedger,
    FrozenDailyEventLedgerLineage,
    build_daily_event_cofiring_audit,
    build_daily_event_gate_semantics,
    load_frozen_daily_event_ledger,
    write_daily_event_cofiring_audit,
)


def _emissions() -> pd.DataFrame:
    rows = [
        ("AAA.NS", 1, "2026-01-01", "buying_climax"),
        ("AAA.NS", 1, "2026-01-01", "upthrust"),
        ("AAA.NS", 2, "2026-01-02", "buying_climax"),
        ("AAA.NS", 2, "2026-01-02", "upthrust"),
        ("AAA.NS", 2, "2026-01-02", "effort_gt_result"),
        ("AAA.NS", 3, "2026-01-03", "no_supply"),
        ("AAA.NS", 3, "2026-01-03", "effort_gt_result"),
        ("AAA.NS", 4, "2026-01-04", "absorption"),
        ("AAA.NS", 4, "2026-01-04", "absorption"),
    ]
    return pd.DataFrame(
        [
            {
                "symbol": symbol,
                "bar_index": bar_index,
                "session": session,
                "code": code,
                "category": "fixture",
                "direction": "fixture",
                "strength": 1.0,
                "weight": 0.0,
                "quality": 1.0,
                "test_index": None,
                "recovery_index": None,
                "occurrence_on_bar_code": occurrence,
            }
            for occurrence, (symbol, bar_index, session, code) in enumerate(
                rows,
                start=1,
            )
        ]
    )


def _ledger() -> FrozenDailyEventLedger:
    emissions = _emissions()
    return FrozenDailyEventLedger(
        source_audit_id="daily-event-inventory-point-in-time-v1",
        requested_symbol_count=1,
        succeeded_symbol_count=1,
        failed_symbol_count=0,
        evaluated_bar_count=10,
        evidence_emission_count=len(emissions),
        event_bar_count=4,
        emissions=emissions,
    )


def test_frequency_deduplicates_same_bar_code_but_keeps_raw_count() -> None:
    audit = build_daily_event_cofiring_audit(_ledger())
    rows = {item.code: item for item in audit.frequency_rows}

    absorption = rows["absorption"]
    assert absorption.raw_emission_count == 2
    assert absorption.unique_event_count == 1
    assert absorption.duplicate_extra_emission_count == 1
    assert absorption.evaluated_bar_rate == 0.1


def test_pairwise_identifies_identical_and_subset_firing_sets() -> None:
    audit = build_daily_event_cofiring_audit(_ledger())
    pairs = {
        (item.code_a, item.code_b): item
        for item in audit.pairwise_rows
    }

    identical = pairs[("buying_climax", "upthrust")]
    assert identical.relationship == "IDENTICAL_FIRING_SET"
    assert identical.jaccard == 1.0

    nested = pairs[("effort_gt_result", "no_supply")]
    assert nested.relationship == "B_STRICT_SUBSET_OF_A"
    assert nested.pct_b_with_a == 1.0


def test_cluster_signatures_use_unique_codes_per_bar() -> None:
    audit = build_daily_event_cofiring_audit(_ledger())

    assert audit.event_bar_count == 4
    assert audit.multi_code_bar_count == 3
    assert audit.three_plus_code_bar_count == 1
    assert audit.max_codes_on_bar == 3
    assert audit.cluster_signature_count == 4


def test_gate_semantics_exposes_non_gating_confirmations() -> None:
    rows = {item.code: item for item in build_daily_event_gate_semantics()}

    for code in (
        "buying_climax",
        "no_demand",
        "upthrust",
        "stopping_volume",
        "selling_climax",
        "test",
        "no_supply",
    ):
        assert rows[code].confirmation_requirement_count > 0
        assert rows[code].shared_confirmation_gate_enforced is False
        assert rows[code].gate_status == "CONFIRMATIONS_PRESENT_NON_GATING"


def test_loader_requires_zero_failure_non_actionable_l1_source(
    tmp_path,
) -> None:
    emissions = _emissions()
    summary = {
        "audit_id": "daily-event-inventory-point-in-time-v1",
        "requested_symbol_count": 1,
        "succeeded_symbol_count": 1,
        "failed_symbol_count": 0,
        "evaluated_bar_count": 10,
        "evidence_emission_count": len(emissions),
        "event_bar_count": 4,
        "input_provenance": {
            "source": "FROZEN_DAILY_INPUT_SNAPSHOT",
            "snapshot_audit_id": "daily-audit-input-snapshot-v1",
            "snapshot_manifest_sha256": "a" * 64,
            "snapshot_basket_name": "test-basket",
            "snapshot_period": "max",
            "snapshot_cutoff": "2026-09-18T00:00:00",
        },
        "is_actionable": False,
    }
    (tmp_path / "daily_event_inventory_summary.json").write_text(
        json.dumps(summary),
        encoding="utf-8",
    )
    emissions.to_csv(tmp_path / "daily_event_emissions.csv", index=False)

    ledger = load_frozen_daily_event_ledger(tmp_path)

    assert ledger.failed_symbol_count == 0
    assert len(ledger.emissions) == len(emissions)
    assert ledger.source_lineage is not None
    assert ledger.source_lineage.input_source == (
        "FROZEN_DAILY_INPUT_SNAPSHOT"
    )
    assert ledger.source_lineage.snapshot_period == "max"
    assert len(ledger.source_lineage.l1_summary_sha256) == 64
    assert len(ledger.source_lineage.l1_emissions_sha256) == 64


def test_audit_remains_non_actionable() -> None:
    audit = build_daily_event_cofiring_audit(_ledger())

    assert audit.audit_id == DAILY_EVENT_COFIRING_AUDIT_ID
    assert audit.is_actionable is False


def test_loader_rejects_legacy_l1_without_frozen_provenance(
    tmp_path,
) -> None:
    emissions = _emissions()
    summary = {
        "audit_id": "daily-event-inventory-point-in-time-v1",
        "requested_symbol_count": 1,
        "succeeded_symbol_count": 1,
        "failed_symbol_count": 0,
        "evaluated_bar_count": 10,
        "evidence_emission_count": len(emissions),
        "event_bar_count": 4,
        "is_actionable": False,
    }
    (tmp_path / "daily_event_inventory_summary.json").write_text(
        json.dumps(summary),
        encoding="utf-8",
    )
    emissions.to_csv(
        tmp_path / "daily_event_emissions.csv",
        index=False,
    )

    try:
        load_frozen_daily_event_ledger(tmp_path)
    except ValueError as exc:
        assert "frozen snapshot input provenance" in str(exc)
    else:
        raise AssertionError("legacy L1 must not be accepted by L2")


def test_l2_summary_preserves_exact_l1_lineage(tmp_path) -> None:
    lineage = FrozenDailyEventLedgerLineage(
        input_source="FROZEN_DAILY_INPUT_SNAPSHOT",
        snapshot_audit_id="daily-audit-input-snapshot-v1",
        snapshot_manifest_sha256="a" * 64,
        snapshot_basket_name="test-basket",
        snapshot_period="max",
        snapshot_cutoff="2026-09-18T00:00:00",
        l1_summary_sha256="b" * 64,
        l1_emissions_sha256="c" * 64,
    )
    ledger = FrozenDailyEventLedger(
        source_audit_id="daily-event-inventory-point-in-time-v1",
        requested_symbol_count=1,
        succeeded_symbol_count=1,
        failed_symbol_count=0,
        evaluated_bar_count=10,
        evidence_emission_count=len(_emissions()),
        event_bar_count=4,
        emissions=_emissions(),
        source_lineage=lineage,
    )

    audit = build_daily_event_cofiring_audit(ledger)
    paths = write_daily_event_cofiring_audit(audit, tmp_path)
    summary = json.loads(
        paths.summary_json.read_text(encoding="utf-8")
    )

    assert audit.source_lineage == lineage
    assert summary["source_lineage"] == {
        "input_source": "FROZEN_DAILY_INPUT_SNAPSHOT",
        "snapshot_audit_id": "daily-audit-input-snapshot-v1",
        "snapshot_manifest_sha256": "a" * 64,
        "snapshot_basket_name": "test-basket",
        "snapshot_period": "max",
        "snapshot_cutoff": "2026-09-18T00:00:00",
        "l1_summary_sha256": "b" * 64,
        "l1_emissions_sha256": "c" * 64,
    }

