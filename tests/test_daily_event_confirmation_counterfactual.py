from __future__ import annotations

import json
from dataclasses import asdict
from hashlib import sha256

import pandas as pd
import pytest

from audit.daily_event_confirmation_counterfactual import (
    POLICY_ALL,
    POLICY_ANY,
    POLICY_CURRENT,
    POLICY_MAJORITY,
    DailyConfirmationObservation,
    DailyConfirmationSourceLineage,
    _policy_survives,
    build_confirmation_counterfactual_audit,
    load_confirmation_sources,
)


def _observation(
    code: str,
    *,
    bar_index: int,
    passed: int,
    total: int,
) -> DailyConfirmationObservation:
    names = tuple(f"c{index}" for index in range(total))
    return DailyConfirmationObservation(
        symbol="AAA.NS",
        bar_index=bar_index,
        session=f"2026-01-{bar_index:02d}T00:00:00",
        code=code,
        confirmation_count=total,
        passed_confirmation_count=passed,
        passed_confirmations=names[:passed],
        failed_confirmations=names[passed:],
        survives_any=passed >= 1,
        survives_strict_majority=passed * 2 > total,
        survives_all=passed == total,
    )


def _lineage() -> DailyConfirmationSourceLineage:
    return DailyConfirmationSourceLineage(
        snapshot_audit_id="daily-audit-input-snapshot-v1",
        snapshot_manifest_sha256="a" * 64,
        snapshot_basket_name="test-basket",
        snapshot_period="max",
        snapshot_cutoff="2026-09-18T00:00:00",
        l1_audit_id="daily-event-inventory-point-in-time-v1",
        l1_summary_sha256="b" * 64,
        l1_emissions_sha256="c" * 64,
        l2_audit_id="daily-event-frequency-cofiring-gates-v1",
        l2_summary_sha256="d" * 64,
    )


def test_confirmation_policies_have_distinct_thresholds() -> None:
    assert _policy_survives(POLICY_CURRENT, 0, 3) is True
    assert _policy_survives(POLICY_ANY, 1, 3) is True
    assert _policy_survives(POLICY_ANY, 0, 3) is False
    assert _policy_survives(POLICY_MAJORITY, 2, 3) is True
    assert _policy_survives(POLICY_MAJORITY, 2, 4) is False
    assert _policy_survives(POLICY_MAJORITY, 3, 4) is True
    assert _policy_survives(POLICY_ALL, 2, 3) is False
    assert _policy_survives(POLICY_ALL, 3, 3) is True


def test_identity_parity_normalizes_equivalent_session_text() -> None:
    observation = DailyConfirmationObservation(
        symbol="AAA.NS",
        bar_index=1,
        session="2026-01-01 00:00:00",
        code="buying_climax",
        confirmation_count=3,
        passed_confirmation_count=1,
        passed_confirmations=("c0",),
        failed_confirmations=("c1", "c2"),
        survives_any=True,
        survives_strict_majority=False,
        survives_all=False,
    )
    baseline = pd.DataFrame(
        [
            {
                "symbol": "AAA.NS",
                "bar_index": 1,
                "session": "2026-01-01T00:00:00",
                "code": "buying_climax",
            }
        ]
    )

    audit = build_confirmation_counterfactual_audit(
        source_audit_id="daily-event-inventory-point-in-time-v1",
        source_lineage=_lineage(),
        requested_symbols=("AAA.NS",),
        baseline=baseline,
        observations=(observation,),
    )

    assert audit.identity_mismatch_count == 0
    assert audit.bar_index_mismatch_count == 0


def test_frozen_replay_bar_index_drift_remains_visible() -> None:
    observation = DailyConfirmationObservation(
        symbol="AAA.NS",
        bar_index=1182,
        session="2026-01-01T00:00:00",
        code="buying_climax",
        confirmation_count=3,
        passed_confirmation_count=1,
        passed_confirmations=("c0",),
        failed_confirmations=("c1", "c2"),
        survives_any=True,
        survives_strict_majority=False,
        survives_all=False,
    )
    baseline = pd.DataFrame(
        [
            {
                "symbol": "AAA.NS",
                "bar_index": 181,
                "session": "2026-01-01T00:00:00",
                "code": "buying_climax",
            }
        ]
    )

    audit = build_confirmation_counterfactual_audit(
        source_audit_id="daily-event-inventory-point-in-time-v1",
        source_lineage=_lineage(),
        requested_symbols=("AAA.NS",),
        baseline=baseline,
        observations=(observation,),
    )

    assert audit.identity_mismatch_count == 0
    assert audit.bar_index_mismatch_count == 1
    assert audit.bar_index_drifts[0].index_delta == 1001


