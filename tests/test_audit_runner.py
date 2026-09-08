from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from audit.run_candidate_audit import build_parser
from audit.runner import (
    CANDIDATE_OUTCOME_COLUMNS,
    DEFAULT_DATASET_FILENAME,
    run_historical_candidate_audit,
    run_symbol_candidate_audit,
)
from background.qualification import PatternQualification


@dataclass(frozen=True)
class CandidateSnapshot:
    qualification: PatternQualification
    bar_index: int
    week: str
    symbol: str | None = None
    actionable: bool = True
    confidence: float = 0.7
    net_strength: float = 1.1
    net_pressure: float = 0.9
    scoring_bar_index: int | None = 1
    scoring_evidence_age: int | None = 0
    used_fallback_evidence: bool = False
    signal_bar_anomaly: bool = False
    signal_bar_anomaly_reason: str | None = None
    reason: str = "synthetic candidate"
    target_bar_evidence_codes: tuple[str, ...] = ("stopping_volume",)
    qualifying_evidence_codes: tuple[str, ...] = ("structural_progression_improving",)
    scoring_evidence_codes: tuple[str, ...] = ("stopping_volume",)
    campaign_evidence_codes: tuple[str, ...] = ("stopping_volume", "structural_progression_improving")

    @property
    def signal_bar_index(self) -> int:
        return self.bar_index

    @property
    def signal_week(self) -> str:
        return self.week

    @property
    def execution_bar_index(self) -> int | None:
        next_index = self.bar_index + 1
        return next_index if next_index < 5 else None

    @property
    def execution_week(self) -> str | None:
        return f"week-{self.execution_bar_index}" if self.execution_bar_index is not None else None


class FakeScanner:
    def scan(self, metrics: pd.DataFrame) -> list[CandidateSnapshot]:
        return [
            CandidateSnapshot(
                qualification=PatternQualification.PERSISTENT_BULLISH,
                bar_index=1,
                week="2026-01-05",
            ),
            CandidateSnapshot(
                qualification=PatternQualification.PERSISTENT_BEARISH,
                bar_index=2,
                week="2026-01-12",
                net_pressure=-0.8,
                target_bar_evidence_codes=("upthrust",),
                qualifying_evidence_codes=("structural_progression_weakening",),
                scoring_evidence_codes=("upthrust",),
                campaign_evidence_codes=("upthrust", "structural_progression_weakening"),
            ),
        ]


class EmptyScanner:
    def scan(self, metrics: pd.DataFrame) -> list[CandidateSnapshot]:
        return []


def _daily_loader(symbol: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": [100.0, 101.0, 102.0, 103.0, 104.0],
            "high": [101.0, 106.0, 112.0, 111.0, 122.0],
            "low": [99.0, 100.0, 101.0, 102.0, 103.0],
            "close": [100.0, 105.0, 110.0, 108.0, 120.0],
            "volume": [1000, 1100, 1200, 1300, 1400],
        },
        index=pd.date_range("2026-01-01", periods=5, freq="D"),
    )


def _weekly_transformer(daily: pd.DataFrame) -> pd.DataFrame:
    return daily.reset_index(drop=True)


def _metrics_calculator(weekly: pd.DataFrame) -> pd.DataFrame:
    return weekly.copy()


def test_run_symbol_candidate_audit_builds_outcome_frame() -> None:
    result = run_symbol_candidate_audit(
        "srf.ns",
        horizons=[1, 2],
        daily_loader=_daily_loader,
        weekly_transformer=_weekly_transformer,
        metrics_calculator=_metrics_calculator,
        scanner_factory=FakeScanner,
    )

    assert result.symbol == "SRF.NS"
    assert result.daily_bars == 5
    assert result.weekly_bars == 5
    assert result.metric_bars == 5
    assert result.candidate_count == 2
    assert result.outcome_rows == 4
    assert list(result.frame["symbol"].unique()) == ["SRF.NS"]
    assert list(result.frame["candidate_id"].unique()) == [0, 1]
    assert set(result.frame["side"]) == {"long", "short"}


def test_run_historical_candidate_audit_writes_dataset_and_reports(tmp_path) -> None:
    result = run_historical_candidate_audit(
        ["AAA.NS", "BBB.NS"],
        horizons=[1],
        output_dir=tmp_path / "calibration",
        report_min_samples=1,
        stability_min_samples=1,
        daily_loader=_daily_loader,
        weekly_transformer=_weekly_transformer,
        metrics_calculator=_metrics_calculator,
        scanner_factory=FakeScanner,
    )

    assert result.symbols == ("AAA.NS", "BBB.NS")
    assert result.candidate_count == 4
    assert result.outcome_rows == 4
    assert result.dataset_path == tmp_path / "calibration" / DEFAULT_DATASET_FILENAME
    assert result.dataset_path.exists()
    assert result.report_paths is not None
    assert result.report_paths.evidence_summary.exists()
    assert result.report_paths.evidence_stability is not None
    assert result.report_paths.evidence_stability.exists()
    assert result.report_paths.metadata.exists()

    dataset = pd.read_csv(result.dataset_path)
    assert len(dataset) == 4
    assert set(dataset["symbol"]) == {"AAA.NS", "BBB.NS"}


