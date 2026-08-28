from types import SimpleNamespace

from evidence.effort import collect_effort
from models import ClosePosition, EvidenceCode, SpreadClass, VolumeClass


def _ctx(*, volume=VolumeClass.HIGH, spread=SpreadClass.NARROW, close=ClosePosition.MIDDLE):
    current = SimpleNamespace(
        volume=volume,
        spread=spread,
        close_position=close,
        bar_index=0,
        week_beginning=None,
    )
    return SimpleNamespace(current=current)


def test_high_effort_low_result_uses_registry_path():
    evidence = collect_effort(_ctx())
    codes = {item.code for item in evidence}
    assert EvidenceCode.EFFORT_GT_RESULT in codes
    assert EvidenceCode.ABSORPTION not in codes
    assert all(item.weight == 0.0 for item in evidence)


def test_low_effort_high_result():
    evidence = collect_effort(
        _ctx(
            volume=VolumeClass.LOW,
            spread=SpreadClass.WIDE,
            close=ClosePosition.UPPER,
        )
    )
    codes = {item.code for item in evidence}
    assert EvidenceCode.RESULT_GT_EFFORT in codes
    assert all(item.weight == 0.0 for item in evidence)


def test_absorption_is_not_emitted_automatically():
    evidence = collect_effort(_ctx())
    codes = {item.code for item in evidence}
    assert EvidenceCode.ABSORPTION not in codes


def test_unrelated_profile_does_not_emit_effort_result():
    evidence = collect_effort(
        _ctx(
            volume=VolumeClass.AVERAGE,
            spread=SpreadClass.AVERAGE,
            close=ClosePosition.MIDDLE,
        )
    )
    assert evidence == []