def test_pairwise_relationship_can_separate_identical_current_labels() -> None:
    observations = (
        _observation("buying_climax", bar_index=1, passed=3, total=3),
        _observation("upthrust", bar_index=1, passed=1, total=3),
        _observation("buying_climax", bar_index=2, passed=2, total=3),
        _observation("upthrust", bar_index=2, passed=0, total=3),
    )
    baseline = pd.DataFrame(
        [
            {
                "symbol": item.symbol,
                "bar_index": item.bar_index,
                "session": item.session,
                "code": item.code,
            }
            for item in observations
        ]
    )
    audit = build_confirmation_counterfactual_audit(
        source_audit_id="daily-event-inventory-point-in-time-v1",
        source_lineage=_lineage(),
        requested_symbols=("AAA.NS",),
        baseline=baseline,
        observations=observations,
    )

    pairs = {
        (item.policy, item.code_a, item.code_b): item
        for item in audit.pairwise_rows
    }
    current = pairs[
        (POLICY_CURRENT, "buying_climax", "upthrust")
    ]
    strict = pairs[
        (POLICY_ALL, "buying_climax", "upthrust")
    ]

    assert current.relationship == "IDENTICAL_FIRING_SET"
    assert strict.relationship != "IDENTICAL_FIRING_SET"


def test_duplicate_stable_identity_is_counted_once_everywhere() -> None:
    observation = _observation(
        "buying_climax",
        bar_index=1,
        passed=1,
        total=3,
    )
    baseline = pd.DataFrame(
        [
            {
                "symbol": observation.symbol,
                "bar_index": observation.bar_index,
                "session": observation.session,
                "code": observation.code,
            }
        ]
    )

    audit = build_confirmation_counterfactual_audit(
        source_audit_id="daily-event-inventory-point-in-time-v1",
        source_lineage=_lineage(),
        requested_symbols=("AAA.NS",),
        baseline=baseline,
        observations=(observation, observation),
    )

    current = next(
        row
        for row in audit.policy_rows
        if row.code == "buying_climax"
        and row.policy == POLICY_CURRENT
    )
    assert audit.physical_observation_count == 2
    assert audit.captured_event_count == 1
    assert audit.duplicate_observation_count == 1
    assert len(audit.observations) == 1
    assert current.current_event_count == 1


def test_conflicting_duplicate_stable_identity_is_rejected() -> None:
    first = _observation(
        "buying_climax",
        bar_index=1,
        passed=1,
        total=3,
    )
    conflicting = _observation(
        "buying_climax",
        bar_index=1,
        passed=2,
        total=3,
    )
    baseline = pd.DataFrame(
        [
            {
                "symbol": first.symbol,
                "bar_index": first.bar_index,
                "session": first.session,
                "code": first.code,
            }
        ]
    )

    with pytest.raises(
        ValueError,
        match="conflicting confirmation observations",
    ):
        build_confirmation_counterfactual_audit(
            source_audit_id="daily-event-inventory-point-in-time-v1",
            source_lineage=_lineage(),
            requested_symbols=("AAA.NS",),
            baseline=baseline,
            observations=(first, conflicting),
        )


