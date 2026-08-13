"""Point-in-time Spring detection and validation.

Spring is treated as a structural Wyckoff event, not a candlestick pattern.
This module is validation-stage only; EvidenceEngine does not collect it yet.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import pandas as pd

from engine.columns import COL_CLOSE, COL_CLOSE_POSITION, COL_LOW, COL_SPREAD, COL_VOLUME
from models import StructuralSwing, SwingType

_MIN_SUPPORT_TOUCHES = 2
_SUPPORT_TOLERANCE_SPREADS = 1.50
_MIN_PENETRATION_SPREADS = 0.10
_MAX_PENETRATION_SPREADS = 1.50
_RECOVERY_CLOSE_TOLERANCE_SPREADS = 0.10
_TEST_MAX_DISTANCE_SPREADS = 1.00
_TEST_MAX_PENETRATION_SPREADS = 0.50
_TEST_MAX_VOLUME_RATIO = 1.00
_TEST_MIN_CLOSE_POSITION = 2
_CONFIRMATION_LOOKAHEAD = 3


class SpringValidationResult(StrEnum):
    CANDIDATE = "candidate"
    TESTED = "tested"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    NO_TEST = "no_test"


@dataclass(frozen=True, slots=True)
class SpringCandidate:
    bar_index: int
    support: float
    penetration_ratio: float
    spread: float
    volume: float
    volume_ratio: float | None
    close_position: int
    recovery: bool
    support_touches: int


@dataclass(frozen=True, slots=True)
class SpringTest:
    result: SpringValidationResult
    test_index: int | None
    distance_ratio: float | None
    penetration_ratio: float | None
    volume_ratio: float | None
    close_position: int | None


@dataclass(frozen=True, slots=True)
class SpringConfirmation:
    result: SpringValidationResult
    confirmation_index: int | None


@dataclass(frozen=True, slots=True)
class SpringValidation:
    candidate: SpringCandidate
    test: SpringTest
    confirmation: SpringConfirmation


def _prior_low_swings(structural_swings: tuple[StructuralSwing, ...], bar_index: int) -> list[StructuralSwing]:
    return [
        item for item in structural_swings
        if item.swing.type is SwingType.LOW and item.swing.bar_index < bar_index
    ]


def _support_from_prior_lows(
    structural_swings: tuple[StructuralSwing, ...],
    bar_index: int,
    spread: float,
) -> tuple[float, int] | None:
    lows = _prior_low_swings(structural_swings, bar_index)
    if len(lows) < _MIN_SUPPORT_TOUCHES:
        return None
    recent = lows[-_MIN_SUPPORT_TOUCHES:]
    prices = [float(item.swing.price) for item in recent]
    if max(prices) - min(prices) > spread * _SUPPORT_TOLERANCE_SPREADS:
        return None
    return min(prices), len(recent)


def detect_spring_candidate(
    metrics: pd.DataFrame,
    *,
    bar_index: int,
    structural_swings: tuple[StructuralSwing, ...],
) -> SpringCandidate | None:
    """Detect a Spring candidate using only information known at bar_index."""
    if bar_index <= 0 or bar_index >= len(metrics):
        return None
    row = metrics.iloc[bar_index]
    previous = metrics.iloc[bar_index - 1]
    spread = float(row[COL_SPREAD])
    if spread <= 0.0:
        return None
    support_info = _support_from_prior_lows(structural_swings, bar_index, spread)
    if support_info is None:
        return None
    support, support_touches = support_info
    low = float(row[COL_LOW])
    close = float(row[COL_CLOSE])
    penetration_ratio = (support - low) / spread
    if not _MIN_PENETRATION_SPREADS <= penetration_ratio <= _MAX_PENETRATION_SPREADS:
        return None
    recovery = close >= support - spread * _RECOVERY_CLOSE_TOLERANCE_SPREADS
    if not recovery:
        return None
    volume = float(row[COL_VOLUME])
    previous_volume = float(previous[COL_VOLUME])
    volume_ratio = volume / previous_volume if previous_volume > 0.0 else None
    return SpringCandidate(
        bar_index=bar_index,
        support=support,
        penetration_ratio=penetration_ratio,
        spread=spread,
        volume=volume,
        volume_ratio=volume_ratio,
        close_position=int(row[COL_CLOSE_POSITION]),
        recovery=recovery,
        support_touches=support_touches,
    )


def validate_spring_test(metrics: pd.DataFrame, candidate: SpringCandidate) -> SpringTest:
    """Validate the first subsequent low-effort test of the Spring area."""
    start = candidate.bar_index + 1
    end = min(len(metrics), start + _CONFIRMATION_LOOKAHEAD + 2)
    for index in range(start, end):
        row = metrics.iloc[index]
        low = float(row[COL_LOW])
        spread = float(row[COL_SPREAD])
        volume = float(row[COL_VOLUME])
        close_position = int(row[COL_CLOSE_POSITION])
        distance_ratio = abs(low - candidate.support) / candidate.spread
        penetration_ratio = (candidate.support - low) / candidate.spread
        volume_ratio = volume / candidate.volume if candidate.volume > 0.0 else 1.0
        if distance_ratio > _TEST_MAX_DISTANCE_SPREADS:
            continue
        if penetration_ratio > _TEST_MAX_PENETRATION_SPREADS:
            continue
        if volume_ratio > _TEST_MAX_VOLUME_RATIO:
            continue
        if close_position < _TEST_MIN_CLOSE_POSITION or spread <= 0.0:
            continue
        return SpringTest(SpringValidationResult.TESTED, index, distance_ratio, penetration_ratio, volume_ratio, close_position)
    return SpringTest(SpringValidationResult.NO_TEST, None, None, None, None, None)


def validate_spring_confirmation(
    metrics: pd.DataFrame,
    *,
    candidate: SpringCandidate,
    test: SpringTest,
) -> SpringConfirmation:
    """Validate bullish follow-through after an accepted Spring test."""
    if test.test_index is None:
        return SpringConfirmation(SpringValidationResult.NO_TEST, None)
    start = test.test_index + 1
    end = min(len(metrics), start + _CONFIRMATION_LOOKAHEAD)
    test_close = float(metrics.iloc[test.test_index][COL_CLOSE])
    for index in range(start, end):
        row = metrics.iloc[index]
        if float(row[COL_CLOSE]) > max(candidate.support, test_close) and int(row[COL_CLOSE_POSITION]) >= 3:
            return SpringConfirmation(SpringValidationResult.CONFIRMED, index)
    return SpringConfirmation(SpringValidationResult.FAILED, None)


def validate_spring(metrics: pd.DataFrame, *, candidate: SpringCandidate) -> SpringValidation:
    """Run candidate -> test -> confirmation validation."""
    test = validate_spring_test(metrics, candidate)
    confirmation = validate_spring_confirmation(metrics, candidate=candidate, test=test)
    return SpringValidation(candidate, test, confirmation)


__all__ = [
    "SpringCandidate", "SpringConfirmation", "SpringTest", "SpringValidation",
    "SpringValidationResult", "detect_spring_candidate", "validate_spring",
    "validate_spring_confirmation", "validate_spring_test",
]
