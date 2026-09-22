from __future__ import annotations

import inspect

import pandas as pd

import config

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
from models import EvidenceCode


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
    "INCREASING_SUPPLY",
    "SUPPLY_DRYING_UP",
    "HIDDEN_SUPPLY",
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
    assert (
        "docs/DAILY_EVENT_STOPPING_VOLUME_DETECTOR_VERDICT.md"
        in contracts["STOPPING_VOLUME"].source_documents
    )
    assert (
        "docs/SELLING_CLIMAX_PRODUCTION_RECORD.md"
        in contracts["SELLING_CLIMAX"].source_documents
    )
    assert "docs/specifications/002_shakeout.md" in contracts["SHAKEOUT"].source_documents
    assert (
        "docs/DAILY_EVENT_SHAKEOUT_DETECTOR_VERDICT.md"
        in contracts["SHAKEOUT"].source_documents
    )
    assert "docs/specifications/003_test.md" in contracts["TEST"].source_documents
    assert (
        "docs/DAILY_EVENT_TEST_DETECTOR_VERDICT.md"
        in contracts["TEST"].source_documents
    )
    assert "docs/specifications/004_spring.md" in contracts["SPRING"].source_documents
    assert "docs/specifications/005_no_supply.md" in contracts["NO_SUPPLY"].source_documents
    assert "docs/ABSORPTION_AUDIT.md" in contracts["ABSORPTION"].source_documents
    assert "docs/NO_DEMAND_AUDIT.md" in contracts["NO_DEMAND"].source_documents
    assert (
        "docs/DAILY_EVENT_NO_DEMAND_DETECTOR_VERDICT.md"
        in contracts["NO_DEMAND"].source_documents
    )
    assert (
        "docs/DAILY_EVENT_HIDDEN_SUPPLY_DETECTOR_VERDICT.md"
        in contracts["HIDDEN_SUPPLY"].source_documents
    )
    assert (
        "docs/INCREASING_SUPPLY_AUDIT.md"
        in contracts["INCREASING_SUPPLY"].source_documents
    )
    assert (
        "docs/SUPPLY_DRYING_UP_AUDIT.md"
        in contracts["SUPPLY_DRYING_UP"].source_documents
    )
    assert (
        "docs/DAILY_EVENT_SUPPLY_COMING_IN_DETECTOR_VERDICT.md"
        in contracts["SUPPLY_COMING_IN"].source_documents
    )


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
    assert "point_in_time = metrics.iloc[: current_index + 1]" in source
    assert "validation.confirmation.confirmation_index != current_index" in source

    support_source = inspect.getsource(spring._prior_low_swings)
    assert "item.swing.bar_index < bar_index" in support_source
    assert "item.swing.confirmation_index <= bar_index" in support_source


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

    snapshot_source = inspect.getsource(demand._candidate_campaign_snapshot)
    assert "validation_metrics.iloc[start : candidate_index + 1]" in snapshot_source
    assert "item.swing.confirmation_index <= candidate_index" in snapshot_source

    trend_source = inspect.getsource(demand._candidate_trend_direction)
    assert "item.swing.confirmation_index <= candidate_index" in trend_source


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


def test_promoted_bc_upthrust_contracts_match_production_source() -> None:
    contracts = contracts_by_code()
    bc = contracts["BUYING_CLIMAX"]
    ut = contracts["UPTHRUST"]

    assert "non-strong high-price acceptance" in " ".join(bc.mandatory_requirements)
    assert "latest causally confirmed structural high exists" in ut.mandatory_requirements
    assert "current high probes above the structural high" in ut.mandatory_requirements
    assert "current close returns to or below the structural high" in ut.mandatory_requirements

    bc_source = inspect.getsource(supply._collect_buying_climax)
    assert 'name="Non-Strong High Acceptance"' in bc_source
    assert "ClosePosition.UPPER" in bc_source
    assert "ClosePosition.ON_HIGH" in bc_source

    ut_source = inspect.getsource(supply._collect_upthrust)
    assert 'name="Confirmed Structural High"' in ut_source
    assert 'name="Probe Above Structural High"' in ut_source
    assert 'name="Failed Acceptance Above Structural High"' in ut_source
    assert "structural_high_price" in ut_source

    high_source = inspect.getsource(supply._latest_confirmed_structural_high)
    assert "confirmation_index <= ctx.current.bar_index" in high_source
    assert "bar_index < ctx.current.bar_index" in high_source


