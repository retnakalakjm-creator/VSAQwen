"""Calibration proposal helpers for Milestone 4 strategy review.

This module converts Milestone 3 calibration summaries into reviewable proposal
rows. It is deliberately analysis-only: it does not write production config,
change evidence weights, change thresholds, or alter scanner decisions.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_PROPOSAL_FILENAME = "calibration_proposals.csv"
DEFAULT_PROPOSAL_METADATA_FILENAME = "calibration_proposal_metadata.csv"
POSITIVE_STABILITY_GRADES = frozenset({"stable_positive", "directionally_positive"})
NEGATIVE_STABILITY_GRADES = frozenset({"stable_negative", "directionally_negative"})
INSUFFICIENT_STABILITY_GRADES = frozenset({"insufficient_sample", ""})


@dataclass(frozen=True, slots=True)
class CalibrationProposalCriteria:
    """Thresholds used to turn summary rows into review proposals."""

    min_samples: int = 30
    min_symbols: int = 5
    min_win_rate: float = 0.52
    max_negative_win_rate: float = 0.48
    min_avg_favorable_return: float = 0.0
    max_negative_avg_favorable_return: float = 0.0
    max_anomaly_rate: float = 0.25
    require_stability: bool = True


@dataclass(frozen=True, slots=True)
class CalibrationProposalRow:
    """One reviewable calibration proposal for an evidence/event group."""

    proposal_id: int
    source: str
    group_key: str
    proposed_action: str
    priority: str
    confidence: str
    rationale: str
    sample_count: int
    symbol_count: int
    horizon_bars: int | None
    side: str | None
    win_rate: float | None
    avg_favorable_return: float | None
    total_favorable_return: float | None
    anomaly_rate: float | None
    stability_grade: str | None = None
    favorable_return_ci_low: float | None = None
    favorable_return_ci_high: float | None = None


@dataclass(frozen=True, slots=True)
class CalibrationProposalPaths:
    """Paths written by :func:`write_calibration_proposal_bundle`."""

    output_dir: Path
    proposals: Path
    metadata: Path

    def as_dict(self) -> dict[str, str]:
        """Return string paths for logging and CLI summaries."""
        return {key: str(value) for key, value in asdict(self).items()}


def build_calibration_proposals(
    summary: pd.DataFrame,
    *,
    stability: pd.DataFrame | None = None,
    criteria: CalibrationProposalCriteria | None = None,
    source: str = "evidence_summary",
) -> pd.DataFrame:
    """Build reviewable strategy-improvement proposals from summary rows.

    The output is a proposal table only. Production scoring changes must be made
    in a later, explicit PR after a human reviews the supporting data.
    """
    effective_criteria = criteria or CalibrationProposalCriteria()
    _validate_criteria(effective_criteria)
    _require_columns(
        summary,
        (
            "group_key",
            "sample_count",
            "symbol_count",
            "horizon_bars",
            "side",
            "win_rate",
            "avg_favorable_return",
            "total_favorable_return",
            "anomaly_rate",
        ),
    )

    stability_by_group = _stability_by_group(stability)
    rows: list[CalibrationProposalRow] = []
    for row in summary.to_dict(orient="records"):
        rows.append(
            _proposal_for_row(
                len(rows),
                row,
                stability_by_group.get(str(row.get("group_key", ""))),
                criteria=effective_criteria,
                source=source,
            )
        )

    if not rows:
        return _empty_proposal_frame()

    return pd.DataFrame(asdict(row) for row in rows).sort_values(
        ["priority", "confidence", "sample_count", "avg_favorable_return"],
        ascending=[True, True, False, False],
        ignore_index=True,
    )


def actionable_proposals(proposals: pd.DataFrame) -> pd.DataFrame:
    """Return proposal rows that merit human review for possible production PRs."""
    _require_columns(proposals, ("proposed_action",))
    if proposals.empty:
        return proposals.copy()
    mask = ~proposals["proposed_action"].isin({"keep_current", "collect_more_data"})
    return proposals.loc[mask].reset_index(drop=True)


def write_calibration_proposal_bundle(
    summary: pd.DataFrame,
    output_dir: str | Path,
    *,
    stability: pd.DataFrame | None = None,
    criteria: CalibrationProposalCriteria | None = None,
    source: str = "evidence_summary",
) -> CalibrationProposalPaths:
    """Write calibration proposal and metadata CSV files."""
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    proposals = build_calibration_proposals(
        summary,
        stability=stability,
        criteria=criteria,
        source=source,
    )
    paths = CalibrationProposalPaths(
        output_dir=destination,
        proposals=destination / DEFAULT_PROPOSAL_FILENAME,
        metadata=destination / DEFAULT_PROPOSAL_METADATA_FILENAME,
    )
    proposals.to_csv(paths.proposals, index=False)
    _metadata_frame(
        summary,
        proposals,
        stability=stability,
        criteria=criteria or CalibrationProposalCriteria(),
        source=source,
    ).to_csv(paths.metadata, index=False)
    return paths


def _proposal_for_row(
    proposal_id: int,
    row: dict[str, Any],
    stability_row: dict[str, Any] | None,
    *,
    criteria: CalibrationProposalCriteria,
    source: str,
) -> CalibrationProposalRow:
    sample_count = _int_value(row.get("sample_count"))
    symbol_count = _int_value(row.get("symbol_count"))
    win_rate = _optional_float(row.get("win_rate"))
    avg_return = _optional_float(row.get("avg_favorable_return"))
    total_return = _optional_float(row.get("total_favorable_return"))
    anomaly_rate = _optional_float(row.get("anomaly_rate"))
    stability_grade = _optional_str(None if stability_row is None else stability_row.get("stability_grade"))
    ci_low = _optional_float(None if stability_row is None else stability_row.get("favorable_return_ci_low"))
    ci_high = _optional_float(None if stability_row is None else stability_row.get("favorable_return_ci_high"))

    action, priority, confidence, rationale = _classify_proposal(
        sample_count=sample_count,
        symbol_count=symbol_count,
        win_rate=win_rate,
        avg_return=avg_return,
        anomaly_rate=anomaly_rate,
        stability_grade=stability_grade,
        criteria=criteria,
    )

    return CalibrationProposalRow(
        proposal_id=proposal_id,
        source=source,
        group_key=str(row.get("group_key", "")),
        proposed_action=action,
        priority=priority,
        confidence=confidence,
        rationale=rationale,
        sample_count=sample_count,
        symbol_count=symbol_count,
        horizon_bars=_optional_int(row.get("horizon_bars")),
        side=_optional_str(row.get("side")),
        win_rate=win_rate,
        avg_favorable_return=avg_return,
        total_favorable_return=total_return,
        anomaly_rate=anomaly_rate,
        stability_grade=stability_grade,
        favorable_return_ci_low=ci_low,
        favorable_return_ci_high=ci_high,
    )


def _classify_proposal(
    *,
    sample_count: int,
    symbol_count: int,
    win_rate: float | None,
    avg_return: float | None,
    anomaly_rate: float | None,
    stability_grade: str | None,
    criteria: CalibrationProposalCriteria,
) -> tuple[str, str, str, str]:
    if sample_count < criteria.min_samples or symbol_count < criteria.min_symbols:
        return (
            "collect_more_data",
            "P3",
            "low",
            "Sample or symbol coverage is below the Milestone 4 review gate.",
        )
    if anomaly_rate is not None and anomaly_rate > criteria.max_anomaly_rate:
        return (
            "collect_more_data",
            "P3",
            "low",
            "Anomaly rate is above the configured review gate.",
        )

    stable_positive = stability_grade in POSITIVE_STABILITY_GRADES
    stable_negative = stability_grade in NEGATIVE_STABILITY_GRADES
    stability_missing = stability_grade is None or stability_grade in INSUFFICIENT_STABILITY_GRADES

    if criteria.require_stability and stability_missing:
        return (
            "collect_more_data",
            "P3",
            "low",
            "Stability evidence is missing or insufficient.",
        )

    positive = (
        avg_return is not None
        and win_rate is not None
        and avg_return > criteria.min_avg_favorable_return
        and win_rate >= criteria.min_win_rate
    )
    negative = (
        avg_return is not None
        and win_rate is not None
        and avg_return < criteria.max_negative_avg_favorable_return
        and win_rate <= criteria.max_negative_win_rate
    )

    if positive and (stable_positive or not criteria.require_stability):
        return (
            "review_for_weight_increase",
            "P1",
            "high" if stable_positive else "medium",
            "Group has positive return, acceptable win rate, and supportive stability evidence.",
        )
    if negative and (stable_negative or not criteria.require_stability):
        return (
            "review_for_weight_decrease",
            "P1",
            "high" if stable_negative else "medium",
            "Group has negative return, weak win rate, and adverse stability evidence.",
        )
    if negative:
        return (
            "review_for_monitoring",
            "P2",
            "medium",
            "Group is weak, but stability evidence is not strong enough for a direct weight proposal.",
        )
    return (
        "keep_current",
        "P4",
        "medium",
        "Group passed coverage gates but does not justify a production calibration proposal.",
    )


def _stability_by_group(stability: pd.DataFrame | None) -> dict[str, dict[str, Any]]:
    if stability is None or stability.empty:
        return {}
    _require_columns(stability, ("group_key", "stability_grade"))
    return {
        str(row.get("group_key", "")): row
        for row in stability.to_dict(orient="records")
    }


def _metadata_frame(
    summary: pd.DataFrame,
    proposals: pd.DataFrame,
    *,
    stability: pd.DataFrame | None,
    criteria: CalibrationProposalCriteria,
    source: str,
) -> pd.DataFrame:
    rows: list[tuple[str, object]] = [
        ("source", source),
        ("summary_rows", len(summary)),
        ("stability_rows", 0 if stability is None else len(stability)),
        ("proposal_rows", len(proposals)),
        ("actionable_proposal_rows", len(actionable_proposals(proposals))),
    ]
    rows.extend((f"criteria_{key}", value) for key, value in asdict(criteria).items())
    return pd.DataFrame(rows, columns=["metric", "value"])


def _validate_criteria(criteria: CalibrationProposalCriteria) -> None:
    if criteria.min_samples <= 0:
        raise ValueError("min_samples must be greater than zero")
    if criteria.min_symbols <= 0:
        raise ValueError("min_symbols must be greater than zero")
    if not 0.0 <= criteria.min_win_rate <= 1.0:
        raise ValueError("min_win_rate must be between 0 and 1")
    if not 0.0 <= criteria.max_negative_win_rate <= 1.0:
        raise ValueError("max_negative_win_rate must be between 0 and 1")
    if not 0.0 <= criteria.max_anomaly_rate <= 1.0:
        raise ValueError("max_anomaly_rate must be between 0 and 1")


def _require_columns(frame: pd.DataFrame, columns: tuple[str, ...]) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing required proposal columns: {missing}")


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return float(value)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return int(value)


def _int_value(value: Any) -> int:
    optional = _optional_int(value)
    return 0 if optional is None else optional


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return str(value)


def _empty_proposal_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=[field.name for field in CalibrationProposalRow.__dataclass_fields__.values()])


__all__ = [
    "CalibrationProposalCriteria",
    "CalibrationProposalPaths",
    "CalibrationProposalRow",
    "actionable_proposals",
    "build_calibration_proposals",
    "write_calibration_proposal_bundle",
]
