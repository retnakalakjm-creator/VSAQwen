"""Offline point-in-time daily Evidence producer for M11 research.

This module reuses the existing ProVSA metrics, swing, structure, trend, and
EvidenceEngine classes on completed daily prefixes. It does not run scanner
qualification, ranking, actionability, alerts, or execution.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from daily_completion import completed_daily_only
from engine.columns import (
    COL_CLOSE,
    COL_HIGH,
    COL_LOW,
    COL_OPEN,
    COL_VOLUME,
    COL_WEEK,
)
from evidence.engine import EvidenceEngine
from market_structure.structure_filter import StructureFilter
from market_structure.swing_engine import SwingEngine
from metrics_engine import MetricsEngine
from models import Evidence
from trading_calendar import NSETradingCalendar, TradingCalendar
from trend import TrendAnalyzer


DEFAULT_DAILY_EVIDENCE_MIN_TARGET_INDEX = 20
DAILY_EVIDENCE_PRODUCER_ID = "existing-vsa-stack-prefix-replay-v1"
DAILY_EVIDENCE_CACHED_PRODUCER_ID = "existing-vsa-stack-causal-cache-replay-v1"
_REQUIRED_DAILY_COLUMNS = (
    COL_OPEN,
    COL_HIGH,
    COL_LOW,
    COL_CLOSE,
    COL_VOLUME,
)


@dataclass(frozen=True, slots=True)
class DailyEvidenceSourceFingerprint:
    symbol: str
    row_count: int
    first_session: str | None
    last_session: str | None
    sha256: str


@dataclass(frozen=True, slots=True)
class DailyEvidenceBarObservation:
    """Target-bar evidence known at one exact completed daily session."""

    bar_index: int
    session: str
    evidence: tuple[Evidence, ...]

    @property
    def is_actionable(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class OfflineDailyEvidenceArchive:
    """Read-only point-in-time daily evidence produced by the existing VSA stack."""

    symbol: str
    producer_id: str
    completed_daily: pd.DataFrame
    source_fingerprint: DailyEvidenceSourceFingerprint
    min_target_index: int
    observations: tuple[DailyEvidenceBarObservation, ...]

    @property
    def evidence(self) -> tuple[Evidence, ...]:
        return tuple(
            item
            for observation in self.observations
            for item in observation.evidence
        )

    @property
    def evidence_count(self) -> int:
        return len(self.evidence)

    @property
    def evaluated_bar_count(self) -> int:
        return len(self.observations)

    @property
    def is_actionable(self) -> bool:
        return False


DailyEvidencePrefixEvaluator = Callable[[pd.DataFrame], tuple[Evidence, ...]]


def _normalize_symbol(symbol: str) -> str:
    normalized = str(symbol).strip().upper()
    if not normalized:
        raise ValueError("symbol cannot be blank")
    return normalized


def _validate_daily_ohlcv(daily: pd.DataFrame) -> None:
    if daily.empty:
        raise ValueError("daily data cannot be empty")
    if not isinstance(daily.index, pd.DatetimeIndex):
        raise TypeError("daily data must use a DatetimeIndex")
    if not daily.index.is_monotonic_increasing:
        raise ValueError("daily sessions must be sorted")
    if daily.index.has_duplicates:
        raise ValueError("daily sessions must be unique")

    missing = [
        column
        for column in _REQUIRED_DAILY_COLUMNS
        if column not in daily.columns
    ]
    if missing:
        raise ValueError(f"daily data missing required columns: {missing}")

    for column in _REQUIRED_DAILY_COLUMNS:
        for value in daily[column]:
            numeric = float(value)
            if not math.isfinite(numeric):
                raise ValueError(f"{column} contains non-finite values")

    if (
        (daily[COL_OPEN] <= 0.0).any()
        or (daily[COL_HIGH] <= 0.0).any()
        or (daily[COL_LOW] <= 0.0).any()
        or (daily[COL_CLOSE] <= 0.0).any()
        or (daily[COL_VOLUME] < 0.0).any()
    ):
        raise ValueError("daily OHLCV contains invalid non-positive price/volume values")


def _session_identity(value: object) -> str:
    return pd.Timestamp(value).isoformat()


def _metrics_input(daily_prefix: pd.DataFrame) -> pd.DataFrame:
    """Map completed daily sessions onto the legacy COL_WEEK identity field.

    Evidence.week_beginning is a legacy field name. In this audit-only daily
    producer it carries the exact completed daily session identity.
    """

    frame = daily_prefix.loc[:, list(_REQUIRED_DAILY_COLUMNS)].copy()
    frame.insert(
        0,
        COL_WEEK,
        [_session_identity(index) for index in frame.index],
    )
    return frame.reset_index(drop=True)


def evaluate_daily_evidence_prefix(
    daily_prefix: pd.DataFrame,
) -> tuple[Evidence, ...]:
    """Evaluate target-bar Evidence using the existing VSA detector stack.

    The function receives only the point-in-time daily prefix. It intentionally
    does not accept the future suffix.
    """

    _validate_daily_ohlcv(daily_prefix)
    metrics = MetricsEngine().calculate(_metrics_input(daily_prefix))

    swings = SwingEngine().calculate(metrics)
    structural_swings = StructureFilter().filter(list(swings), metrics)
    trend = TrendAnalyzer().analyze_from_swings(
        metrics,
        swings,
        structural_swings=structural_swings,
    )
    result = EvidenceEngine().collect(
        metrics=metrics,
        trend=trend,
        structural_swings=tuple(structural_swings),
    )

    target_index = len(metrics) - 1
    return tuple(
        item
        for item in result.evidence
        if item.bar_index == target_index
    )


def _confirmation_index(item: object) -> int:
    swing = getattr(item, "swing", item)
    return int(swing.confirmation_index)


def _validate_confirmation_order(
    items: tuple[object, ...] | list[object],
) -> None:
    previous = -1
    for item in items:
        current = _confirmation_index(item)
        if current < previous:
            raise ValueError(
                "confirmed swing inputs must be confirmation ordered"
            )
        previous = current


def _evaluate_cached_target(
    *,
    metrics: pd.DataFrame,
    swings: tuple,
    structural_swings: tuple,
    swing_count: int,
    structural_count: int,
    target_index: int,
    cached_trend,
    cached_structural_count: int,
):
    """Evaluate one target from causal cached metrics/swing/structure state."""

    metrics_prefix = metrics.iloc[: target_index + 1]
    causal_swings = swings[:swing_count]
    causal_structural = structural_swings[:structural_count]

    trend = cached_trend
    if trend is None or structural_count != cached_structural_count:
        trend = TrendAnalyzer().analyze_from_swings(
            metrics_prefix,
            causal_swings,
            structural_swings=causal_structural,
        )

    result = EvidenceEngine().collect(
        metrics=metrics_prefix,
        validation_metrics=metrics_prefix,
        trend=trend,
        structural_swings=causal_structural,
    )
    evidence = tuple(
        item
        for item in result.evidence
        if item.bar_index == target_index
    )
    return evidence, trend, structural_count


def fingerprint_daily_evidence_source(
    symbol: str,
    completed_daily: pd.DataFrame,
) -> DailyEvidenceSourceFingerprint:
    """Fingerprint the exact completed raw OHLCV source consumed by K5."""

    normalized_symbol = _normalize_symbol(symbol)
    _validate_daily_ohlcv(completed_daily)

    payload = {
        "symbol": normalized_symbol,
        "rows": [
            {
                "session": _session_identity(index),
                COL_OPEN: float(row[COL_OPEN]),
                COL_HIGH: float(row[COL_HIGH]),
                COL_LOW: float(row[COL_LOW]),
                COL_CLOSE: float(row[COL_CLOSE]),
                COL_VOLUME: float(row[COL_VOLUME]),
            }
            for index, row in completed_daily.iterrows()
        ],
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()

    return DailyEvidenceSourceFingerprint(
        symbol=normalized_symbol,
        row_count=len(completed_daily),
        first_session=_session_identity(completed_daily.index[0]),
        last_session=_session_identity(completed_daily.index[-1]),
        sha256=f"sha256:{digest}",
    )


def produce_offline_daily_evidence(
    *,
    symbol: str,
    daily: pd.DataFrame,
    now: datetime | pd.Timestamp | str | None = None,
    calendar: TradingCalendar | None = None,
    min_target_index: int = DEFAULT_DAILY_EVIDENCE_MIN_TARGET_INDEX,
    prefix_evaluator: DailyEvidencePrefixEvaluator | None = None,
) -> OfflineDailyEvidenceArchive:
    """Replay the existing Evidence stack over completed daily prefixes.

    Every target bar is evaluated from its prefix only. Future bars are never
    passed to the evaluator.

    Only evidence whose bar_index equals the current target is retained in the
    archive. Older context may help the existing detector decide, but it is not
    duplicated or re-attributed to later bars.
    """

    clean_symbol = _normalize_symbol(symbol)
    if min_target_index < 0:
        raise ValueError("min_target_index cannot be negative")

    _validate_daily_ohlcv(daily)
    exchange_calendar = calendar or NSETradingCalendar()
    completed = completed_daily_only(
        daily,
        now=now,
        calendar=exchange_calendar,
    )
    if completed.empty:
        raise ValueError("no completed daily bars are available")
    _validate_daily_ohlcv(completed)

    evaluator = prefix_evaluator or evaluate_daily_evidence_prefix
    observations: list[DailyEvidenceBarObservation] = []

    for target_index in range(min_target_index, len(completed)):
        prefix = completed.iloc[: target_index + 1].copy()
        evidence = tuple(evaluator(prefix))

        wrong_bar = [
            item.bar_index
            for item in evidence
            if item.bar_index != target_index
        ]
        if wrong_bar:
            raise ValueError(
                "daily evidence prefix evaluator returned non-target-bar "
                f"evidence at target {target_index}: {wrong_bar}"
            )

        observations.append(
            DailyEvidenceBarObservation(
                bar_index=target_index,
                session=_session_identity(completed.index[target_index]),
                evidence=evidence,
            )
        )

    return OfflineDailyEvidenceArchive(
        symbol=clean_symbol,
        producer_id=DAILY_EVIDENCE_PRODUCER_ID,
        completed_daily=completed.copy(),
        source_fingerprint=fingerprint_daily_evidence_source(
            clean_symbol,
            completed,
        ),
        min_target_index=min_target_index,
        observations=tuple(observations),
    )


def produce_offline_daily_evidence_cached(
    *,
    symbol: str,
    daily: pd.DataFrame,
    now: datetime | pd.Timestamp | str | None = None,
    calendar: TradingCalendar | None = None,
    min_target_index: int = DEFAULT_DAILY_EVIDENCE_MIN_TARGET_INDEX,
) -> OfflineDailyEvidenceArchive:
    """Replay Evidence causally while caching metrics, swings, and structure.

    This path is semantically equivalent to the legacy prefix producer, but it
    avoids recomputing the full metric/swing/structure stack from bar zero for
    every target session.

    Metrics are computed once from the completed history. MetricsEngine uses
    trailing/shifted historical calculations, and parity tests lock that a full
    calculation's prefix equals a standalone prefix calculation.

    SwingEngine and StructureFilter are also computed once. Only swings whose
    confirmation_index is already visible at the target bar are exposed to the
    target evaluation. Trend is recomputed only when the causal structural
    prefix changes.

    EvidenceEngine still receives only the point-in-time metric prefix and the
    causal swing/structure/trend state, preserving detector visibility rules.
    """

    clean_symbol = _normalize_symbol(symbol)
    if min_target_index < 0:
        raise ValueError("min_target_index cannot be negative")

    _validate_daily_ohlcv(daily)
    exchange_calendar = calendar or NSETradingCalendar()
    completed = completed_daily_only(
        daily,
        now=now,
        calendar=exchange_calendar,
    )
    if completed.empty:
        raise ValueError("no completed daily bars are available")
    _validate_daily_ohlcv(completed)

    if min_target_index >= len(completed):
        return OfflineDailyEvidenceArchive(
            symbol=clean_symbol,
            producer_id=DAILY_EVIDENCE_CACHED_PRODUCER_ID,
            completed_daily=completed.copy(),
            source_fingerprint=fingerprint_daily_evidence_source(
                clean_symbol,
                completed,
            ),
            min_target_index=min_target_index,
            observations=(),
        )

    metrics = MetricsEngine().calculate(_metrics_input(completed))
    swings = tuple(SwingEngine().calculate(metrics))
    structural_swings = tuple(
        StructureFilter().filter(list(swings), metrics)
    )

    _validate_confirmation_order(swings)
    _validate_confirmation_order(structural_swings)

    observations: list[DailyEvidenceBarObservation] = []
    cached_trend = None
    cached_structural_count = -1
    swing_count = 0
    structural_count = 0

    for target_index in range(min_target_index, len(completed)):
        while (
            swing_count < len(swings)
            and _confirmation_index(swings[swing_count]) <= target_index
        ):
            swing_count += 1
        while (
            structural_count < len(structural_swings)
            and _confirmation_index(
                structural_swings[structural_count]
            ) <= target_index
        ):
            structural_count += 1

        (
            evidence,
            cached_trend,
            cached_structural_count,
        ) = _evaluate_cached_target(
            metrics=metrics,
            swings=swings,
            structural_swings=structural_swings,
            swing_count=swing_count,
            structural_count=structural_count,
            target_index=target_index,
            cached_trend=cached_trend,
            cached_structural_count=cached_structural_count,
        )

        wrong_bar = [
            item.bar_index
            for item in evidence
            if item.bar_index != target_index
        ]
        if wrong_bar:
            raise ValueError(
                "cached daily evidence evaluator returned non-target-bar "
                f"evidence at target {target_index}: {wrong_bar}"
            )

        observations.append(
            DailyEvidenceBarObservation(
                bar_index=target_index,
                session=_session_identity(completed.index[target_index]),
                evidence=evidence,
            )
        )

    return OfflineDailyEvidenceArchive(
        symbol=clean_symbol,
        producer_id=DAILY_EVIDENCE_CACHED_PRODUCER_ID,
        completed_daily=completed.copy(),
        source_fingerprint=fingerprint_daily_evidence_source(
            clean_symbol,
            completed,
        ),
        min_target_index=min_target_index,
        observations=tuple(observations),
    )


__all__ = [
    "DAILY_EVIDENCE_CACHED_PRODUCER_ID",
    "DAILY_EVIDENCE_PRODUCER_ID",
    "DEFAULT_DAILY_EVIDENCE_MIN_TARGET_INDEX",
    "DailyEvidenceBarObservation",
    "DailyEvidenceSourceFingerprint",
    "OfflineDailyEvidenceArchive",
    "evaluate_daily_evidence_prefix",
    "fingerprint_daily_evidence_source",
    "produce_offline_daily_evidence",
    "produce_offline_daily_evidence_cached",
]