def test_no_supply_contract_records_source_naming_mismatch() -> None:
    contract = contracts_by_code()["NO_SUPPLY"]

    assert any("Bullish Environment" in item for item in contract.mandatory_requirements)
    assert any("ctx.is_bearish_environment" in note for note in contract.known_review_notes)
    source = inspect.getsource(demand._collect_no_supply)
    assert 'name="Bullish Environment"' in source
    assert "ctx.is_bearish_environment()" in source


def test_absorption_contract_records_connected_non_scoring_alignment() -> None:
    contract = contracts_by_code()["ABSORPTION"]

    assert contract.module == "evidence.absorption"
    assert contract.detector == "collect_absorption"
    assert any(
        "production-connected non-scoring role" in note
        for note in contract.known_review_notes
    )
    assert not any(
        "stale" in note.lower() or "mismatch" in note.lower()
        for note in contract.known_review_notes
    )

    collect_source = inspect.getsource(demand.collect_demand)
    absorption_source = inspect.getsource(absorption.collect_absorption)
    assert "collect_absorption(ctx)" in collect_source
    assert "EvidenceCode.ABSORPTION" in absorption_source


def test_no_demand_contract_matches_current_source() -> None:
    contract = contracts_by_code()["NO_DEMAND"]

    assert contract.module == "evidence.supply"
    assert contract.detector == "_collect_no_demand"
    assert contract.direction == "bearish"
    assert contract.recognition_timing == CURRENT_BAR
    assert contract.mandatory_requirements == (
        "bullish environment",
        "bullish/up bar",
        "low volume",
        "narrow spread",
    )
    assert contract.diagnostic_confirmations == (
        "volume decreasing versus previous bar",
        "weak close",
    )
    assert contract.uses_future_bars is False
    assert any(
        "historical audit-path typo was corrected" in note
        for note in contract.known_review_notes
    )

    source = inspect.getsource(supply._collect_no_demand)
    assert 'name="Bullish Environment"' in source
    assert "ctx.is_bullish_environment()" in source
    assert 'name="Bullish Bar"' in source
    assert 'name="Low Volume"' in source
    assert 'name="Narrow Spread"' in source
    assert 'name="Volume Decreasing"' in source
    assert 'name="Weak Close"' in source
    assert "EvidenceCode.NO_DEMAND" in source
    assert hasattr(supply, "_collect_no_demand")
    assert not hasattr(demand, "_collect_no_demand")


def test_hidden_supply_contract_matches_current_source() -> None:
    contract = contracts_by_code()["HIDDEN_SUPPLY"]

    assert contract.module == "evidence.supply"
    assert contract.detector == "_collect_hidden_supply"
    assert contract.recognition_timing == CURRENT_BAR
    assert contract.diagnostic_confirmations == ()
    assert contract.uses_future_bars is False
    assert contract.mandatory_requirements == (
        "bullish/up bar",
        "high volume",
        "lower/weak close",
    )

    source = inspect.getsource(supply._collect_hidden_supply)
    assert "is_up_bar(bar)" in source
    assert "is_high_volume(bar)" in source
    assert "closes_lower(bar)" in source
    assert "EvidenceCode.HIDDEN_SUPPLY" in source


def test_increasing_supply_contract_matches_current_source() -> None:
    contract = contracts_by_code()["INCREASING_SUPPLY"]

    assert contract.module == "evidence.supply"
    assert contract.detector == "_collect_increasing_supply"
    assert contract.recognition_timing == CURRENT_BAR
    assert contract.diagnostic_confirmations == ()
    assert contract.uses_future_bars is False
    assert contract.mandatory_requirements == (
        "bearish/down bar",
        "volume increasing versus previous bar",
        "spread increasing versus previous bar",
    )

    source = inspect.getsource(supply._collect_increasing_supply)
    assert "is_down_bar(current)" in source
    assert "volume_increasing(current, previous)" in source
    assert "spread_increasing(current, previous)" in source
    assert "EvidenceCode.INCREASING_SUPPLY" in source


