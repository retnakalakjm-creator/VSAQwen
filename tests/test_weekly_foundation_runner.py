from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from audit.weekly_foundation_runner import (
    build_weekly_foundation_symbol_study_from_metrics,
    run_weekly_foundation_historical_study,
    write_weekly_foundation_study_bundle,
)
from background.qualification import PatternQualification, PatternQualificationResult
from engine.columns import COL_CLOSE, COL_HIGH, COL_LOW, COL_WEEK
from model.evidence_result_model import EvidenceResult
from model.score_model import ProfessionalScore, ProfessionalScoreResult
from models import (
    Evidence,
    EvidenceCategory,
    EvidenceCode,
    EvidenceDirection,
    StructuralPattern,
    TrendDirection,
    TrendState,
)
from scanner import ScannerCandidate
from weekly_evidence_promotion_audit import WeeklyEvidenceAuditPartition
from weekly_replay_comparison import WeeklyReplayBucket


def _metrics(rows: int = 26, *, price_offset: float = 0.0) -> pd.DataFrame:
    weeks = pd.date_range("2026-01-02", periods=rows, freq="7D")
    closes = [100.0 + price_offset + index for index in range(rows)]
    return pd.DataFrame(
        {
            COL_WEEK: [item.strftime("%Y-%m-%d") for item in weeks],
            COL_HIGH: [value + 2.0 for value in closes],
            COL_LOW: [value - 2.0 for value in closes],
            COL_CLOSE: closes,
        }
    )


def _candidate(metrics: pd.DataFrame, bar_index: int) -> ScannerCandidate:
    week = str(metrics.iloc[bar_index][COL_WEEK])
    demand = Evidence(
        code=EvidenceCode.DEMAND_COMING_IN,
        category=EvidenceCategory.DEMAND,
        direction=EvidenceDirection.BULLISH,
        strength=0.8,
        weight=1.0,
        observation="demand coming in",
        description="weekly foundation runner fixture",
        bar_index=bar_index,
        week_beginning=week,
    )
    context = SimpleNamespace(
        trend=SimpleNamespace(
            direction=TrendDirection.UP,
            state=TrendState.HEALTHY,
        ),
        structural_pattern=StructuralPattern.IMPROVING,
        structural_swings=(),
    )
    evidence = EvidenceResult(context=context, evidence=(demand,))  # type: ignore[arg-type]
    scores = ProfessionalScore(
        trend=0.7,
        supply=0.2,
        demand=0.8,
        effort=0.6,
        strength=0.8,
        weakness=0.2,
        confidence=0.8,
    )
    professional = ProfessionalScoreResult(scores=scores, evidence=(demand,))
    qualification = PatternQualificationResult(
        qualification=PatternQualification.UNQUALIFIED,
        is_actionable_evidence=False,
        reason="fixture remains legacy-unqualified",
    )
    return ScannerCandidate(
        evidence=evidence,
        professional=professional,
        qualification_result=qualification,
        target_bar_evidence=(demand,),
        campaign_evidence=(demand,),
        qualifying_evidence=(),
        scoring_evidence=(),
        scoring_bar_index=None,
        scoring_evidence_age=None,
        bar_index=bar_index,
        week=week,
    )


class _Scanner:
    def scan_to_indices(
        self,
        metrics: pd.DataFrame,
        target_indices: tuple[int, ...],
    ) -> dict[int, ScannerCandidate]:
        return {
            index: _candidate(metrics, index)
            for index in target_indices
        }


def _scanner_factory() -> _Scanner:
    return _Scanner()


def test_symbol_study_materializes_wf1_to_wf5_without_production_authority() -> None:
    study = build_weekly_foundation_symbol_study_from_metrics(
        symbol="test.ns",
        metrics=_metrics(),
        horizons_weeks=(1, 2),
        scanner_factory=_scanner_factory,
    )

    assert study.symbol == "TEST.NS"
    assert study.audited_bars == 6
    assert len(study.audits) == len(study.prices) == len(study.replay.records) == 6
    assert study.out_of_sample_start_bar_index is None

    first = study.replay.records[0]
    assert first.legacy_actionable is False
    assert first.shadow_supported is True
    assert first.bucket is WeeklyReplayBucket.LEGACY_NO_SHADOW_YES
    assert study.replay.is_actionable is False


