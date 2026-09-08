"""Calibration summaries for candidate outcome datasets.

This module is analysis-only. It summarizes rows produced by
:mod:`audit.candidates` so evidence rules can be reviewed with outcome data
before any production scoring changes are proposed.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd

from audit.bool_utils import coerce_bool_series


DEFAULT_OUTCOME_FILTER_COLUMNS = ("outcome_available", "complete")
DEFAULT_VALUE_COLUMN = "favorable_return"


@dataclass(frozen=True, slots=True)
class CalibrationSummaryRow:
    """Grouped outcome statistics for one calibration segment."""

    group_key: str
    horizon_bars: int | None
    side: str | None
    sample_count: int
    symbol_count: int
    actionable_rate: float
    anomaly_rate: float
    win_rate: float
    avg_favorable_return: float
    median_favorable_return: float
    avg_raw_return: float
    avg_mfe: float
    avg_mae: float
    total_favorable_return: float


def completed_scored_frame(
    frame: pd.DataFrame,
    *,
    require_complete: bool = True,
    require_outcome: bool = True,
) -> pd.DataFrame:
    """Return rows that are safe for production calibration summaries.

    By default, calibration uses rows with an available outcome and a completed
    horizon. Callers may relax either condition for exploratory diagnostics, but
    those reports should be labelled clearly.
    """
    _require_columns(frame, DEFAULT_OUTCOME_FILTER_COLUMNS)

    mask = pd.Series(True, index=frame.index)
    if require_outcome:
        mask &= coerce_bool_series(frame["outcome_available"])
    if require_complete:
        mask &= coerce_bool_series(frame["complete"])
    return frame.loc[mask].copy()


def explode_evidence_codes(
    frame: pd.DataFrame,
    *,
    evidence_column: str = "scoring_evidence_codes",
    output_column: str = "evidence_code",
    drop_empty: bool = True,
) -> pd.DataFrame:
    """Explode pipe-delimited evidence-code columns into one row per code."""
    _require_columns(frame, (evidence_column,))
    exploded = frame.copy()
    exploded[output_column] = exploded[evidence_column].map(_split_codes)
    exploded = exploded.explode(output_column, ignore_index=True)
    if drop_empty:
        exploded = exploded[exploded[output_column].notna() & (exploded[output_column] != "")]
    return exploded.reset_index(drop=True)


def summarize_outcomes(
    frame: pd.DataFrame,
    *,
    group_by: str | Sequence[str],
    value_column: str = DEFAULT_VALUE_COLUMN,
    min_samples: int = 1,
) -> pd.DataFrame:
    """Summarize completed candidate outcomes by one or more columns."""
    group_columns = _normalize_group_columns(group_by)
    required = [
        *group_columns,
        value_column,
        "raw_return",
        "mfe",
        "mae",
        "actionable",
        "signal_bar_anomaly",
    ]
    _require_columns(frame, required)
    if min_samples <= 0:
        raise ValueError("min_samples must be greater than zero")

    if frame.empty:
        return _empty_summary_frame()

    clean = frame.dropna(subset=[value_column]).copy()
    if clean.empty:
        return _empty_summary_frame()

    rows: list[CalibrationSummaryRow] = []
    dropna = False
    for group_key, group in clean.groupby(group_columns, dropna=dropna, sort=True):
        sample_count = len(group)
        if sample_count < min_samples:
            continue
        values = group[value_column].astype(float)
        rows.append(
            CalibrationSummaryRow(
                group_key=_group_key_text(group_key),
                horizon_bars=_optional_int(_first_group_value(group, "horizon_bars")),
                side=_optional_str(_first_group_value(group, "side")),
                sample_count=sample_count,
                symbol_count=_symbol_count(group),
                actionable_rate=float(coerce_bool_series(group["actionable"]).mean()),
                anomaly_rate=float(
                    coerce_bool_series(group["signal_bar_anomaly"]).mean()
                ),
                win_rate=float((values > 0.0).mean()),
                avg_favorable_return=float(values.mean()),
                median_favorable_return=float(values.median()),
                avg_raw_return=_mean_or_zero(group, "raw_return"),
                avg_mfe=_mean_or_zero(group, "mfe"),
                avg_mae=_mean_or_zero(group, "mae"),
                total_favorable_return=float(values.sum()),
            )
        )

    if not rows:
        return _empty_summary_frame()

    summary = pd.DataFrame(asdict(row) for row in rows)
    return summary.sort_values(
        ["avg_favorable_return", "win_rate", "sample_count"],
        ascending=[False, False, False],
        ignore_index=True,
    )


def summarize_evidence_outcomes(
    frame: pd.DataFrame,
    *,
    evidence_column: str = "scoring_evidence_codes",
    extra_group_by: Iterable[str] = ("horizon_bars", "side"),
    min_samples: int = 1,
    require_complete: bool = True,
) -> pd.DataFrame:
    """Summarize outcome value for each evidence code.

    The default path filters to completed scored rows, explodes the requested
    evidence-code column, and groups by evidence code, horizon, and side.
    """
    scored = completed_scored_frame(frame, require_complete=require_complete)
    exploded = explode_evidence_codes(scored, evidence_column=evidence_column)
    group_by = ["evidence_code", *tuple(extra_group_by)]
    return summarize_outcomes(exploded, group_by=group_by, min_samples=min_samples)


def summarize_qualification_outcomes(
    frame: pd.DataFrame,
    *,
    min_samples: int = 1,
    require_complete: bool = True,
) -> pd.DataFrame:
    """Summarize outcome value by qualification, horizon, and side."""
    scored = completed_scored_frame(frame, require_complete=require_complete)
    return summarize_outcomes(
        scored,
        group_by=("qualification", "horizon_bars", "side"),
        min_samples=min_samples,
    )


def rank_calibration_summary(
    summary: pd.DataFrame,
    *,
    min_samples: int = 1,
    ascending: bool = False,
) -> pd.DataFrame:
    """Rank calibration summary rows by average favorable return."""
    _require_columns(summary, ("sample_count", "avg_favorable_return", "win_rate"))
    if min_samples <= 0:
        raise ValueError("min_samples must be greater than zero")
    ranked = summary[summary["sample_count"] >= min_samples].copy()
    return ranked.sort_values(
        ["avg_favorable_return", "win_rate", "sample_count"],
        ascending=[ascending, ascending, not ascending],
        ignore_index=True,
    )


def _normalize_group_columns(group_by: str | Sequence[str]) -> list[str]:
    if isinstance(group_by, str):
        columns = [group_by]
    else:
        columns = list(group_by)
    if not columns:
        raise ValueError("group_by must contain at least one column")
    return columns


def _require_columns(frame: pd.DataFrame, columns: Iterable[str]) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing required calibration columns: {missing}")


def _split_codes(value: Any) -> list[str]:
    if value is None:
        return []
    try:
        if pd.isna(value):
            return []
    except (TypeError, ValueError):
        pass
    if isinstance(value, str):
        return [part.strip() for part in value.split("|") if part.strip()]
    return [str(part).strip() for part in value if str(part).strip()]


def _group_key_text(group_key: Any) -> str:
    if isinstance(group_key, tuple):
        return "|".join(_optional_str(value) or "" for value in group_key)
    return _optional_str(group_key) or ""


def _first_group_value(group: pd.DataFrame, column: str) -> Any:
    if column not in group.columns or group.empty:
        return None
    return group.iloc[0][column]


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return int(value)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return str(value)


def _symbol_count(group: pd.DataFrame) -> int:
    if "symbol" not in group.columns:
        return 0
    return int(group["symbol"].dropna().nunique())


def _mean_or_zero(group: pd.DataFrame, column: str) -> float:
    if column not in group.columns:
        return 0.0
    values = group[column].dropna()
    if values.empty:
        return 0.0
    return float(values.astype(float).mean())


def _empty_summary_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "group_key",
            "horizon_bars",
            "side",
            "sample_count",
            "symbol_count",
            "actionable_rate",
            "anomaly_rate",
            "win_rate",
            "avg_favorable_return",
            "median_favorable_return",
            "avg_raw_return",
            "avg_mfe",
            "avg_mae",
            "total_favorable_return",
        ]
    )


__all__ = [
    "CalibrationSummaryRow",
    "completed_scored_frame",
    "explode_evidence_codes",
    "rank_calibration_summary",
    "summarize_evidence_outcomes",
    "summarize_outcomes",
    "summarize_qualification_outcomes",
]