def test_supply_drying_up_contract_matches_current_source() -> None:
    contract = contracts_by_code()["SUPPLY_DRYING_UP"]

    assert contract.module == "evidence.supply"
    assert contract.detector == "_collect_supply_drying_up"
    assert contract.direction == "bullish/contextual"
    assert contract.recognition_timing == CURRENT_BAR
    assert contract.diagnostic_confirmations == ()
    assert contract.uses_future_bars is False
    assert contract.mandatory_requirements == (
        "bearish/down bar",
        "low volume",
        "narrow spread",
    )

    source = inspect.getsource(supply._collect_supply_drying_up)
    assert "is_down_bar(bar)" in source
    assert "is_low_volume(bar)" in source
    assert "is_narrow_spread(bar)" in source
    assert "EvidenceCode.SUPPLY_DRYING_UP" in source


def test_supply_coming_in_contract_matches_current_source() -> None:
    contract = contracts_by_code()["SUPPLY_COMING_IN"]

    assert contract.module == "evidence.supply"
    assert contract.detector == "_collect_supply_coming_in"
    assert contract.recognition_timing == CURRENT_BAR
    assert contract.diagnostic_confirmations == ()
    assert contract.uses_future_bars is False
    assert contract.mandatory_requirements == (
        "buying campaign",
        "down bar",
        "high volume",
        "above-average spread",
        "weak close",
        "volume increasing versus previous bar",
    )

    source = inspect.getsource(supply._collect_supply_coming_in)
    assert 'name="Buying Campaign"' in source
    assert "snapshot.has_buying_campaign()" in source
    assert 'name="Down Bar"' in source
    assert 'name="High Volume"' in source
    assert 'name="Above Average Spread"' in source
    assert 'name="Weak Close"' in source
    assert 'name="Volume Increasing"' in source
    assert "EvidenceCode.SUPPLY_COMING_IN" in source


def test_selling_climax_contract_matches_current_source() -> None:
    contract = contracts_by_code()["SELLING_CLIMAX"]

    assert contract.module == "evidence.demand"
    assert contract.detector == "_collect_selling_climax"
    assert contract.direction == "bullish"
    assert contract.recognition_timing == CURRENT_BAR
    assert contract.mandatory_requirements == (
        "selling campaign",
        "bearish/down bar",
        "very high volume",
        "above-average spread",
    )
    assert contract.diagnostic_confirmations == (
        "wide spread",
        "strong close",
        "increasing volume versus previous bar",
    )
    assert contract.uses_future_bars is False

    source = inspect.getsource(demand._collect_selling_climax)
    assert 'name="Selling Campaign"' in source
    assert "snapshot.has_selling_campaign()" in source
    assert 'name="Bearish Bar"' in source
    assert 'name="Very High Volume"' in source
    assert 'name="Above Average Spread"' in source
    assert 'name="Wide Spread"' in source
    assert 'name="Strong Close"' in source
    assert 'name="Increasing Volume"' in source
    assert "EvidenceCode.SELLING_CLIMAX" in source

    helper_source = inspect.getsource(helpers.add_evidence)
    assert "EvidenceCode.SELLING_CLIMAX: 0.38" in helper_source


def test_stopping_volume_contract_matches_current_source() -> None:
    contract = contracts_by_code()["STOPPING_VOLUME"]

    assert contract.module == "evidence.demand"
    assert contract.detector == "_collect_stopping_volume"
    assert contract.direction == "bullish"
    assert contract.recognition_timing == CURRENT_BAR
    assert contract.mandatory_requirements == (
        "selling campaign",
        "bearish/down bar",
        "high volume",
        "above-average spread",
        "close not on weak/lower area",
    )
    assert contract.diagnostic_confirmations == (
        "very high volume",
        "wide spread",
        "volume increasing versus previous bar",
        "higher low versus previous bar",
    )
    assert contract.uses_future_bars is False

    source = inspect.getsource(demand._collect_stopping_volume)
    assert 'name="Selling Campaign"' in source
    assert "snapshot.has_selling_campaign()" in source
    assert 'name="Bearish Bar"' in source
    assert 'name="High Volume"' in source
    assert 'name="Above Average Spread"' in source
    assert 'name="Close Off Low"' in source
    assert "not is_weak_close(bar)" in source
    assert 'name="Very High Volume"' in source
    assert 'name="Wide Spread"' in source
    assert 'name="Volume Increasing"' in source
    assert 'name="Higher Low"' in source
    assert "EvidenceCode.STOPPING_VOLUME" in source