def test_caller_defined_oos_week_resolves_to_first_audited_bar_on_or_after_date() -> None:
    metrics = _metrics()
    split_week = str(metrics.iloc[23][COL_WEEK])

    study = build_weekly_foundation_symbol_study_from_metrics(
        symbol="TEST.NS",
        metrics=metrics,
        horizons_weeks=(1,),
        out_of_sample_start_week=split_week,
        scanner_factory=_scanner_factory,
    )

    assert study.out_of_sample_start_bar_index == 23
    assert study.evidence_promotion_input.out_of_sample_start_bar_index == 23

    with pytest.raises(ValueError, match="after the available audited history"):
        build_weekly_foundation_symbol_study_from_metrics(
            symbol="TEST.NS",
            metrics=metrics,
            horizons_weeks=(1,),
            out_of_sample_start_week="2030-01-01",
            scanner_factory=_scanner_factory,
        )


def test_multi_symbol_study_feeds_wf6_and_keeps_split_visible() -> None:
    frames = {
        "AAA.NS": _metrics(price_offset=0.0),
        "BBB.NS": _metrics(price_offset=50.0),
    }

    def daily_loader(symbol: str) -> pd.DataFrame:
        return frames[symbol].copy()

    result = run_weekly_foundation_historical_study(
        ("AAA.NS", "BBB.NS"),
        horizons_weeks=(1, 2),
        location_distance_thresholds_pct=(0.5, 1.0),
        out_of_sample_start_week=str(frames["AAA.NS"].iloc[23][COL_WEEK]),
        daily_loader=daily_loader,
        weekly_transformer=lambda frame: frame,
        metrics_calculator=lambda frame: frame,
        scanner_factory=_scanner_factory,
    )

    assert result.symbols == ("AAA.NS", "BBB.NS")
    assert result.is_actionable is False
    assert result.evidence_promotion.is_actionable is False
    assert result.audited_bars == 12
    assert result.location_distance_thresholds_pct == (0.5, 1.0)
    assert result.evidence_promotion.symbols == ("AAA.NS", "BBB.NS")
    assert result.evidence_promotion.observations
    assert result.evidence_promotion.summaries
    assert result.evidence_promotion.leave_one_symbol_out

    partitions = {item.partition for item in result.evidence_promotion.observations}
    assert WeeklyEvidenceAuditPartition.IN_SAMPLE in partitions
    assert WeeklyEvidenceAuditPartition.OUT_OF_SAMPLE in partitions

    summary = result.summary()
    assert summary["is_actionable"] is False
    assert summary["replay_bucket_counts"][WeeklyReplayBucket.LEGACY_NO_SHADOW_YES.value] == 12


def test_bundle_writer_exports_reviewable_json_and_csv_artifacts(tmp_path) -> None:
    frames = {
        "AAA.NS": _metrics(price_offset=0.0),
        "BBB.NS": _metrics(price_offset=25.0),
    }

    result = run_weekly_foundation_historical_study(
        tuple(frames),
        horizons_weeks=(1,),
        daily_loader=lambda symbol: frames[symbol].copy(),
        weekly_transformer=lambda frame: frame,
        metrics_calculator=lambda frame: frame,
        scanner_factory=_scanner_factory,
    )

    paths = write_weekly_foundation_study_bundle(result, tmp_path)

    for path in paths.as_dict().values():
        assert Path(path).exists()

    replay = pd.read_csv(paths.replay_records_csv)
    observations = pd.read_csv(paths.promotion_observations_csv)
    summaries = pd.read_csv(paths.promotion_summaries_csv)

    assert set(replay["symbol"]) == {"AAA.NS", "BBB.NS"}
    assert not observations.empty
    assert not summaries.empty


def test_runner_rejects_incomplete_scanner_replay_and_invalid_inputs() -> None:
    class MissingScanner:
        def scan_to_indices(self, metrics, target_indices):
            return {}

    with pytest.raises(ValueError, match="every requested replay bar"):
        build_weekly_foundation_symbol_study_from_metrics(
            symbol="TEST.NS",
            metrics=_metrics(),
            horizons_weeks=(1,),
            scanner_factory=MissingScanner,
        )

    with pytest.raises(ValueError, match="positive week counts"):
        build_weekly_foundation_symbol_study_from_metrics(
            symbol="TEST.NS",
            metrics=_metrics(),
            horizons_weeks=(0,),
            scanner_factory=_scanner_factory,
        )
