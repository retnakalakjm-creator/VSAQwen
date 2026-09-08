from __future__ import annotations

import pandas as pd

from evidence.campaign import (
    ShakeoutRecoveryResult,
    ShakeoutRecoveryValidation,
    ShakeoutTestResult,
    ShakeoutTestValidation,
    ShakeoutValidation,
    calculate_shakeout_quality,
    validate_shakeout,
)


def test_validate_shakeout_does_not_print_rejections(capsys) -> None:
    metrics = pd.DataFrame(
        {
            "low": [100.0, 102.0],
            "spread": [10.0, 4.0],
            "volume": [1_000.0, 500.0],
            "close_position": [4, 4],
            "direction": [1, 1],
            "close": [105.0, 106.0],
        }
    )

    validation = validate_shakeout(metrics, 0)

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
    assert validation.test.result == ShakeoutTestResult.NO_TEST


def test_calculate_shakeout_quality_does_not_print(capsys) -> None:
    validation = ShakeoutValidation(
        test=ShakeoutTestValidation(
            result=ShakeoutTestResult.VALID,
            test_index=1,
            distance_ratio=0.0,
            spread_ratio=0.5,
            volume_ratio=0.5,
            close_position=4,
        ),
        recovery=ShakeoutRecoveryValidation(
            result=ShakeoutRecoveryResult.VALID,
            recovery_index=2,
            spread_ratio=0.8,
            volume_ratio=0.8,
            close_position=4,
            close_change_spread_ratio=0.2,
            low_clearance_ratio=0.0,
        ),
    )

    quality = calculate_shakeout_quality(validation=validation)

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
    assert 0.0 <= quality <= 1.0
