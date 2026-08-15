from types import SimpleNamespace

import pandas as pd
import pytest

import config
from engine.columns import (
    COL_CLOSE_RATIO,
    COL_SPREAD_PERCENTILE,
    COL_VOLUME_PERCENTILE,
)
from smart_money.rules.stopping_volume import StoppingVolumeRule


def _ctx(
    *,
    history_has_previous: bool = True,
    volume_percentile: float = 90.0,
    spread_percentile: float = 80.0,
    close_ratio: float = 0.70,
) -> SimpleNamespace:
    metrics = pd.DataFrame(
        {
            COL_VOLUME_PERCENTILE: [volume_percentile],
            COL_SPREAD_PERCENTILE: [spread_percentile],
            COL_CLOSE_RATIO: [close_ratio],
        }
    )
    return SimpleNamespace(
        metrics=metrics,
        swing=SimpleNamespace(metrics_index=0),
        history=SimpleNamespace(has_previous=history_has_previous),
    )


def test_stopping_volume_detects_when_all_required_conditions_pass() -> None:
    rule = StoppingVolumeRule()
    ctx = _ctx()

    assert rule._detect(ctx)


def test_stopping_volume_requires_previous_history() -> None:
    rule = StoppingVolumeRule()
    ctx = _ctx(history_has_previous=False)

    assert not rule._detect(ctx)


def test_stopping_volume_requires_exceptional_volume() -> None:
    rule = StoppingVolumeRule()
    ctx = _ctx(
        volume_percentile=config.STOPPING_VOLUME_MIN_VOLUME_PERCENTILE - 0.01,
    )

    assert not rule._detect(ctx)


def test_stopping_volume_requires_wide_spread() -> None:
    rule = StoppingVolumeRule()
    ctx = _ctx(
        spread_percentile=config.STOPPING_VOLUME_MIN_SPREAD_PERCENTILE - 0.01,
    )

    assert not rule._detect(ctx)


def test_stopping_volume_requires_strong_close() -> None:
    rule = StoppingVolumeRule()
    ctx = _ctx(
        close_ratio=config.STOPPING_VOLUME_MIN_CLOSE_RATIO - 0.01,
    )

    assert not rule._detect(ctx)


def test_stopping_volume_confidence_averages_volume_spread_and_close() -> None:
    rule = StoppingVolumeRule()
    ctx = _ctx(
        volume_percentile=90.0,
        spread_percentile=80.0,
        close_ratio=0.70,
    )

    confidence = rule._calculate_confidence(ctx)
    expected = (0.90 + 0.80 + 0.70) / 3.0

    assert confidence == pytest.approx(expected)
