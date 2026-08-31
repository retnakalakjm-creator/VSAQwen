from __future__ import annotations

from types import SimpleNamespace

from evidence.demand_coming_in import collect_demand_coming_in
from models import (
    ClosePosition,
    Direction,
    EvidenceCode,
    EvidenceCategory,
    SpreadClass,
    VolumeClass,
)


def _ctx(
    *,
    direction=Direction.UP,
    volume=VolumeClass.HIGH,
    spread=SpreadClass.ABOVE_AVERAGE,
    close_position=ClosePosition.UPPER,
):
    bar = SimpleNamespace(
        bar_index=10,
        week_beginning="2026-01-05",
        direction=direction,
        volume=volume,
        spread=spread,
        close_position=close_position,
    )
    return SimpleNamespace(current=bar)


def test_demand_coming_in_emits_when_all_requirements_pass() -> None:
    evidence = collect_demand_coming_in(_ctx())

    assert len(evidence) == 1
    item = evidence[0]
    assert item.code is EvidenceCode.DEMAND_COMING_IN
    assert item.category is EvidenceCategory.DEMAND


def test_demand_coming_in_requires_bullish_bar() -> None:
    assert not collect_demand_coming_in(_ctx(direction=Direction.DOWN))


def test_demand_coming_in_requires_high_volume() -> None:
    assert not collect_demand_coming_in(_ctx(volume=VolumeClass.AVERAGE))


def test_demand_coming_in_requires_above_average_spread() -> None:
    assert not collect_demand_coming_in(_ctx(spread=SpreadClass.AVERAGE))


def test_demand_coming_in_requires_strong_close() -> None:
    assert not collect_demand_coming_in(_ctx(close_position=ClosePosition.MIDDLE))
