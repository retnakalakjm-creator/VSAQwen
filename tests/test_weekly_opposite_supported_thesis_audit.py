from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from models import EvidenceDirection
from weekly_actionability_counterfactual import (
    WeeklyCounterfactualPartition,
    WeeklyCounterfactualReason,
)
from weekly_audit_input_reproducibility import (
    WeeklyAuditInputFingerprint,
    compare_weekly_audit_inputs,
)
from weekly_contradiction_reason_audit import (
    WeeklyContradictionReasonAuditReport,
    WeeklyContradictionReasonClass,
    WeeklyContradictionReasonObservation,
)
from weekly_opposite_supported_thesis_audit import (
    WeeklyOppositeRegime,
    WeeklyOppositeSupportedThesisAuditEngine,
)
from weekly_replay_comparison import DirectionalForwardOutcome
from weekly_thesis import ShadowWeeklyThesisState


def _outcome(direction: EvidenceDirection, close: float) -> tuple[DirectionalForwardOutcome, ...]:
    return (
        DirectionalForwardOutcome(
            horizon_weeks=5,
            available_weeks=5,
            complete=True,
            direction=direction,
            close_return_pct=close,
            maximum_favorable_excursion_pct=max(close, 1.0),
            maximum_adverse_excursion_pct=min(close, -1.0),
        ),
    )


def _observation(
    *,
    bar_index: int,
    reason: WeeklyContradictionReasonClass,
    close: float,
    episode_id: int,
    episode_start: bool = True,
    symbol: str = "ABC.NS",
    direction: EvidenceDirection = EvidenceDirection.BULLISH,
) -> WeeklyContradictionReasonObservation:
    shadow_direction = (
        EvidenceDirection.BEARISH
        if reason is WeeklyContradictionReasonClass.OPPOSITE_SUPPORTED_THESIS
        else direction
    )
    shadow_state = (
        ShadowWeeklyThesisState.BEARISH_SUPPORTED
        if shadow_direction is EvidenceDirection.BEARISH
        else ShadowWeeklyThesisState.BULLISH_SUPPORTED
    )
    source_reason = (
        WeeklyCounterfactualReason.OPPOSITE_SUPPORTED_THESIS
        if reason is WeeklyContradictionReasonClass.OPPOSITE_SUPPORTED_THESIS
        else WeeklyCounterfactualReason.NONE
    )
    return WeeklyContradictionReasonObservation(
        symbol=symbol,
        week=f"2026-01-{bar_index:02d}",
        bar_index=bar_index,
        partition=WeeklyCounterfactualPartition.IN_SAMPLE,
        legacy_direction=direction,
        shadow_state=shadow_state,
        shadow_direction=shadow_direction,
        reason_class=reason,
        source_reasons=(source_reason,),
        episode_id=episode_id,
        episode_start=episode_start,
        episode_length_so_far=1,
        outcomes=_outcome(direction, close),
    )


def _report(
    observations: tuple[WeeklyContradictionReasonObservation, ...],
) -> WeeklyContradictionReasonAuditReport:
    return WeeklyContradictionReasonAuditReport(
        symbols=tuple(sorted({item.symbol for item in observations})),
        horizons_weeks=(5,),
        observations=observations,
        summaries=(),
        leave_one_symbol_out=(),
    )


def test_exact_regime_matching_is_nearest_and_without_replacement() -> None:
    observations = (
        _observation(
            bar_index=8,
            reason=WeeklyContradictionReasonClass.SAME_DIRECTION_SUPPORTED,
            close=4.0,
            episode_id=1,
        ),
        _observation(
            bar_index=10,
            reason=WeeklyContradictionReasonClass.OPPOSITE_SUPPORTED_THESIS,
            close=-6.0,
            episode_id=2,
        ),
        _observation(
            bar_index=11,
            reason=WeeklyContradictionReasonClass.OPPOSITE_SUPPORTED_THESIS,
            close=-2.0,
            episode_id=3,
        ),
        _observation(
            bar_index=12,
            reason=WeeklyContradictionReasonClass.SHADOW_SUPPORT_MISSING,
            close=2.0,
            episode_id=4,
        ),
        _observation(
            bar_index=13,
            reason=WeeklyContradictionReasonClass.SHADOW_SUPPORT_MISSING,
            close=99.0,
            episode_id=5,
            episode_start=False,
        ),
    )
    regimes = {
        (item.symbol, item.bar_index): WeeklyOppositeRegime("up", "strong", "improving")
        for item in observations
        if item.episode_start
    }

    result = WeeklyOppositeSupportedThesisAuditEngine.audit(
        reason_report=_report(observations),
        regimes=regimes,
    )

    assert len(result.observations) == 4
    assert [(pair.treatment.bar_index, pair.control.bar_index) for pair in result.matched_pairs] == [
        (10, 8),
        (11, 12),
    ]
    assert result.unmatched_treatments == ()

    summary = next(
        item
        for item in result.matched_summaries
        if item.partition is WeeklyCounterfactualPartition.ALL
        and item.horizon_weeks == 5
        and item.legacy_direction is EvidenceDirection.BULLISH
    )
    assert summary.complete_pair_count == 2
    assert summary.mean_paired_close_delta_pct == pytest.approx(-7.0)
    assert summary.symbol_balanced_mean_paired_close_delta_pct == pytest.approx(-7.0)