def _write_source_chain(tmp_path) -> tuple[object, object, object]:
    snapshot_dir = tmp_path / "snapshot"
    l1_dir = tmp_path / "l1"
    l2_dir = tmp_path / "l2"
    snapshot_dir.mkdir()
    l1_dir.mkdir()
    l2_dir.mkdir()

    manifest = {
        "audit_id": "daily-audit-input-snapshot-v1",
        "basket_name": "test-basket",
        "provider": "fixture",
        "period": "max",
        "cutoff": "2026-09-18T00:00:00",
        "symbol_count": 1,
        "is_actionable": False,
        "fingerprints": [
            {
                "symbol": "AAA.NS",
                "version": "daily-ohlcv-v1",
                "period": "max",
                "cutoff": "2026-09-18T00:00:00",
                "row_count": 1,
                "first_session": "2026-01-01T00:00:00",
                "last_session": "2026-01-01T00:00:00",
                "sha256": "e" * 64,
                "relative_path": "snapshots/AAA.NS.csv",
                "columns": [
                    "session",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                ],
            }
        ],
    }
    manifest_path = snapshot_dir / "daily_audit_input_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    manifest_sha = sha256(manifest_path.read_bytes()).hexdigest()

    emissions = pd.DataFrame(
        [
            {
                "symbol": "AAA.NS",
                "bar_index": 23,
                "session": "2026-01-01T00:00:00",
                "code": "buying_climax",
                "direction": "bearish",
                "occurrence_on_bar_code": 1,
            }
        ]
    )
    emissions_path = l1_dir / "daily_event_emissions.csv"
    emissions.to_csv(emissions_path, index=False)

    l1_summary = {
        "audit_id": "daily-event-inventory-point-in-time-v1",
        "requested_symbol_count": 1,
        "succeeded_symbol_count": 1,
        "failed_symbol_count": 0,
        "evaluated_bar_count": 1,
        "evidence_emission_count": 1,
        "event_bar_count": 1,
        "input_provenance": {
            "source": "FROZEN_DAILY_INPUT_SNAPSHOT",
            "snapshot_audit_id": "daily-audit-input-snapshot-v1",
            "snapshot_manifest_sha256": manifest_sha,
            "snapshot_basket_name": "test-basket",
            "snapshot_period": "max",
            "snapshot_cutoff": "2026-09-18T00:00:00",
        },
        "is_actionable": False,
    }
    l1_summary_path = l1_dir / "daily_event_inventory_summary.json"
    l1_summary_path.write_text(
        json.dumps(l1_summary),
        encoding="utf-8",
    )

    l1_lineage = {
        "input_source": "FROZEN_DAILY_INPUT_SNAPSHOT",
        "snapshot_audit_id": "daily-audit-input-snapshot-v1",
        "snapshot_manifest_sha256": manifest_sha,
        "snapshot_basket_name": "test-basket",
        "snapshot_period": "max",
        "snapshot_cutoff": "2026-09-18T00:00:00",
        "l1_summary_sha256": sha256(
            l1_summary_path.read_bytes()
        ).hexdigest(),
        "l1_emissions_sha256": sha256(
            emissions_path.read_bytes()
        ).hexdigest(),
    }
    l2_summary = {
        "audit_id": "daily-event-frequency-cofiring-gates-v1",
        "source_audit_id": "daily-event-inventory-point-in-time-v1",
        "requested_symbol_count": 1,
        "succeeded_symbol_count": 1,
        "confirmation_sensitive_detector_count": 7,
        "non_gating_confirmation_detector_count": 7,
        "source_lineage": l1_lineage,
        "is_actionable": False,
    }
    (l2_dir / "daily_event_cofiring_summary.json").write_text(
        json.dumps(l2_summary),
        encoding="utf-8",
    )
    return l1_dir, l2_dir, snapshot_dir


def test_source_chain_requires_exact_frozen_l1_l2_lineage(
    tmp_path,
) -> None:
    l1_dir, l2_dir, snapshot_dir = _write_source_chain(tmp_path)

    sources = load_confirmation_sources(
        l1_dir=l1_dir,
        l2_dir=l2_dir,
        input_snapshot_dir=snapshot_dir,
        basket_name="test-basket",
    )

    assert len(sources.baseline) == 1
    assert sources.lineage.snapshot_basket_name == "test-basket"
    assert len(sources.lineage.l2_summary_sha256) == 64


def test_source_chain_rejects_l2_from_different_l1(tmp_path) -> None:
    l1_dir, l2_dir, snapshot_dir = _write_source_chain(tmp_path)
    summary_path = l2_dir / "daily_event_cofiring_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["source_lineage"]["l1_emissions_sha256"] = "0" * 64
    summary_path.write_text(json.dumps(summary), encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="L2 source lineage does not match canonical L1",
    ):
        load_confirmation_sources(
            l1_dir=l1_dir,
            l2_dir=l2_dir,
            input_snapshot_dir=snapshot_dir,
            basket_name="test-basket",
        )
