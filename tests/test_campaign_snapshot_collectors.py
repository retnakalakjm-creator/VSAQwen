from types import SimpleNamespace

import evidence.demand as demand
import evidence.supply as supply


class _Snapshot:
    def has_buying_campaign(self) -> bool:
        return True

    def has_selling_campaign(self) -> bool:
        return True


def _ctx() -> SimpleNamespace:
    bar = SimpleNamespace()
    previous = SimpleNamespace()
    return SimpleNamespace(current=bar, previous=previous)


def test_buying_climax_uses_snapshot_not_campaign_function(monkeypatch) -> None:
    ctx = _ctx()

    monkeypatch.setattr(supply, "is_bullish_bar", lambda _bar: True)
    monkeypatch.setattr(supply, "is_very_high_volume", lambda _bar: True)
    monkeypatch.setattr(supply, "is_above_average_spread", lambda _bar: True)
    monkeypatch.setattr(supply, "has_strong_spread", lambda _bar: True)
    monkeypatch.setattr(supply, "is_weak_close", lambda _bar: True)
    monkeypatch.setattr(supply, "volume_increasing", lambda _bar, _previous: True)
    monkeypatch.setattr(supply, "requirements_passed", lambda _requirements: True)
    monkeypatch.setattr(supply, "evaluate_detector", lambda **_kwargs: None)

    result = supply._collect_buying_climax(ctx, _Snapshot())

    assert result == []


def test_stopping_volume_uses_snapshot_campaign_state(monkeypatch) -> None:
    ctx = _ctx()

    monkeypatch.setattr(demand, "is_bearish_bar", lambda _bar: True)
    monkeypatch.setattr(demand, "is_high_volume", lambda _bar: True)
    monkeypatch.setattr(demand, "is_above_average_spread", lambda _bar: True)
    monkeypatch.setattr(demand, "is_weak_close", lambda _bar: False)
    monkeypatch.setattr(demand, "requirements_passed", lambda _requirements: True)
    monkeypatch.setattr(demand, "is_very_high_volume", lambda _bar: True)
    monkeypatch.setattr(demand, "has_strong_spread", lambda _bar: True)
    monkeypatch.setattr(demand, "volume_increasing", lambda _bar, _previous: True)
    monkeypatch.setattr(demand, "makes_higher_low", lambda _bar, _previous: True)
    monkeypatch.setattr(demand, "evaluate_detector", lambda **_kwargs: None)

    result = demand._collect_stopping_volume(ctx, _Snapshot())

    assert result == []


def test_selling_climax_uses_snapshot_campaign_state(monkeypatch) -> None:
    ctx = _ctx()

    monkeypatch.setattr(demand, "is_bearish_bar", lambda _bar: True)
    monkeypatch.setattr(demand, "is_very_high_volume", lambda _bar: True)
    monkeypatch.setattr(demand, "is_above_average_spread", lambda _bar: True)
    monkeypatch.setattr(demand, "requirements_passed", lambda _requirements: True)
    monkeypatch.setattr(demand, "has_strong_spread", lambda _bar: True)
    monkeypatch.setattr(demand, "is_strong_close", lambda _bar: True)
    monkeypatch.setattr(demand, "volume_increasing", lambda _bar, _previous: True)
    monkeypatch.setattr(demand, "evaluate_detector", lambda **_kwargs: None)

    result = demand._collect_selling_climax(ctx, _Snapshot())

    assert result == []


def test_test_uses_snapshot_campaign_state(monkeypatch) -> None:
    ctx = _ctx()

    monkeypatch.setattr(demand, "is_bearish_bar", lambda _bar: True)
    monkeypatch.setattr(demand, "is_low_volume", lambda _bar: True)
    monkeypatch.setattr(demand, "is_narrow_spread", lambda _bar: True)
    monkeypatch.setattr(demand, "is_confirmed_downtrend", lambda _trend: False)
    monkeypatch.setattr(demand, "_recent_structural_weakness", lambda _ctx: False)
    monkeypatch.setattr(demand, "requirements_passed", lambda _requirements: True)
    monkeypatch.setattr(demand, "volume_decreasing", lambda _bar, _previous: True)
    monkeypatch.setattr(demand, "is_strong_close", lambda _bar: True)
    monkeypatch.setattr(demand, "makes_higher_low", lambda _bar, _previous: True)
    monkeypatch.setattr(demand, "evaluate_detector", lambda **_kwargs: None)

    result = demand._collect_test(ctx, _Snapshot())

    assert result == []