def test_shakeout_recovery_contract_matches_validated_source() -> None:
    contract = contracts_by_code()["SHAKEOUT"]

    assert contract.module == "evidence.demand / evidence.campaign"
    assert contract.detector == "_collect_shakeout / validate_shakeout"
    assert contract.direction == "bullish"
    assert contract.recognition_timing == RECOVERY_ANCHORED
    assert contract.diagnostic_confirmations == ()
    assert contract.uses_future_bars is False
    assert contract.mandatory_requirements == (
        "candidate bearish/down bar",
        "selling pressure present",
        "wide spread",
        "very high volume",
        "lower low versus previous bar",
        "valid low-volume/low-spread test after candidate",
        "valid recovery after test",
    )

    finder_source = inspect.getsource(demand._find_recovery_anchored_shakeout)
    assert 'name="Bearish Bar"' in finder_source
    assert 'name="Selling Pressure Present"' in finder_source
    assert 'name="Wide Spread"' in finder_source
    assert 'name="Very High Volume"' in finder_source
    assert 'name="Lower Low"' in finder_source
    assert "validation.recovery.recovery_index != current_index" in finder_source

    recovery_source = inspect.getsource(campaign._validate_shakeout_recovery)
    assert "direction == 1" in recovery_source
    assert "close_position >= config.SHAKEOUT_RECOVERY_MIN_CLOSE_POSITION" in recovery_source
    assert "bar_close > test_close" in recovery_source
    assert "bar_low >= test_low" in recovery_source

    # These legacy/reserved settings exist in config but are not part of the
    # validated production recovery gate.
    assert "SHAKEOUT_RECOVERY_MIN_UP_BARS" not in recovery_source
    assert "SHAKEOUT_RECOVERY_MIN_STRONG_CLOSES" not in recovery_source


def test_shakeout_emits_on_recovery_bar_with_sequence_provenance() -> None:
    source = inspect.getsource(demand._collect_shakeout)

    assert "validation.test.test_index is not None" in source
    assert "validation.recovery.recovery_index is not None" in source
    assert "test_index=validation.test.test_index" in source
    assert "recovery_index=validation.recovery.recovery_index" in source
    assert "quality = calculate_shakeout_quality(validation=validation)" in source


def test_test_contract_matches_audited_production_source() -> None:
    contract = contracts_by_code()["TEST"]

    assert contract.module == "evidence.demand"
    assert contract.detector == "_collect_test"
    assert contract.direction == "bullish"
    assert contract.recognition_timing == CURRENT_BAR
    assert contract.mandatory_requirements == (
        "selling campaign",
        "bearish/down bar",
        "low volume",
        "narrow spread",
        "no strong downtrend contradiction",
    )
    assert contract.diagnostic_confirmations == (
        "volume decreasing versus previous bar",
        "strong close",
        "higher low versus previous bar",
    )
    assert contract.uses_future_bars is False

    source = inspect.getsource(demand._collect_test)
    assert 'name="Selling Campaign"' in source
    assert "snapshot.has_selling_campaign()" in source
    assert 'name="Down Bar"' in source
    assert 'name="Low Volume"' in source
    assert 'name="Narrow Spread"' in source
    assert 'name="No Strong Downtrend Contradiction"' in source
    assert "is_confirmed_downtrend(trend)" in source
    assert "_recent_structural_weakness(ctx)" in source
    assert 'name="Volume Decreasing"' in source
    assert 'name="Strong Close"' in source
    assert 'name="Higher Low"' in source
    assert "EvidenceCode.TEST" in source


def test_test_remains_professional_non_scoring_contextual_confirmation() -> None:
    assert EvidenceCode.TEST not in config.DEMAND_EVIDENCE_WEIGHTS

    helper_source = inspect.getsource(helpers.add_evidence)
    weight_source = inspect.getsource(helpers.WeightCalculator._test_weight)
    assert "WeightCalculator.calculate(" in helper_source
    assert "return max(0.50, min(weight, 2.00))" in weight_source
