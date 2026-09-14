from types import SimpleNamespace

from evidence.high_volume_reversal import HIGH_VOLUME_REVERSAL_CODE, collect_high_volume_reversal
from models import ClosePosition, Direction, EvidenceCategory, EvidenceDirection, SpreadClass, VolumeClass


def _context(
    *,
    direction=Direction.DOWN,
    volume=VolumeClass.HIGH,
    spread=SpreadClass.ABOVE_AVERAGE,
    close=ClosePosition.UPPER,
    low=90.0,
    previous_low=100.0,
    close_ratio=0.62,
):
    current = SimpleNamespace(
        direction=direction,
        volume=volume,
        spread=spread,
        close_position=close,
        close_ratio=close_ratio,
        low=low,
        bar_index=42,
        week_beginning="2026-01-05",
    )
    previous = SimpleNamespace(
        direction=Direction.DOWN,
        volume=VolumeClass.AVERAGE,
        spread=SpreadClass.AVERAGE,
        close_position=ClosePosition.LOWER,
        close_ratio=0.25,
        low=previous_low,
        bar_index=41,
        week_beginning="2025-12-29",
    )
    return SimpleNamespace(current=current, previous=previous)


def test_high_volume_reversal_emits_on_lower_low_with_recovery():
    evidence = collect_high_volume_reversal(_context())

    assert len(evidence) == 1
    item = evidence[0]
    assert item.code is HIGH_VOLUME_REVERSAL_CODE
    assert item.code.value == "high_volume_reversal"
    assert item.category is EvidenceCategory.DEMAND
    assert item.direction is EvidenceDirection.BULLISH
    assert item.weight == 0.0
    assert item.bar_index == 42


def test_high_volume_reversal_accepts_mid_close_recovery():
    evidence = collect_high_volume_reversal(
        _context(
            close=ClosePosition.MIDDLE,
            close_ratio=0.48,
        )
    )

    assert len(evidence) == 1
    assert evidence[0].code is HIGH_VOLUME_REVERSAL_CODE


def test_high_volume_reversal_requires_each_mandatory_condition():
    cases = (
        {"volume": VolumeClass.AVERAGE},
        {"low": 100.0, "previous_low": 100.0},
        {"close": ClosePosition.LOWER, "close_ratio": 0.20},
    )

    for overrides in cases:
        assert collect_high_volume_reversal(_context(**overrides)) == []


def test_high_volume_reversal_returns_empty_without_previous_context():
    context = _context()
    context = SimpleNamespace(current=context.current)

    assert collect_high_volume_reversal(context) == []


def test_high_volume_reversal_returns_empty_without_direction_context():
    context = _context()
    current = SimpleNamespace(
        volume=context.current.volume,
        spread=context.current.spread,
        close_position=context.current.close_position,
        close_ratio=context.current.close_ratio,
        low=context.current.low,
        bar_index=context.current.bar_index,
        week_beginning=context.current.week_beginning,
    )

    assert collect_high_volume_reversal(SimpleNamespace(current=current, previous=context.previous)) == []