def test_regime_mismatch_remains_unmatched_without_fallback() -> None:
    treatment = _observation(
        bar_index=10,
        reason=WeeklyContradictionReasonClass.OPPOSITE_SUPPORTED_THESIS,
        close=-5.0,
        episode_id=1,
    )
    control = _observation(
        bar_index=9,
        reason=WeeklyContradictionReasonClass.SAME_DIRECTION_SUPPORTED,
        close=5.0,
        episode_id=2,
    )
    regimes = {
        ("ABC.NS", 10): WeeklyOppositeRegime("up", "strong", "improving"),
        ("ABC.NS", 9): WeeklyOppositeRegime("up", "weak", "improving"),
    }

    result = WeeklyOppositeSupportedThesisAuditEngine.audit(
        reason_report=_report((treatment, control)),
        regimes=regimes,
    )

    assert result.matched_pairs == ()
    assert tuple(item.bar_index for item in result.unmatched_treatments) == (10,)


def test_symbol_balanced_summary_equal_weights_symbols_not_episode_counts() -> None:
    observations = (
        _observation(
            bar_index=10,
            reason=WeeklyContradictionReasonClass.OPPOSITE_SUPPORTED_THESIS,
            close=-10.0,
            episode_id=1,
            symbol="AAA.NS",
        ),
        _observation(
            bar_index=20,
            reason=WeeklyContradictionReasonClass.OPPOSITE_SUPPORTED_THESIS,
            close=-10.0,
            episode_id=2,
            symbol="AAA.NS",
        ),
        _observation(
            bar_index=30,
            reason=WeeklyContradictionReasonClass.OPPOSITE_SUPPORTED_THESIS,
            close=10.0,
            episode_id=3,
            symbol="BBB.NS",
        ),
    )
    regimes = {
        (item.symbol, item.bar_index): WeeklyOppositeRegime("up", "strong", "improving")
        for item in observations
    }

    result = WeeklyOppositeSupportedThesisAuditEngine.audit(
        reason_report=_report(observations),
        regimes=regimes,
    )
    summary = next(
        item
        for item in result.symbol_balanced_summaries
        if item.partition is WeeklyCounterfactualPartition.ALL
        and item.horizon_weeks == 5
        and item.legacy_direction is EvidenceDirection.BULLISH
    )
    assert summary.observation_count == 3
    assert summary.symbol_count == 2
    assert summary.equal_weight_mean_close_return_pct == pytest.approx(0.0)


def test_manifest_loader_and_fingerprint_gate(monkeypatch, tmp_path) -> None:
    import audit.weekly_opposite_supported_thesis_runner as runner

    expected = WeeklyAuditInputFingerprint(
        symbol="ABC.NS",
        version="weekly-ohlcv-v1",
        row_count=3,
        first_week="2026-01-01T00:00:00",
        last_week="2026-01-15T00:00:00",
        sha256="a" * 64,
    )
    manifest = tmp_path / "fingerprints.json"
    manifest.write_text(
        json.dumps({"fingerprints": [dict(
            symbol=expected.symbol,
            version=expected.version,
            row_count=expected.row_count,
            first_week=expected.first_week,
            last_week=expected.last_week,
            sha256=expected.sha256,
            columns=list(expected.columns),
        )]}),
        encoding="utf-8",
    )
    assert runner.load_weekly_input_fingerprint_manifest(manifest) == (expected,)

    changed = WeeklyAuditInputFingerprint(
        symbol="ABC.NS",
        version=expected.version,
        row_count=expected.row_count,
        first_week=expected.first_week,
        last_week=expected.last_week,
        sha256="b" * 64,
    )
    fake = SimpleNamespace(
        input_fingerprints=(changed,),
        foundation=SimpleNamespace(),
    )
    monkeypatch.setattr(
        runner,
        "run_reproducible_weekly_foundation_study",
        lambda *args, **kwargs: fake,
    )
    with pytest.raises(ValueError, match="input fingerprint mismatch"):
        runner.run_reproducible_weekly_opposite_supported_study(
            ("ABC.NS",),
            expected_fingerprints=(expected,),
        )


def test_bundle_writer_keeps_audit_non_actionable(tmp_path) -> None:
    import audit.weekly_opposite_supported_thesis_runner as runner

    treatment = _observation(
        bar_index=10,
        reason=WeeklyContradictionReasonClass.OPPOSITE_SUPPORTED_THESIS,
        close=-4.0,
        episode_id=1,
    )
    control = _observation(
        bar_index=8,
        reason=WeeklyContradictionReasonClass.SAME_DIRECTION_SUPPORTED,
        close=3.0,
        episode_id=2,
    )
    regimes = {
        ("ABC.NS", 10): WeeklyOppositeRegime("up", "strong", "improving"),
        ("ABC.NS", 8): WeeklyOppositeRegime("up", "strong", "improving"),
    }
    report = WeeklyOppositeSupportedThesisAuditEngine.audit(
        reason_report=_report((treatment, control)),
        regimes=regimes,
    )
    fingerprint = WeeklyAuditInputFingerprint(
        symbol="ABC.NS",
        version="weekly-ohlcv-v1",
        row_count=3,
        first_week="2026-01-01T00:00:00",
        last_week="2026-01-15T00:00:00",
        sha256="a" * 64,
    )
    study = runner.ReproducibleWeeklyOppositeSupportedStudy(
        report=report,
        input_fingerprints=(fingerprint,),
        fingerprint_comparison=compare_weekly_audit_inputs(
            (fingerprint,),
            (fingerprint,),
        ),
    )

    paths = runner.write_weekly_opposite_supported_bundle(study, tmp_path)
    payload = json.loads(paths.summary_json.read_text(encoding="utf-8"))
    assert payload["fingerprint_match"] is True
    assert payload["is_actionable"] is False
    assert payload["matched_pairs"] == 1
    assert paths.matched_summaries_csv.exists()
