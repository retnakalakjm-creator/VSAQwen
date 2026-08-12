from types import SimpleNamespace

from models import EvidenceCode

import evidence.demand as demand


def _ctx(*, bearish_environment: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        current=SimpleNamespace(bar_index=10),
        previous=SimpleNamespace(),
        is_bearish_environment=lambda: bearish_environment,
    )


def _capture_detector(monkeypatch):
    captured = []

    def fake_evaluate_detector(**kwargs):
        captured.append(kwargs)

    monkeypatch.setattr(demand, "evaluate_detector", fake_evaluate_detector)
    return captured


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
