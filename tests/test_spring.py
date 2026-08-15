import pandas as pd
import pytest

from engine.columns import COL_CLOSE, COL_CLOSE_POSITION, COL_LOW, COL_SPREAD, COL_VOLUME
from evidence.spring import (
    SpringCandidate,
    SpringValidationResult,
    validate_spring_confirmation,
    validate_spring_test,
)


def _metrics(rows: list[dict[str, float | int]]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def _candidate(*, penetration_ratio: float = 0.50, volume: float = 100.0) -> SpringCandidate:
    return SpringCandidate(
        bar_index=0,
        support=100.0,
        penetration_ratio=penetration_ratio,
        spread=1.0,
        volume=volume,
        volume_ratio=1.0,
        close_position=3,
        recovery=True,
        support_touches=2,
    )


def _candidate_bar() -> dict[str, float | int]:
    return {
        COL_LOW: 99.5,
        COL_SPREAD: 1.0,
        COL_VOLUME: 100.0,
        COL_CLOSE_POSITION: 3,
        COL_CLOSE: 100.0,
    }


def _test_bar(*, volume: float = 70.0, low: float = 99.8) -> dict[str, float | int]:
    return {
        COL_LOW: low,
        COL_SPREAD: 1.0,
        COL_VOLUME: volume,
        COL_CLOSE_POSITION: 3,
        COL_CLOSE: 100.0,
    }


def test_spring_test_accepts_low_volume_test():
    metrics = _metrics([
        _candidate_bar(),
        _test_bar(),
    ])

    result = validate_spring_test(metrics, _candidate())

    assert result.result is SpringValidationResult.TESTED
    assert result.test_index == 1
    assert result.volume_ratio == 0.70
    assert result.penetration_ratio == pytest.approx(0.2)


def test_spring_test_rejects_high_volume_test():
    metrics = _metrics([
        _candidate_bar(),
        _test_bar(volume=101.0),
    ])

    result = validate_spring_test(metrics, _candidate())

    assert result.result is SpringValidationResult.NO_TEST
    assert result.test_index is None


def test_spring_test_rejects_deep_penetration():
    metrics = _metrics([
        _candidate_bar(),
        _test_bar(low=98.0),
    ])

    result = validate_spring_test(metrics, _candidate())

    assert result.result is SpringValidationResult.NO_TEST
    assert result.test_index is None


def test_spring_confirmation_requires_future_follow_through():
    metrics = _metrics([
        _candidate_bar(),
        _test_bar(),
    ])
    candidate = _candidate()
    test = validate_spring_test(metrics, candidate)

    assert test.result is SpringValidationResult.TESTED

    result = validate_spring_confirmation(
        metrics,
        candidate=candidate,
        test=test,
    )

    assert result.result is SpringValidationResult.FAILED
    assert result.confirmation_index is None


def test_spring_confirmation_accepts_bullish_follow_through():
    metrics = _metrics([
        _candidate_bar(),
        _test_bar(),
        {
            COL_LOW: 100.0,
            COL_SPREAD: 1.0,
            COL_VOLUME: 80.0,
            COL_CLOSE_POSITION: 3,
            COL_CLOSE: 101.0,
        },
    ])
    candidate = _candidate()
    test = validate_spring_test(metrics, candidate)

    assert test.result is SpringValidationResult.TESTED

    result = validate_spring_confirmation(
        metrics,
        candidate=candidate,
        test=test,
    )

    assert result.result is SpringValidationResult.CONFIRMED
    assert result.confirmation_index == 2
