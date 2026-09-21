from __future__ import annotations

import json

import pandas as pd
import pytest

from audit.daily_event_confirmation_semantics import (
    build_confirmation_contract_rows,
    build_detector_confirmation_semantics_audit,
)


def _rows_by_code():
    rows = build_confirmation_contract_rows()
    grouped: dict[str, list] = {}
    for row in rows:
        grouped.setdefault(row.code, []).append(row)
    return rows, grouped


def test_contract_inventory_covers_exact_l3_detector_surface() -> None:
    rows, grouped = _rows_by_code()

    assert len(grouped) == 7
    assert len(rows) == 51
    assert sum(
        row.requirement_kind == "CONFIRMATION"
        for row in rows
    ) == 21

    assert set(grouped) == {
        "buying_climax",
        "no_demand",
        "no_supply",
        "selling_climax",
        "stopping_volume",
        "test",
        "upthrust",
    }


def test_buying_climax_and_upthrust_share_mandatory_contract_only() -> None:
    _, grouped = _rows_by_code()

    def contract(code: str, kind: str) -> tuple[tuple[str, str], ...]:
        return tuple(
            (row.requirement_name, row.passed_expression)
            for row in grouped[code]
            if row.requirement_kind == kind
        )

    assert contract("buying_climax", "MANDATORY") == contract(
        "upthrust",
        "MANDATORY",
    )
    assert contract("buying_climax", "CONFIRMATION") != contract(
        "upthrust",
        "CONFIRMATION",
    )
    assert contract("buying_climax", "CONFIRMATION")[-1][0] == (
        "Increasing Volume"
    )
    assert contract("upthrust", "CONFIRMATION")[-1][0] == (
        "Lower Close Than Previous"
    )


def test_no_supply_contract_exposes_environment_label_expression() -> None:
    _, grouped = _rows_by_code()
    mandatory = [
        row
        for row in grouped["no_supply"]
        if row.requirement_kind == "MANDATORY"
    ]

    environment = mandatory[0]
    assert environment.requirement_name == "Bullish Environment"
    assert environment.passed_expression == "ctx.is_bearish_environment()"


def _write_fixture_l3(tmp_path):
    rows, grouped = _rows_by_code()
    del rows

    observations: list[dict[str, object]] = []
    for index, code in enumerate(sorted(grouped), start=1):
        confirmation_names = [
            row.requirement_name
            for row in grouped[code]
            if row.requirement_kind == "CONFIRMATION"
        ]
        observations.append(
            {
                "symbol": "AAA.NS",
                "bar_index": index,
                "session": f"2026-01-{index:02d}T00:00:00",
                "code": code,
                "confirmation_count": len(confirmation_names),
                "passed_confirmation_count": len(confirmation_names),
                "passed_confirmations": "|".join(confirmation_names),
                "failed_confirmations": "",
                "survives_any": True,
                "survives_strict_majority": True,
                "survives_all": True,
            }
        )

    frame = pd.DataFrame(observations)
    frame.to_csv(
        tmp_path / "daily_confirmation_observations.csv",
        index=False,
    )
    summary = {
        "audit_id": "daily-event-confirmation-counterfactual-v1",
        "requested_symbol_count": 1,
        "succeeded_symbol_count": 1,
        "failed_symbol_count": 0,
        "baseline_event_count": 7,
        "captured_event_count": 7,
        "physical_observation_count": 7,
        "duplicate_observation_count": 0,
        "identity_mismatch_count": 0,
        "bar_index_mismatch_count": 0,
        "source_lineage": {
            "snapshot_manifest_sha256": "a" * 64,
            "l1_summary_sha256": "b" * 64,
            "l1_emissions_sha256": "c" * 64,
            "l2_summary_sha256": "d" * 64,
        },
        "is_actionable": False,
    }
    (tmp_path / "daily_confirmation_counterfactual_summary.json").write_text(
        json.dumps(summary),
        encoding="utf-8",
    )


def test_semantics_audit_joins_contract_to_l3_without_replay(
    tmp_path,
) -> None:
    _write_fixture_l3(tmp_path)

    audit = build_detector_confirmation_semantics_audit(tmp_path)

    assert audit.detector_count == 7
    assert audit.event_count == 7
    assert audit.contract_row_count == 51
    assert audit.confirmation_requirement_row_count == 21
    assert audit.pattern_row_count == 7
    assert len(audit.source_lineage.l3_summary_sha256) == 64
    assert len(audit.source_lineage.l3_observations_sha256) == 64

    by_code = {row.code: row for row in audit.detector_rows}
    assert by_code["buying_climax"].same_mandatory_codes == (
        "upthrust",
    )
    assert by_code["upthrust"].same_mandatory_codes == (
        "buying_climax",
    )
    assert by_code["stopping_volume"].confirmation_requirement_count == 4
    assert by_code["no_demand"].confirmation_requirement_count == 2


def test_semantics_audit_rejects_confirmation_name_drift(tmp_path) -> None:
    _write_fixture_l3(tmp_path)
    path = tmp_path / "daily_confirmation_observations.csv"
    frame = pd.read_csv(path)
    index = frame.index[frame["code"] == "buying_climax"][0]
    frame.loc[index, "passed_confirmations"] = (
        "Invented Confirmation|Weak Close|Increasing Volume"
    )
    frame.to_csv(path, index=False)

    with pytest.raises(
        ValueError,
        match="confirmation names differ from source contract",
    ):
        build_detector_confirmation_semantics_audit(tmp_path)
