<<<<<<< HEAD
"""Point-in-time Spring detection and validation.

Spring is treated as a structural Wyckoff event, not a candlestick pattern.
The production collector emits evidence only when the validated interaction
is present on the current bar: confirmed Spring + low-volume test + shallow
penetration.
"""
=======
"""Point-in-time Spring detection and validation."""
>>>>>>> 2bb1f9c94c1f4e565ceb4cd1bdcaa1bd4b662288
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import pandas as pd

from engine.columns import COL_CLOSE, COL_CLOSE_POSITION, COL_LOW, COL_SPREAD, COL_VOLUME
from evidence.evidence_registry import EVIDENCE_LIBRARY
from models import BackgroundContext, StructuralSwing, SwingType, Evidence, EvidenceCode

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
_PRODUCTION_CANDIDATE_LOOKBACK = _CONFIRMATION_LOOKAHEAD + 4
_TARGET_TEST_VOLUME_RATIO = 0.75
_TARGET_PENETRATION_RATIO = 0.50
_CALIBRATED_WEIGHT = 0.75


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
    return [item for item in structural_swings if item.swing.type is SwingType.LOW and item.swing.bar_index < bar_index]


def _support_from_prior_lows(structural_swings: tuple[StructuralSwing, ...], bar_index: int, spread: float) -> tuple[float, int] | None:
    lows = _prior_low_swings(structural_swings, bar_index)
    if len(lows) < _MIN_SUPPORT_TOUCHES:
        return None
    recent = lows[-_MIN_SUPPORT_TOUCHES:]
    prices = [float(item.swing.price) for item in recent]
    if max(prices) - min(prices) > spread * _SUPPORT_TOLERANCE_SPREADS:
        return None
    return min(prices), len(recent)


def detect_spring_candidate(metrics: pd.DataFrame, *, bar_index: int, structural_swings: tuple[StructuralSwing, ...]) -> SpringCandidate | None:
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
    if close < support - spread * _RECOVERY_CLOSE_TOLERANCE_SPREADS:
        return None
    volume = float(row[COL_VOLUME])
    previous_volume = float(previous[COL_VOLUME])
    volume_ratio = volume / previous_volume if previous_volume > 0.0 else None
<<<<<<< HEAD
    return SpringCandidate(
        bar_index=bar_index,
        support=support,
        penetration_ratio=penetration_ratio,
        spread=spread,
        volume=volume,
        volume_ratio=volume_ratio,
        close_position=int(row[COL_CLOSE_POSITION]),
        recovery=True,
        support_touches=support_touches,
    )
=======
    return SpringCandidate(bar_index, support, penetration_ratio, spread, volume, volume_ratio, int(row[COL_CLOSE_POSITION]), True, support_touches)
>>>>>>> 2bb1f9c94c1f4e565ceb4cd1bdcaa1bd4b662288


def validate_spring_test(metrics: pd.DataFrame, candidate: SpringCandidate) -> SpringTest:
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
        if distance_ratio > _TEST_MAX_DISTANCE_SPREADS or penetration_ratio > _TEST_MAX_PENETRATION_SPREADS:
            continue
        if volume_ratio > _TEST_MAX_VOLUME_RATIO or close_position < _TEST_MIN_CLOSE_POSITION or spread <= 0.0:
            continue
        return SpringTest(SpringValidationResult.TESTED, index, distance_ratio, penetration_ratio, volume_ratio, close_position)
    return SpringTest(SpringValidationResult.NO_TEST, None, None, None, None, None)


def validate_spring_confirmation(metrics: pd.DataFrame, *, candidate: SpringCandidate, test: SpringTest) -> SpringConfirmation:
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
    test = validate_spring_test(metrics, candidate)
    confirmation = validate_spring_confirmation(metrics, candidate=candidate, test=test)
    return SpringValidation(candidate, test, confirmation)


def collect_spring(ctx: BackgroundContext, metrics: pd.DataFrame) -> list[Evidence]:
    """Emit the validated Spring interaction on the current bar only."""
    current_index = ctx.current.bar_index
    if current_index <= 0:
        return []
<<<<<<< HEAD

    point_in_time = metrics.iloc[: current_index + 1].copy()
    start = max(1, current_index - _PRODUCTION_CANDIDATE_LOOKBACK)

    for candidate_index in range(current_index - 1, start - 1, -1):
        candidate = detect_spring_candidate(
            point_in_time,
            bar_index=candidate_index,
            structural_swings=ctx.structural_swings,
        )
        if candidate is None:
            continue

=======
    point_in_time = metrics.iloc[: current_index + 1].copy()
    start = max(1, current_index - _PRODUCTION_CANDIDATE_LOOKBACK)
    for candidate_index in range(current_index - 1, start - 1, -1):
        candidate = detect_spring_candidate(point_in_time, bar_index=candidate_index, structural_swings=ctx.structural_swings)
        if candidate is None:
            continue
>>>>>>> 2bb1f9c94c1f4e565ceb4cd1bdcaa1bd4b662288
        validation = validate_spring(point_in_time, candidate=candidate)
        if validation.confirmation.result is not SpringValidationResult.CONFIRMED:
            continue
        if validation.confirmation.confirmation_index != current_index:
            continue
        if validation.test.result is not SpringValidationResult.TESTED:
            continue
        if validation.test.volume_ratio is None or validation.test.volume_ratio > _TARGET_TEST_VOLUME_RATIO:
            continue
        if candidate.penetration_ratio > _TARGET_PENETRATION_RATIO:
            continue
<<<<<<< HEAD

        profile = EVIDENCE_LIBRARY[EvidenceCode.SPRING]
        return [
            Evidence(
                code=profile.code,
                category=profile.category,
                direction=profile.direction,
                strength=profile.strength,
                quality=1.0,
                weight=_CALIBRATED_WEIGHT,
                observation=profile.observation,
                description=profile.description,
                bar_index=current_index,
                week_beginning=ctx.current.week_beginning,
                test_index=validation.test.test_index,
                recovery_index=current_index,
            )
        ]

    return []


__all__ = [
    "SpringCandidate", "SpringConfirmation", "SpringTest", "SpringValidation",
    "SpringValidationResult", "detect_spring_candidate", "validate_spring",
    "validate_spring_confirmation", "validate_spring_test", "collect_spring",
]
=======
        profile = EVIDENCE_LIBRARY[EvidenceCode.SPRING]
        return [Evidence(
            code=EvidenceCode.SPRING,
            category=profile.category,
            direction=profile.direction,
            strength=profile.strength,
            quality=1.0,
            weight=_CALIBRATED_WEIGHT,
            observation=profile.observation,
            description=profile.description,
            bar_index=current_index,
            week_beginning=ctx.current.week_beginning,
            test_index=validation.test.test_index,
            recovery_index=current_index,
        )]
    return []


__all__ = ["SpringCandidate", "SpringConfirmation", "SpringTest", "SpringValidation", "SpringValidationResult", "detect_spring_candidate", "validate_spring", "validate_spring_confirmation", "validate_spring_test", "collect_spring"]
>>>>>>> 2bb1f9c94c1f4e565ceb4cd1bdcaa1bd4b662288
