from types import SimpleNamespace

import evidence.demand_drying_up as module
from evidence.demand_drying_up import collect_demand_drying_up
from models import Direction, EvidenceCode, SpreadClass, VolumeClass


def _ctx(
    direction=Direction.UP,
    volume=VolumeClass.LOW,
    spread=SpreadClass.NARROW,
):
    return SimpleNamespace(
        current=SimpleNamespace(
            direction=direction,
            volume=volume,
            spread=spread,
            bar_index=10,
            week_beginning="2025-01-06",
        )
    )


def _capture(monkeypatch):
    calls = []

    def fake_evaluate_detector(**kwargs):
        calls.append(kwargs)
        return True

    monkeypatch.setattr(module, "evaluate_detector", fake_evaluate_detector)
    return calls


def test_demand_drying_up_requires_up_bar_low_volume_and_narrow_spread(monkeypatch) -> None:
    calls = _capture(monkeypatch)
    assert collect_demand_drying_up(_ctx()) == []
    assert len(calls) == 1
    assert calls[0]["code"] is EvidenceCode.DEMAND_DRYING_UP


def test_demand_drying_up_rejects_down_bar(monkeypatch) -> None:
    calls = _capture(monkeypatch)
    collect_demand_drying_up(_ctx(direction=Direction.DOWN))
    assert calls == []


def test_demand_drying_up_rejects_high_volume(monkeypatch) -> None:
    calls = _capture(monkeypatch)
    collect_demand_drying_up(_ctx(volume=VolumeClass.HIGH))
    assert calls == []


def test_demand_drying_up_rejects_wide_spread(monkeypatch) -> None:
    calls = _capture(monkeypatch)
    collect_demand_drying_up(_ctx(spread=SpreadClass.WIDE))
    assert calls == []
