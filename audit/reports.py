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

from audit.calibration import (
    rank_calibration_summary,
    summarize_evidence_outcomes,
    summarize_qualification_outcomes,
)


DEFAULT_REPORT_TOP_N = 25


@dataclass(frozen=True, slots=True)
class CalibrationReportPaths:
    """Paths written by :func:`write_calibration_report_bundle`."""

    output_dir: Path
    evidence_summary: Path
    qualification_summary: Path
    top_positive_evidence: Path
    bottom_negative_evidence: Path
    metadata: Path

    def as_dict(self) -> dict[str, str]:
        """Return string paths for logging, JSON, or test assertions."""
        return {key: str(value) for key, value in asdict(self).items()}


def build_calibration_report_tables(
    frame: pd.DataFrame,
    *,
    min_samples: int = 30,
    top_n: int = DEFAULT_REPORT_TOP_N,
    evidence_column: str = "scoring_evidence_codes",
    require_complete: bool = True,
) -> dict[str, pd.DataFrame]:
    """Build the standard calibration report table bundle.

    The returned tables are deterministic and CSV-ready. They do not mutate the
    source frame and they do not alter production evidence weights.
    """
    if min_samples <= 0:
        raise ValueError("min_samples must be greater than zero")
    if top_n <= 0:
        raise ValueError("top_n must be greater than zero")

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

    return {
        "evidence_summary": evidence_summary,
        "qualification_summary": qualification_summary,
        "top_positive_evidence": top_positive.reset_index(drop=True),
        "bottom_negative_evidence": bottom_negative.reset_index(drop=True),
    }


def write_calibration_report_bundle(
    frame: pd.DataFrame,
    output_dir: str | Path,
    *,
    min_samples: int = 30,
    top_n: int = DEFAULT_REPORT_TOP_N,
    evidence_column: str = "scoring_evidence_codes",
    require_complete: bool = True,
) -> CalibrationReportPaths:
    """Write the standard calibration report CSV bundle.

    Files written:

    - ``evidence_summary.csv``
    - ``qualification_summary.csv``
    - ``top_positive_evidence.csv``
    - ``bottom_negative_evidence.csv``
    - ``metadata.csv``
    """
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)

    tables = build_calibration_report_tables(
        frame,
        min_samples=min_samples,
        top_n=top_n,
        evidence_column=evidence_column,
        require_complete=require_complete,
    )

    paths = CalibrationReportPaths(
        output_dir=destination,
        evidence_summary=destination / "evidence_summary.csv",
        qualification_summary=destination / "qualification_summary.csv",
        top_positive_evidence=destination / "top_positive_evidence.csv",
        bottom_negative_evidence=destination / "bottom_negative_evidence.csv",
        metadata=destination / "metadata.csv",
    )

    tables["evidence_summary"].to_csv(paths.evidence_summary, index=False)
    tables["qualification_summary"].to_csv(paths.qualification_summary, index=False)
    tables["top_positive_evidence"].to_csv(paths.top_positive_evidence, index=False)
    tables["bottom_negative_evidence"].to_csv(paths.bottom_negative_evidence, index=False)
    _metadata_frame(
        frame,
        tables=tables,
        min_samples=min_samples,
        top_n=top_n,
        evidence_column=evidence_column,
        require_complete=require_complete,
    ).to_csv(paths.metadata, index=False)

    return paths


def _metadata_frame(
    frame: pd.DataFrame,
    *,
    tables: dict[str, pd.DataFrame],
    min_samples: int,
    top_n: int,
    evidence_column: str,
    require_complete: bool,
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
    ]
    rows.extend((f"{name}_rows", len(table)) for name, table in tables.items())
    return pd.DataFrame(rows, columns=["metric", "value"])


def _safe_bool_count(frame: pd.DataFrame, column: str) -> int:
    if column not in frame.columns:
        return 0
    return int(frame[column].fillna(False).astype(bool).sum())


__all__ = [
    "CalibrationReportPaths",
    "DEFAULT_REPORT_TOP_N",
    "build_calibration_report_tables",
    "write_calibration_report_bundle",
]
