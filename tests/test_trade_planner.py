from __future__ import annotations

from types import SimpleNamespace

from trade_planner import build_trade_plan


def _bar(close: float) -> SimpleNamespace:
    return SimpleNamespace(close=close)


def _swing(
    type_: str,
    label: str,
    price: float,
    *,
    is_failed: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        type=type_,
        label=label,
        price=price,
        week="2026-08-31 00:00:00",
        is_failed=is_failed,
    )


def _context(
    *,
    bias: str = "bullish",
    tradability: str = "wait_for_pullback",
    decision: str = "wait_for_pullback",
    confidence: float = 0.64,
) -> SimpleNamespace:
    return SimpleNamespace(
        bias=bias,
        tradability=tradability,
        decision=decision,
        confidence=confidence,
        story=SimpleNamespace(
            confirmation_condition="Fresh demand or No Supply after pullback confirms the plan.",
            invalidation_condition="A decisive breakdown below support invalidates the plan.",
        ),
    )


def _analysis(
    *,
    bias: str = "bullish",
    tradability: str = "wait_for_pullback",
    decision: str = "wait_for_pullback",
    close: float = 100.0,
) -> SimpleNamespace:
    return SimpleNamespace(
        bars=[_bar(close)],
        structural_swings=[
            _swing("HIGH", "HH", 112.0),
            _swing("LOW", "HL", 96.0),
        ],
        decision_context=_context(
            bias=bias,
            tradability=tradability,
            decision=decision,
        ),
    )


def test_bullish_pullback_plan_uses_support_and_plain_english() -> None:
    plan = build_trade_plan(_analysis())

    assert plan.posture == "Wait for pullback"
    assert plan.setup_type == "Bullish pullback watch"
    assert plan.support.price == 96.0
    assert plan.resistance.price == 112.0
    assert "No Supply" in plan.entry_condition
    assert plan.analysis_only is True
    assert any("not an order signal" in note for note in plan.notes)


def test_bearish_context_avoids_bullish_swing_plan() -> None:
    plan = build_trade_plan(
        _analysis(
            bias="bearish",
            tradability="wait_for_confirmation",
            decision="wait_for_confirmation",
        )
    )

    assert plan.posture == "Avoid bullish swing setup"
    assert plan.setup_type == "Bearish context / no bullish swing plan"
    assert "No bullish entry condition" in plan.entry_condition
    assert "Bullish reward is not attractive" in plan.reward_reading


def test_failed_structural_swing_is_not_used_as_current_support() -> None:
    analysis = SimpleNamespace(
        bars=[_bar(100.0)],
        structural_swings=[
            _swing("LOW", "HL", 80.0, is_failed=True),
            _swing("LOW", "HL", 95.0),
            _swing("HIGH", "HH", 115.0),
        ],
        decision_context=_context(),
    )

    plan = build_trade_plan(analysis)

    assert plan.support.price == 95.0
    assert "80" not in plan.entry_condition


def test_missing_structure_keeps_plan_available_but_marks_levels_unknown() -> None:
    analysis = SimpleNamespace(
        bars=[_bar(100.0)],
        structural_swings=[],
        decision_context=_context(),
    )

    plan = build_trade_plan(analysis)

    assert plan.support.price is None
    assert plan.resistance.price is None
    assert plan.support.source == "Not available"
    assert "Risk is unknown" in plan.risk_reading
