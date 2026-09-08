"""Statistical stability diagnostics for calibration datasets.

This module is analysis-only. It adds confidence intervals and simple stability
labels to candidate outcome datasets so evidence calibration reviews do not
over-read small or noisy samples before proposing production scoring changes.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from math import sqrt
from typing import Any

import pandas as pd

from audit.calibration import completed_scored_frame, explode_evidence_codes

DEFAULT_STABILITY_Z_SCORE = 1.96
DEFAULT_STABILITY_MIN_SAMPLES = 30
DEFAULT_VALUE_COLUMN = "favorable_return"


@dataclass(frozen=True, slots=True)
class StabilitySummaryRow:
    """Confidence-aware return diagnostics for one calibration segment."""

    group_key: str
    horizon_bars: int | None
    side: str | None
    sample_count: int
    symbol_count: int
    positive_count: int
    negative_count: int
    zero_count: int
    win_rate: float
    win_rate_ci_low: float
    win_rate_ci_high: float
    avg_favorable_return: float
    favorable_return_std: float
    favorable_return_sem: float
    favorable_return_ci_low: float
    favorable_return_ci_high: float
    stability_grade: str


def summarize_return_stability(
    frame: pd.DataFrame,
    *,
    group_by: str | Sequence[str],
    value_column: str = DEFAULT_VALUE_COLUMN,
    min_samples: int = 1,
    require_complete: bool = True,
    z_score: float = DEFAULT_STABILITY_Z_SCORE,
) -> pd.DataFrame:
    """Summarize confidence-aware outcome stability by one or more columns."""
    group_columns = _normalize_group_columns(group_by)
    _validate_positive_int("min_samples", min_samples)
    _validate_positive_number("z_score", z_score)
    _require_columns(
        frame,
        [
            *group_columns,
            value_column,
            "outcome_available",
            "complete",
        ],
    )

    scored = completed_scored_frame(frame, require_complete=require_complete)
    if scored.empty:
        return _empty_stability_frame()

    clean = scored.dropna(subset=[value_column]).copy()
    if clean.empty:
        return _empty_stability_frame()

    rows: list[StabilitySummaryRow] = []
    for group_key, group in clean.groupby(group_columns, dropna=False, sort=True):
        sample_count = len(group)
        if sample_count < min_samples:
            continue

        values = group[value_column].astype(float)
        positive_count = int((values > 0.0).sum())
        negative_count = int((values < 0.0).sum())
        zero_count = int((values == 0.0).sum())
        win_rate = positive_count / sample_count
        win_low, win_high = wilson_interval(positive_count, sample_count, z_score=z_score)
        mean = float(values.mean())
        std = 0.0 if sample_count < 2 else float(values.std(ddof=1))
        sem = std / sqrt(sample_count) if sample_count else 0.0
        mean_low = mean - z_score * sem
        mean_high = mean + z_score * sem

        rows.append(
            StabilitySummaryRow(
                group_key=_group_key_text(group_key),
                horizon_bars=_optional_int(_first_group_value(group, "horizon_bars")),
                side=_optional_str(_first_group_value(group, "side")),
                sample_count=sample_count,
                symbol_count=_symbol_count(group),
                positive_count=positive_count,
                negative_count=negative_count,
                zero_count=zero_count,
                win_rate=float(win_rate),
                win_rate_ci_low=float(win_low),
                win_rate_ci_high=float(win_high),
                avg_favorable_return=mean,
                favorable_return_std=std,
                favorable_return_sem=float(sem),
                favorable_return_ci_low=float(mean_low),
                favorable_return_ci_high=float(mean_high),
                stability_grade=_stability_grade(
                    sample_count=sample_count,
                    min_samples=min_samples,
                    win_rate=win_rate,
                    win_rate_ci_low=win_low,
                    win_rate_ci_high=win_high,
                    mean=mean,
                    mean_ci_low=mean_low,
                    mean_ci_high=mean_high,
                ),
            )
        )

    if not rows:
        return _empty_stability_frame()

    summary = pd.DataFrame(asdict(row) for row in rows)
    return summary.sort_values(
        ["stability_grade", "favorable_return_ci_low", "avg_favorable_return", "sample_count"],
        ascending=[True, False, False, False],
        ignore_index=True,
    )


def summarize_evidence_stability(
    frame: pd.DataFrame,
    *,
    evidence_column: str = "scoring_evidence_codes",
    extra_group_by: Iterable[str] = ("horizon_bars", "side"),
    min_samples: int = DEFAULT_STABILITY_MIN_SAMPLES,
    require_complete: bool = True,
    z_score: float = DEFAULT_STABILITY_Z_SCORE,
) -> pd.DataFrame:
    """Summarize stability for each exploded evidence code."""
    scored = completed_scored_frame(frame, require_complete=require_complete)
    exploded = explode_evidence_codes(scored, evidence_column=evidence_column)
    group_by = ["evidence_code", *tuple(extra_group_by)]
    return summarize_return_stability(
        exploded,
        group_by=group_by,
        min_samples=min_samples,
        require_complete=require_complete,
        z_score=z_score,
    )


def add_stability_labels(
    summary: pd.DataFrame,
    *,
    min_samples: int = DEFAULT_STABILITY_MIN_SAMPLES,
) -> pd.DataFrame:
    """Add stability labels to an existing confidence-aware summary frame."""
    _validate_positive_int("min_samples", min_samples)
    _require_columns(
        summary,
        [
            "sample_count",
            "win_rate",
            "win_rate_ci_low",
            "win_rate_ci_high",
            "avg_favorable_return",
            "favorable_return_ci_low",
            "favorable_return_ci_high",
        ],
    )
    labelled = summary.copy()
    labelled["stability_grade"] = labelled.apply(
        lambda row: _stability_grade(
            sample_count=int(row["sample_count"]),
            min_samples=min_samples,
            win_rate=float(row["win_rate"]),
            win_rate_ci_low=float(row["win_rate_ci_low"]),
            win_rate_ci_high=float(row["win_rate_ci_high"]),
            mean=float(row["avg_favorable_return"]),
            mean_ci_low=float(row["favorable_return_ci_low"]),
            mean_ci_high=float(row["favorable_return_ci_high"]),
        ),
        axis=1,
    )
    return labelled


def wilson_interval(
    successes: int,
    total: int,
    *,
    z_score: float = DEFAULT_STABILITY_Z_SCORE,
) -> tuple[float, float]:
    """Return a Wilson score interval for a binomial proportion."""
    _validate_non_negative_int("successes", successes)
    _validate_non_negative_int("total", total)
    _validate_positive_number("z_score", z_score)
    if successes > total:
        raise ValueError("successes cannot exceed total")
    if total == 0:
        return 0.0, 0.0

    proportion = successes / total
    z_squared = z_score * z_score
    denominator = 1.0 + z_squared / total
    center = proportion + z_squared / (2.0 * total)
    margin = z_score * sqrt(
        (proportion * (1.0 - proportion) + z_squared / (4.0 * total)) / total
    )
    low = (center - margin) / denominator
    high = (center + margin) / denominator
    return max(0.0, low), min(1.0, high)


def _stability_grade(
    *,
    sample_count: int,
    min_samples: int,
    win_rate: float,
    win_rate_ci_low: float,
    win_rate_ci_high: float,
    mean: float,
    mean_ci_low: float,
    mean_ci_high: float,
) -> str:
    if sample_count < min_samples:
        return "insufficient_sample"
    if mean_ci_low > 0.0 and win_rate_ci_low > 0.5:
        return "stable_positive"
    if mean_ci_high < 0.0 and win_rate_ci_high < 0.5:
        return "stable_negative"
    if mean > 0.0 and win_rate > 0.5:
        return "directionally_positive"
    if mean < 0.0 and win_rate < 0.5:
        return "directionally_negative"
    return "mixed"


def _normalize_group_columns(group_by: str | Sequence[str]) -> list[str]:
    if isinstance(group_by, str):
        columns = [group_by]
    else:
        columns = list(group_by)
    if not columns:
        raise ValueError("group_by must contain at least one column")
    return columns


def _empty_stability_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=[field for field in StabilitySummaryRow.__dataclass_fields__])


def _require_columns(frame: pd.DataFrame, columns: Iterable[str]) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing required stability columns: {missing}")


def _validate_positive_int(name: str, value: int) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")


def _validate_non_negative_int(name: str, value: int) -> None:
    if value < 0:
        raise ValueError(f"{name} cannot be negative")


def _validate_positive_number(name: str, value: float) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")


def _group_key_text(group_key: Any) -> str:
    if isinstance(group_key, tuple):
        return "|".join(_optional_str(value) or "" for value in group_key)
    return _optional_str(group_key) or ""


def _first_group_value(group: pd.DataFrame, column: str) -> Any:
    if column not in group.columns or group.empty:
        return None
    return group.iloc[0][column]


def _symbol_count(group: pd.DataFrame) -> int:
    if "symbol" not in group.columns:
        return 0
    return int(group["symbol"].dropna().nunique())


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


__all__ = [
    "DEFAULT_STABILITY_MIN_SAMPLES",
    "DEFAULT_STABILITY_Z_SCORE",
    "StabilitySummaryRow",
    "add_stability_labels",
    "summarize_evidence_stability",
    "summarize_return_stability",
    "wilson_interval",
]
