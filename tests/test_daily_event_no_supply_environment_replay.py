from __future__ import annotations

import pandas as pd

from audit.daily_event_no_supply_environment_replay import (
    NoSupplyEnvironmentObservation,
    NoSupplyEnvironmentSourceLineage,
    NoSupplySymbolReplaySummary,
    build_no_supply_environment_replay_audit,
    is_raw_bearish_target,
)
from audit.daily_event_no_supply_environment_runner import (
    build_no_supply_checkpoint_signature,
    load_no_supply_symbol_checkpoint,
    replay_progress_manifest_path,
    select_symbol_shard,
    write_no_supply_symbol_checkpoint,
)
from engine.columns import COL_CLOSE, COL_OPEN


def _lineage() -> NoSupplyEnvironmentSourceLineage:
    return NoSupplyEnvironmentSourceLineage(
        l5_audit_id="daily-event-detector-correction-design-v1",
        l5_summary_sha256="a" * 64,
        l5_correction_candidates_sha256="b" * 64,
        l3_audit_id="daily-event-confirmation-counterfactual-v1",
        l3_summary_sha256="c" * 64,
        l3_observations_sha256="d" * 64,
        snapshot_audit_id="daily-audit-input-snapshot-v1",
        snapshot_manifest_sha256="e" * 64,
        snapshot_basket_name="basket",
        snapshot_period="max",
        snapshot_cutoff="2026-09-18T00:00:00",
        l1_summary_sha256="f" * 64,
        l1_emissions_sha256="1" * 64,
        l2_summary_sha256="2" * 64,
    )


def _observation(
    *,
    symbol: str,
    bar_index: int,
    session: str,
    current: bool,
    alternate: bool,
) -> NoSupplyEnvironmentObservation:
    return NoSupplyEnvironmentObservation(
        symbol=symbol,
        bar_index=bar_index,
        session=session,
        trend_direction=(
            "DOWN" if current else "UP" if alternate else "RANGE"
        ),
        current_bearish_environment=current,
        alternate_bullish_environment=alternate,
        current_candidate=current,
        alternate_candidate=alternate,
        confirmation_count=3,
        passed_confirmation_count=1,
        passed_confirmations=("Weak Spread",),
        failed_confirmations=(
            "Volume Decreasing",
            "Weak Selling Result",
        ),
    )


def test_raw_bearish_prefilter_matches_direction_definition() -> None:
    assert is_raw_bearish_target(
        pd.Series({COL_OPEN: 10.0, COL_CLOSE: 9.0})
    )
    assert not is_raw_bearish_target(
        pd.Series({COL_OPEN: 10.0, COL_CLOSE: 10.0})
    )
    assert not is_raw_bearish_target(
        pd.Series({COL_OPEN: 10.0, COL_CLOSE: 11.0})
    )


