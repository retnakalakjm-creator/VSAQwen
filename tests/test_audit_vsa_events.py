from __future__ import annotations

import inspect

import pandas as pd

from audit.vsa_events import (
    CONFIRMATION_ANCHORED,
    CURRENT_BAR,
    RECOVERY_ANCHORED,
    VSA_EVENT_CONTRACTS,
    contracts_by_code,
    non_causal_contracts,
    vsa_event_contract_frame,
)
from evidence import absorption
from evidence import campaign
from evidence import demand
from evidence import helpers
from evidence import spring
from evidence import supply


EXPECTED_EVENT_CODES = {
    "STOPPING_VOLUME",
    "SELLING_CLIMAX",
    "TEST",
    "NO_SUPPLY",
    "INCREASING_DEMAND",
    "SHAKEOUT",
    "SPRING",
    "BUYING_CLIMAX",
    "UPTHRUST",
    "NO_DEMAND",
    "SUPPLY_COMING_IN",
    "ABSORPTION",
}


def test_vsa_event_contract_catalog_covers_core_events() -> None:
    contracts = contracts_by_code()

    assert EXPECTED_EVENT_CODES <= set(contracts)
    assert len(VSA_EVENT_CONTRACTS) == len(set(contracts))
    assert non_causal_contracts() == ()


def test_vsa_event_contract_frame_is_review_ready() -> None:
    frame = vsa_event_contract_frame()

    assert isinstance(frame, pd.DataFrame)
    assert len(frame) == len(VSA_EVENT_CONTRACTS)
    assert {
        "evidence_code",
        "module",
        "detector",
        "direction",
        "recognition_timing",
        "emitted_bar",
        "mandatory_requirements",
        "diagnostic_confirmations",
        "uses_future_bars",
        "future_bar_policy",
        "source_documents",
        "known_review_notes",
    } <= set(frame.columns)
    assert not frame["uses_future_bars"].any()
    assert frame["source_documents"].map(bool).all()


def test_source_documents_include_existing_audit_records() -> None:
    contracts = contracts_by_code()

    assert "docs/specifications/001_stopping_volume.md" in contracts["STOPPING_VOLUME"].source_documents
    assert "docs/specifications/002_shakeout.md" in contracts["SHAKEOUT"].source_documents
    assert "docs/specifications/003_test.md" in contracts["TEST"].source_documents
    assert "docs/specifications/004_spring.md" in contracts["SPRING"].source_documents
    assert "docs/specifications/005_no_supply.md" in contracts["NO_SUPPLY"].source_documents
    assert "docs/ABSORPTION_AUDIT.md" in contracts["ABSORPTION"].source_documents
    assert "docs/NO_DEMAND_AUDIT.md" in contracts["NO_DEMAND"].source_documents


def test_shakeout_is_documented_as_delayed_recognition_not_candidate_bar_signal() -> None:
    contract = contracts_by_code()["SHAKEOUT"]

    assert contract.recognition_timing == RECOVERY_ANCHORED
    assert "recovery" in contract.emitted_bar
    assert "test_index" in contract.emitted_bar
    assert "recovery_index" in contract.emitted_bar
    assert contract.uses_future_bars is False
    assert "current recovery bar only" in contract.future_bar_policy


def test_spring_is_documented_as_confirmation_anchored_not_candidate_bar_signal() -> None:
    contract = contracts_by_code()["SPRING"]

    assert contract.recognition_timing == CONFIRMATION_ANCHORED
    assert "confirmation" in contract.emitted_bar
    assert "test_index" in contract.emitted_bar
    assert "recovery_index" in contract.emitted_bar
    assert contract.uses_future_bars is False
    assert "current confirmation bar only" in contract.future_bar_policy

    source = inspect.getsource(spring.collect_spring)
    assert "point_in_time = metrics.iloc[: current_index + 1].copy()" in source
    assert "validation.confirmation.confirmation_index != current_index" in source


def test_current_bar_events_are_not_marked_as_using_future_bars() -> None:
    for contract in VSA_EVENT_CONTRACTS:
        if contract.recognition_timing == CURRENT_BAR:
            assert contract.uses_future_bars is False
            assert "No forward bars" in contract.future_bar_policy


def test_evaluate_detector_confirmations_are_diagnostic_not_gating() -> None:
    source = inspect.getsource(helpers.evaluate_detector)

    assert "if not requirements_passed(requirements)" in source
    assert "confirmation_count(confirmations)" in source
    assert "add_evidence(" in source
    assert "confirmation_score" in source
    assert "return False" in source
    assert "return True" in source

    add_position = source.index("add_evidence(")
    confirmation_position = source.index("confirmation_count(confirmations)")
    assert confirmation_position < add_position
    assert "if confirmation" not in source[confirmation_position:add_position]


def test_shakeout_validation_is_sliced_to_current_bar_before_forward_validation() -> None:
    source = inspect.getsource(demand._find_recovery_anchored_shakeout)

    assert "current_index = int(ctx.current.bar_index)" in source
    assert "point_in_time_metrics = validation_metrics.iloc[: current_index + 1]" in source
    assert "validate_shakeout(metrics=point_in_time_metrics" in source
    assert "validation.recovery.recovery_index != current_index" in source


def test_contract_detector_names_exist_in_source_modules() -> None:
    module_sources = {
        "evidence.demand": inspect.getsource(demand),
        "evidence.supply": inspect.getsource(supply),
        "evidence.spring": inspect.getsource(spring),
        "evidence.absorption": inspect.getsource(absorption),
        "evidence.demand / evidence.campaign": inspect.getsource(demand) + inspect.getsource(campaign),
    }

    for contract in VSA_EVENT_CONTRACTS:
        source = module_sources[contract.module]
        for detector_name in contract.detector.split(" / "):
            assert f"def {detector_name}" in source


def test_no_supply_contract_records_source_naming_mismatch() -> None:
    contract = contracts_by_code()["NO_SUPPLY"]

    assert any("Bullish Environment" in item for item in contract.mandatory_requirements)
    assert any("ctx.is_bearish_environment" in note for note in contract.known_review_notes)
    source = inspect.getsource(demand._collect_no_supply)
    assert 'name="Bullish Environment"' in source
    assert "ctx.is_bearish_environment()" in source


def test_absorption_contract_records_connected_non_scoring_doc_mismatch() -> None:
    contract = contracts_by_code()["ABSORPTION"]

    assert contract.module == "evidence.absorption"
    assert contract.detector == "collect_absorption"
    assert any("production-connected non-scoring" in note for note in contract.known_review_notes)
    assert any("PRIMARY_VSA_EVENT_MATRIX.md" in note for note in contract.known_review_notes)

    collect_source = inspect.getsource(demand.collect_demand)
    absorption_source = inspect.getsource(absorption.collect_absorption)
    assert "collect_absorption(ctx)" in collect_source
    assert "EvidenceCode.ABSORPTION" in absorption_source


def test_no_demand_contract_records_audit_path_typo() -> None:
    contract = contracts_by_code()["NO_DEMAND"]

    assert contract.module == "evidence.supply"
    assert any("NO_DEMAND_AUDIT.md" in note for note in contract.known_review_notes)
    assert any("evidence/demand.py::_collect_no_demand" in note for note in contract.known_review_notes)
    assert hasattr(supply, "_collect_no_demand")
    assert not hasattr(demand, "_collect_no_demand")
