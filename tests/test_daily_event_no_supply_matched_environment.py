from __future__ import annotations

import pandas as pd
import pytest

import audit.daily_event_no_supply_matched_environment as matched_module
from audit.daily_event_no_supply_forward_outcomes import (
    COHORT_ALTERNATE,
    COHORT_CURRENT,
)
from audit.daily_event_no_supply_matched_environment import (
    NoSupplyMatchedControl,
    NoSupplyMatchedPairOutcome,
    NoSupplyMatchedSourceLineage,
    NoSupplySymbolMatchSummary,
    build_matched_outcome_summaries,
    match_symbol_controls,
)
from audit.daily_event_no_supply_matched_runner import (
    build_matched_checkpoint_signature,
    load_symbol_match_checkpoint,
    write_symbol_match_checkpoint,
)


def _daily(periods: int = 18) -> pd.DataFrame:
    index = pd.bdate_range("2026-01-01", periods=periods)
    close = [100.0 + index_value for index_value in range(periods)]
    return pd.DataFrame(
        {
            "open": [value + 1.0 for value in close],
            "high": [value + 2.0 for value in close],
            "low": [value - 1.0 for value in close],
            "close": close,
            "volume": [1000.0] * periods,
        },
        index=index,
    )


def _target(
    daily: pd.DataFrame,
    *,
    index: int,
    cohort: str,
    direction: str,
) -> dict[str, object]:
    return {
        "symbol": "AAA.NS",
        "bar_index": index,
        "session": daily.index[index].isoformat(),
        "trend_direction": direction,
        "cohort": cohort,
    }


def _lineage() -> NoSupplyMatchedSourceLineage:
    return NoSupplyMatchedSourceLineage(
        l7_audit_id="daily-event-no-supply-forward-outcomes-v1",
        l7_summary_sha256="a" * 64,
        l7_event_outcomes_sha256="b" * 64,
        l7_comparison_sha256="c" * 64,
        l7_data_quality_sha256="d" * 64,
        l6_audit_id="daily-event-no-supply-environment-replay-v1",
        l6_summary_sha256="e" * 64,
        l6_observations_sha256="f" * 64,
        snapshot_audit_id="daily-audit-input-snapshot-v1",
        snapshot_manifest_sha256="1" * 64,
        snapshot_basket_name="basket",
        snapshot_period="max",
        snapshot_cutoff="2026-09-18T00:00:00",
        l5_audit_id="daily-event-detector-correction-design-v1",
        l5_summary_sha256="2" * 64,
        l5_correction_candidates_sha256="3" * 64,
        l3_audit_id="daily-event-confirmation-counterfactual-v1",
        l3_summary_sha256="4" * 64,
        l3_observations_sha256="5" * 64,
        l1_summary_sha256="6" * 64,
        l1_emissions_sha256="7" * 64,
        l2_summary_sha256="8" * 64,
    )


def test_matching_excludes_common_signature_and_matches_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    daily = _daily()
    targets = pd.DataFrame(
        [
            _target(
                daily,
                index=6,
                cohort=COHORT_CURRENT,
                direction="DOWN",
            ),
            _target(
                daily,
                index=11,
                cohort=COHORT_ALTERNATE,
                direction="UP",
            ),
        ]
    )
    common = pd.DataFrame(
        [
            {
                "symbol": "AAA.NS",
                "session": daily.index[5].isoformat(),
                "bar_index": 5,
            },
            {
                "symbol": "AAA.NS",
                "session": daily.index[6].isoformat(),
                "bar_index": 6,
            },
            {
                "symbol": "AAA.NS",
                "session": daily.index[11].isoformat(),
                "bar_index": 11,
            },
        ]
    )

    def fake_direction(prefix: pd.DataFrame) -> str:
        position = len(prefix) - 1
        return "DOWN" if position <= 8 else "UP"

    monkeypatch.setattr(
        matched_module,
        "replay_environment_direction",
        fake_direction,
    )
    controls, unmatched, summary = match_symbol_controls(
        symbol="AAA.NS",
        daily=daily,
        targets=targets,
        common_signature_sessions=common,
        max_match_distance_sessions=5,
        min_target_index=0,
    )

    assert not unmatched
    assert len(controls) == 2

    current = next(
        item for item in controls if item.cohort == COHORT_CURRENT
    )
    assert current.control_bar_index == 7
    assert current.distance_sessions == 1
    assert current.control_trend_direction == "DOWN"

    alternate = next(
        item for item in controls if item.cohort == COHORT_ALTERNATE
    )
    assert alternate.control_bar_index == 10
    assert alternate.distance_sessions == 1
    assert alternate.control_trend_direction == "UP"

    assert summary.matched_target_count == 2
    assert summary.unmatched_target_count == 0
    assert summary.used_control_count == 2