def test_build_audit_requires_exact_current_parity() -> None:
    baseline = pd.DataFrame(
        [
            {
                "symbol": "AAA.NS",
                "bar_index": 20,
                "session": "2026-01-20T00:00:00",
                "code": "no_supply",
            },
            {
                "symbol": "BBB.NS",
                "bar_index": 30,
                "session": "2026-02-20T00:00:00",
                "code": "no_supply",
            },
        ]
    )
    observations = (
        _observation(
            symbol="AAA.NS",
            bar_index=20,
            session="2026-01-20T00:00:00",
            current=True,
            alternate=False,
        ),
        _observation(
            symbol="AAA.NS",
            bar_index=25,
            session="2026-01-25T00:00:00",
            current=False,
            alternate=True,
        ),
        _observation(
            symbol="AAA.NS",
            bar_index=26,
            session="2026-01-26T00:00:00",
            current=False,
            alternate=False,
        ),
        _observation(
            symbol="BBB.NS",
            bar_index=30,
            session="2026-02-20T00:00:00",
            current=True,
            alternate=False,
        ),
        _observation(
            symbol="BBB.NS",
            bar_index=35,
            session="2026-02-25T00:00:00",
            current=False,
            alternate=True,
        ),
    )
    symbol_rows = (
        NoSupplySymbolReplaySummary(
            symbol="AAA.NS",
            evaluated_target_count=50,
            replayed_bearish_target_count=25,
            skipped_non_bearish_target_count=25,
            common_signature_count=3,
            current_candidate_count=1,
            alternate_candidate_count=1,
            neither_environment_count=1,
        ),
        NoSupplySymbolReplaySummary(
            symbol="BBB.NS",
            evaluated_target_count=40,
            replayed_bearish_target_count=20,
            skipped_non_bearish_target_count=20,
            common_signature_count=2,
            current_candidate_count=1,
            alternate_candidate_count=1,
            neither_environment_count=0,
        ),
    )

    audit = build_no_supply_environment_replay_audit(
        source_lineage=_lineage(),
        requested_symbols=("AAA.NS", "BBB.NS"),
        baseline_current=baseline,
        observations=observations,
        symbol_rows=symbol_rows,
        snapshot_worker_count=2,
    )

    assert audit.current_baseline_event_count == 2
    assert audit.current_replay_event_count == 2
    assert audit.alternate_replay_event_count == 2
    assert audit.current_identity_mismatch_count == 0
    assert audit.current_bar_index_mismatch_count == 0
    assert audit.current_alternate_overlap_count == 0
    assert audit.current_only_count == 2
    assert audit.alternate_only_count == 2
    assert audit.neither_environment_count == 1
    assert audit.evaluated_target_count == 90
    assert audit.replayed_bearish_target_count == 45
    assert audit.skipped_non_bearish_target_count == 45


def test_build_audit_surfaces_identity_and_index_drift() -> None:
    baseline = pd.DataFrame(
        [
            {
                "symbol": "AAA.NS",
                "bar_index": 20,
                "session": "2026-01-20T00:00:00",
                "code": "no_supply",
            },
            {
                "symbol": "AAA.NS",
                "bar_index": 30,
                "session": "2026-01-30T00:00:00",
                "code": "no_supply",
            },
        ]
    )
    observations = (
        _observation(
            symbol="AAA.NS",
            bar_index=21,
            session="2026-01-20T00:00:00",
            current=True,
            alternate=False,
        ),
        _observation(
            symbol="AAA.NS",
            bar_index=40,
            session="2026-02-10T00:00:00",
            current=True,
            alternate=False,
        ),
    )
    symbol_rows = (
        NoSupplySymbolReplaySummary(
            symbol="AAA.NS",
            evaluated_target_count=50,
            replayed_bearish_target_count=25,
            skipped_non_bearish_target_count=25,
            common_signature_count=2,
            current_candidate_count=2,
            alternate_candidate_count=0,
            neither_environment_count=0,
        ),
    )

    audit = build_no_supply_environment_replay_audit(
        source_lineage=_lineage(),
        requested_symbols=("AAA.NS",),
        baseline_current=baseline,
        observations=observations,
        symbol_rows=symbol_rows,
    )

    assert audit.current_identity_mismatch_count == 2
    assert {
        item.side for item in audit.identity_mismatches
    } == {"MISSING_FROM_REPLAY", "EXTRA_IN_REPLAY"}
    assert audit.current_bar_index_mismatch_count == 1
    drift = audit.bar_index_drifts[0]
    assert drift.baseline_bar_index == 20
    assert drift.replay_bar_index == 21
    assert drift.index_delta == 1


