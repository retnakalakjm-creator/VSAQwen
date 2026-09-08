from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import pytest

from audit.bool_utils import coerce_bool_series, coerce_bool_value
from audit.candidates import (
    CANDIDATE_OUTCOME_COLUMNS,
    build_candidate_outcome_frame,
    build_candidate_outcome_rows,
)
from audit.calibration import completed_scored_frame, summarize_outcomes
from audit.reports import write_calibration_report_bundle
from audit.run_candidate_audit import build_parser
from audit.runner import run_historical_candidate_audit
from background.qualification import PatternQualification


@dataclass(frozen=True)
class CandidateSnapshot:
    qualification: PatternQualification
    bar_index: int
    week: str
    actionable: object = True
    used_fallback_evidence: object = False
    signal_bar_anomaly: object = False
    target_bar_evidence_codes: tuple[str, ...] = ("stopping_volume",)
    qualifying_evidence_codes: tuple[str, ...] = ("structural_progression_improving",)
    scoring_evidence_codes: tuple[str, ...] = ("stopping_volume",)
    campaign_evidence_codes: tuple[str, ...] = (
        "stopping_volume",
        "structural_progression_improving",
    )

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
                target_bar_evidence_codes=("upthrust",),
                qualifying_evidence_codes=("structural_progression_weakening",),
                scoring_evidence_codes=("upthrust",),
                campaign_evidence_codes=("upthrust",),
            ),
        ]


def _bars() -> pd.DataFrame:
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


def test_coerce_bool_value_handles_csv_roundtrip_strings() -> None:
    assert coerce_bool_value(True) is True
    assert coerce_bool_value(False) is False
    assert coerce_bool_value("True") is True
    assert coerce_bool_value("False") is False
    assert coerce_bool_value("1") is True
    assert coerce_bool_value("0") is False
    assert coerce_bool_value("") is False
    assert coerce_bool_value(None) is False
    assert list(coerce_bool_series(pd.Series(["True", "False", "yes", "no"]))) == [
        True,
        False,
        True,
        False,
    ]


def test_candidate_rows_do_not_treat_string_false_as_truthy() -> None:
    candidate = CandidateSnapshot(
        qualification=PatternQualification.PERSISTENT_BULLISH,
        bar_index=1,
        week="2026-01-05",
        actionable="False",
        used_fallback_evidence="0",
        signal_bar_anomaly="no",
    )

    rows = build_candidate_outcome_rows(_bars(), [candidate], horizons=[1])

    assert len(rows) == 1
    assert rows[0].actionable is False
    assert rows[0].used_fallback_evidence is False
    assert rows[0].signal_bar_anomaly is False


def test_candidate_outcome_frame_preserves_schema_when_empty() -> None:
    frame = build_candidate_outcome_frame(_bars(), [], horizons=[1])

    assert list(frame.columns) == list(CANDIDATE_OUTCOME_COLUMNS)
    assert frame.empty


def test_calibration_filters_and_rates_parse_string_booleans() -> None:
    frame = pd.DataFrame(
        [
            _row("AAA", "True", "True", "True", "False", 0.05),
            _row("BBB", "False", "True", "True", "True", 0.07),
            _row("CCC", "True", "False", "False", "True", 0.09),
        ]
    )

    scored = completed_scored_frame(frame)
    summary = summarize_outcomes(scored, group_by="side")

    assert list(scored["symbol"]) == ["AAA"]
    assert summary.iloc[0]["actionable_rate"] == 1.0
    assert summary.iloc[0]["anomaly_rate"] == 0.0


def test_report_metadata_counts_string_false_as_false(tmp_path) -> None:
    frame = pd.DataFrame(
        [
            _row("AAA", "True", "True", True, False, 0.05),
            _row("BBB", "False", "False", True, False, None),
        ]
    )

    paths = write_calibration_report_bundle(
        frame,
        tmp_path / "reports",
        min_samples=1,
        stability_min_samples=1,
    )
    metadata = pd.read_csv(paths.metadata)
    metadata_values = dict(zip(metadata["metric"], metadata["value"], strict=True))

    assert int(metadata_values["source_rows"]) == 2
    assert int(metadata_values["outcome_available_rows"]) == 1
    assert int(metadata_values["complete_rows"]) == 1


