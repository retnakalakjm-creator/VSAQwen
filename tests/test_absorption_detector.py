from types import SimpleNamespace

from evidence.absorption import collect_absorption
from evidence.profiles import EVIDENCE_REGISTRY
from models import ClosePosition, Direction, EvidenceCategory, EvidenceCode, VolumeClass, SpreadClass


def _context(
    *,
    direction=Direction.DOWN,
    volume=VolumeClass.HIGH,
    spread=SpreadClass.ABOVE_AVERAGE,
    close=ClosePosition.UPPER,
    low=90.0,
    previous_low=100.0,
    close_ratio=0.70,
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
        direction=Direction.UP,
        volume=VolumeClass.AVERAGE,
        spread=SpreadClass.AVERAGE,
        close_position=ClosePosition.MIDDLE,
        close_ratio=0.50,
        low=previous_low,
        bar_index=41,
        week_beginning="2025-12-29",
    )
    return SimpleNamespace(current=current, previous=previous)


def test_absorption_emits_on_all_mandatory_conditions():
    evidence = collect_absorption(_context())

    assert len(evidence) == 1
    item = evidence[0]
    assert item.code is EvidenceCode.ABSORPTION
    assert item.category is EvidenceCategory.ABSORPTION
    assert item.weight == 0.0
    assert item.bar_index == 42


def test_absorption_accepts_mid_close_recovery_after_lower_low():
    evidence = collect_absorption(
        _context(
            spread=SpreadClass.AVERAGE,
            close=ClosePosition.MIDDLE,
            close_ratio=0.48,
        )
    )

    assert len(evidence) == 1
    assert evidence[0].code is EvidenceCode.ABSORPTION


def test_absorption_requires_each_mandatory_condition():
    cases = (
        {"direction": Direction.UP},
        {"volume": VolumeClass.AVERAGE},
        {"close": ClosePosition.LOWER, "close_ratio": 0.30},
        {"low": 100.0, "previous_low": 100.0},
        {"spread": SpreadClass.AVERAGE, "close": ClosePosition.LOWER, "close_ratio": 0.30},
    )

    for overrides in cases:
        assert collect_absorption(_context(**overrides)) == []


def test_absorption_returns_empty_without_previous_context():
    context = _context()
    context = SimpleNamespace(current=context.current)

    assert collect_absorption(context) == []


def test_absorption_returns_empty_without_direction_context():
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

    assert collect_absorption(SimpleNamespace(current=current, previous=context.previous)) == []


def test_absorption_registry_profile_is_scoring_disabled():
    profile = EVIDENCE_REGISTRY[EvidenceCode.ABSORPTION]

    assert profile.category is EvidenceCategory.ABSORPTION
    assert profile.direction.value == 1
    assert profile.strength == 0.90
    assert profile.weight == 0.0
