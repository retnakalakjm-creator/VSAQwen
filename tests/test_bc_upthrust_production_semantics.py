from __future__ import annotations

from types import SimpleNamespace

import evidence.supply as supply
from models import ClosePosition, EvidenceCode, SwingType


class _BuyingCampaign:
    def has_buying_campaign(self) -> bool:
        return True


def _structural_high(
    *,
    price: float,
    bar_index: int,
    confirmation_index: int,
):
    return SimpleNamespace(
        swing=SimpleNamespace(
            type=SwingType.HIGH,
            price=price,
            bar_index=bar_index,
            confirmation_index=confirmation_index,
        )
    )


def _structural_low(
    *,
    price: float,
    bar_index: int,
    confirmation_index: int,
):
    return SimpleNamespace(
        swing=SimpleNamespace(
            type=SwingType.LOW,
            price=price,
            bar_index=bar_index,
            confirmation_index=confirmation_index,
        )
    )


def test_buying_climax_requires_non_strong_high_acceptance(
    monkeypatch,
) -> None:
    calls: list[dict[str, object]] = []

    monkeypatch.setattr(supply, "is_bullish_bar", lambda _bar: True)
    monkeypatch.setattr(supply, "is_very_high_volume", lambda _bar: True)
    monkeypatch.setattr(
        supply,
        "is_above_average_spread",
        lambda _bar: True,
    )
    monkeypatch.setattr(supply, "has_strong_spread", lambda _bar: True)
    monkeypatch.setattr(supply, "is_weak_close", lambda _bar: False)
    monkeypatch.setattr(
        supply,
        "volume_increasing",
        lambda _bar, _previous: True,
    )
    monkeypatch.setattr(
        supply,
        "evaluate_detector",
        lambda **kwargs: calls.append(kwargs),
    )

    previous = SimpleNamespace()

    middle_ctx = SimpleNamespace(
        current=SimpleNamespace(close_position=ClosePosition.MIDDLE),
        previous=previous,
    )
    supply._collect_buying_climax(middle_ctx, _BuyingCampaign())

    assert len(calls) == 1
    assert calls[0]["code"] is EvidenceCode.BUYING_CLIMAX
    requirements = calls[0]["requirements"]
    assert tuple(item.name for item in requirements) == (
        "Buying Campaign",
        "Bullish Bar",
        "Very High Volume",
        "Above Average Spread",
        "Non-Strong High Acceptance",
    )
    assert all(item.passed for item in requirements)

    calls.clear()
    upper_ctx = SimpleNamespace(
        current=SimpleNamespace(close_position=ClosePosition.UPPER),
        previous=previous,
    )
    assert supply._collect_buying_climax(
        upper_ctx,
        _BuyingCampaign(),
    ) == []
    assert calls == []

    on_high_ctx = SimpleNamespace(
        current=SimpleNamespace(close_position=ClosePosition.ON_HIGH),
        previous=previous,
    )
    assert supply._collect_buying_climax(
        on_high_ctx,
        _BuyingCampaign(),
    ) == []
    assert calls == []


def test_latest_confirmed_structural_high_is_causal() -> None:
    earlier = _structural_high(
        price=100.0,
        bar_index=5,
        confirmation_index=8,
    )
    latest_visible = _structural_high(
        price=110.0,
        bar_index=9,
        confirmation_index=12,
    )
    future = _structural_high(
        price=120.0,
        bar_index=13,
        confirmation_index=16,
    )
    low = _structural_low(
        price=90.0,
        bar_index=10,
        confirmation_index=11,
    )
    ctx = SimpleNamespace(
        current=SimpleNamespace(bar_index=14),
        structural_swings=(earlier, latest_visible, low, future),
    )

    assert supply._latest_confirmed_structural_high(ctx) is latest_visible


def test_structural_high_confirmed_on_current_bar_is_visible() -> None:
    visible = _structural_high(
        price=110.0,
        bar_index=9,
        confirmation_index=14,
    )
    ctx = SimpleNamespace(
        current=SimpleNamespace(bar_index=14),
        structural_swings=(visible,),
    )

    assert supply._latest_confirmed_structural_high(ctx) is visible


def test_structural_high_pivot_on_current_bar_is_not_reference() -> None:
    invalid = _structural_high(
        price=110.0,
        bar_index=14,
        confirmation_index=14,
    )
    ctx = SimpleNamespace(
        current=SimpleNamespace(bar_index=14),
        structural_swings=(invalid,),
    )

    assert supply._latest_confirmed_structural_high(ctx) is None


def test_upthrust_requires_probe_and_failed_structural_acceptance(
    monkeypatch,
) -> None:
    calls: list[dict[str, object]] = []

    monkeypatch.setattr(supply, "is_weak_close", lambda _bar: True)
    monkeypatch.setattr(supply, "is_very_high_volume", lambda _bar: False)
    monkeypatch.setattr(
        supply,
        "is_above_average_spread",
        lambda _bar: False,
    )
    monkeypatch.setattr(
        supply,
        "evaluate_detector",
        lambda **kwargs: calls.append(kwargs),
    )

    reference = _structural_high(
        price=110.0,
        bar_index=8,
        confirmation_index=11,
    )

    ctx = SimpleNamespace(
        current=SimpleNamespace(
            bar_index=14,
            high=112.0,
            close_price=109.5,
        ),
        structural_swings=(reference,),
    )

    supply._collect_upthrust(ctx)

    assert len(calls) == 1
    assert calls[0]["code"] is EvidenceCode.UPTHRUST
    requirements = calls[0]["requirements"]
    assert tuple(item.name for item in requirements) == (
        "Confirmed Structural High",
        "Probe Above Structural High",
        "Failed Acceptance Above Structural High",
    )
    assert all(item.passed for item in requirements)

    confirmations = calls[0]["confirmations"]
    assert tuple(item.name for item in confirmations) == (
        "Weak Close",
        "Very High Volume",
        "Above Average Spread",
    )
    assert tuple(item.passed for item in confirmations) == (
        True,
        False,
        False,
    )


def test_upthrust_does_not_emit_when_probe_holds_above_reference(
    monkeypatch,
) -> None:
    monkeypatch.setattr(supply, "is_weak_close", lambda _bar: False)
    monkeypatch.setattr(supply, "is_very_high_volume", lambda _bar: True)
    monkeypatch.setattr(
        supply,
        "is_above_average_spread",
        lambda _bar: True,
    )

    reference = _structural_high(
        price=110.0,
        bar_index=8,
        confirmation_index=11,
    )
    ctx = SimpleNamespace(
        current=SimpleNamespace(
            bar_index=14,
            high=112.0,
            close_price=111.0,
        ),
        structural_swings=(reference,),
    )

    assert supply._collect_upthrust(ctx) == []


def test_upthrust_does_not_emit_without_causal_structural_high(
    monkeypatch,
) -> None:
    monkeypatch.setattr(supply, "is_weak_close", lambda _bar: True)
    monkeypatch.setattr(supply, "is_very_high_volume", lambda _bar: True)
    monkeypatch.setattr(
        supply,
        "is_above_average_spread",
        lambda _bar: True,
    )

    future = _structural_high(
        price=110.0,
        bar_index=8,
        confirmation_index=15,
    )
    ctx = SimpleNamespace(
        current=SimpleNamespace(
            bar_index=14,
            high=112.0,
            close_price=109.0,
        ),
        structural_swings=(future,),
    )

    assert supply._collect_upthrust(ctx) == []