def test_audit_runner_writes_vsa_event_reports_by_default(tmp_path) -> None:
    result = run_historical_candidate_audit(
        ["AAA.NS"],
        horizons=[1],
        output_dir=tmp_path / "calibration",
        report_min_samples=1,
        stability_min_samples=1,
        daily_loader=lambda _symbol: _bars(),
        weekly_transformer=_weekly_transformer,
        metrics_calculator=_metrics_calculator,
        scanner_factory=FakeScanner,
    )

    assert result.report_paths is not None
    assert result.vsa_event_report_paths is not None
    assert result.vsa_event_report_paths.event_summary.exists()
    assert result.vsa_event_report_paths.event_stability.exists()
    assert result.vsa_event_report_paths.event_contracts.exists()
    assert result.vsa_event_report_paths.metadata.exists()
    assert result.summary()["vsa_event_report_paths"] is not None


def test_audit_runner_can_skip_vsa_event_reports(tmp_path) -> None:
    result = run_historical_candidate_audit(
        ["AAA.NS"],
        horizons=[1],
        output_dir=tmp_path / "calibration",
        report_min_samples=1,
        stability_min_samples=1,
        write_vsa_event_reports=False,
        daily_loader=lambda _symbol: _bars(),
        weekly_transformer=_weekly_transformer,
        metrics_calculator=_metrics_calculator,
        scanner_factory=FakeScanner,
    )

    assert result.report_paths is not None
    assert result.vsa_event_report_paths is None
    assert not (tmp_path / "calibration" / "vsa_event_summary.csv").exists()


def test_cli_parser_accepts_vsa_event_report_controls() -> None:
    args = build_parser().parse_args(
        [
            "SRF.NS",
            "--output",
            "reports/calibration/latest",
            "--vsa-event-min-samples",
            "2",
            "--vsa-event-stability-min-samples",
            "3",
            "--no-vsa-event-reports",
        ]
    )

    assert args.output == Path("reports/calibration/latest")
    assert args.vsa_event_min_samples == 2
    assert args.vsa_event_stability_min_samples == 3
    assert args.no_vsa_event_reports is True


def test_vsa_event_report_arguments_are_validated() -> None:
    with pytest.raises(ValueError, match="vsa_event_min_samples"):
        run_historical_candidate_audit(
            ["AAA.NS"],
            vsa_event_min_samples=0,
            daily_loader=lambda _symbol: _bars(),
        )

    with pytest.raises(ValueError, match="vsa_event_stability_min_samples"):
        run_historical_candidate_audit(
            ["AAA.NS"],
            vsa_event_stability_min_samples=0,
            daily_loader=lambda _symbol: _bars(),
        )


def _row(
    symbol: str,
    outcome_available: object,
    complete: object,
    actionable: object,
    signal_bar_anomaly: object,
    favorable_return: float | None,
) -> dict[str, object]:
    return {
        "symbol": symbol,
        "candidate_id": 1,
        "horizon_bars": 1,
        "outcome_available": outcome_available,
        "complete": complete,
        "actionable": actionable,
        "signal_bar_anomaly": signal_bar_anomaly,
        "qualification": "persistent_bullish",
        "side": "long",
        "scoring_evidence_codes": "stopping_volume",
        "target_bar_evidence_codes": "stopping_volume",
        "qualifying_evidence_codes": "structural_progression_improving",
        "campaign_evidence_codes": "stopping_volume",
        "raw_return": favorable_return,
        "favorable_return": favorable_return,
        "mfe": None if favorable_return is None else favorable_return,
        "mae": None if favorable_return is None else -0.01,
    }
