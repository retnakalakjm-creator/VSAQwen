from types import SimpleNamespace

from models import EvidenceCode

import evidence.demand as demand


def _ctx(*, bearish_environment: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        current=SimpleNamespace(bar_index=10),
        previous=SimpleNamespace(),
        trend=SimpleNamespace(direction=SimpleNamespace()),
        is_bearish_environment=lambda: bearish_environment,
    )


def _capture_detector(monkeypatch):
    captured = []

    def fake_evaluate_detector(**kwargs):
        captured.append(kwargs)

    monkeypatch.setattr(demand, "evaluate_detector", fake_evaluate_detector)
    return captured


def test_stopping_volume_detector_requirements_and_confirmations(monkeypatch) -> None:
    ctx = _ctx()
    captured = _capture_detector(monkeypatch)
    monkeypatch.setattr(demand, "has_selling_campaign", lambda ctx: True)
    monkeypatch.setattr(demand, "is_bearish_bar", lambda bar: True)
    monkeypatch.setattr(demand, "is_high_volume", lambda bar: True)
    monkeypatch.setattr(demand, "is_above_average_spread", lambda bar: True)
    monkeypatch.setattr(demand, "is_weak_close", lambda bar: False)
    monkeypatch.setattr(demand, "is_very_high_volume", lambda bar: True)
    monkeypatch.setattr(demand, "has_strong_spread", lambda bar: True)
    monkeypatch.setattr(demand, "volume_increasing", lambda bar, previous: True)
    monkeypatch.setattr(demand, "makes_higher_low", lambda bar, previous: True)

    result = demand._collect_stopping_volume(ctx)

    assert result == []
    assert len(captured) == 1
    assert captured[0]["code"] == EvidenceCode.STOPPING_VOLUME
    assert all(item.passed for item in captured[0]["requirements"])
    assert all(item.passed for item in captured[0]["confirmations"])


def test_stopping_volume_rejects_missing_required_condition(monkeypatch) -> None:
    ctx = _ctx()
    captured = _capture_detector(monkeypatch)
    monkeypatch.setattr(demand, "has_selling_campaign", lambda ctx: True)
    monkeypatch.setattr(demand, "is_bearish_bar", lambda bar: True)
    monkeypatch.setattr(demand, "is_high_volume", lambda bar: True)
    monkeypatch.setattr(demand, "is_above_average_spread", lambda bar: True)
    monkeypatch.setattr(demand, "is_weak_close", lambda bar: True)

    result = demand._collect_stopping_volume(ctx)

    assert result == []
    assert captured == []


def test_stopping_volume_confirmations_are_non_mandatory(monkeypatch) -> None:
    ctx = _ctx()
    captured = _capture_detector(monkeypatch)
    monkeypatch.setattr(demand, "has_selling_campaign", lambda ctx: True)
    monkeypatch.setattr(demand, "is_bearish_bar", lambda bar: True)
    monkeypatch.setattr(demand, "is_high_volume", lambda bar: True)
    monkeypatch.setattr(demand, "is_above_average_spread", lambda bar: True)
    monkeypatch.setattr(demand, "is_weak_close", lambda bar: False)
    monkeypatch.setattr(demand, "is_very_high_volume", lambda bar: False)
    monkeypatch.setattr(demand, "has_strong_spread", lambda bar: False)
    monkeypatch.setattr(demand, "volume_increasing", lambda bar, previous: False)
    monkeypatch.setattr(demand, "makes_higher_low", lambda bar, previous: False)

    result = demand._collect_stopping_volume(ctx)

    assert result == []
    assert len(captured) == 1
    assert captured[0]["code"] == EvidenceCode.STOPPING_VOLUME
    assert all(item.passed for item in captured[0]["requirements"])
    assert not any(item.passed for item in captured[0]["confirmations"])


def test_selling_climax_detector_requirements_and_confirmations(monkeypatch) -> None:
    ctx = _ctx()
    captured = _capture_detector(monkeypatch)
    monkeypatch.setattr(demand, "has_selling_campaign", lambda ctx: True)
    monkeypatch.setattr(demand, "is_bearish_bar", lambda bar: True)
    monkeypatch.setattr(demand, "is_very_high_volume", lambda bar: True)
    monkeypatch.setattr(demand, "is_above_average_spread", lambda bar: True)
    monkeypatch.setattr(demand, "has_strong_spread", lambda bar: True)
    monkeypatch.setattr(demand, "is_strong_close", lambda bar: True)
    monkeypatch.setattr(demand, "volume_increasing", lambda bar, previous: True)
    result = demand._collect_selling_climax(ctx)
    assert result == []
    assert len(captured) == 1
    assert captured[0]["code"] == EvidenceCode.SELLING_CLIMAX
    assert all(item.passed for item in captured[0]["requirements"])
    assert all(item.passed for item in captured[0]["confirmations"])