def test_build_audit_counts_overlap_if_context_is_inconsistent() -> None:
    baseline = pd.DataFrame(
        [
            {
                "symbol": "AAA.NS",
                "bar_index": 20,
                "session": "2026-01-20T00:00:00",
                "code": "no_supply",
            }
        ]
    )
    observations = (
        _observation(
            symbol="AAA.NS",
            bar_index=20,
            session="2026-01-20T00:00:00",
            current=True,
            alternate=True,
        ),
    )
    symbol_rows = (
        NoSupplySymbolReplaySummary(
            symbol="AAA.NS",
            evaluated_target_count=1,
            replayed_bearish_target_count=1,
            skipped_non_bearish_target_count=0,
            common_signature_count=1,
            current_candidate_count=1,
            alternate_candidate_count=1,
            neither_environment_count=0,
        ),
    )

    audit = build_no_supply_environment_replay_audit(
        source_lineage=_lineage(),
        requested_symbols=("AAA.NS",),
        baseline_current=baseline,
        observations=observations,
        symbol_rows=symbol_rows,
    )

    assert audit.current_alternate_overlap_count == 1
    assert audit.current_only_count == 0
    assert audit.alternate_only_count == 0


def test_checkpoint_round_trip_requires_exact_signature(tmp_path) -> None:
    lineage = _lineage()
    signature = build_no_supply_checkpoint_signature(
        source_lineage=lineage,
        now="2026-09-18T16:00:00+05:30",
        min_target_index=20,
    )
    observation = _observation(
        symbol="AAA.NS",
        bar_index=20,
        session="2026-01-20T00:00:00",
        current=True,
        alternate=False,
    )
    summary = NoSupplySymbolReplaySummary(
        symbol="AAA.NS",
        evaluated_target_count=10,
        replayed_bearish_target_count=6,
        skipped_non_bearish_target_count=4,
        common_signature_count=1,
        current_candidate_count=1,
        alternate_candidate_count=0,
        neither_environment_count=0,
    )

    path = write_no_supply_symbol_checkpoint(
        checkpoint_dir=tmp_path,
        checkpoint_signature=signature,
        symbol="AAA.NS",
        observations=(observation,),
        symbol_summary=summary,
    )
    assert path.exists()

    loaded = load_no_supply_symbol_checkpoint(
        checkpoint_dir=tmp_path,
        checkpoint_signature=signature,
        symbol="AAA.NS",
    )
    assert loaded == ((observation,), summary)

    stale = load_no_supply_symbol_checkpoint(
        checkpoint_dir=tmp_path,
        checkpoint_signature="different-signature",
        symbol="AAA.NS",
    )
    assert stale is None


def test_checkpoint_signature_changes_with_replay_inputs() -> None:
    lineage = _lineage()
    base = build_no_supply_checkpoint_signature(
        source_lineage=lineage,
        now="2026-09-18T16:00:00+05:30",
        min_target_index=20,
    )
    different_now = build_no_supply_checkpoint_signature(
        source_lineage=lineage,
        now="2026-09-19T16:00:00+05:30",
        min_target_index=20,
    )
    different_start = build_no_supply_checkpoint_signature(
        source_lineage=lineage,
        now="2026-09-18T16:00:00+05:30",
        min_target_index=21,
    )

    assert base != different_now
    assert base != different_start


def test_symbol_sharding_is_deterministic_and_complete() -> None:
    symbols = (
        "A.NS",
        "B.NS",
        "C.NS",
        "D.NS",
        "E.NS",
        "F.NS",
    )
    shard_zero = select_symbol_shard(
        symbols,
        shard_index=0,
        shard_count=2,
    )
    shard_one = select_symbol_shard(
        symbols,
        shard_index=1,
        shard_count=2,
    )

    assert shard_zero == ("A.NS", "C.NS", "E.NS")
    assert shard_one == ("B.NS", "D.NS", "F.NS")
    assert set(shard_zero).isdisjoint(shard_one)
    assert set(shard_zero) | set(shard_one) == set(symbols)


def test_progress_manifest_path_is_selection_specific(tmp_path) -> None:
    first = replay_progress_manifest_path(
        tmp_path,
        ("A.NS", "B.NS"),
    )
    same = replay_progress_manifest_path(
        tmp_path,
        ("A.NS", "B.NS"),
    )
    other = replay_progress_manifest_path(
        tmp_path,
        ("B.NS", "A.NS"),
    )

    assert first == same
    assert first != other
    assert first.parent == tmp_path / "progress"
