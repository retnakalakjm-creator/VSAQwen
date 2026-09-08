"""Report export helpers for Milestone 3 calibration reviews.

This module is analysis-only. It turns candidate outcome datasets into a small
bundle of CSV reports that can be reviewed before proposing production scoring
changes.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from audit.bool_utils import coerce_bool_series
from audit.calibration import (
    rank_calibration_summary,
    summarize_evidence_outcomes,
    summarize_qualification_outcomes,
)
from audit.stability import (
    DEFAULT_STABILITY_MIN_SAMPLES,
    DEFAULT_STABILITY_Z_SCORE,
    summarize_evidence_stability,
)


DEFAULT_REPORT_TOP_N = 25
POSITIVE_STABILITY_GRADES = ("stable_positive", "directionally_positive")
NEGATIVE_STABILITY_GRADES = ("stable_negative", "directionally_negative")


@dataclass(frozen=True, slots=True)
class CalibrationReportPaths:
    """Paths written by :func:`write_calibration_report_bundle`."""

    output_dir: Path
    evidence_summary: Path
    qualification_summary: Path
    top_positive_evidence: Path
    bottom_negative_evidence: Path
    metadata: Path
    evidence_stability: Path | None = None
    top_stable_positive_evidence: Path | None = None
    top_stable_negative_evidence: Path | None = None

    def as_dict(self) -> dict[str, str | None]:
        """Return string paths for logging, JSON, or test assertions."""
        return {
            key: None if value is None else str(value)
            for key, value in asdict(self).items()
        }


def build_calibration_report_tables(
    frame: pd.DataFrame,
    *,
    min_samples: int = 30,
    top_n: int = DEFAULT_REPORT_TOP_N,
    evidence_column: str = "scoring_evidence_codes",
    require_complete: bool = True,
    include_stability: bool = True,
    stability_min_samples: int | None = None,
    stability_z_score: float = DEFAULT_STABILITY_Z_SCORE,
) -> dict[str, pd.DataFrame]:
    """Build the standard calibration report table bundle.

    The returned tables are deterministic and CSV-ready. They do not mutate the
    source frame and they do not alter production evidence weights.
    """
    _validate_report_arguments(
        min_samples=min_samples,
        top_n=top_n,
        stability_min_samples=stability_min_samples,
        stability_z_score=stability_z_score,
    )

    evidence_summary = summarize_evidence_outcomes(
        frame,
        evidence_column=evidence_column,
        min_samples=min_samples,
        require_complete=require_complete,
    )
    qualification_summary = summarize_qualification_outcomes(
        frame,
        min_samples=min_samples,
        require_complete=require_complete,
    )

    top_positive = rank_calibration_summary(
        evidence_summary,
        min_samples=min_samples,
        ascending=False,
    ).head(top_n)
    bottom_negative = rank_calibration_summary(
        evidence_summary,
        min_samples=min_samples,
        ascending=True,
    ).head(top_n)

    tables = {
        "evidence_summary": evidence_summary,
        "qualification_summary": qualification_summary,
        "top_positive_evidence": top_positive.reset_index(drop=True),
        "bottom_negative_evidence": bottom_negative.reset_index(drop=True),
    }

    if include_stability:
        effective_stability_min_samples = _effective_stability_min_samples(
            stability_min_samples
        )
        evidence_stability = summarize_evidence_stability(
            frame,
            evidence_column=evidence_column,
            min_samples=effective_stability_min_samples,
            require_complete=require_complete,
            z_score=stability_z_score,
        )
        tables["evidence_stability"] = evidence_stability
        tables["top_stable_positive_evidence"] = _rank_stability_table(
            evidence_stability,
            grades=POSITIVE_STABILITY_GRADES,
            top_n=top_n,
            ascending=False,
        )
        tables["top_stable_negative_evidence"] = _rank_stability_table(
            evidence_stability,
            grades=NEGATIVE_STABILITY_GRADES,
            top_n=top_n,
            ascending=True,
        )

    return tables


def write_calibration_report_bundle(
    frame: pd.DataFrame,
    output_dir: str | Path,
    *,
    min_samples: int = 30,
    top_n: int = DEFAULT_REPORT_TOP_N,
    evidence_column: str = "scoring_evidence_codes",
    require_complete: bool = True,
    include_stability: bool = True,
    stability_min_samples: int | None = None,
    stability_z_score: float = DEFAULT_STABILITY_Z_SCORE,
) -> CalibrationReportPaths:
    """Write the standard calibration report CSV bundle.

    Files written:

    - ``evidence_summary.csv``
    - ``qualification_summary.csv``
    - ``top_positive_evidence.csv``
    - ``bottom_negative_evidence.csv``
    - ``metadata.csv``

    When ``include_stability`` is true, the bundle also includes:

    - ``evidence_stability.csv``
    - ``top_stable_positive_evidence.csv``
    - ``top_stable_negative_evidence.csv``
    """
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)

    tables = build_calibration_report_tables(
        frame,
        min_samples=min_samples,
        top_n=top_n,
        evidence_column=evidence_column,
        require_complete=require_complete,
        include_stability=include_stability,
        stability_min_samples=stability_min_samples,
        stability_z_score=stability_z_score,
    )

    paths = CalibrationReportPaths(
        output_dir=destination,
        evidence_summary=destination / "evidence_summary.csv",
        qualification_summary=destination / "qualification_summary.csv",
        top_positive_evidence=destination / "top_positive_evidence.csv",
        bottom_negative_evidence=destination / "bottom_negative_evidence.csv",
        metadata=destination / "metadata.csv",
        evidence_stability=(
            destination / "evidence_stability.csv" if include_stability else None
        ),
        top_stable_positive_evidence=(
            destination / "top_stable_positive_evidence.csv"
            if include_stability
            else None
        ),
        top_stable_negative_evidence=(
            destination / "top_stable_negative_evidence.csv"
            if include_stability
            else None
        ),
    )

    tables["evidence_summary"].to_csv(paths.evidence_summary, index=False)
    tables["qualification_summary"].to_csv(paths.qualification_summary, index=False)
    tables["top_positive_evidence"].to_csv(paths.top_positive_evidence, index=False)
    tables["bottom_negative_evidence"].to_csv(paths.bottom_negative_evidence, index=False)

    if include_stability:
        assert paths.evidence_stability is not None
        assert paths.top_stable_positive_evidence is not None
        assert paths.top_stable_negative_evidence is not None
        tables["evidence_stability"].to_csv(paths.evidence_stability, index=False)
        tables["top_stable_positive_evidence"].to_csv(
            paths.top_stable_positive_evidence,
            index=False,
        )
        tables["top_stable_negative_evidence"].to_csv(
            paths.top_stable_negative_evidence,
            index=False,
        )

    _metadata_frame(
        frame,
        tables=tables,
        min_samples=min_samples,
        top_n=top_n,
        evidence_column=evidence_column,
        require_complete=require_complete,
        include_stability=include_stability,
        stability_min_samples=stability_min_samples,
        stability_z_score=stability_z_score,
    ).to_csv(paths.metadata, index=False)

    return paths


def _rank_stability_table(
    evidence_stability: pd.DataFrame,
    *,
    grades: Iterable[str],
    top_n: int,
    ascending: bool,
) -> pd.DataFrame:
    if evidence_stability.empty:
        return evidence_stability.copy()

    grade_set = set(grades)
    ranked = evidence_stability[
        evidence_stability["stability_grade"].isin(grade_set)
    ].copy()
    if ranked.empty:
        return ranked.reset_index(drop=True)

    return ranked.sort_values(
        ["favorable_return_ci_low", "avg_favorable_return", "sample_count"],
        ascending=[ascending, ascending, False],
        ignore_index=True,
    ).head(top_n)


def _metadata_frame(
    frame: pd.DataFrame,
    *,
    tables: dict[str, pd.DataFrame],
    min_samples: int,
    top_n: int,
    evidence_column: str,
    require_complete: bool,
    include_stability: bool,
    stability_min_samples: int | None,
    stability_z_score: float,
) -> pd.DataFrame:
    scored_rows = _safe_bool_count(frame, "outcome_available")
    complete_rows = _safe_bool_count(frame, "complete")
    rows = [
        ("source_rows", len(frame)),
        ("outcome_available_rows", scored_rows),
        ("complete_rows", complete_rows),
        ("min_samples", min_samples),
        ("top_n", top_n),
        ("evidence_column", evidence_column),
        ("require_complete", require_complete),
        ("include_stability", include_stability),
        ("stability_min_samples", _effective_stability_min_samples(stability_min_samples)),
        ("stability_z_score", stability_z_score),
    ]
    rows.extend((f"{name}_rows", len(table)) for name, table in tables.items())
    return pd.DataFrame(rows, columns=["metric", "value"])


def _effective_stability_min_samples(stability_min_samples: int | None) -> int:
    return (
        DEFAULT_STABILITY_MIN_SAMPLES
        if stability_min_samples is None
        else stability_min_samples
    )


def _validate_report_arguments(
    *,
    min_samples: int,
    top_n: int,
    stability_min_samples: int | None,
    stability_z_score: float,
) -> None:
    if min_samples <= 0:
        raise ValueError("min_samples must be greater than zero")
    if top_n <= 0:
        raise ValueError("top_n must be greater than zero")
    if stability_min_samples is not None and stability_min_samples <= 0:
        raise ValueError("stability_min_samples must be greater than zero")
    if stability_z_score <= 0:
        raise ValueError("stability_z_score must be greater than zero")


def _safe_bool_count(frame: pd.DataFrame, column: str) -> int:
    if column not in frame.columns:
        return 0
    return int(coerce_bool_series(frame[column]).sum())


__all__ = [
    "CalibrationReportPaths",
    "DEFAULT_REPORT_TOP_N",
    "NEGATIVE_STABILITY_GRADES",
    "POSITIVE_STABILITY_GRADES",
    "build_calibration_report_tables",
    "write_calibration_report_bundle",
]