def test_selling_climax_detector_rejects_missing_required_condition(monkeypatch) -> None:
    ctx = _ctx()
    captured = _capture_detector(monkeypatch)
    monkeypatch.setattr(demand, "has_selling_campaign", lambda ctx: True)
    monkeypatch.setattr(demand, "is_bearish_bar", lambda bar: True)
    monkeypatch.setattr(demand, "is_very_high_volume", lambda bar: False)
    monkeypatch.setattr(demand, "is_above_average_spread", lambda bar: True)
    result = demand._collect_selling_climax(ctx)
    assert result == []
    assert captured == []


def test_test_detector_requirements_and_confirmations(monkeypatch) -> None:
    ctx = _ctx()
    captured = _capture_detector(monkeypatch)
    monkeypatch.setattr(demand, "has_selling_campaign", lambda ctx: True)
    monkeypatch.setattr(demand, "is_confirmed_downtrend", lambda trend: False)
    monkeypatch.setattr(demand, "is_bearish_bar", lambda bar: True)
    monkeypatch.setattr(demand, "is_low_volume", lambda bar: True)
    monkeypatch.setattr(demand, "is_narrow_spread", lambda bar: True)
    monkeypatch.setattr(demand, "volume_decreasing", lambda bar, previous: True)
    monkeypatch.setattr(demand, "is_strong_close", lambda bar: True)
    monkeypatch.setattr(demand, "makes_higher_low", lambda bar, previous: True)
    result = demand._collect_test(ctx)
    assert result == []
    assert len(captured) == 1
    assert captured[0]["code"] == EvidenceCode.TEST
    assert all(item.passed for item in captured[0]["requirements"])
    assert all(item.passed for item in captured[0]["confirmations"])


def test_test_detector_rejects_missing_required_condition(monkeypatch) -> None:
    ctx = _ctx()
    captured = _capture_detector(monkeypatch)
    monkeypatch.setattr(demand, "has_selling_campaign", lambda ctx: False)
    monkeypatch.setattr(demand, "is_bearish_bar", lambda bar: True)
    monkeypatch.setattr(demand, "is_low_volume", lambda bar: True)
    monkeypatch.setattr(demand, "is_narrow_spread", lambda bar: True)
    result = demand._collect_test(ctx)
    assert result == []
    assert captured == []


def test_no_supply_detector_requirements_and_confirmations(monkeypatch) -> None:
    ctx = _ctx(bearish_environment=True)
    captured = _capture_detector(monkeypatch)
    monkeypatch.setattr(demand, "is_bearish_bar", lambda bar: True)
    monkeypatch.setattr(demand, "is_low_volume", lambda bar: True)
    monkeypatch.setattr(demand, "is_narrow_spread", lambda bar: True)
    monkeypatch.setattr(demand, "has_weak_spread", lambda bar: True)
    monkeypatch.setattr(demand, "volume_decreasing", lambda bar, previous: True)
    monkeypatch.setattr(demand, "is_weak_close", lambda bar: True)
    result = demand._collect_no_supply(ctx)
    assert result == []
    assert len(captured) == 1
    assert captured[0]["code"] == EvidenceCode.NO_SUPPLY
    assert all(item.passed for item in captured[0]["requirements"])
    assert all(item.passed for item in captured[0]["confirmations"])


def test_no_supply_detector_rejects_missing_required_condition(monkeypatch) -> None:
    ctx = _ctx(bearish_environment=False)
    captured = _capture_detector(monkeypatch)
    monkeypatch.setattr(demand, "is_bearish_bar", lambda bar: True)
    monkeypatch.setattr(demand, "is_low_volume", lambda bar: True)
    monkeypatch.setattr(demand, "is_narrow_spread", lambda bar: True)
    result = demand._collect_no_supply(ctx)
    assert result == []
    assert captured == []


def test_stopping_volume_is_registered_in_production_demand_collection(monkeypatch) -> None:
    ctx = _ctx()
    captured = []
    monkeypatch.setattr(demand, "_collect_stopping_volume", lambda ctx: captured.append(EvidenceCode.STOPPING_VOLUME) or [])
    monkeypatch.setattr(demand, "_collect_test", lambda ctx: [])
    monkeypatch.setattr(demand, "_collect_shakeout", lambda *, ctx, validation_metrics: [])
    monkeypatch.setattr(demand, "_collect_no_supply", lambda ctx: [])
    result = demand.collect_demand(ctx, SimpleNamespace())
    assert result == []
    assert captured == [EvidenceCode.STOPPING_VOLUME]


def test_no_supply_is_registered_in_production_demand_collection(monkeypatch) -> None:
    ctx = _ctx()
    captured = []
    monkeypatch.setattr(demand, "_collect_stopping_volume", lambda ctx: [])
    monkeypatch.setattr(demand, "_collect_test", lambda ctx: [])
    monkeypatch.setattr(demand, "_collect_shakeout", lambda *, ctx, validation_metrics: [])
    monkeypatch.setattr(demand, "_collect_no_supply", lambda ctx: captured.append(EvidenceCode.NO_SUPPLY) or [])
    result = demand.collect_demand(ctx, SimpleNamespace())
    assert result == []
    assert captured == [EvidenceCode.NO_SUPPLY]