def test_run_historical_candidate_audit_can_skip_stability_reports(tmp_path) -> None:
    result = run_historical_candidate_audit(
        ["AAA.NS"],
        horizons=[1],
        output_dir=tmp_path / "calibration",
        report_min_samples=1,
        include_stability_reports=False,
        daily_loader=_daily_loader,
        weekly_transformer=_weekly_transformer,
        metrics_calculator=_metrics_calculator,
        scanner_factory=FakeScanner,
    )

    assert result.report_paths is not None
    assert result.report_paths.evidence_stability is None
    assert result.report_paths.top_stable_positive_evidence is None
    assert result.report_paths.top_stable_negative_evidence is None


def test_run_historical_candidate_audit_preserves_empty_schema(tmp_path) -> None:
    result = run_historical_candidate_audit(
        ["EMPTY.NS"],
        horizons=[1],
        output_dir=tmp_path / "calibration",
        report_min_samples=1,
        stability_min_samples=1,
        daily_loader=_daily_loader,
        weekly_transformer=_weekly_transformer,
        metrics_calculator=_metrics_calculator,
        scanner_factory=EmptyScanner,
    )

    assert result.candidate_count == 0
    assert result.outcome_rows == 0
    assert list(result.frame.columns) == list(CANDIDATE_OUTCOME_COLUMNS)
    assert result.dataset_path is not None
    assert result.dataset_path.exists()
    assert result.report_paths is not None
    assert result.report_paths.evidence_summary.exists()
    assert result.report_paths.evidence_stability is not None
    assert result.report_paths.evidence_stability.exists()

    dataset = pd.read_csv(result.dataset_path)
    assert list(dataset.columns) == list(CANDIDATE_OUTCOME_COLUMNS)
    assert dataset.empty


def test_run_historical_candidate_audit_can_skip_writes(tmp_path) -> None:
    result = run_historical_candidate_audit(
        ["AAA.NS"],
        horizons=[1],
        output_dir=tmp_path / "calibration",
        write_dataset=False,
        write_reports=False,
        daily_loader=_daily_loader,
        weekly_transformer=_weekly_transformer,
        metrics_calculator=_metrics_calculator,
        scanner_factory=FakeScanner,
    )

    assert result.dataset_path is None
    assert result.report_paths is None
    assert not (tmp_path / "calibration").exists()


def test_runner_validates_symbols_and_horizons() -> None:
    try:
        run_historical_candidate_audit([], daily_loader=_daily_loader)
    except ValueError as exc:
        assert "symbols" in str(exc)
    else:
        raise AssertionError("empty symbols should fail")

    try:
        run_historical_candidate_audit(["AAA.NS", "aaa.ns"], daily_loader=_daily_loader)
    except ValueError as exc:
        assert "unique" in str(exc)
    else:
        raise AssertionError("duplicate normalized symbols should fail")

    try:
        run_historical_candidate_audit(["AAA.NS"], horizons=[1, 1], daily_loader=_daily_loader)
    except ValueError as exc:
        assert "unique" in str(exc)
    else:
        raise AssertionError("duplicate horizons should fail")

    try:
        run_historical_candidate_audit(["AAA.NS"], horizons=[0], daily_loader=_daily_loader)
    except ValueError as exc:
        assert "greater than zero" in str(exc)
    else:
        raise AssertionError("zero horizon should fail")

    try:
        run_historical_candidate_audit(["AAA.NS"], stability_min_samples=0, daily_loader=_daily_loader)
    except ValueError as exc:
        assert "stability_min_samples" in str(exc)
    else:
        raise AssertionError("zero stability_min_samples should fail")


def test_cli_parser_accepts_expected_arguments() -> None:
    args = build_parser().parse_args(
        [
            "SRF.NS",
            "RELIANCE.NS",
            "--horizons",
            "1",
            "4",
            "8",
            "--output",
            "reports/calibration/test",
            "--min-samples",
            "5",
            "--stability-min-samples",
            "7",
            "--stability-z-score",
            "1.64",
            "--top-n",
            "10",
            "--drop-unscored",
            "--no-stability-reports",
        ]
    )

    assert args.symbols == ["SRF.NS", "RELIANCE.NS"]
    assert args.horizons == [1, 4, 8]
    assert args.output == Path("reports/calibration/test")
    assert args.min_samples == 5
    assert args.stability_min_samples == 7
    assert args.stability_z_score == 1.64
    assert args.top_n == 10
    assert args.drop_unscored is True
    assert args.no_stability_reports is True
