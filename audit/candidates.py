"""Candidate-level outcome dataset builders for scanner calibration.

This module converts point-in-time scanner candidates into flat, analysis-ready
rows and attaches next-bar-execution forward outcomes from :mod:`audit.outcomes`.
It is intentionally analysis-only: production scanner paths should not import it
to decide actionability, ranking, qualification, or evidence weights.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd

from audit.outcomes import (
    ForwardOutcome,
    OutcomeSide,
    compute_forward_outcome,
    normalize_outcome_side,
)
from background.qualification import PatternQualification


CandidateSideResolver = Callable[[Any], OutcomeSide | int | str]


@dataclass(frozen=True, slots=True)
class CandidateOutcomeRow:
    """Flat candidate observation joined to one forward-outcome horizon."""

    candidate_id: int
    horizon_bars: int
    outcome_available: bool
    symbol: str | None
    signal_bar_index: int | None
    signal_week: str | None
    execution_bar_index: int | None
    execution_week: str | None
    actionable: bool
    qualification: str
    side: str
    confidence: float
    net_strength: float
    net_pressure: float
    scoring_bar_index: int | None
    scoring_evidence_age: int | None
    used_fallback_evidence: bool
    signal_bar_anomaly: bool
    signal_bar_anomaly_reason: str | None
    reason: str | None
    target_bar_evidence_codes: str
    qualifying_evidence_codes: str
    scoring_evidence_codes: str
    campaign_evidence_codes: str
    outcome_signal_bar_index: int | None = None
    outcome_execution_bar_index: int | None = None
    exit_bar_index: int | None = None
    bars_available: int | None = None
    entry_price: float | None = None
    exit_price: float | None = None
    raw_return: float | None = None
    favorable_return: float | None = None
    mfe: float | None = None
    mae: float | None = None
    complete: bool = False


def default_candidate_side(candidate: Any) -> OutcomeSide:
    """Infer validation side from scanner qualification.

    Persistent bullish candidates are scored as long outcomes. Persistent bearish
    candidates are scored as short outcomes. Unqualified candidates are retained
    as neutral observations unless callers provide a custom resolver.
    """
    qualification = _attribute(candidate, "qualification")
    qualification_text = _enum_text(qualification)

    if qualification is PatternQualification.PERSISTENT_BULLISH or qualification_text == "persistent_bullish":
        return OutcomeSide.LONG
    if qualification is PatternQualification.PERSISTENT_BEARISH or qualification_text == "persistent_bearish":
        return OutcomeSide.SHORT
    return OutcomeSide.NEUTRAL


def build_candidate_outcome_rows(
    bars: pd.DataFrame,
    candidates: Sequence[Any] | Iterable[Any],
    *,
    horizons: Iterable[int],
    symbol: str | None = None,
    side_resolver: CandidateSideResolver = default_candidate_side,
    include_unscored: bool = True,
) -> list[CandidateOutcomeRow]:
    """Build candidate outcome rows for many candidates and horizons.

    Parameters
    ----------
    bars
        Metric or OHLCV bars aligned to candidate indexes.
    candidates
        Point-in-time scanner candidates. Objects are read duck-typed so tests
        and future audit pipelines can use snapshots without importing the full
        scanner stack.
    horizons
        Forward holding horizons measured after the execution bar.
    symbol
        Optional symbol applied to all rows. A candidate-level ``symbol``
        attribute, when present, takes precedence.
    side_resolver
        Function used to convert a candidate into long, short, or neutral
        validation side.
    include_unscored
        When true, latest candidates without an execution bar still produce rows
        with ``outcome_available=False``. When false, those rows are omitted.
    """
    normalized_horizons = tuple(horizons)
    if not normalized_horizons:
        raise ValueError("horizons must contain at least one value")
    if any(horizon <= 0 for horizon in normalized_horizons):
        raise ValueError("all horizons must be greater than zero")

    rows: list[CandidateOutcomeRow] = []
    for candidate_id, candidate in enumerate(candidates):
        signal_bar_index = _optional_int(
            _first_present(
                candidate,
                "signal_bar_index",
                "bar_index",
            )
        )
        side = normalize_outcome_side(side_resolver(candidate))
        if signal_bar_index is None:
            if include_unscored:
                for horizon in normalized_horizons:
                    rows.append(_candidate_row(candidate_id, candidate, horizon, symbol=symbol, side=side))
            continue

        for horizon in normalized_horizons:
            outcome = compute_forward_outcome(
                bars,
                signal_bar_index=signal_bar_index,
                horizon_bars=horizon,
                side=side,
            )
            if outcome is None and not include_unscored:
                continue
            rows.append(
                _candidate_row(
                    candidate_id,
                    candidate,
                    horizon,
                    symbol=symbol,
                    side=side,
                    outcome=outcome,
                )
            )
    return rows


def build_candidate_outcome_frame(
    bars: pd.DataFrame,
    candidates: Sequence[Any] | Iterable[Any],
    *,
    horizons: Iterable[int],
    symbol: str | None = None,
    side_resolver: CandidateSideResolver = default_candidate_side,
    include_unscored: bool = True,
) -> pd.DataFrame:
    """Return candidate outcome rows as a pandas DataFrame."""
    rows = build_candidate_outcome_rows(
        bars,
        candidates,
        horizons=horizons,
        symbol=symbol,
        side_resolver=side_resolver,
        include_unscored=include_unscored,
    )
    return pd.DataFrame(asdict(row) for row in rows)


def _candidate_row(
    candidate_id: int,
    candidate: Any,
    horizon_bars: int,
    *,
    symbol: str | None,
    side: OutcomeSide | int | str,
    outcome: ForwardOutcome | None = None,
) -> CandidateOutcomeRow:
    candidate_symbol = _optional_str(_attribute(candidate, "symbol", default=None)) or symbol
    normalized_side = normalize_outcome_side(side)

    outcome_values = _outcome_values(outcome)
    return CandidateOutcomeRow(
        candidate_id=candidate_id,
        horizon_bars=horizon_bars,
        outcome_available=outcome is not None,
        symbol=candidate_symbol,
        signal_bar_index=_optional_int(_first_present(candidate, "signal_bar_index", "bar_index")),
        signal_week=_optional_str(_first_present(candidate, "signal_week", "week")),
        execution_bar_index=_optional_int(_attribute(candidate, "execution_bar_index", default=None)),
        execution_week=_optional_str(_attribute(candidate, "execution_week", default=None)),
        actionable=bool(_attribute(candidate, "actionable", default=False)),
        qualification=_enum_text(_attribute(candidate, "qualification", default="")),
        side=_side_text(normalized_side),
        confidence=_float_or_zero(_attribute(candidate, "confidence", default=0.0)),
        net_strength=_float_or_zero(_attribute(candidate, "net_strength", default=0.0)),
        net_pressure=_float_or_zero(_attribute(candidate, "net_pressure", default=0.0)),
        scoring_bar_index=_optional_int(_attribute(candidate, "scoring_bar_index", default=None)),
        scoring_evidence_age=_optional_int(_attribute(candidate, "scoring_evidence_age", default=None)),
        used_fallback_evidence=bool(_attribute(candidate, "used_fallback_evidence", default=False)),
        signal_bar_anomaly=bool(_attribute(candidate, "signal_bar_anomaly", default=False)),
        signal_bar_anomaly_reason=_optional_str(_attribute(candidate, "signal_bar_anomaly_reason", default=None)),
        reason=_optional_str(_attribute(candidate, "reason", default=None)),
        target_bar_evidence_codes=_join_codes(_attribute(candidate, "target_bar_evidence_codes", default=())),
        qualifying_evidence_codes=_join_codes(_attribute(candidate, "qualifying_evidence_codes", default=())),
        scoring_evidence_codes=_join_codes(_attribute(candidate, "scoring_evidence_codes", default=())),
        campaign_evidence_codes=_join_codes(_attribute(candidate, "campaign_evidence_codes", default=())),
        **outcome_values,
    )


def _outcome_values(outcome: ForwardOutcome | None) -> dict[str, Any]:
    if outcome is None:
        return {
            "outcome_signal_bar_index": None,
            "outcome_execution_bar_index": None,
            "exit_bar_index": None,
            "bars_available": None,
            "entry_price": None,
            "exit_price": None,
            "raw_return": None,
            "favorable_return": None,
            "mfe": None,
            "mae": None,
            "complete": False,
        }
    return {
        "outcome_signal_bar_index": outcome.signal_bar_index,
        "outcome_execution_bar_index": outcome.execution_bar_index,
        "exit_bar_index": outcome.exit_bar_index,
        "bars_available": outcome.bars_available,
        "entry_price": outcome.entry_price,
        "exit_price": outcome.exit_price,
        "raw_return": outcome.raw_return,
        "favorable_return": outcome.favorable_return,
        "mfe": outcome.mfe,
        "mae": outcome.mae,
        "complete": outcome.complete,
    }


def _attribute(candidate: Any, name: str, *, default: Any = None) -> Any:
    if isinstance(candidate, Mapping):
        return candidate.get(name, default)
    return getattr(candidate, name, default)


def _first_present(candidate: Any, *names: str) -> Any:
    for name in names:
        value = _attribute(candidate, name, default=None)
        if value is not None:
            return value
    return None


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


def _float_or_zero(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        if pd.isna(value):
            return 0.0
    except (TypeError, ValueError):
        pass
    return float(value)


def _enum_text(value: Any) -> str:
    if value is None:
        return ""
    enum_value = getattr(value, "value", None)
    if enum_value is not None:
        return str(enum_value)
    return str(value)


def _side_text(side: OutcomeSide | int | str) -> str:
    normalized = normalize_outcome_side(side)
    return normalized.name.lower()


def _join_codes(values: Any) -> str:
    if values is None:
        return ""
    if isinstance(values, str):
        return values
    return "|".join(_enum_text(value) for value in values)


__all__ = [
    "CandidateOutcomeRow",
    "CandidateSideResolver",
    "build_candidate_outcome_frame",
    "build_candidate_outcome_rows",
    "default_candidate_side",
]