def test_matching_does_not_reuse_control(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    daily = _daily()
    targets = pd.DataFrame(
        [
            _target(
                daily,
                index=6,
                cohort=COHORT_CURRENT,
                direction="DOWN",
            ),
            _target(
                daily,
                index=8,
                cohort=COHORT_CURRENT,
                direction="DOWN",
            ),
        ]
    )
    common = targets.loc[:, ["symbol", "session", "bar_index"]].copy()

    monkeypatch.setattr(
        matched_module,
        "replay_environment_direction",
        lambda prefix: "DOWN",
    )
    controls, unmatched, summary = match_symbol_controls(
        symbol="AAA.NS",
        daily=daily,
        targets=targets,
        common_signature_sessions=common,
        max_match_distance_sessions=3,
        min_target_index=0,
    )

    assert not unmatched
    assert len(controls) == 2
    assert len({item.control_bar_index for item in controls}) == 2
    assert summary.used_control_count == 2


def test_matching_reports_unmatched_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    daily = _daily()
    targets = pd.DataFrame(
        [
            _target(
                daily,
                index=6,
                cohort=COHORT_CURRENT,
                direction="DOWN",
            )
        ]
    )
    common = targets.loc[:, ["symbol", "session", "bar_index"]].copy()
    monkeypatch.setattr(
        matched_module,
        "replay_environment_direction",
        lambda prefix: "UP",
    )

    controls, unmatched, summary = match_symbol_controls(
        symbol="AAA.NS",
        daily=daily,
        targets=targets,
        common_signature_sessions=common,
        max_match_distance_sessions=2,
        min_target_index=0,
    )

    assert not controls
    assert len(unmatched) == 1
    assert unmatched[0].reason == (
        "NO_SAME_ENVIRONMENT_CONTROL_WITHIN_DISTANCE"
    )
    assert summary.matched_target_count == 0
    assert summary.unmatched_target_count == 1


def _pair(
    *,
    cohort: str,
    symbol: str,
    target_return: float,
    control_return: float,
    target_positive: bool,
    control_positive: bool,
    clean: bool = True,
) -> NoSupplyMatchedPairOutcome:
    return NoSupplyMatchedPairOutcome(
        symbol=symbol,
        cohort=cohort,
        trend_direction=(
            "DOWN" if cohort == COHORT_CURRENT else "UP"
        ),
        target_session="2026-01-05T00:00:00",
        target_bar_index=2,
        control_session="2026-01-02T00:00:00",
        control_bar_index=1,
        distance_sessions=1,
        horizon_sessions=5,
        target_horizon_session="2026-01-12T00:00:00",
        control_horizon_session="2026-01-09T00:00:00",
        target_forward_return_pct=target_return,
        control_forward_return_pct=control_return,
        paired_return_delta_pct=target_return - control_return,
        target_positive_close=target_positive,
        control_positive_close=control_positive,
        target_mfe_pct=max(target_return, 0.0) + 1.0,
        control_mfe_pct=max(control_return, 0.0) + 1.0,
        paired_mfe_delta_pct=target_return - control_return,
        target_mae_pct=min(target_return, 0.0) - 1.0,
        control_mae_pct=min(control_return, 0.0) - 1.0,
        paired_mae_delta_pct=target_return - control_return,
        target_price_discontinuity=not clean,
        control_price_discontinuity=False,
        clean_pair=clean,
        control_max_single_session_price_move_pct=5.0,
    )


def test_matched_summary_uses_paired_and_symbol_normalized_deltas() -> None:
    outcomes = (
        _pair(
            cohort=COHORT_CURRENT,
            symbol="AAA.NS",
            target_return=4.0,
            control_return=1.0,
            target_positive=True,
            control_positive=True,
        ),
        _pair(
            cohort=COHORT_CURRENT,
            symbol="AAA.NS",
            target_return=6.0,
            control_return=1.0,
            target_positive=True,
            control_positive=True,
        ),
        _pair(
            cohort=COHORT_CURRENT,
            symbol="BBB.NS",
            target_return=-2.0,
            control_return=0.0,
            target_positive=False,
            control_positive=False,
        ),
        _pair(
            cohort=COHORT_ALTERNATE,
            symbol="AAA.NS",
            target_return=2.0,
            control_return=1.0,
            target_positive=True,
            control_positive=True,
        ),
        _pair(
            cohort=COHORT_ALTERNATE,
            symbol="BBB.NS",
            target_return=3.0,
            control_return=1.0,
            target_positive=True,
            control_positive=True,
        ),
    )

    summaries, symbols = build_matched_outcome_summaries(
        outcomes,
        horizons=(5,),
    )

    assert len(summaries) == 2
    assert len(symbols) == 4
    current = next(
        item for item in summaries if item.cohort == COHORT_CURRENT
    )
    assert current.clean_pair_count == 3
    assert current.clean_mean_paired_return_delta_pct == pytest.approx(
        2.0
    )
    # AAA mean pair delta = 4, BBB = -2; equal-symbol mean = 1.
    assert (
        current.clean_symbol_normalized_return_delta_pct
        == pytest.approx(1.0)
    )


def test_checkpoint_round_trip_and_signature_guard(tmp_path) -> None:
    lineage = _lineage()
    signature = build_matched_checkpoint_signature(
        source_lineage=lineage,
        max_match_distance_sessions=60,
        min_target_index=23,
    )
    control = NoSupplyMatchedControl(
        symbol="AAA.NS",
        cohort=COHORT_CURRENT,
        trend_direction="DOWN",
        target_session="2026-01-05T00:00:00",
        target_bar_index=2,
        control_session="2026-01-02T00:00:00",
        control_bar_index=1,
        distance_sessions=1,
        control_trend_direction="DOWN",
        candidate_environment_replay_count=1,
    )
    summary = NoSupplySymbolMatchSummary(
        symbol="AAA.NS",
        source_target_count=1,
        matched_target_count=1,
        unmatched_target_count=0,
        candidate_environment_replay_count=1,
        environment_cache_hit_count=0,
        used_control_count=1,
    )
    write_symbol_match_checkpoint(
        checkpoint_dir=tmp_path,
        signature=signature,
        symbol="AAA.NS",
        controls=(control,),
        unmatched_targets=(),
        symbol_summary=summary,
    )

    loaded = load_symbol_match_checkpoint(
        checkpoint_dir=tmp_path,
        signature=signature,
        symbol="AAA.NS",
    )
    assert loaded == ((control,), (), summary)
    assert (
        load_symbol_match_checkpoint(
            checkpoint_dir=tmp_path,
            signature="stale",
            symbol="AAA.NS",
        )
        is None
    )
